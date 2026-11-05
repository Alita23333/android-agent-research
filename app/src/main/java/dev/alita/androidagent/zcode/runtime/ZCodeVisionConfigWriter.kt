package dev.alita.androidagent.zcode.runtime

import android.content.Context
import dev.alita.androidagent.model.SecureSettings
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.net.URI
import java.nio.file.Files
import java.nio.file.StandardCopyOption

data class VisionConfig(val enabled: Boolean = false, val providerId: String = "custom",
    val baseUrl: String = "", val modelId: String = "")

/** An explicit independent image provider; never silently inherits the chat key/model. */
object ZCodeVisionConfigWriter {
    private const val KEY = "vision_config"
    fun load(context: Context): VisionConfig = document(context).let {
        VisionConfig(it.optBoolean("enabled"), it.optString("providerId", "custom"),
            it.optString("baseUrl"), it.optString("modelId"))
    }
    private fun document(context: Context): JSONObject = SecureSettings(context).getSecret(KEY)
        ?.let(::JSONObject) ?: JSONObject().put("enabled", false)

    fun saveFromUi(context: Context, config: VisionConfig, typedKey: String) {
        val old = document(context)
        // Retention is scoped to the same endpoint, provider and model.
        val retained = if (old.optString("baseUrl") == config.baseUrl && old.optString("providerId") == config.providerId &&
            old.optString("modelId") == config.modelId) old.optString("apiKey") else ""
        val doc = JSONObject().put("enabled", config.enabled).put("providerId", config.providerId)
            .put("baseUrl", config.baseUrl).put("modelId", config.modelId)
            .put("apiType", "openai-chat-completions").put("apiKey", typedKey.trim().ifEmpty { retained })
        validate(doc, File(context.filesDir, "labvision.enabled").isFile)
        SecureSettings(context).putSecret(KEY, doc.toString())
        materialize(context)
    }

    private fun validate(doc: JSONObject, lab: Boolean) {
        if (!doc.optBoolean("enabled")) return
        require(doc.optString("providerId").matches(Regex("[a-zA-Z0-9_-]{1,64}"))) { "视觉服务名称无效" }
        require(doc.optString("modelId").isNotBlank() && doc.optString("modelId").length <= 200) { "请填写支持图片输入的模型" }
        require(doc.optString("apiKey").isNotBlank()) { "请填写独立的视觉 API Key" }
        val uri = URI(doc.getString("baseUrl"))
        require(uri.userInfo == null && uri.fragment == null && uri.query == null && !uri.host.isNullOrBlank()) { "视觉接口地址无效" }
        require(uri.scheme == "https" || (lab && uri.scheme == "http" && uri.host == "127.0.0.1" && uri.port == 18086)) { "视觉接口必须使用 HTTPS" }
    }

    fun materialize(context: Context) {
        val doc = document(context)
        validate(doc, File(context.filesDir, "labvision.enabled").isFile)
        val dir = File(context.filesDir, "runtime/vision").apply { mkdirs() }
        val output = File(dir, "vision_config.json")
        val temporary = File(dir, ".vision_config.tmp")
        try {
            FileOutputStream(temporary).use { it.write(doc.toString().toByteArray()); it.fd.sync() }
            check(temporary.setReadable(false, false) && temporary.setWritable(false, false))
            check(temporary.setReadable(true, true) && temporary.setWritable(true, true))
            Files.move(temporary.toPath(), output.toPath(), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
            check(JSONObject(output.readText()).toString() == doc.toString()) { "视觉配置写入校验失败" }
        } finally { temporary.delete() }
    }
}
