package dev.alita.androidagent.execution

import dev.alita.androidagent.core.CancellationSignal
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit

data class ExecutionRequest(
    val command: String,
    val workingDirectory: File,
    val environment: Map<String, String> = emptyMap(),
    val timeoutMillis: Long = 60_000,
    val maxOutputBytes: Int = 1_048_576,
)

data class ExecutionResult(
    val executionId: String,
    val exitCode: Int?,
    val output: String,
    val timedOut: Boolean = false,
    val truncated: Boolean = false,
    val running: Boolean = false,
)

interface ExecutionBackend {
    val id: String
    suspend fun execute(request: ExecutionRequest, cancellation: CancellationSignal): ExecutionResult
    fun start(request: ExecutionRequest): String
    fun status(executionId: String): ExecutionResult?
    fun cancel(executionId: String): Boolean
}

class ProcessExecutionBackend(
    override val id: String,
    private val commandFactory: (String) -> List<String>,
) : ExecutionBackend {
    private val sessions = ConcurrentHashMap<String, Session>()

    override suspend fun execute(request: ExecutionRequest, cancellation: CancellationSignal): ExecutionResult = withContext(Dispatchers.IO) {
        val executionId = start(request)
        val session = sessions.getValue(executionId)
        cancellation.onCancel { cancel(executionId) }
        val finished = session.process.waitFor(request.timeoutMillis, TimeUnit.MILLISECONDS)
        if (!finished) session.process.destroyProcessTree()
        session.reader.join(3_000)
        val snapshot = session.snapshot(timedOut = !finished)
        if (finished) sessions.remove(executionId)
        snapshot
    }

    override fun start(request: ExecutionRequest): String {
        require(request.workingDirectory.isDirectory) { "Working directory does not exist" }
        val process = ProcessBuilder(commandFactory(request.command))
            .directory(request.workingDirectory)
            .redirectErrorStream(true)
            .apply { environment().putAll(request.environment) }
            .start()
        val id = UUID.randomUUID().toString()
        val session = Session(id, process, request.maxOutputBytes)
        sessions[id] = session
        session.reader.start()
        return id
    }

    override fun status(executionId: String): ExecutionResult? {
        val session = sessions[executionId] ?: return null
        val result = session.snapshot()
        if (!result.running) sessions.remove(executionId)
        return result
    }

    override fun cancel(executionId: String): Boolean {
        val session = sessions.remove(executionId) ?: return false
        session.process.destroyProcessTree()
        return true
    }

    private class Session(val id: String, val process: Process, private val limit: Int) {
        private val output = ByteArrayOutputStream()
        @Volatile private var truncated = false
        val reader = Thread({
            process.inputStream.use { input ->
                val buffer = ByteArray(8192)
                while (true) {
                    val read = input.read(buffer)
                    if (read < 0) break
                    synchronized(output) {
                        val available = (limit - output.size()).coerceAtLeast(0)
                        if (available > 0) output.write(buffer, 0, minOf(read, available))
                        if (read > available) truncated = true
                    }
                }
            }
        }, "agent-exec-$id").apply { isDaemon = true }

        fun snapshot(timedOut: Boolean = false): ExecutionResult {
            val running = process.isAlive
            val bytes = synchronized(output) { output.toByteArray() }
            return ExecutionResult(id, if (running) null else runCatching { process.exitValue() }.getOrNull(), bytes.toString(Charsets.UTF_8), timedOut, truncated, running)
        }
    }
}

private fun Process.destroyProcessTree() {
    destroy()
    if (isAlive) {
        destroyForcibly()
    }
}
