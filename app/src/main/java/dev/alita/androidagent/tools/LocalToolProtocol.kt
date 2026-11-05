package dev.alita.androidagent.tools

import dev.alita.androidagent.zcode.adapter.AndroidToolError
import dev.alita.androidagent.zcode.adapter.AndroidToolRequest
import dev.alita.androidagent.zcode.adapter.AndroidToolResult
import org.json.JSONObject

/** Exact JSON-RPC 2.0 mapping for the Android Local Tool Protocol 1.x. */
object LocalToolProtocol {
    const val VERSION = "1.0"

    fun initializeRequest(id: Long): JSONObject = envelope(
        id,
        "initialize",
        JSONObject()
            .put("protocolVersion", VERSION)
            .put("client", JSONObject().put("name", "android-agent").put("version", "0.1.0")),
    )

    fun toolCallRequest(id: Long, request: AndroidToolRequest): JSONObject = envelope(
        id,
        "tools/call",
        JSONObject()
            .put("name", request.toolId.substringAfterLast('.'))
            .put("arguments", request.arguments)
            .put("callId", request.requestId),
    )

    fun decodeToolResult(request: AndroidToolRequest, result: JSONObject): AndroidToolResult {
        val ok = result.optBoolean("ok", true)
        val error = result.optJSONObject("error")
        return if (ok) {
            AndroidToolResult.success(request, result.optJSONObject("data") ?: result)
        } else {
            AndroidToolResult(
                requestId = request.requestId,
                ok = false,
                error = AndroidToolError(
                    code = error?.optString("code", "REMOTE_ERROR") ?: "REMOTE_ERROR",
                    message = error?.optString("message", "Remote tool failed") ?: "Remote tool failed",
                    retryable = error?.optBoolean("retryable", false) ?: false,
                    details = error?.optJSONObject("details") ?: JSONObject(),
                ),
            )
        }
    }

    private fun envelope(id: Long, method: String, params: JSONObject) = JSONObject()
        .put("jsonrpc", "2.0")
        .put("id", id)
        .put("method", method)
        .put("params", params)
}
