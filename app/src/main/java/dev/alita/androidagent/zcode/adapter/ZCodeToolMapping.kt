package dev.alita.androidagent.zcode.adapter

import org.json.JSONArray
import org.json.JSONObject

/**
 * Canonical carrier-neutral representation used at the ZCode boundary.
 * A concrete upstream MCP/tool carrier may wrap these fields, but it must not
 * change the Android contract or silently discard structured errors/artifacts.
 */
object ZCodeToolMapping {
    fun encodeDefinition(definition: AndroidToolDefinition): JSONObject = JSONObject()
        .put("name", definition.id)
        .put("description", definition.description)
        .put("inputSchema", definition.inputSchema)
        .put("metadata", JSONObject()
            .put("version", definition.version)
            .apply { definition.providerContentHash?.let { put("providerContentHash", it) } }
            .apply { definition.providerDefinitionHash?.let { put("providerDefinitionHash", it) } }
            .put("capabilities", JSONArray(definition.capabilities.sorted()))
            .put("readOnly", definition.readOnly)
            .put("supportsCancellation", definition.supportsCancellation))

    fun decodeCall(call: JSONObject, sessionId: String? = null): AndroidToolRequest {
        val id = call.optString("callId").ifBlank { call.optString("id") }
        require(id.isNotBlank()) { "ZCode tool call is missing callId" }
        val name = call.optString("name").ifBlank { call.optString("toolId") }
        require(name.isNotBlank()) { "ZCode tool call is missing tool name" }
        return AndroidToolRequest(
            requestId = id,
            toolId = name,
            arguments = call.optJSONObject("arguments") ?: call.optJSONObject("input") ?: JSONObject(),
            sessionId = sessionId,
            metadata = call.optJSONObject("metadata") ?: JSONObject(),
        )
    }

    fun encodeResult(result: AndroidToolResult): JSONObject {
        val structured = result.toJson()
        val text = if (result.ok) result.data.toString() else result.error!!.toJson().toString()
        return JSONObject()
            .put("toolCallId", result.requestId)
            .put("isError", !result.ok)
            .put("content", JSONArray().put(JSONObject().put("type", "text").put("text", text)))
            .put("structuredContent", structured)
    }
}

interface ZCodeToolCarrier {
    val carrierId: String
    suspend fun publish(
        definitions: List<JSONObject>,
        handler: suspend (call: JSONObject, cancellation: AndroidToolCancellation) -> JSONObject,
    )
    suspend fun close() = Unit
}

/** Connects a future upstream-supported carrier to the Android dispatcher. */
class ZCodeToolCarrierAdapter(
    private val carrier: ZCodeToolCarrier,
    private val dispatcher: AndroidToolDispatcher,
) {
    suspend fun start() {
        val definitions = dispatcher.definitions().map(ZCodeToolMapping::encodeDefinition)
        carrier.publish(definitions) { call, cancellation ->
            val request = runCatching { ZCodeToolMapping.decodeCall(call) }.getOrElse { error ->
                val requestId = call.optString("callId", call.optString("id", "unknown"))
                return@publish ZCodeToolMapping.encodeResult(AndroidToolResult(
                    requestId = requestId,
                    ok = false,
                    error = AndroidToolError("INVALID_TOOL_CALL", error.message ?: "Invalid tool call"),
                ))
            }
            ZCodeToolMapping.encodeResult(dispatcher.execute(request, cancellation))
        }
    }

    suspend fun close() = carrier.close()
}

/** Test carrier; production binding must come from an upstream-supported seam. */
class InMemoryZCodeToolCarrier : ZCodeToolCarrier {
    override val carrierId = "in-memory-test"
    var definitions: List<JSONObject> = emptyList()
        private set
    private var handler: (suspend (JSONObject, AndroidToolCancellation) -> JSONObject)? = null

    override suspend fun publish(
        definitions: List<JSONObject>,
        handler: suspend (JSONObject, AndroidToolCancellation) -> JSONObject,
    ) {
        this.definitions = definitions
        this.handler = handler
    }

    suspend fun invoke(call: JSONObject, cancellation: AndroidToolCancellation = NeverCancelled): JSONObject =
        requireNotNull(handler) { "Carrier has not been published" }(call, cancellation)
}
