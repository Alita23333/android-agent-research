package dev.alita.androidagent.tools

import dev.alita.androidagent.core.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

/** Bounded Local Tool Protocol 1.x / JSON-RPC 2.0; neither ZCode Protocol nor MCP. */
class JsonRpcStdioProvider(
    override val providerId: String,
    private val command: List<String>,
    private val directory: File,
    private val maxMessageBytes: Int = 1_048_576,
    private val requestTimeoutMs: Long = 30_000,
    private val environment: Map<String, String> = emptyMap(),
    private val beforeStart: () -> Unit = {},
    declaredTools: List<ToolDefinition>? = null,
    private val processFactory: (() -> Process)? = null,
    private val cancellableProcessFactory: ((CancellationSignal) -> Process)? = null,
) : ToolProvider {
    private class Failure(val code: String, message: String) : Exception(message)
    private class Frame(val bytes: ByteArray? = null, val error: Throwable? = null)
    private class Session(val process: Process) {
        val instanceId = java.util.UUID.randomUUID().toString()
        val frames = ArrayBlockingQueue<Frame>(2)
        val stopped = AtomicBoolean(false)
        var signature: String? = null
        var protocolVersion = LocalToolProtocol.VERSION
    }
    @Volatile private var active: Session? = null
    private var expectedSignature: String? = null
    private val ids = AtomicLong()
    private val mutex = Mutex()
    // Opt-in host metadata, not a permission grant. Copy before exposing tool descriptions.
    private val declared = declaredTools?.map(::snapshotDefinition)
    private val declaredSignature = declared?.let(::definitionSignature)
    init {
        require(providerId.matches(Regex("[A-Za-z][A-Za-z0-9_-]{1,48}")))
        require(maxMessageBytes in 256..1_048_576 && requestTimeoutMs in 100..60_000)
        require(command.isNotEmpty())
        require(processFactory == null || cancellableProcessFactory == null) { "Choose one provider backend" }
        require(cancellableProcessFactory == null || declared != null) { "Cancellable backend requires non-executing discovery metadata" }
        declared?.let { items ->
            require(items.size in 1..64 && items.map { it.id }.toSet().size == items.size)
            items.forEach { item ->
                require(item.id.startsWith("$providerId.") && item.id.removePrefix("$providerId.").matches(Regex("[A-Za-z][A-Za-z0-9_-]{0,63}")))
                require(item.description.isNotBlank() && item.inputSchema.optString("type") == "object" && item.capabilities.size <= 32)
            }
        }
    }

    override suspend fun tools(): List<AgentTool> = mutex.withLock { withContext(Dispatchers.IO) {
        // Registration/discovery must not start externally supplied code when declarations exist.
        declared?.let { return@withContext it.map { definition -> RemoteTool(snapshotDefinition(definition)) } }
        val session = start()
        try { negotiate(session).map { RemoteTool(toDefinition(it)) } }
        catch (e: Throwable) { stop(session); throw e }
    } }
    override suspend fun close() { active?.let(::stop) }

    private fun negotiate(session: Session): List<JSONObject> {
        val result = exchange(session, "initialize", JSONObject().put("protocolVersion", "1.0")
            .put("client", JSONObject().put("name", "android-agent").put("version", "0.1.0")))
        val version = result.getString("protocolVersion")
        require(version.matches(Regex("1\\.[0-9]+"))) { "Unsupported local tool protocol" }
        val array = result.getJSONArray("tools")
        require(array.length() <= 64) { "Too many local tools" }
        val items = (0 until array.length()).map { array.getJSONObject(it) }
        require(items.map { it.getString("name") }.toSet().size == items.size) { "Duplicate local tool name" }
        items.forEach { item ->
            require(item.getString("name").matches(Regex("[A-Za-z][A-Za-z0-9_-]{0,63}"))) { "Invalid local tool name" }
            require(item.getString("description").isNotBlank())
            require(item.getJSONObject("inputSchema").optString("type") == "object")
            if (item.has("sideEffect")) SideEffect.valueOf(item.getString("sideEffect"))
            if (item.has("supportsCancellation")) require(item.get("supportsCancellation") is Boolean)
            val caps = item.optJSONArray("capabilities") ?: JSONArray()
            require(caps.length() <= 32)
            repeat(caps.length()) { require(caps.get(it) is String) }
        }
        val signature = items.sortedBy { it.getString("name") }.joinToString("\n") { it.toString() }
        if (declaredSignature != null && definitionSignature(items.map(::toDefinition)) != declaredSignature)
            throw Failure("PROVIDER_DEFINITION_MISMATCH", "Provider handshake differs from the host-pinned definitions")
        require(expectedSignature == null || expectedSignature == signature) { "Provider definitions changed on restart" }
        expectedSignature = signature
        session.signature = signature
        session.protocolVersion = version
        return items
    }

    private fun toDefinition(item: JSONObject) = ToolDefinition(
            id = "$providerId.${item.getString("name")}", version = item.optString("version", "1.0.0"),
            description = item.getString("description"), inputSchema = item.getJSONObject("inputSchema"),
            capabilities = item.optJSONArray("capabilities")?.let { a -> (0 until a.length()).map { a.getString(it) }.toSet() }.orEmpty(),
            sideEffect = SideEffect.valueOf(item.optString("sideEffect", "NONE")),
            supportsCancellation = item.optBoolean("supportsCancellation", false),
        )
    private inner class RemoteTool(override val definition: ToolDefinition) : AgentTool {
        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult = mutex.withLock { withContext(Dispatchers.IO) {
            if (context.cancellation.isCancelled()) return@withContext ToolResult.failure(call, "CANCELLED", "Tool call cancelled")
            val session = try { start(context.cancellation) } catch (e: Exception) {
                return@withContext ToolResult.failure(call, if (context.cancellation.isCancelled()) "CANCELLED" else (e as? Failure)?.code ?: "PROVIDER_START_FAILED",
                    if (context.cancellation.isCancelled()) "Tool call cancelled" else e.message ?: "Local provider could not start", false)
            }
            val inFlight = AtomicBoolean(true)
            context.cancellation.onCancel { if (inFlight.get()) stop(session) }
            try {
                if (context.cancellation.isCancelled()) throw Failure("CANCELLED", "Tool call cancelled")
                if (session.signature == null) negotiate(session)
                val result = exchange(session, "tools/call", JSONObject().put("name", definition.id.substringAfter('.'))
                    .put("arguments", call.arguments).put("callId", call.callId))
                if (context.cancellation.isCancelled()) throw Failure("CANCELLED", "Tool call cancelled")
                require(result.get("ok") is Boolean) { "Result requires boolean ok" }
                val ok = result.getBoolean("ok")
                val error = result.optJSONObject("error")
                require(ok == (error == null)) { "Result ok/error mismatch" }
                val data = result.optJSONObject("data") ?: JSONObject()
                data.put("_localProvider", JSONObject().put("providerId", providerId)
                    .put("protocolVersion", session.protocolVersion).put("rpcVersion", "2.0").put("method", "tools/call")
                    .put("requestId", ids.get()).put("processInstanceId", session.instanceId)
                    .put("replyValidated", true))
                ToolResult(call.callId, ok, data, error?.let {
                    ToolFailure(it.getString("code"), it.getString("message"), it.optBoolean("retryable", false))
                })
            } catch (e: Throwable) {
                stop(session)
                ToolResult.failure(call, if (context.cancellation.isCancelled()) "CANCELLED" else (e as? Failure)?.code ?: "PROVIDER_PROTOCOL_ERROR",
                    if (context.cancellation.isCancelled()) "Tool call cancelled" else e.message ?: "Local provider failed", false)
            } finally { inFlight.set(false) }
        } }
    }

    private fun exchange(session: Session, method: String, params: JSONObject): JSONObject {
        val id = ids.incrementAndGet()
        val bytes = JSONObject().put("jsonrpc", "2.0").put("id", id).put("method", method).put("params", params)
            .toString().toByteArray(Charsets.UTF_8)
        require(bytes.size <= maxMessageBytes) { "Request byte limit" }
        if (session.stopped.get()) throw Failure("PROVIDER_EXITED", "Provider session stopped")
        val written = ArrayBlockingQueue<Throwable>(1)
        val success = Exception("write complete")
        val deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(requestTimeoutMs)
        Thread({
            try { session.process.outputStream.write(bytes); session.process.outputStream.write(10); session.process.outputStream.flush(); written.offer(success) }
            catch (e: Throwable) { written.offer(e) }
        }, "local-rpc-write").apply { isDaemon = true; start() }
        val done = written.poll(requestTimeoutMs, TimeUnit.MILLISECONDS)
            ?: throw Failure("PROVIDER_TIMEOUT", "Provider stdin deadline exceeded")
        if (done !== success) throw Failure("PROVIDER_EXITED", "Provider stdin closed")
        val left = deadline - System.nanoTime()
        val frame = if (left > 0) session.frames.poll(left, TimeUnit.NANOSECONDS) else null
        if (frame == null) throw Failure("PROVIDER_TIMEOUT", "Provider response deadline exceeded")
        frame.error?.let { throw it }
        val decoder = Charsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT)
        val response = JSONObject(decoder.decode(ByteBuffer.wrap(requireNotNull(frame.bytes))).toString())
        require(response.optString("jsonrpc") == "2.0") { "Invalid JSON-RPC version" }
        require(response.get("id") is Number && response.get("id").toString() == id.toString()) { "Response id mismatch" }
        require(response.has("result") xor response.has("error")) { "Response requires exactly result or error" }
        if (response.has("error")) {
            val error = response.getJSONObject("error")
            require(error.get("code") is Number && error.get("message") is String)
            throw Failure("PROVIDER_RPC_ERROR", error.getString("message"))
        }
        return response.getJSONObject("result")
    }

    @Synchronized private fun start(cancellation: CancellationSignal = CancellationSignal()): Session {
        if (cancellation.isCancelled()) throw Failure("CANCELLED", "Tool call cancelled")
        active?.takeIf { !it.stopped.get() }?.let { return it }
        try { beforeStart() }
        catch (e: Exception) { throw Failure("PROVIDER_INTEGRITY_FAILED", e.message ?: "Provider version verification failed") }
        if (cancellation.isCancelled()) throw Failure("CANCELLED", "Tool call cancelled")
        // An explicitly selected backend must never fall back to the application UID.
        val running = if (cancellableProcessFactory != null) requireNotNull(cancellableProcessFactory.invoke(cancellation)) {
            "Selected cancellable execution backend returned no process"
        } else if (processFactory != null) requireNotNull(processFactory.invoke()) {
            "Selected provider execution backend returned no process"
        } else ProcessBuilder(command).directory(directory)
            .redirectError(ProcessBuilder.Redirect.INHERIT).apply { environment().putAll(environment) }.start()
        if (cancellation.isCancelled()) {
            running.destroyForcibly()
            Thread({
                runCatching { running.outputStream.close() }; runCatching { running.inputStream.close() }; runCatching { running.errorStream.close() }
            }, "local-rpc-aborted-start-close").apply { isDaemon = true; start() }
            throw Failure("CANCELLED", "Tool call cancelled")
        }
        val session = Session(running)
        active = session
        Thread({ pump(session) }, "local-rpc-read").apply { isDaemon = true; start() }
        return session
    }
    private fun pump(session: Session) {
        try {
            val input = session.process.inputStream
            val line = ByteArrayOutputStream()
            while (!session.stopped.get()) {
                val available = input.available()
                if (available == 0) {
                    if (!session.process.isAlive) throw Failure("PROVIDER_EXITED", "Provider exited before a complete response")
                    Thread.sleep(10); continue
                }
                repeat(minOf(available, 8192)) {
                    val byte = input.read()
                    if (byte < 0) throw Failure("PROVIDER_EXITED", "Provider stdout closed")
                    if (byte == 10) {
                        if (!session.frames.offer(Frame(line.toByteArray()))) throw Failure("PROVIDER_PROTOCOL_ERROR", "Unsolicited provider output")
                        line.reset()
                    } else {
                        if (line.size() >= maxMessageBytes) throw Failure("PROVIDER_OUTPUT_LIMIT", "Response byte limit exceeded")
                        line.write(byte)
                    }
                }
            }
        } catch (e: Throwable) { if (!session.stopped.get()) session.frames.offer(Frame(error = e)) }
    }
    @Synchronized private fun stop(session: Session) {
        if (!session.stopped.compareAndSet(false, true)) return
        if (active === session) active = null
        session.frames.clear()
        session.frames.offer(Frame(error = Failure("PROVIDER_EXITED", "Provider session terminated")))
        session.process.destroy()
        if (session.process.isAlive) session.process.destroyForcibly()
        // Direct-process cleanup only; fixed APK providers launch no descendants. Not a sandbox.
        Thread({
            runCatching { session.process.outputStream.close() }
            runCatching { session.process.inputStream.close() }
            runCatching { session.process.errorStream.close() }
        }, "local-rpc-close").apply { isDaemon = true; start() }
    }

    private fun definitionSignature(definitions: List<ToolDefinition>): String = definitions.sortedBy { it.id }.joinToString("\n") {
        canonical(JSONObject().put("id", it.id).put("version", it.version).put("description", it.description)
            .put("inputSchema", it.inputSchema).put("capabilities", JSONArray(it.capabilities.sorted()))
            .put("sideEffect", it.sideEffect.name).put("supportsCancellation", it.supportsCancellation))
    }

    private fun snapshotDefinition(definition: ToolDefinition) = definition.copy(
        inputSchema = JSONObject(definition.inputSchema.toString()), capabilities = definition.capabilities.toSet())

    private fun canonical(value: Any?): String = when (value) {
        is JSONObject -> value.keys().asSequence().toList().sorted().joinToString(prefix = "{", postfix = "}") { JSONObject.quote(it) + ":" + canonical(value.get(it)) }
        is JSONArray -> (0 until value.length()).joinToString(prefix = "[", postfix = "]") { canonical(value.get(it)) }
        null, JSONObject.NULL -> "null"
        is String -> JSONObject.quote(value)
        else -> value.toString()
    }
}
