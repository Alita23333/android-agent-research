package dev.alita.androidagent.zcode.runtime

import org.json.JSONObject
import java.util.concurrent.atomic.AtomicLong

/** ZCode Protocol is NDJSON and intentionally has no jsonrpc field. */
object ZCodeProtocol {
    private val ids = AtomicLong()

    fun request(method: String, params: JSONObject = JSONObject(), id: String = ids.incrementAndGet().toString()): JSONObject {
        require(method.isNotBlank()) { "ZCode method is blank" }
        return JSONObject().put("id", id).put("method", method).put("params", params)
    }

    fun response(id: String, result: JSONObject): JSONObject = JSONObject().put("id", id).put("result", result)

    fun error(id: String, code: String, message: String): JSONObject = JSONObject()
        .put("id", id)
        .put("error", JSONObject().put("code", code).put("message", message))

    fun encode(message: JSONObject, maxBytes: Int = 1_048_576): String {
        require(!message.has("jsonrpc")) { "ZCode Protocol must not contain jsonrpc" }
        val line = message.toString()
        require(line.toByteArray(Charsets.UTF_8).size <= maxBytes) { "ZCode message exceeds limit" }
        require('\n' !in line && '\r' !in line) { "ZCode message must occupy one NDJSON line" }
        return line
    }

    fun decode(line: String, maxBytes: Int = 1_048_576): JSONObject {
        require(line.toByteArray(Charsets.UTF_8).size <= maxBytes) { "ZCode message exceeds limit" }
        val message = JSONObject(line)
        require(!message.has("jsonrpc")) { "Received JSON-RPC on ZCode Protocol channel" }
        require(message.optString("id").isNotBlank() || message.has("method")) { "Invalid ZCode message" }
        return message
    }
}
