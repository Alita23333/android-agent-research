package dev.alita.androidagent

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import dev.alita.androidagent.zcode.adapter.*
import dev.alita.androidagent.zcode.runtime.ZCodeCarrierWorker
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.io.InputStream
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

/** Real loopback I/O; a stopped generation must not register, execute, or settle late work. */
@RunWith(RobolectricTestRunner::class)
@Config(application = Application::class, sdk = [35])
class ZCodeCarrierWorkerLifecycleTest {
    private val app: Application = ApplicationProvider.getApplicationContext()

    private class Bridge : AutoCloseable {
        val statusEntered = CountDownLatch(1)
        val statusRelease = CountDownLatch(1)
        val nextEntered = CountDownLatch(1)
        val nextRelease = CountDownLatch(1)
        val registrations = CopyOnWriteArrayList<JSONObject>()
        val responses = AtomicInteger()
        private val delivered = AtomicInteger()
        private val executor = Executors.newCachedThreadPool { Thread(it, "carrier-http-test").apply { isDaemon = true } }
        private val sockets = CopyOnWriteArrayList<Socket>()
        @Volatile private var closed = false
        private val server = ServerSocket(0, 50, InetAddress.getByName("127.0.0.1"))
        private val acceptThread = Thread({
            while (!closed) {
                val socket = try { server.accept() } catch (_: Exception) { break }
                sockets += socket
                executor.execute { respond(socket) }
            }
        }, "carrier-http-accept").apply { isDaemon = true; start() }

        private fun line(input: InputStream): String {
            val result = StringBuilder()
            while (true) {
                val byte = input.read()
                check(byte >= 0) { "Unexpected HTTP EOF" }
                if (byte == 10) return result.toString().removeSuffix("\r")
                check(result.length < 8192) { "HTTP header too long" }
                result.append(byte.toChar())
            }
        }

        private fun respond(socket: Socket) {
            try {
                socket.use {
                    it.soTimeout = 15000
                    val input = it.getInputStream().buffered()
                    val path = line(input).split(' ')[1].substringBefore('?')
                    val headers = mutableMapOf<String, String>()
                    while (true) {
                        val header = line(input)
                        if (header.isEmpty()) break
                        val key = header.substringBefore(':').lowercase()
                        headers[key] = header.substringAfter(':').trim()
                    }
                    val length = headers["content-length"]?.toInt() ?: 0
                    check(length in 0..262144)
                    val bodyBytes = ByteArray(length)
                    var offset = 0
                    while (offset < length) {
                        val count = input.read(bodyBytes, offset, length - offset)
                        check(count > 0) { "Unexpected HTTP body EOF" }
                        offset += count
                    }
                    val body = bodyBytes.toString(Charsets.UTF_8)
                    val value = when (path) {
                        "/status" -> { statusEntered.countDown(); statusRelease.await(); JSONObject().put("phase", "ready") }
                        "/carrier/register" -> { registrations += JSONObject(body); JSONObject().put("ok", true) }
                        "/carrier/next" -> {
                            nextEntered.countDown(); nextRelease.await()
                            if (delivered.getAndIncrement() == 0) JSONObject().put("callId", "late-call")
                                .put("toolId", "fixture_compute").put("arguments", JSONObject())
                                .put("meta", JSONObject().put("sessionId", "session"))
                            else null
                        }
                        "/carrier/active" -> JSONObject().put("active", true).put("authorized", true)
                        "/carrier/respond" -> { responses.incrementAndGet(); JSONObject().put("ok", true) }
                        else -> null
                    }
                    val bytes = value?.toString()?.toByteArray() ?: ByteArray(0)
                    val status = if (value == null) "204 No Content" else "200 OK"
                    val header = "HTTP/1.1 $status\r\nContent-Length: ${bytes.size}\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n"
                    it.getOutputStream().use { output ->
                        output.write(header.toByteArray(Charsets.US_ASCII)); output.write(bytes); output.flush()
                    }
                }
            } catch (_: Exception) { /* A stopped worker disconnects blocked requests. */ }
            finally { sockets -= socket }
        }
        val port: Int get() = server.localPort
        override fun close() {
            closed = true
            statusRelease.countDown(); nextRelease.countDown()
            server.close(); sockets.forEach { runCatching { it.close() } }
            executor.shutdownNow(); acceptThread.join(1000)
        }
    }

    private class Dispatcher : AndroidToolDispatcher {
        var version = "v1"
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val executions = AtomicInteger()
        @Volatile var hold = false
        @Volatile var cancellation: AndroidToolCancellation? = null
        override suspend fun definitions() = listOf(AndroidToolDefinition(
            "fixture.compute", version, "Fixture $version", JSONObject().put("type", "object"), readOnly = true,
        ))
        override suspend fun execute(request: AndroidToolRequest, cancellation: AndroidToolCancellation): AndroidToolResult {
            this.cancellation = cancellation
            executions.incrementAndGet(); entered.countDown()
            // Simulate an executor that takes time to honour cancellation. stop must
            // report non-quiescence rather than forgetting this operation's thread.
            while (hold && release.count > 0) try { release.await() } catch (_: InterruptedException) { }
            return AndroidToolResult.success(request)
        }
    }

    private fun worker(bridge: Bridge, dispatcher: Dispatcher): ZCodeCarrierWorker {
        File(app.filesDir, "runtime/carrier/endpoint.json").apply {
            parentFile!!.mkdirs()
            writeText(JSONObject().put("port", bridge.port).put("token", "fixture-only").toString())
        }
        return ZCodeCarrierWorker(app, dispatcher)
    }

    private fun await(condition: () -> Boolean) {
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
        while (!condition() && System.nanoTime() < deadline) Thread.sleep(10)
        assertTrue("condition did not become true", condition())
    }

    @Test fun lateReadinessNeverRegistersStoppedGeneration() {
        Bridge().use { bridge ->
            val worker = worker(bridge, Dispatcher())
            try {
                worker.start(); assertTrue(bridge.statusEntered.await(5, TimeUnit.SECONDS))
                val start = System.nanoTime()
                worker.stop()
                assertTrue("stop exceeded its bounded wait", TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - start) < 5000)
                bridge.statusRelease.countDown()
                await { worker.isQuiescent() }
                assertTrue(bridge.registrations.isEmpty())
            } finally { bridge.statusRelease.countDown(); worker.stop() }
        }
    }

    @Test fun lateLongPollCannotExecuteAndRestartSnapshotsNewDefinitions() {
        Bridge().use { bridge ->
            val dispatcher = Dispatcher()
            val worker = worker(bridge, dispatcher)
            try {
                bridge.statusRelease.countDown(); worker.start()
                assertTrue(bridge.nextEntered.await(5, TimeUnit.SECONDS))
                worker.stop(); bridge.nextRelease.countDown()
                await { worker.isQuiescent() }
                assertEquals(0, dispatcher.executions.get())
                assertEquals(1, bridge.registrations.size)
                dispatcher.version = "v2"; worker.start()
                await { bridge.registrations.size == 2 }
                val definitions = bridge.registrations.last().getJSONArray("tools")
                val fixture = (0 until definitions.length()).map { definitions.getJSONObject(it) }
                    .single { it.getString("toolId") == "fixture_compute" }
                assertEquals("v2", fixture.getJSONObject("metadata").getString("version"))
                assertEquals(0, dispatcher.executions.get())
            } finally { bridge.nextRelease.countDown(); worker.stop() }
        }
    }

    @Test fun uncooperativeExecutionBlocksRestartAndCannotSettleAfterStop() {
        Bridge().use { bridge ->
            val dispatcher = Dispatcher().apply { hold = true }
            val worker = worker(bridge, dispatcher)
            try {
                bridge.statusRelease.countDown(); bridge.nextRelease.countDown(); worker.start()
                assertTrue(dispatcher.entered.await(5, TimeUnit.SECONDS))
                assertFalse(worker.stop()); assertFalse(worker.isQuiescent())
                assertTrue(dispatcher.cancellation!!.isCancelled)
                try { worker.start(); fail("restart must refuse a live previous execution") } catch (_: IllegalStateException) { }
                assertEquals(1, bridge.registrations.size)
                dispatcher.release.countDown(); await { worker.isQuiescent() }
                assertEquals(0, bridge.responses.get())
                assertTrue(worker.stop())
            } finally { dispatcher.release.countDown(); worker.stop() }
        }
    }

    @Test fun synchronousInterruptBlockerCannotHoldStopCallerOrLifecycleLock() {
        val interruptEntered = CountDownLatch(1)
        val releaseInterrupt = CountDownLatch(1)
        val targetEntered = CountDownLatch(1)
        val releaseTarget = CountDownLatch(1)
        val target = object : Thread("blocked-interrupt-fixture") {
            override fun run() { targetEntered.countDown(); releaseTarget.await() }
            override fun interrupt() {
                interruptEntered.countDown()
                // Android can synchronously enter an I/O blocker here. A finite
                // guard lets the old regression fail instead of hanging the suite.
                releaseInterrupt.await(8, TimeUnit.SECONDS)
                super.interrupt()
            }
        }.apply { isDaemon = true; start() }
        val worker = ZCodeCarrierWorker(app, Dispatcher())
        ZCodeCarrierWorker::class.java.getDeclaredField("workerThread").apply {
            isAccessible = true
            set(worker, target)
        }
        try {
            assertTrue(targetEntered.await(5, TimeUnit.SECONDS))
            val started = System.nanoTime()
            assertFalse(worker.stop())
            assertTrue("interrupt cleanup must actually run", interruptEntered.await(1, TimeUnit.SECONDS))
            assertTrue("stop blocked inside Thread.interrupt", TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started) < 5000)
            assertFalse(worker.isQuiescent())
            try { worker.start(); fail("cleanup still owns the previous generation") } catch (_: IllegalStateException) { }
            releaseTarget.countDown(); releaseInterrupt.countDown()
            await { worker.isQuiescent() }
        } finally {
            releaseTarget.countDown(); releaseInterrupt.countDown(); worker.stop()
        }
    }
}
