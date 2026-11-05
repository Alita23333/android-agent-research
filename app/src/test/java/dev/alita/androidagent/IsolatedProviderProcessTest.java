package dev.alita.androidagent;

import dev.alita.androidagent.execution.IsolatedProviderProcess;
import org.junit.Test;
import java.io.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.Assert.*;

public class IsolatedProviderProcessTest {
    private static class Endpoint implements IsolatedProviderProcess.Endpoint {
        volatile IsolatedProviderProcess.Events events;
        boolean ready = true, failStart, exitDuringStart, failCallback;
        AtomicInteger stops = new AtomicInteger(), closes = new AtomicInteger();
        final ByteArrayInputStream output = new ByteArrayInputStream(new byte[]{42});
        final ByteArrayInputStream error = new ByteArrayInputStream(new byte[]{43});
        final ByteArrayOutputStream input = new ByteArrayOutputStream();
        public InputStream stdout() { return output; }
        public InputStream stderr() { return error; }
        public OutputStream stdin() { return input; }
        public void start(IsolatedProviderProcess.Events events) throws IOException {
            this.events = events;
            if (failStart) throw new IOException("bind rejected");
            if (failCallback) events.failed(new IOException("native loader rejected"));
            if (exitDuringStart) events.exited(70);
            if (ready) events.ready();
        }
        public void terminate() { stops.incrementAndGet(); }
        public void close() { closes.incrementAndGet(); }
    }
    @Test public void streamsAreExactAndOutputCanDrainAfterExit() throws Exception {
        Endpoint endpoint = new Endpoint();
        Process process = IsolatedProviderProcess.launch(endpoint, 100);
        assertSame(endpoint.output, process.getInputStream());
        assertSame(endpoint.error, process.getErrorStream());
        assertSame(endpoint.input, process.getOutputStream());
        process.getOutputStream().write(44);
        endpoint.events.exited(0);
        assertEquals(0, process.waitFor()); assertFalse(process.isAlive());
        assertEquals(42, process.getInputStream().read()); assertEquals(43, process.getErrorStream().read());
        assertArrayEquals(new byte[]{44}, endpoint.input.toByteArray());
        assertEquals(1, endpoint.closes.get());
    }
    @Test public void cancelIsNotADeathAcknowledgementAndIsIdempotent() throws Exception {
        Endpoint endpoint = new Endpoint();
        Process process = IsolatedProviderProcess.launch(endpoint, 100);
        process.destroy(); process.destroyForcibly(); process.destroy();
        assertEquals(1, endpoint.stops.get()); assertTrue(process.isAlive());
        assertFalse(process.waitFor(5, TimeUnit.MILLISECONDS));
        try { process.exitValue(); fail(); } catch (IllegalThreadStateException expected) { }
        assertEquals(0, endpoint.closes.get());
        endpoint.events.exited(137); endpoint.events.exited(0); endpoint.events.ready();
        assertEquals(137, process.exitValue()); assertEquals(1, endpoint.closes.get());
        process.destroy(); assertEquals(1, endpoint.stops.get());
    }
    @Test public void startupTimeoutRequestsStopAndLateReadyCannotRevive() throws Exception {
        Endpoint endpoint = new Endpoint(); endpoint.ready = false;
        try { IsolatedProviderProcess.launch(endpoint, 5); fail(); }
        catch (IOException expected) { assertTrue(expected.getMessage().contains("deadline")); }
        assertEquals(1, endpoint.stops.get()); assertEquals(0, endpoint.closes.get());
        endpoint.events.ready(); endpoint.events.exited(137);
        assertEquals(1, endpoint.closes.get());
    }
    @Test public void synchronousStartFailureRequestsStop() throws Exception {
        Endpoint endpoint = new Endpoint(); endpoint.failStart = true;
        try { IsolatedProviderProcess.launch(endpoint, 100); fail(); }
        catch (IOException expected) { assertEquals("bind rejected", expected.getMessage()); }
        assertEquals(1, endpoint.stops.get());
        endpoint.events.exited(70); assertEquals(1, endpoint.closes.get());
    }
    @Test public void nativeFailureNeverReturnsUsableProcess() throws Exception {
        Endpoint endpoint = new Endpoint(); endpoint.failCallback = true;
        try { IsolatedProviderProcess.launch(endpoint, 100); fail(); }
        catch (IOException expected) { assertEquals("native loader rejected", expected.getMessage()); }
        assertEquals(1, endpoint.stops.get()); endpoint.events.exited(70);
    }
    @Test public void earlyDeathCannotBeRevivedByReady() throws Exception {
        Endpoint endpoint = new Endpoint(); endpoint.exitDuringStart = true;
        try { IsolatedProviderProcess.launch(endpoint, 100); fail(); }
        catch (IOException expected) { assertTrue(expected.getMessage().contains("startup")); }
        assertEquals(1, endpoint.closes.get()); assertEquals(0, endpoint.stops.get());
    }
    @Test public void interruptedStartupStopsTransport() throws Exception {
        Endpoint endpoint = new Endpoint(); endpoint.ready = false;
        Thread.currentThread().interrupt();
        try { IsolatedProviderProcess.launch(endpoint, 100); fail(); }
        catch (InterruptedException expected) { assertEquals(1, endpoint.stops.get()); }
        finally { Thread.interrupted(); endpoint.events.exited(137); }
    }
    @Test public void waitersCompleteOnlyOnActualDeath() throws Exception {
        Endpoint endpoint = new Endpoint();
        Process process = IsolatedProviderProcess.launch(endpoint, 100);
        ExecutorService pool = Executors.newSingleThreadExecutor();
        try {
            Future<Integer> waiting = pool.submit((Callable<Integer>) process::waitFor);
            process.destroy(); assertFalse(waiting.isDone());
            endpoint.events.exited(137); assertEquals(Integer.valueOf(137), waiting.get(1, TimeUnit.SECONDS));
        } finally { pool.shutdownNow(); }
    }
    @Test public void invalidDeadlineDoesNotStartTransport() throws Exception {
        Endpoint endpoint = new Endpoint();
        for (long timeout : new long[]{0, -1, 60001}) {
            try { IsolatedProviderProcess.launch(endpoint, timeout); fail(); }
            catch (IllegalArgumentException expected) { assertNull(endpoint.events); }
        }
    }
    @Test public void releaseFailureCannotHideConfirmedDeath() throws Exception {
        Endpoint endpoint = new Endpoint() {
            @Override public void close() { super.close(); throw new IllegalStateException("unbind failed"); }
        };
        Process process = IsolatedProviderProcess.launch(endpoint, 100);
        endpoint.events.exited(71);
        assertTrue(process.waitFor(10, TimeUnit.MILLISECONDS)); assertEquals(71, process.exitValue());
        endpoint.events.exited(0); assertEquals(1, endpoint.closes.get());
    }
    @Test public void preCancelledLaunchDoesNotBindAndReleasesResources() throws Exception {
        Endpoint endpoint = new Endpoint();
        try { IsolatedProviderProcess.launch(endpoint, 10000, () -> true); fail(); }
        catch (InterruptedIOException expected) { assertTrue(expected.getMessage().contains("cancelled")); }
        assertNull(endpoint.events); assertEquals(0, endpoint.stops.get()); assertEquals(1, endpoint.closes.get());
    }
    @Test public void cancellationDuringStartupStopsBeforeDeadlineAndRejectsLateReady() throws Exception {
        Endpoint endpoint = new Endpoint(); endpoint.ready = false;
        java.util.concurrent.atomic.AtomicBoolean cancel = new java.util.concurrent.atomic.AtomicBoolean();
        CountDownLatch entered = new CountDownLatch(1);
        ExecutorService pool = Executors.newSingleThreadExecutor();
        try {
            Future<?> pending = pool.submit(() -> {
                try {
                    IsolatedProviderProcess.launch(endpoint, 10000, () -> { entered.countDown(); return cancel.get(); });
                    throw new AssertionError("cancelled launch returned a process");
                } catch (InterruptedIOException expected) { }
                catch (Exception error) { throw new RuntimeException(error); }
            });
            assertTrue(entered.await(1, TimeUnit.SECONDS));
            // Wait for endpoint.start, rather than racing cancellation against the pre-check.
            long limit = System.nanoTime() + TimeUnit.SECONDS.toNanos(1);
            while (endpoint.events == null && System.nanoTime() < limit) Thread.yield();
            assertNotNull(endpoint.events); cancel.set(true);
            pending.get(1, TimeUnit.SECONDS);
            assertEquals(1, endpoint.stops.get()); assertEquals(0, endpoint.closes.get());
            endpoint.events.ready(); endpoint.events.exited(137); assertEquals(1, endpoint.closes.get());
        } finally { pool.shutdownNow(); }
    }
    @Test public void readyAndCancellationInSameCallbackCannotReturnProcess() throws Exception {
        java.util.concurrent.atomic.AtomicBoolean cancel = new java.util.concurrent.atomic.AtomicBoolean();
        Endpoint endpoint = new Endpoint() {
            @Override public void start(IsolatedProviderProcess.Events events) throws IOException {
                super.start(events); cancel.set(true);
            }
        };
        try { IsolatedProviderProcess.launch(endpoint, 10000, cancel::get); fail(); }
        catch (InterruptedIOException expected) { assertEquals(1, endpoint.stops.get()); }
        endpoint.events.exited(137);
    }
}
