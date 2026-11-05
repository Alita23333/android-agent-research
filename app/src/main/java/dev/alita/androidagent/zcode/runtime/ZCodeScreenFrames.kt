package dev.alita.androidagent.zcode.runtime

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest
import java.util.UUID

/** Private, bounded live observations. Never an artifact or a durable session attachment. */
class ZCodeScreenFrames(context: Context) {
    private val directory = File(context.filesDir, "runtime/vision/shots")

    @Synchronized fun save(bytes: ByteArray, metadata: JSONObject, session: String): JSONObject {
        require(session.isNotBlank()) { "ui_session_missing" }
        require(bytes.size <= 153600) { "ui_screenshot_too_large" }
        directory.mkdirs()
        val old = index()
        val retained = (0 until old.length()).map { old.getJSONObject(it) }
            .filter { it.optString("sessionId") == session }.takeLast(1)
        val id = "shot_" + UUID.randomUUID().toString().replace("-", "")
        val filename = "$id.jpeg"
        val hash = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        val row = JSONObject(metadata.toString()).put("shotId", id).put("sessionId", session)
            .put("filename", filename).put("sha256", hash).put("bytes", bytes.size)
            .put("capturedAt", System.currentTimeMillis()).put("format", "jpeg")
        writeSynced(File(directory, filename), bytes)
        try {
            val rows = JSONArray().apply { retained.forEach(::put); put(row) }
            writeSynced(File(directory, "index.json.tmp"), rows.toString().toByteArray())
            java.nio.file.Files.move(File(directory, "index.json.tmp").toPath(), File(directory, "index.json").toPath(),
                java.nio.file.StandardCopyOption.ATOMIC_MOVE, java.nio.file.StandardCopyOption.REPLACE_EXISTING)
            check(index().toString() == rows.toString()) { "ui_screenshot_store_failed" }
            val keep = retained.map { it.getString("filename") }.toSet() + filename + "index.json"
            directory.listFiles()?.filter { it.name !in keep }?.forEach { check(it.delete()) }
            return JSONObject(row.toString()).apply { remove("filename"); remove("sessionId") }
        } catch (error: Throwable) { purge(); throw error }
    }

    @Synchronized fun resolve(id: String, session: String): JSONObject? {
        if (!id.matches(Regex("shot_[a-f0-9]{32}"))) return null
        val rows = index()
        return (0 until rows.length()).map { rows.getJSONObject(it) }
            .firstOrNull { it.optString("shotId") == id && it.optString("sessionId") == session }
    }

    @Synchronized fun purge() { directory.listFiles()?.forEach { it.delete() } }
    private fun index(): JSONArray = runCatching { JSONArray(File(directory, "index.json").readText()) }.getOrDefault(JSONArray())
    private fun writeSynced(file: File, bytes: ByteArray) {
        FileOutputStream(file).use { it.write(bytes); it.fd.sync() }
        file.setReadable(false, false); file.setWritable(false, false)
        check(file.setReadable(true, true) && file.setWritable(true, true))
    }
}
