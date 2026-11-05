package dev.alita.androidagent.zcode.runtime

import android.content.Context
import dev.alita.androidagent.model.SecureSettings
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.URI

/** Materializes the Phase 4 strict personal-provider schema immediately before spawn. */
object ZCodeProviderConfigWriter {
    fun materialize(context: Context): File {
        val output = File(context.filesDir, "runtime/provider/personal_provider_config.json")
        output.parentFile?.mkdirs()
        val settings = SecureSettings(context).load()
        val providers = JSONArray()
        val models = JSONArray()
        if (settings.apiKey.isNotBlank() && settings.model.isNotBlank() && settings.baseUrl.isNotBlank()) {
            val deepSeek = runCatching { URI(settings.baseUrl).host?.endsWith("deepseek.com") == true }.getOrDefault(false)
            val providerId = if (deepSeek) "deepseek" else "android-byok"
            val providerName = if (deepSeek) "DeepSeek" else "Android BYOK"
            providers.put(JSONObject()
                .put("providerId", providerId)
                .put("providerName", providerName)
                .put("enabled", true)
                .put("config", JSONObject()
                    .put("group", "standard-personal")
                    .put("access", JSONObject().put("type", "api-key").put("apiKey", settings.apiKey))
                    .put("api", JSONObject().put("type", "openai-chat-completions").put("baseUrl", settings.baseUrl))
                    .put("personalModelIds", JSONArray().put(settings.model))))
            models.put(JSONObject()
                .put("providerId", providerId)
                .put("modelId", settings.model)
                .put("config", JSONObject()
                    .put("enabled", true)
                    .put("properties", JSONObject()
                        .put("contextWindow", 128000)
                        .put("supportsJsonSchemaOutput", false)
                        .put("supportsNativeWebSearch", false)
                        .put("supportsMidConversationSystem", false)
                        .put("inputFormat", JSONObject()
                            .put("supportsImage", false)
                            .put("supportsVideo", false)
                            .put("supportsPdf", false)))
                    .put("optionSpecs", JSONObject()
                        .put("reasoningLevel", JSONObject()
                            .put("values", JSONArray().put("disabled").put("enabled"))
                            .put("map", "{}"))
                        .put("maxOutputTokens", JSONObject().put("max", 8192)))))
        }
        val json = JSONObject()
            .put("schemaVersion", 1)
            .put("config", JSONObject()
                .put("providerConfigRules", JSONObject().put("providerRules", providers))
                .put("modelConfigRules", JSONObject()
                    .put("providerModelRules", JSONArray())
                    .put("manualProviderModelRules", models)))
        output.writeText(json.toString(2))
        output.setReadable(false, false)
        output.setReadable(true, true)
        return output
    }
}
