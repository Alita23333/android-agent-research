package dev.alita.androidagent.zcode.runtime

import android.content.Context
import dev.alita.androidagent.model.SecureSettings
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.net.URI
import java.nio.file.Files
import java.nio.file.StandardCopyOption

data class SearchBackend(
    val id: String,
    val name: String,
    val enabled: Boolean = true,
    val baseUrl: String,
    val defaultCount: Int = 8,
    val timeoutMs: Int = 60_000,
    val sessionCap: Int = 60,
)

data class SearchNetwork(
    val httpProxy: String? = null,
    val noProxy: String? = null,
    val caCertFile: String? = null,
    val timeout: Int? = null,
)

data class SearchConfig(
    val backends: List<SearchBackend>,
    val network: SearchNetwork = SearchNetwork(),
    val sessionCap: Int? = null,
)

/** Materializes the validated Phase 7 BYOK search contract for the Node bridge. */
object ZCodeSearchConfigWriter {
    private const val INDEX_KEY = "search_index"
    private fun keyEntry(id: String) = "search_api_key::$id"
    val backendIds = setOf("brave", "tavily", "bocha", "custom")
    val enabledBackendIds = setOf("brave", "tavily")

    fun defaultBaseUrl(id: String): String = when (id) {
        "brave" -> "https://api.search.brave.com/res/v1"
        "tavily" -> "https://api.tavily.com"
        "bocha" -> "https://api.bochaai.com"
        else -> ""
    }

    fun load(context: Context): SearchConfig? = SecureSettings(context).getSecret(INDEX_KEY)?.let(::parse)

    fun apiKeyFor(context: Context, id: String): String =
        SecureSettings(context).getSecret(keyEntry(id)).orEmpty()

    /**
     * Full-replacement semantics: every configured backend must be present in [keys].
     * A missing or empty value deletes any stale key for that backend.
     */
    fun save(context: Context, config: SearchConfig, keys: Map<String, String>) {
        validate(config, allowLab = File(context.filesDir, "labsearch.enabled").isFile)
        val secure = SecureSettings(context)
        secure.putSecret(INDEX_KEY, toIndexJson(config, keys).toString())
        backendIds.forEach { id ->
            val key = keys[id].orEmpty()
            if (config.backends.any { it.id == id } && key.isNotEmpty()) secure.putSecret(keyEntry(id), key)
            else secure.deleteSecret(keyEntry(id))
        }
    }

    fun saveFromUi(context: Context, config: SearchConfig, typedKey: String) {
        val id = config.backends.single().id
        val retained = typedKey.trim().ifEmpty { apiKeyFor(context, id) }
        save(context, config, mapOf(id to retained))
        check(materialize(context)) { lastMaterializeError ?: "Unable to materialize search settings" }
    }

    @Volatile var lastMaterializeError: String? = null
        private set

    fun materialize(context: Context): Boolean {
        lastMaterializeError = null
        val outDir = File(context.filesDir, "runtime/search").apply { mkdirs() }
        val output = File(outDir, "search_config.json")
        val config = load(context)
        val document = if (config == null) {
            JSONObject().put("schemaVersion", 1).put("backends", JSONArray()).put("network", JSONObject())
        } else {
            runCatching { validate(config, allowLab = File(context.filesDir, "labsearch.enabled").isFile) }
                .onFailure { lastMaterializeError = it.message }
                .getOrElse { return false }
            toRuntimeJson(context, config)
        }
        val text = document.toString(2)
        val temporary = File(outDir, ".search_config.json.tmp")
        return try {
            FileOutputStream(temporary).use { stream ->
                stream.write(text.toByteArray(Charsets.UTF_8))
                stream.fd.sync()
            }
            Files.move(
                temporary.toPath(), output.toPath(),
                StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING,
            )
            output.setReadable(false, false)
            output.setReadable(true, true)
            val reread = JSONObject(output.readText())
            check(reread.toString() == JSONObject(text).toString()) { "read-back mismatch after write" }
            true
        } catch (error: Throwable) {
            temporary.delete()
            lastMaterializeError = "search config materialization failed: ${error.message}"
            false
        }
    }

    fun validate(config: SearchConfig, allowLab: Boolean = false) {
        require(config.backends.map { it.id }.distinct().size == config.backends.size) { "Duplicate search backend id" }
        config.backends.forEach { backend ->
            require(backend.id in backendIds) { "Unsupported search backend: ${backend.id}" }
            require(!backend.enabled || backend.id in enabledBackendIds) { "${backend.id} adapter is disabled pending endpoint validation" }
            require(backend.defaultCount in 1..20) { "Search result count must be 1-20" }
            require(backend.timeoutMs in 1_000..120_000) { "Search timeout must be 1000-120000 ms" }
            require(backend.sessionCap in 1..10_000) { "Search session cap is invalid" }
            val uri = URI(backend.baseUrl)
            require(uri.userInfo == null && !uri.host.isNullOrBlank()) { "Search base URL must not contain credentials and must have a host" }
            val labOrigin = allowLab && uri.scheme.equals("http", true) &&
                (uri.host == "127.0.0.1" || uri.host.equals("localhost", true))
            require(uri.scheme.equals("https", true) || labOrigin) { "Search base URL must use HTTPS" }
        }
        config.sessionCap?.let { require(it in 1..10_000) { "Global search session cap is invalid" } }
        config.network.timeout?.let { require(it in 1_000..120_000) { "Network timeout must be 1000-120000 ms" } }
    }

    private fun parse(raw: String): SearchConfig = JSONObject(raw).let { root ->
        val backends = root.optJSONArray("backends") ?: JSONArray()
        val parsed = (0 until backends.length()).map { index ->
            backends.getJSONObject(index).let { item ->
                SearchBackend(
                    id = item.getString("id"),
                    name = item.optString("name", item.getString("id")),
                    enabled = item.optBoolean("enabled", true),
                    baseUrl = item.getString("baseUrl"),
                    defaultCount = item.optInt("defaultCount", 8),
                    timeoutMs = item.optInt("timeoutMs", 60_000),
                    sessionCap = item.optInt("sessionCap", 60),
                )
            }
        }
        val network = root.optJSONObject("network")
        SearchConfig(
            backends = parsed,
            network = SearchNetwork(
                httpProxy = network?.optString("httpProxy")?.takeIf(String::isNotBlank),
                noProxy = network?.optString("noProxy")?.takeIf(String::isNotBlank),
                caCertFile = network?.optString("caCertFile")?.takeIf(String::isNotBlank),
                timeout = network?.takeIf { it.has("timeout") }?.optInt("timeout"),
            ),
            sessionCap = root.optJSONObject("limits")?.takeIf { it.has("sessionCap") }?.optInt("sessionCap"),
        )
    }

    private fun toIndexJson(config: SearchConfig, keys: Map<String, String>) = JSONObject()
        .put("schemaVersion", 1)
        .put("backends", JSONArray(config.backends.map { backendJson(it).put("hasKey", keys[ it.id ].orEmpty().isNotEmpty()) }))
        .put("network", networkJson(config.network))
        .apply { config.sessionCap?.let { put("limits", JSONObject().put("sessionCap", it)) } }

    private fun toRuntimeJson(context: Context, config: SearchConfig) = JSONObject()
        .put("schemaVersion", 1)
        .put("backends", JSONArray(config.backends.map(::backendJson)))
        .put("network", networkJson(config.network))
        .put("_keys", JSONObject().apply {
            config.backends.forEach { backend ->
                apiKeyFor(context, backend.id).takeIf(String::isNotEmpty)?.let { put(backend.id, it) }
            }
        })
        .apply { config.sessionCap?.let { put("limits", JSONObject().put("sessionCap", it)) } }

    private fun backendJson(backend: SearchBackend) = JSONObject()
        .put("id", backend.id).put("name", backend.name).put("enabled", backend.enabled)
        .put("baseUrl", backend.baseUrl).put("defaultCount", backend.defaultCount)
        .put("timeoutMs", backend.timeoutMs).put("sessionCap", backend.sessionCap)

    private fun networkJson(network: SearchNetwork) = JSONObject().apply {
        network.httpProxy?.let { put("httpProxy", it) }
        network.noProxy?.let { put("noProxy", it) }
        network.caCertFile?.let { put("caCertFile", it) }
        network.timeout?.let { put("timeout", it) }
    }
}
