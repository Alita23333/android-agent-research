package dev.alita.androidagent.tools

import android.content.Context
import dev.alita.androidagent.core.AgentTool
import dev.alita.androidagent.core.SideEffect
import dev.alita.androidagent.core.ToolDefinition
import dev.alita.androidagent.zcode.adapter.AndroidToolRequest
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.nio.file.StandardCopyOption.ATOMIC_MOVE
import java.nio.file.StandardCopyOption.REPLACE_EXISTING
import java.util.UUID

/** Host review metadata over the existing immutable catalog, never an execution grant or registry.
 * Installation/active selection never writes this store. Only explicit host review selects records.
 */
class ProviderReviewStore internal constructor(
    private val catalog: LocalProviderCatalog,
    private val file: File,
    scopeRoot: File = requireNotNull(file.parentFile),
    private val factory: (LocalProviderDescriptor, List<ToolDefinition>) -> PinnedIsolatedProvider,
) {
    constructor(context: Context, catalog: LocalProviderCatalog) : this(catalog,
        File(context.filesDir, "provider-reviews.json"), context.dataDir.canonicalFile,
        { pin, definitions -> PinnedIsolatedProvider.review(context, catalog, pin, definitions) })

    private val storageRoot = scopeRoot.canonicalFile

    private fun keys(json: JSONObject) = json.keys().asSequence().toSet()
    private fun checkedPath(target: File) {
        var current: File? = target.absoluteFile
        require(target.canonicalFile.toPath().startsWith(storageRoot.toPath())) { "Provider metadata outside owner scope" }
        while (current != null) {
            require(!Files.isSymbolicLink(current.toPath())) { "Provider metadata link refused" }
            // Android's framework-owned /data/user/0 alias may be above dataDir.
            // Reject links inside the fixed owner root, without inspecting its ancestors.
            if (current.canonicalFile == storageRoot) return
            current = current.parentFile
        }
        error("Provider metadata outside owner scope")
    }
    private fun read(): JSONObject {
        checkedPath(file)
        if (!Files.exists(file.toPath(), NOFOLLOW_LINKS)) return JSONObject().put("schemaVersion", 1).put("reviews", JSONArray()).put("selected", JSONArray())
        require(Files.isRegularFile(file.toPath(), NOFOLLOW_LINKS) && file.length() in 1..1048576)
        val json = JSONObject(file.readText(Charsets.UTF_8))
        require(keys(json) == setOf("schemaVersion", "reviews", "selected") && json.get("schemaVersion") == 1)
        require(json.getJSONArray("reviews").length() <= 128 && json.getJSONArray("selected").length() <= 32)
        val seen = mutableSetOf<String>()
        for (value in objects(json.getJSONArray("reviews"))) {
            require(keys(value) == setOf("snapshot", "definitions", "revoked") && value.get("revoked") is Boolean)
            val snapshot = snapshot(value.getJSONObject("snapshot"))
            require(seen.add(key(snapshot))) { "Duplicate provider review" }
            require(value.getJSONArray("definitions").length() in 1..16)
        }
        val selected = objects(json.getJSONArray("selected")).map(::snapshot)
        require(selected.map { it.getString("id").lowercase() }.distinct().size == selected.size)
        val wire = selected.flatMap { strings(it.getJSONArray("toolIds")) }.map { it.replace('.', '_') }
        require(wire.distinct().size == wire.size) { "Carrier tool collision" }
        require(selected.all { pin -> objects(json.getJSONArray("reviews")).any {
            !it.getBoolean("revoked") && same(it.getJSONObject("snapshot"), pin)
        } }) { "Selected provider has no review" }
        return json
    }
    private fun save(json: JSONObject) {
        checkedPath(file); require(file.parentFile!!.mkdirs() || file.parentFile!!.isDirectory)
        val bytes = json.toString().toByteArray(Charsets.UTF_8); require(bytes.size <= 1048576)
        val temporary = File(file.parentFile, ".provider-review-${UUID.randomUUID()}")
        try {
            java.io.FileOutputStream(temporary).use { it.write(bytes); it.fd.sync() }
            checkedPath(file)
            Files.move(temporary.toPath(), file.toPath(), ATOMIC_MOVE, REPLACE_EXISTING)
        } finally { temporary.delete() }
    }
    private fun objects(array: JSONArray) = (0 until array.length()).map { array.getJSONObject(it) }
    private fun strings(array: JSONArray) = (0 until array.length()).map { array.getString(it) }
    private fun same(a: JSONObject, b: JSONObject) = PinnedIsolatedProvider.canonical(a) == PinnedIsolatedProvider.canonical(b)
    private fun key(pin: JSONObject) = listOf("id", "contentHash", "definitionHash").joinToString(":") { pin.getString(it) }
    private fun snapshot(value: JSONObject): JSONObject {
        require(keys(value) == setOf("id", "version", "contentHash", "definitionHash", "toolIds"))
        for (field in listOf("id", "version", "contentHash", "definitionHash")) require(value.get(field) is String)
        val id = value.getString("id")
        require(id.matches(Regex("[a-zA-Z][a-zA-Z0-9_-]{1,48}")) && id.lowercase() !in setOf("device_info", "text_digest", "ui", "workspace", "web"))
        require(value.getString("version").length in 1..128 && value.getString("version").none { it.isISOControl() })
        for (field in listOf("contentHash", "definitionHash")) require(value.getString(field).matches(Regex("[a-f0-9]{64}")))
        val tools = strings(value.getJSONArray("toolIds")); require(tools.size in 1..16 && tools.distinct().size == tools.size)
        require(tools.all { it.startsWith("$id.") && it.removePrefix("$id.").matches(Regex("[A-Za-z][A-Za-z0-9_-]{0,63}")) && !it.replace('.', '_').matches(Regex("(?i)(ui|workspace|web)_.*")) })
        return JSONObject(value.toString())
    }
    private fun definitions(array: JSONArray): List<ToolDefinition> = objects(array).map { value ->
        require(keys(value) == setOf("id", "version", "description", "inputSchema", "capabilities", "sideEffect", "supportsCancellation"))
        require(value.get("supportsCancellation") is Boolean)
        ToolDefinition(value.getString("id"), value.getString("version"), value.getString("description"),
            value.getJSONObject("inputSchema"), strings(value.getJSONArray("capabilities")).toSet(),
            SideEffect.valueOf(value.getString("sideEffect")), value.getBoolean("supportsCancellation"))
    }

    /** Explicit trusted-host review API only. Validates inert bytes/metadata; never spawns. */
    @Synchronized fun preview(pin: LocalProviderDescriptor, declarations: List<ToolDefinition>): PinnedIsolatedProvider =
        factory(pin, declarations)

    @Synchronized fun review(pin: LocalProviderDescriptor, declarations: List<ToolDefinition>): PinnedIsolatedProvider {
        val provider = preview(pin, declarations)
        val snap = snapshot(provider.sessionSnapshot()); val json = read()
        val reviews = objects(json.getJSONArray("reviews")).filterNot { key(it.getJSONObject("snapshot")) == key(snap) }
        require(reviews.size < 128)
        val selected = objects(json.getJSONArray("selected")).filterNot { it.getString("id").equals(pin.id, true) } + snap
        require(selected.size <= 32)
        val wire = selected.flatMap { strings(it.getJSONArray("toolIds")) }.map { it.replace('.', '_') }
        require(wire.distinct().size == wire.size) { "Carrier tool collision" }
        json.put("reviews", JSONArray(reviews + JSONObject().put("snapshot", snap).put("definitions", provider.declarations()).put("revoked", false)))
            .put("selected", JSONArray(selected))
        save(json)
        return provider
    }
    @Synchronized fun selectedSnapshots(): List<JSONObject> = objects(read().getJSONArray("selected")).map {
        resolve(it); snapshot(it)
    }
    /** Identity-only UI projection; not a validation or execution grant. */
    @Synchronized fun selectedIdentities(): List<JSONObject> = objects(read().getJSONArray("selected")).map(::snapshot)
    @Synchronized fun resolve(value: JSONObject): PinnedIsolatedProvider {
        val pin = snapshot(value)
        val entry = objects(read().getJSONArray("reviews")).singleOrNull { same(it.getJSONObject("snapshot"), pin) && !it.getBoolean("revoked") }
            ?: throw IllegalArgumentException("Provider review unavailable")
        val provider = factory(catalog.pinned(pin.getString("id"), pin.getString("contentHash")), definitions(entry.getJSONArray("definitions")))
        require(same(provider.sessionSnapshot(), pin)) { "Reviewed declaration or package identity changed" }
        return provider
    }
    @Synchronized fun verify(pin: JSONObject): Boolean = runCatching { resolve(pin); true }.getOrDefault(false)
    @Synchronized fun retire(id: String) {
        val json = read(); json.put("selected", JSONArray(objects(json.getJSONArray("selected")).filterNot { it.getString("id") == id })); save(json)
    }
    @Synchronized fun revoke(value: JSONObject) {
        val pin = snapshot(value); val json = read()
        objects(json.getJSONArray("reviews")).filter { same(it.getJSONObject("snapshot"), pin) }.forEach { it.put("revoked", true) }
        json.put("selected", JSONArray(objects(json.getJSONArray("selected")).filterNot { same(it, pin) })); save(json)
    }

    /** Reads the same host-owned session index as Node; caller metadata cannot select a version. */
    fun resolveSession(request: AndroidToolRequest, index: File, workspaceRoot: File): AgentTool {
        checkedPath(index); checkedPath(workspaceRoot)
        require(Files.isRegularFile(index.toPath(), NOFOLLOW_LINKS) && index.length() in 1..1048576)
        val session = requireNotNull(request.sessionId); require(session.matches(Regex("[A-Za-z0-9_-]{1,128}")))
        val rows = objects(JSONArray(index.readText(Charsets.UTF_8)))
        val row = rows.single { it.getString("sessionId") == session }
        require(row.get("managedProviderBindingVersion") == 1)
        val workspace = File(row.getString("managedProviderWorkspace")); checkedPath(workspace)
        require(workspace.isDirectory && workspace.canonicalPath.startsWith(workspaceRoot.canonicalPath + File.separator))
        val pins = objects(row.getJSONArray("managedProviders")); require(pins.size <= 32)
        val pin = snapshot(pins.single { strings(it.getJSONArray("toolIds")).contains(request.toolId) })
        require(request.metadata.optString("providerContentHash") == pin.getString("contentHash") &&
            request.metadata.optString("providerDefinitionHash") == pin.getString("definitionHash"))
        return runBlocking { resolve(pin).tools().single { it.definition.id == request.toolId } }
    }
}
