package dev.alita.androidagent.zcode.runtime

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** Android host client for the production-approved Phase 4 loopback Gateway API. */
class ZCodeGatewayClient(context: Context) {
    private val appContext = context.applicationContext
    private val baseUrl = "http://127.0.0.1:8765"

    suspend fun status(): JSONObject = request("GET", "/status")
    suspend fun capabilities(): JSONObject = request("GET", "/capabilities")
    suspend fun pending(): JSONObject = request("GET", "/gateway/pending")
    suspend fun journal(limit: Int = 50): JSONObject = request("GET", "/gateway/journal?limit=${limit.coerceIn(1, 500)}")
    suspend fun networkJournal(limit: Int = 100): JSONObject = request("GET", "/gateway/network?limit=${limit.coerceIn(1, 500)}")
    suspend fun domainRules(): JSONObject = request("GET", "/gateway/rules")
    suspend fun searchStatus(): JSONObject = request("GET", "/search/status")
    suspend fun sessions(): JSONObject = request("GET", "/sessions")

    suspend fun registerCarrierTools(tools: JSONArray): JSONObject =
        request("POST", "/carrier/register", JSONObject().put("tools", tools))

    suspend fun nextCarrierCall(): JSONObject = request("GET", "/carrier/next", readTimeoutMs = 130_000)

    suspend fun respondCarrier(result: JSONObject): JSONObject =
        request("POST", "/carrier/respond", result)

    suspend fun respond(requestId: String, allow: Boolean, confirmToken: String? = null): JSONObject =
        request("POST", "/respond", JSONObject()
            .put("requestId", requestId)
            .put("decision", if (allow) "allow" else "deny")
            .apply { if (confirmToken != null) put("confirmToken", confirmToken) })

    suspend fun rollback(operationId: Long): JSONObject =
        request("POST", "/gateway/rollback", JSONObject().put("id", operationId))

    suspend fun rpc(message: JSONObject): JSONObject = request("POST", "/rpc", message)

    suspend fun resume(sessionId: String): JSONObject =
        request("GET", "/session/resume?id=${java.net.URLEncoder.encode(sessionId, "UTF-8")}")

    private suspend fun request(
        method: String,
        path: String,
        body: JSONObject? = null,
        readTimeoutMs: Int = 20_000,
    ): JSONObject = withContext(Dispatchers.IO) {
        val separator = if ('?' in path) '&' else '?'
        val token = ZCodeRuntimeBundle(appContext).bridgeToken()
        val connection = URL("$baseUrl$path${separator}t=$token").openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = 5_000
            connection.readTimeout = readTimeoutMs
            connection.setRequestProperty("X-Bridge-Token", token)
            connection.setRequestProperty("Content-Type", "application/json")
            if (body != null) {
                connection.doOutput = true
                connection.outputStream.bufferedWriter().use { it.write(body.toString()) }
            }
            val status = connection.responseCode
            val text = (if (status in 200..299) connection.inputStream else connection.errorStream)
                ?.bufferedReader()?.use { it.readText() }.orEmpty()
            val json = if (text.isBlank()) JSONObject() else JSONObject(text)
            if (status !in 200..299) throw ZCodeGatewayException(status, json)
            json
        } finally {
            connection.disconnect()
        }
    }
}

class ZCodeGatewayException(val statusCode: Int, val payload: JSONObject) :
    IllegalStateException("Gateway HTTP $statusCode: $payload")
