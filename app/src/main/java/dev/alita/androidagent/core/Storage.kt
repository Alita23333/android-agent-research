package dev.alita.androidagent.core

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.util.UUID

enum class RunStatus { QUEUED, RUNNING, WAITING_APPROVAL, WAITING_USER, COMPLETED, FAILED, CANCELLED }

data class RunRecord(val id: String, val goal: String, val status: RunStatus, val createdAt: Long, val updatedAt: Long)
data class RunEvent(val id: Long, val runId: String, val type: String, val payload: JSONObject, val createdAt: Long)

interface RunStore {
    fun create(goal: String): RunRecord
    fun updateStatus(runId: String, status: RunStatus)
    fun append(runId: String, type: String, payload: JSONObject = JSONObject())
    fun events(runId: String): List<RunEvent>
    fun recentRuns(limit: Int = 50): List<RunRecord>
}

class SqliteRunStore(context: Context) : SQLiteOpenHelper(context, "agent-runs.db", null, 1), RunStore {
    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("CREATE TABLE runs(id TEXT PRIMARY KEY, goal TEXT NOT NULL, status TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)")
        db.execSQL("CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, type TEXT NOT NULL, payload TEXT NOT NULL, created_at INTEGER NOT NULL)")
        db.execSQL("CREATE INDEX events_run_id ON events(run_id, id)")
    }
    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit

    override fun create(goal: String): RunRecord {
        val now = System.currentTimeMillis()
        val record = RunRecord(UUID.randomUUID().toString(), goal, RunStatus.QUEUED, now, now)
        writableDatabase.insertOrThrow("runs", null, ContentValues().apply {
            put("id", record.id); put("goal", goal); put("status", record.status.name)
            put("created_at", now); put("updated_at", now)
        })
        append(record.id, "run.created", JSONObject().put("goal", goal))
        return record
    }

    override fun updateStatus(runId: String, status: RunStatus) {
        writableDatabase.beginTransaction()
        try {
            writableDatabase.update("runs", ContentValues().apply {
                put("status", status.name); put("updated_at", System.currentTimeMillis())
            }, "id=?", arrayOf(runId))
            append(runId, "run.status", JSONObject().put("status", status.name))
            writableDatabase.setTransactionSuccessful()
        } finally { writableDatabase.endTransaction() }
    }

    override fun append(runId: String, type: String, payload: JSONObject) {
        writableDatabase.insertOrThrow("events", null, ContentValues().apply {
            put("run_id", runId); put("type", type); put("payload", payload.toString()); put("created_at", System.currentTimeMillis())
        })
    }

    override fun events(runId: String): List<RunEvent> = readableDatabase.query(
        "events", arrayOf("id", "run_id", "type", "payload", "created_at"), "run_id=?", arrayOf(runId), null, null, "id ASC"
    ).use { cursor ->
        buildList {
            while (cursor.moveToNext()) add(RunEvent(cursor.getLong(0), cursor.getString(1), cursor.getString(2), JSONObject(cursor.getString(3)), cursor.getLong(4)))
        }
    }

    override fun recentRuns(limit: Int): List<RunRecord> = readableDatabase.query(
        "runs", arrayOf("id", "goal", "status", "created_at", "updated_at"), null, null, null, null, "updated_at DESC", limit.toString()
    ).use { cursor ->
        buildList {
            while (cursor.moveToNext()) add(RunRecord(cursor.getString(0), cursor.getString(1), RunStatus.valueOf(cursor.getString(2)), cursor.getLong(3), cursor.getLong(4)))
        }
    }
}

class FileArtifactStore(context: Context) : ArtifactStore {
    private val root = File(context.filesDir, "artifacts").apply { mkdirs() }

    override fun create(runId: String, name: String, mimeType: String, bytes: ByteArray): ArtifactRef {
        val safeName = name.replace(Regex("[^a-zA-Z0-9._-]"), "_").take(100).ifBlank { "artifact" }
        val directory = File(root, runId).apply { mkdirs() }
        val id = sha256(bytes).take(16)
        val file = File(directory, "${id}_$safeName")
        file.writeBytes(bytes)
        return ArtifactRef(id, safeName, mimeType, file.absolutePath, bytes.size.toLong())
    }

    private fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(bytes).joinToString("") { "%02x".format(it) }
}
