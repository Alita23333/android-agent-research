package dev.alita.androidagent.zcode.adapter

import dev.alita.androidagent.core.ArtifactStore
import dev.alita.androidagent.core.CancellationSignal
import dev.alita.androidagent.core.SideEffect
import dev.alita.androidagent.core.ToolCall
import dev.alita.androidagent.core.ToolContext
import dev.alita.androidagent.core.ToolRegistry
import dev.alita.androidagent.tools.PinnedIsolatedProvider

/**
 * Production dispatcher for the first Android carrier slice. The upstream
 * permission broker and Gateway authorize each call before it reaches here;
 * this boundary publishes only device identity. Phase 8 UI tools are owned by
 * the single accessibility carrier worker and map ui.inspect to ui_dump.
 */
class ReadOnlyToolDispatcher(
    private val registry: ToolRegistry,
    private val artifactStore: ArtifactStore,
    private val pinnedResolver: ((AndroidToolRequest) -> dev.alita.androidagent.core.AgentTool)? = null,
) : AndroidToolDispatcher {
    private val allowed = setOf("device_info.identity", "text_digest.inspect")

    private fun exposedIds(): Set<String> = allowed + registry.definitions().filter {
        registry.find(it.id) is PinnedIsolatedProvider.BoundTool
    }.map { it.id }

    override suspend fun definitions(): List<AndroidToolDefinition> = exposedIds().mapNotNull { id ->
        registry.find(id)?.let { tool ->
            val definition = tool.definition
            require(definition.sideEffect == SideEffect.NONE) { "Read-only carrier tool declares a side effect: $id" }
            AndroidToolDefinition(
                id = definition.id,
                version = definition.version,
                description = definition.description,
                inputSchema = definition.inputSchema,
                capabilities = definition.capabilities,
                readOnly = true,
                supportsCancellation = definition.supportsCancellation,
                providerContentHash = (tool as? PinnedIsolatedProvider.BoundTool)?.packageHash,
                providerDefinitionHash = (tool as? PinnedIsolatedProvider.BoundTool)?.reviewedDefinitionHash,
            )
        }
    }.sortedBy { it.id }

    override suspend fun execute(
        request: AndroidToolRequest,
        cancellation: AndroidToolCancellation,
    ): AndroidToolResult {
        if (request.toolId !in exposedIds()) {
            return AndroidToolResult.failure(request, "TOOL_NOT_EXPOSED", "Tool is outside the approved read-only carrier slice")
        }
        val resolver = pinnedResolver
        val tool = if (request.toolId !in allowed && resolver != null) runCatching { resolver.invoke(request) }
            .getOrElse { return AndroidToolResult.failure(request, "PROVIDER_SESSION_PIN_UNAVAILABLE", "Original reviewed provider could not be resolved") }
        else registry.find(request.toolId)
            ?: return AndroidToolResult.failure(request, "TOOL_NOT_FOUND", "Tool is not registered: ${request.toolId}")
        if (request.toolId !in allowed) {
            if (tool !is PinnedIsolatedProvider.BoundTool)
                return AndroidToolResult.failure(request, "TOOL_NOT_EXPOSED", "Tool registration changed")
            if (request.metadata.optString("providerContentHash") != tool.packageHash)
                return AndroidToolResult.failure(request, "PROVIDER_PIN_MISMATCH", "Carrier snapshot differs from the registered provider pin")
            if (pinnedResolver != null && request.metadata.optString("providerDefinitionHash") != tool.reviewedDefinitionHash)
                return AndroidToolResult.failure(request, "PROVIDER_PIN_MISMATCH", "Reviewed declaration differs from the session pin")
        }
        if (tool.definition.sideEffect != SideEffect.NONE) {
            return AndroidToolResult.failure(request, "READ_ONLY_VIOLATION", "Read-only dispatcher refuses state-changing tools")
        }
        if (request.toolId == "text_digest.inspect" && tool.definition.capabilities != setOf("data-transform")) {
            return AndroidToolResult.failure(request, "CAPABILITY_MISMATCH", "Digest provider exceeds its host ceiling")
        }
        val digestInput = if (request.toolId == "text_digest.inspect") runCatching {
            require(request.arguments.keys().asSequence().toSet() == setOf("base64"))
            val encoded = request.arguments.getString("base64")
            require(encoded.length <= 21848)
            val bytes = android.util.Base64.decode(encoded, android.util.Base64.NO_WRAP)
            require(bytes.size <= 16384 && android.util.Base64.encodeToString(bytes, android.util.Base64.NO_WRAP) == encoded)
            bytes
        }.getOrElse { return AndroidToolResult.failure(request, "INVALID_INPUT", "Digest requires canonical base64 at most 16 KiB") } else null

        val coreCancellation = CancellationSignal()
        cancellation.onCancel(coreCancellation::cancel)
        if (cancellation.isCancelled) coreCancellation.cancel()
        val call = ToolCall(callId = request.requestId, toolId = request.toolId, arguments = request.arguments)
        val result = runCatching {
            tool.execute(call, ToolContext(request.sessionId ?: "zcode-carrier", coreCancellation, artifactStore))
        }.getOrElse { error ->
            if (cancellation.isCancelled) {
                return AndroidToolResult.failure(request, "CANCELLED", "Tool call cancelled")
            }
            return AndroidToolResult.failure(request, "TOOL_CRASHED", error.message ?: error.javaClass.simpleName, true)
        }
        if (cancellation.isCancelled) return AndroidToolResult.failure(request, "CANCELLED", "Tool call cancelled")
        val artifacts = result.artifacts.toMutableList()
        if (request.toolId == "text_digest.inspect" && result.ok) {
            val report = runCatching {
                val bytes = requireNotNull(digestInput)
                val hash = java.security.MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
                require(result.data.getInt("bytes") == bytes.size && result.data.getString("sha256") == hash)
                val runId = request.sessionId ?: "zcode-carrier"
                require(runId.matches(Regex("[A-Za-z0-9_-]{1,128}")))
                artifactStore.create(runId, "digest.txt", "text/plain", "SHA-256: $hash\nBytes: ${bytes.size}\n".toByteArray())
            }.getOrElse { return AndroidToolResult.failure(request, "RESULT_VERIFICATION_FAILED", "Digest result failed host verification") }
            artifacts.add(report)
        }
        return AndroidToolResult(
            requestId = request.requestId,
            ok = result.ok,
            data = result.data,
            error = result.error?.let { AndroidToolError(it.code, it.message, it.retryable) },
            artifacts = artifacts.map { ArtifactRef(it.id, it.name, it.mimeType, it.uri, it.size) },
        )
    }
}
