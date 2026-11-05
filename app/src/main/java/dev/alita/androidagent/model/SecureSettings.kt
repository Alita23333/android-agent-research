package dev.alita.androidagent.model

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

data class ModelSettings(
    val baseUrl: String,
    val apiKey: String,
    val model: String,
)

class SecureSettings(context: Context) {
    private val preferences = context.getSharedPreferences("agent-settings", Context.MODE_PRIVATE)
    private val alias = "android-agent-api-key"

    fun load(): ModelSettings = ModelSettings(
        baseUrl = preferences.getString("baseUrl", "https://api.openai.com/v1")!!,
        apiKey = decrypt(preferences.getString("apiKey", null)).orEmpty(),
        model = preferences.getString("model", "")!!,
    )

    fun save(settings: ModelSettings) {
        val saved = preferences.edit()
            .putString("baseUrl", settings.baseUrl.trim())
            .putString("model", settings.model.trim())
            .putString("apiKey", encrypt(settings.apiKey.trim()))
            .commit()
        check(saved) { "Unable to persist model settings" }
    }

    /** Keystore-backed storage used by runtime adapters for additional BYOK secrets. */
    fun getSecret(name: String): String? = decrypt(preferences.getString(secretKey(name), null))

    fun putSecret(name: String, value: String) {
        require(name.matches(Regex("[A-Za-z0-9_.:-]{1,120}"))) { "Invalid secret name" }
        val saved = preferences.edit().putString(secretKey(name), encrypt(value)).commit()
        check(saved) { "Unable to persist secret" }
    }

    fun deleteSecret(name: String) {
        val saved = preferences.edit().remove(secretKey(name)).commit()
        check(saved) { "Unable to delete secret" }
    }

    private fun secretKey(name: String): String {
        require(name.matches(Regex("[A-Za-z0-9_.:-]{1,120}"))) { "Invalid secret name" }
        return "secret.$name"
    }

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(alias, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").run {
            init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .build())
            generateKey()
        }
    }

    private fun encrypt(plain: String): String {
        if (plain.isEmpty()) return ""
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val combined = cipher.iv + cipher.doFinal(plain.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(combined, Base64.NO_WRAP)
    }

    private fun decrypt(encoded: String?): String? = runCatching {
        if (encoded.isNullOrEmpty()) return null
        val combined = Base64.decode(encoded, Base64.NO_WRAP)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, combined.copyOfRange(0, 12)))
        cipher.doFinal(combined.copyOfRange(12, combined.size)).toString(Charsets.UTF_8)
    }.getOrNull()
}
