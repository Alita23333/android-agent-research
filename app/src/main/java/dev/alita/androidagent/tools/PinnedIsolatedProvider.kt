package dev.alita.androidagent.tools

import android.content.Context
import android.util.Base64
import dev.alita.androidagent.core.*
import dev.alita.androidagent.execution.isolation.IsolatedNodeRuntime
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/** A host-reviewed, byte-bound ToolProvider. Installation/active selection never constructs this.
 * No permission/Gateway decision is made here. Only a bounded, isolated pure-data profile exists.
 */
class PinnedIsolatedProvider private constructor(
    private val catalog: LocalProviderCatalog,
    private val pin: LocalProviderDescriptor,
    reviewed: List<ToolDefinition>,
    private val launch: (ByteArray, String, CancellationSignal) -> Process,
) : ToolProvider {
    override val providerId = pin.id
    val contentHash = pin.directory.name
    private val definitions = reviewed.map { it.copy(inputSchema = JSONObject(it.inputSchema.toString()), capabilities = it.capabilities.toSet()) }
    internal fun reviewedDefinitions(): List<ToolDefinition> = definitions.map {
        it.copy(inputSchema = JSONObject(it.inputSchema.toString()), capabilities = it.capabilities.toSet())
    }
    val definitionHash: String get() = java.security.MessageDigest.getInstance("SHA-256")
        .digest(canonical(declarations()).toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
    internal fun declarations() = org.json.JSONArray(definitions.sortedBy { it.id }.map { d ->
        JSONObject().put("id", d.id).put("version", d.version).put("description", d.description)
            .put("inputSchema", JSONObject(d.inputSchema.toString())).put("capabilities", org.json.JSONArray(d.capabilities.sorted()))
            .put("sideEffect", d.sideEffect.name).put("supportsCancellation", d.supportsCancellation)
    })
    fun sessionSnapshot(): JSONObject = JSONObject().put("id", providerId).put("version", pin.version)
        .put("contentHash", contentHash).put("definitionHash", definitionHash)
        .put("toolIds", org.json.JSONArray(definitions.map { it.id }.sorted()))

    companion object {
        fun inputSchema() = JSONObject("""{"type":"object","required":["base64"],"additionalProperties":false,"properties":{"base64":{"type":"string","maxLength":21848}}}""")
        fun review(context: Context, catalog: LocalProviderCatalog, pin: LocalProviderDescriptor,
                   hostDefinitions: List<ToolDefinition>): PinnedIsolatedProvider {
            val runtime = IsolatedNodeRuntime(context)
            return reviewed(catalog, pin, hostDefinitions) { bytes, hash, cancellation ->
                runtime.launch(bytes, hash, cancellation::isCancelled, {}, 60000)
            }
        }
        internal fun reviewed(catalog: LocalProviderCatalog, pin: LocalProviderDescriptor,
                              definitions: List<ToolDefinition>, launch: (ByteArray, String, CancellationSignal) -> Process): PinnedIsolatedProvider {
            require(pin.id.lowercase() !in setOf("device_info", "text_digest", "ui", "workspace", "web")) { "Reserved host provider namespace" }
            require(definitions.size in 1..16 && definitions.map { it.id }.toSet().size == definitions.size)
            definitions.forEach {
                require(it.id.startsWith("${pin.id}.") && it.id.removePrefix("${pin.id}.").matches(Regex("[A-Za-z][A-Za-z0-9_-]{0,63}")))
                require(it.sideEffect == SideEffect.NONE && it.capabilities == setOf("data-transform") && it.supportsCancellation)
                require(it.version.length in 1..128 && it.description.length in 1..4096)
                require(canonical(it.inputSchema) == canonical(inputSchema())) { "Only bounded base64 data inputs are admitted" }
                require(!it.id.replace('.', '_').matches(Regex("(?i)(ui|workspace|web)_.*"))) { "Reserved carrier namespace" }
            }
            catalog.readPinnedNodeEntry(pin) // Integrity/dependency check only; no launch/hook execution.
            return PinnedIsolatedProvider(catalog, pin, definitions, launch)
        }
        internal fun canonical(value: Any?): String = when (value) {
            is JSONObject -> value.keys().asSequence().toList().sorted().joinToString(prefix = "{", postfix = "}") { JSONObject.quote(it) + ":" + canonical(value.get(it)) }
            is org.json.JSONArray -> (0 until value.length()).joinToString(prefix = "[", postfix = "]") { canonical(value.get(it)) }
            is String -> JSONObject.quote(value)
            else -> value.toString()
        }
    }

    override suspend fun tools(): List<AgentTool> = definitions.map { BoundTool(it.id) }
    /** Marker is a concrete host class with a private constructor, never a provider metadata claim. */
    inner class BoundTool internal constructor(private val id: String) : AgentTool {
        override val definition: ToolDefinition get() = definitions.single { it.id == id }.let {
            it.copy(inputSchema = JSONObject(it.inputSchema.toString()), capabilities = it.capabilities.toSet())
        }
        val packageHash: String get() = contentHash
        val reviewedDefinitionHash: String get() = definitionHash
        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult = withContext(Dispatchers.IO) {
            if (context.cancellation.isCancelled()) return@withContext ToolResult.failure(call, "CANCELLED", "Tool call cancelled")
            if (call.toolId != id || !context.runId.matches(Regex("[A-Za-z0-9_-]{1,128}")) || !call.callId.matches(Regex("[A-Za-z0-9_-]{1,128}")))
                return@withContext ToolResult.failure(call, "INVALID_INPUT", "Unsafe call/session identity")
            val input = runCatching {
                require(call.arguments.keys().asSequence().toSet() == setOf("base64"))
                val encoded = call.arguments.getString("base64"); require(encoded.length <= 21848)
                val bytes = Base64.decode(encoded, Base64.NO_WRAP)
                require(bytes.size <= 16384 && Base64.encodeToString(bytes, Base64.NO_WRAP) == encoded)
                JSONObject().put("base64", encoded)
            }.getOrElse { return@withContext ToolResult.failure(call, "INVALID_INPUT", "Canonical base64 up to16KiB required") }
            var process: Process? = null
            var stopped = true
            var scriptHash = ""
            val provider = JsonRpcStdioProvider(providerId, listOf("isolated-only"), pin.directory,
                maxMessageBytes = 65536, beforeStart = { catalog.readPinnedNodeEntry(pin) }, declaredTools = definitions,
                cancellableProcessFactory = { signal ->
                    val script = catalog.readPinnedNodeEntry(pin)
                    scriptHash = IsolatedNodeRuntime.hash(script)
                    launch(script, scriptHash, signal).also { process = it }
                })
            val result = try { provider.tools().single { it.definition.id == id }.execute(call.copy(arguments = input), context) }
                catch (error: Exception) { ToolResult.failure(call, if (context.cancellation.isCancelled()) "CANCELLED" else "PROVIDER_START_FAILED", "Pinned provider could not execute") }
                finally { provider.close(); process?.let { stopped = runCatching { it.waitFor(3000, TimeUnit.MILLISECONDS) }.getOrDefault(false) } }
            if (!stopped) return@withContext ToolResult.failure(call, "PROVIDER_TERMINATION_UNCONFIRMED", "Provider death was not confirmed")
            if (!result.ok) return@withContext result
            if (context.cancellation.isCancelled()) return@withContext ToolResult.failure(call, "CANCELLED", "Tool call cancelled")
            val data = JSONObject(result.data.toString())
            data.put("_hostProvider", JSONObject().put("id", providerId).put("packageVersion", pin.version)
                .put("contentHash", contentHash).put("definitionHash", definitionHash).put("scriptSha256", scriptHash).put("toolVersion", definition.version)
                .put("runtimeVersion", "node24.18.0").put("backend", "android-isolated-node"))
            val report = JSONObject().put("toolId", id).put("callId", call.callId).put("data", data).toString(2).toByteArray()
            if (report.size > 32768) return@withContext ToolResult.failure(call, "PROVIDER_RESULT_LIMIT", "Provider report exceeds32KiB")
            // Only host-created bytes become an artifact. Never dereference a provider-returned URI.
            val artifact = runCatching { context.artifactStore.create(context.runId, "provider-${call.callId}.json", "application/json", report) }
                .getOrElse { return@withContext ToolResult.failure(call, "ARTIFACT_FAILED", "Host report could not be saved") }
            ToolResult.success(call, data, listOf(artifact))
        }
    }
}
