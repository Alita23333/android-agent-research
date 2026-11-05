package dev.alita.androidagent.model

import dev.alita.androidagent.core.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

class OpenAiCompatibleProvider(private val settings: ModelSettings) : ModelProvider {
    override val id = "openai-compatible"
    override val capabilities = ModelCapabilities(toolCalls = true, streaming = true)

    override suspend fun complete(request: ModelRequest, onEvent: suspend (ModelEvent) -> Unit): ModelResponse = withContext(Dispatchers.IO) {
        require(settings.apiKey.isNotBlank()) { "API Key 尚未设置" }
        require(settings.model.isNotBlank()) { "模型名称尚未设置" }

        val nameToId = request.tools.associate { toolName(it.id) to it.id }
        val body = JSONObject()
            .put("model", settings.model)
            .put("messages", JSONArray(request.messages.map { messageJson(it) }))
            .put("tools", JSONArray(request.tools.map { toolJson(it) }))
            .put("tool_choice", "auto")
            .put("parallel_tool_calls", false)
            .put("stream", true)

        val endpoint = settings.baseUrl.trimEnd('/').let {
            if (it.endsWith("/chat/completions")) it else "$it/chat/completions"
        }
        val connection = (URL(endpoint).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 30_000
            readTimeout = 180_000
            doOutput = true
            setRequestProperty("Authorization", "Bearer ${settings.apiKey}")
            setRequestProperty("Content-Type", "application/json")
            setRequestProperty("Accept", "text/event-stream, application/json")
        }
        connection.outputStream.use { it.write(body.toString().toByteArray()) }
        val status = connection.responseCode
        if (status !in 200..299) {
            val error = connection.errorStream?.bufferedReader()?.use { it.readText() }.orEmpty()
            error("模型接口返回 HTTP $status: ${error.take(2000)}")
        }

        val contentType = connection.contentType.orEmpty()
        if (!contentType.contains("text/event-stream", ignoreCase = true)) {
            val json = connection.inputStream.bufferedReader().use { JSONObject(it.readText()) }
            return@withContext parseComplete(json, nameToId)
        }

        val text = StringBuilder()
        val calls = linkedMapOf<Int, StreamingCall>()
        var finishReason: String? = null
        BufferedReader(InputStreamReader(connection.inputStream)).use { reader ->
            while (true) {
                val raw = reader.readLine() ?: break
                if (!raw.startsWith("data:")) continue
                val payload = raw.removePrefix("data:").trim()
                if (payload == "[DONE]") break
                if (payload.isBlank()) continue
                val json = JSONObject(payload)
                val choice = json.optJSONArray("choices")?.optJSONObject(0) ?: continue
                finishReason = choice.optString("finish_reason").takeIf { it.isNotBlank() && it != "null" } ?: finishReason
                val delta = choice.optJSONObject("delta") ?: continue
                delta.optString("content").takeIf { it.isNotEmpty() && it != "null" }?.let {
                    text.append(it)
                    onEvent(ModelEvent.TextDelta(it))
                }
                val toolCalls = delta.optJSONArray("tool_calls")
                if (toolCalls != null) {
                    repeat(toolCalls.length()) { i ->
                        val item = toolCalls.getJSONObject(i)
                        val index = item.optInt("index", i)
                        val partial = calls.getOrPut(index) { StreamingCall() }
                        item.optString("id").takeIf { it.isNotBlank() }?.let { partial.id = it }
                        item.optJSONObject("function")?.let { function ->
                            function.optString("name").takeIf { it.isNotBlank() }?.let { partial.name += it }
                            function.optString("arguments").takeIf { it.isNotEmpty() }?.let { partial.arguments.append(it) }
                        }
                    }
                }
            }
        }
        ModelResponse(text.toString(), calls.values.map { partial ->
            val toolId = nameToId[partial.name] ?: partial.name.replace("__", ".")
            ToolCall(partial.id.ifBlank { java.util.UUID.randomUUID().toString() }, toolId, parseArguments(partial.arguments.toString()))
        }, finishReason)
    }

    private fun parseComplete(json: JSONObject, nameToId: Map<String, String>): ModelResponse {
        val choice = json.getJSONArray("choices").getJSONObject(0)
        val message = choice.getJSONObject("message")
        val calls = buildList {
            val array = message.optJSONArray("tool_calls") ?: JSONArray()
            repeat(array.length()) { index ->
                val item = array.getJSONObject(index)
                val function = item.getJSONObject("function")
                val wireName = function.getString("name")
                add(ToolCall(item.getString("id"), nameToId[wireName] ?: wireName.replace("__", "."), parseArguments(function.optString("arguments", "{}"))))
            }
        }
        return ModelResponse(message.optString("content").takeUnless { it == "null" }.orEmpty(), calls, choice.optString("finish_reason"))
    }

    private fun messageJson(message: AgentMessage): JSONObject = JSONObject().apply {
        put("role", message.role.name.lowercase())
        if (message.content != null) put("content", message.content) else put("content", JSONObject.NULL)
        message.toolCallId?.let { put("tool_call_id", it) }
        if (message.toolCalls.isNotEmpty()) put("tool_calls", JSONArray(message.toolCalls.map { call ->
            JSONObject().put("id", call.callId).put("type", "function").put("function", JSONObject()
                .put("name", toolName(call.toolId)).put("arguments", call.arguments.toString()))
        }))
    }

    private fun toolJson(definition: ToolDefinition) = JSONObject().put("type", "function").put("function", JSONObject()
        .put("name", toolName(definition.id))
        .put("description", definition.description)
        .put("parameters", definition.inputSchema)
        .put("strict", false))

    private fun toolName(id: String): String {
        val safe = id.replace(Regex("[^a-zA-Z0-9_-]"), "__")
        if (safe.length <= 60) return safe
        val hash = MessageDigest.getInstance("SHA-256").digest(id.toByteArray()).take(3).joinToString("") { "%02x".format(it) }
        return safe.take(53) + "_" + hash
    }

    private fun parseArguments(value: String): JSONObject = runCatching { JSONObject(value.ifBlank { "{}" }) }
        .getOrElse { JSONObject().put("_raw", value) }

    private class StreamingCall(var id: String = "", var name: String = "", val arguments: StringBuilder = StringBuilder())
}
