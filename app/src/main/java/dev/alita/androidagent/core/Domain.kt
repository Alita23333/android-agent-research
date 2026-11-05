package dev.alita.androidagent.core

import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

enum class SideEffect { NONE, REVERSIBLE, EXTERNAL, DESTRUCTIVE, SYSTEM }

data class ToolDefinition(
    val id: String,
    val version: String = "1.0.0",
    val description: String,
    val inputSchema: JSONObject,
    val capabilities: Set<String> = emptySet(),
    val sideEffect: SideEffect = SideEffect.NONE,
    val supportsCancellation: Boolean = false,
)

data class ToolCall(
    val callId: String = UUID.randomUUID().toString(),
    val toolId: String,
    val arguments: JSONObject = JSONObject(),
)

data class ArtifactRef(
    val id: String,
    val name: String,
    val mimeType: String,
    val uri: String,
    val size: Long,
) {
    fun toJson() = JSONObject()
        .put("id", id).put("name", name).put("mimeType", mimeType)
        .put("uri", uri).put("size", size)
}

data class ToolFailure(
    val code: String,
    val message: String,
    val retryable: Boolean = false,
)

data class ToolResult(
    val callId: String,
    val ok: Boolean,
    val data: JSONObject = JSONObject(),
    val error: ToolFailure? = null,
    val artifacts: List<ArtifactRef> = emptyList(),
) {
    fun toJson(): JSONObject = JSONObject()
        .put("ok", ok)
        .put("data", data)
        .put("error", error?.let {
            JSONObject().put("code", it.code).put("message", it.message).put("retryable", it.retryable)
        })
        .put("artifacts", JSONArray(artifacts.map { it.toJson() }))

    companion object {
        fun success(call: ToolCall, data: JSONObject = JSONObject(), artifacts: List<ArtifactRef> = emptyList()) =
            ToolResult(call.callId, true, data, artifacts = artifacts)

        fun failure(call: ToolCall, code: String, message: String, retryable: Boolean = false) =
            ToolResult(call.callId, false, error = ToolFailure(code, message, retryable))
    }
}

interface AgentTool {
    val definition: ToolDefinition
    suspend fun execute(call: ToolCall, context: ToolContext): ToolResult
}

data class ToolContext(
    val runId: String,
    val cancellation: CancellationSignal,
    val artifactStore: ArtifactStore,
)

class CancellationSignal {
    @Volatile private var cancelled = false
    private val callbacks = mutableListOf<() -> Unit>()

    fun cancel() {
        val copy = synchronized(callbacks) {
            if (cancelled) return
            cancelled = true
            callbacks.toList()
        }
        copy.forEach { runCatching(it) }
    }

    fun isCancelled() = cancelled
    fun throwIfCancelled() { if (cancelled) throw InterruptedException("Task cancelled") }
    fun onCancel(action: () -> Unit) = synchronized(callbacks) {
        if (cancelled) action() else callbacks += action
    }
}

interface ArtifactStore {
    fun create(runId: String, name: String, mimeType: String, bytes: ByteArray): ArtifactRef
}

enum class AgentRole { SYSTEM, USER, ASSISTANT, TOOL }

data class AgentMessage(
    val role: AgentRole,
    val content: String? = null,
    val toolCalls: List<ToolCall> = emptyList(),
    val toolCallId: String? = null,
)

data class ModelRequest(
    val messages: List<AgentMessage>,
    val tools: List<ToolDefinition>,
    val maxOutputTokens: Int = 4096,
)

data class ModelResponse(
    val text: String,
    val toolCalls: List<ToolCall>,
    val finishReason: String? = null,
)

data class ModelCapabilities(
    val toolCalls: Boolean,
    val streaming: Boolean,
    val imageInput: Boolean = false,
)

sealed interface ModelEvent {
    data class TextDelta(val text: String) : ModelEvent
    data class Status(val text: String) : ModelEvent
}

interface ModelProvider {
    val id: String
    val capabilities: ModelCapabilities
    suspend fun complete(request: ModelRequest, onEvent: suspend (ModelEvent) -> Unit = {}): ModelResponse
}
