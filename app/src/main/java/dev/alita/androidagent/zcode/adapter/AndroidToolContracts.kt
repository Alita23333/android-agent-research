package dev.alita.androidagent.zcode.adapter

import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

/**
 * Stable Android-host boundary. Phase 4 may replace the dispatcher behind this
 * contract, but ZCode carriers and local providers must not depend on that
 * implementation.
 */
data class AndroidToolDefinition(
    val id: String,
    val version: String,
    val description: String,
    val inputSchema: JSONObject,
    val capabilities: Set<String> = emptySet(),
    val readOnly: Boolean,
    val supportsCancellation: Boolean = false,
    val providerContentHash: String? = null,
    val providerDefinitionHash: String? = null,
)

data class AndroidToolRequest(
    val requestId: String = UUID.randomUUID().toString(),
    val toolId: String,
    val arguments: JSONObject = JSONObject(),
    val sessionId: String? = null,
    val metadata: JSONObject = JSONObject(),
)

data class ArtifactRef(
    val id: String,
    val name: String,
    val mimeType: String,
    val uri: String,
    val size: Long,
) {
    fun toJson(): JSONObject = JSONObject()
        .put("id", id)
        .put("name", name)
        .put("mimeType", mimeType)
        .put("uri", uri)
        .put("size", size)
}

data class AndroidToolError(
    val code: String,
    val message: String,
    val retryable: Boolean = false,
    val details: JSONObject = JSONObject(),
) {
    fun toJson(): JSONObject = JSONObject()
        .put("code", code)
        .put("message", message)
        .put("retryable", retryable)
        .put("details", details)
}

data class AndroidToolResult(
    val requestId: String,
    val ok: Boolean,
    val data: JSONObject = JSONObject(),
    val error: AndroidToolError? = null,
    val artifacts: List<ArtifactRef> = emptyList(),
    val metadata: JSONObject = JSONObject(),
) {
    init {
        require(ok == (error == null)) { "Successful results cannot contain an error; failed results must contain one" }
    }

    fun toJson(): JSONObject = JSONObject()
        .put("requestId", requestId)
        .put("ok", ok)
        .put("data", data)
        .put("error", error?.toJson())
        .put("artifacts", JSONArray(artifacts.map { it.toJson() }))
        .put("metadata", metadata)

    companion object {
        fun success(
            request: AndroidToolRequest,
            data: JSONObject = JSONObject(),
            artifacts: List<ArtifactRef> = emptyList(),
            metadata: JSONObject = JSONObject(),
        ) = AndroidToolResult(request.requestId, true, data, artifacts = artifacts, metadata = metadata)

        fun failure(
            request: AndroidToolRequest,
            code: String,
            message: String,
            retryable: Boolean = false,
            details: JSONObject = JSONObject(),
        ) = AndroidToolResult(
            requestId = request.requestId,
            ok = false,
            error = AndroidToolError(code, message, retryable, details),
        )
    }
}

interface AndroidToolCancellation {
    val isCancelled: Boolean
    fun onCancel(callback: () -> Unit)
    fun throwIfCancelled() {
        if (isCancelled) throw AndroidToolCancelledException()
    }
}

class AndroidToolCancelledException : InterruptedException("Android tool call cancelled")

class MutableAndroidToolCancellation : AndroidToolCancellation {
    @Volatile private var cancelled = false
    private val callbacks = mutableListOf<() -> Unit>()

    override val isCancelled: Boolean get() = cancelled

    fun cancel() {
        val pending = synchronized(callbacks) {
            if (cancelled) return
            cancelled = true
            callbacks.toList().also { callbacks.clear() }
        }
        pending.forEach { runCatching(it) }
    }

    override fun onCancel(callback: () -> Unit) {
        val runNow = synchronized(callbacks) {
            if (cancelled) true else false.also { callbacks += callback }
        }
        if (runNow) callback()
    }
}

object NeverCancelled : AndroidToolCancellation {
    override val isCancelled = false
    override fun onCancel(callback: () -> Unit) = Unit
}

interface AndroidToolDispatcher {
    suspend fun definitions(): List<AndroidToolDefinition>
    suspend fun execute(request: AndroidToolRequest, cancellation: AndroidToolCancellation): AndroidToolResult
}
