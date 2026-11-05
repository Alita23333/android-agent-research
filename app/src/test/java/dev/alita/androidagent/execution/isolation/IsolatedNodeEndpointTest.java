package dev.alita.androidagent.execution.isolation;

import android.app.Application;
import android.content.*;
import android.os.*;
import dev.alita.androidagent.execution.IsolatedProviderProcess;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import org.robolectric.Shadows;
import java.io.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(application = Application.class, sdk = 35)
public class IsolatedNodeEndpointTest {
    private static final ComponentName NAME = new ComponentName("fixture", "IsolatedNodeService");
    private static class Binding implements IsolatedNodeEndpoint.Binding {
        ServiceConnection connection;
        boolean accept = true, rejectException, unbindException;
        int unbound;
        public boolean bind(ServiceConnection value) { connection = value; if (rejectException) throw new SecurityException("fixture denied"); return accept; }
        public void unbind(ServiceConnection value) { unbound++; if (unbindException) throw new IllegalStateException("fixture unbind failed"); }
    }
    private static class Events implements IsolatedProviderProcess.Events {
        int failures, exits, ready, status;
        public void ready() { ready++; }
        public void exited(int status) { exits++; this.status = status; }
        public void failed(IOException failure) { failures++; }
    }
    private static IsolatedNodeEndpoint endpoint(Binding binding, AtomicInteger releases) throws IOException {
        Bundle payload = new Bundle(); payload.putByteArray("scriptUtf8", new byte[]{42});
        return new IsolatedNodeEndpoint(payload, new ArrayList<>(), data -> {}, releases::incrementAndGet, binding, ParcelFileDescriptor::createPipe);
    }
    private static void streams(IsolatedNodeEndpoint endpoint) throws IOException {
        endpoint.stdin().close(); endpoint.stdout().close(); endpoint.stderr().close();
    }
    @Test public void partialPipeAllocationClosesEveryEarlierDescriptor() throws Exception {
        ArrayList<ParcelFileDescriptor> opened = new ArrayList<>(); AtomicInteger allocations = new AtomicInteger();
        try {
            new IsolatedNodeEndpoint(new Bundle(), new ArrayList<>(), data -> {}, () -> {}, new Binding(), () -> {
                if (allocations.incrementAndGet() == 3) throw new IOException("third pipe failed");
                ParcelFileDescriptor[] pair = ParcelFileDescriptor.createPipe(); Collections.addAll(opened, pair); return pair;
            }); fail("partial allocation accepted");
        } catch (IOException expected) { assertEquals("third pipe failed", expected.getMessage()); }
        assertEquals(4, opened.size());
        for (ParcelFileDescriptor fd : opened) {
            try { fd.getFd(); fail("allocated FD left open"); } catch (IllegalStateException expected) { }
        }
    }
    @Test public void bindFalseReleasesExactlyOnceWithoutDispatch() throws Exception {
        Binding binding = new Binding(); binding.accept = false; AtomicInteger releases = new AtomicInteger(); Events events = new Events();
        IsolatedNodeEndpoint endpoint = endpoint(binding, releases);
        try { endpoint.start(events); fail(); } catch (IOException expected) { }
        endpoint.close(); endpoint.terminate();
        assertEquals(1, releases.get()); assertEquals(1, events.exits); assertEquals(70, events.status); assertEquals(0, binding.unbound);
        streams(endpoint);
    }
    @Test public void bindExceptionCannotLeakLease() throws Exception {
        Binding binding = new Binding(); binding.rejectException = true; AtomicInteger releases = new AtomicInteger(); Events events = new Events();
        IsolatedNodeEndpoint endpoint = endpoint(binding, releases);
        try { endpoint.start(events); fail(); } catch (IOException expected) { assertTrue(expected.getCause() instanceof SecurityException); }
        assertEquals(1, releases.get()); assertEquals(1, events.exits); streams(endpoint);
    }
    @Test public void nullBindingClosesAndLateConnectionCannotDispatch() throws Exception {
        Binding binding = new Binding(); AtomicInteger releases = new AtomicInteger(); Events events = new Events();
        IsolatedNodeEndpoint endpoint = endpoint(binding, releases); endpoint.start(events);
        binding.connection.onNullBinding(NAME);
        AtomicInteger messages = new AtomicInteger();
        Messenger peer = new Messenger(new Handler(Looper.getMainLooper(), message -> { messages.incrementAndGet(); return true; }));
        binding.connection.onServiceConnected(NAME, peer.getBinder()); Shadows.shadowOf(Looper.getMainLooper()).idle();
        assertEquals(0, messages.get()); assertEquals(1, events.failures); assertEquals(1, events.exits);
        assertEquals(1, binding.unbound); assertEquals(1, releases.get()); streams(endpoint);
    }
    @Test public void cancelBeforeConnectClosesGateAndSuppressesLateCallbacks() throws Exception {
        Binding binding = new Binding(); AtomicInteger releases = new AtomicInteger(); Events events = new Events();
        IsolatedNodeEndpoint endpoint = endpoint(binding, releases); endpoint.start(events); endpoint.terminate(); endpoint.terminate();
        AtomicInteger messages = new AtomicInteger();
        Messenger peer = new Messenger(new Handler(Looper.getMainLooper(), message -> { messages.incrementAndGet(); return true; }));
        binding.connection.onServiceConnected(NAME, peer.getBinder()); binding.connection.onServiceDisconnected(NAME);
        Shadows.shadowOf(Looper.getMainLooper()).idle();
        assertEquals(0, messages.get()); assertEquals(1, binding.unbound); assertEquals(1, releases.get()); assertEquals(1, events.exits);
        assertEquals(137, events.status); streams(endpoint);
    }
    @Test public void unbindFailureStillClosesDescriptorsAndReleasesOnce() throws Exception {
        Binding binding = new Binding(); binding.unbindException = true; AtomicInteger releases = new AtomicInteger(); Events events = new Events();
        IsolatedNodeEndpoint endpoint = endpoint(binding, releases); endpoint.start(events); endpoint.terminate(); endpoint.close();
        assertEquals(1, releases.get()); assertEquals(1, events.exits); assertEquals(1, binding.unbound); streams(endpoint);
    }
    @Test public void dispatchedCancellationWaitsForDeathRatherThanStopSend() throws Exception {
        Binding binding = new Binding(); AtomicInteger releases = new AtomicInteger(); Events events = new Events(); AtomicInteger starts = new AtomicInteger(), stops = new AtomicInteger();
        Messenger peer = new Messenger(new Handler(Looper.getMainLooper(), message -> {
            if (message.what == IsolatedNodeService.START) starts.incrementAndGet();
            if (message.what == IsolatedNodeService.STOP) stops.incrementAndGet(); return true;
        }));
        IsolatedNodeEndpoint endpoint = endpoint(binding, releases); endpoint.start(events);
        binding.connection.onServiceConnected(NAME, peer.getBinder()); endpoint.terminate(); endpoint.terminate();
        Shadows.shadowOf(Looper.getMainLooper()).idle();
        assertEquals(1, starts.get()); assertEquals(1, stops.get()); assertEquals(0, events.exits); assertEquals(0, releases.get());
        binding.connection.onServiceDisconnected(NAME); assertEquals(1, events.exits); assertEquals(1, releases.get()); streams(endpoint);
    }
    @Test public void unusedEndpointCanBeClosedBeforeStart() throws Exception {
        Binding binding = new Binding(); AtomicInteger releases = new AtomicInteger(); IsolatedNodeEndpoint endpoint = endpoint(binding, releases);
        endpoint.close(); endpoint.close(); assertEquals(1, releases.get()); assertNull(binding.connection);
        try { endpoint.start(new Events()); fail(); } catch (IOException expected) { }
        streams(endpoint);
    }
    @Test public void connectionDeadlineClosesBeforeDispatchAndReleasesLease() throws Exception {
        Binding binding = new Binding(); AtomicInteger releases = new AtomicInteger(); Events events = new Events();
        IsolatedNodeEndpoint endpoint = endpoint(binding, releases); endpoint.start(events);
        Shadows.shadowOf(Looper.getMainLooper()).idleFor(java.time.Duration.ofSeconds(11));
        assertEquals(1, events.failures); assertEquals(1, events.exits); assertEquals(1, releases.get()); assertEquals(1, binding.unbound);
        binding.connection.onBindingDied(NAME); assertEquals(1, events.exits); streams(endpoint);
    }
    @Test public void bindingDeathBeforeDispatchReleasesWithoutAllowingReconnect() throws Exception {
        Binding binding = new Binding(); AtomicInteger releases = new AtomicInteger(); Events events = new Events();
        IsolatedNodeEndpoint endpoint = endpoint(binding, releases); endpoint.start(events);
        binding.connection.onBindingDied(NAME); binding.connection.onNullBinding(NAME);
        assertEquals(1, events.failures); assertEquals(1, events.exits); assertEquals(1, releases.get()); streams(endpoint);
    }
}
