package dev.alita.androidagent.tools

import dev.alita.androidagent.core.SideEffect
import dev.alita.androidagent.core.ToolDefinition
import dev.alita.androidagent.core.ToolRegistry
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import java.util.UUID

data class ProviderAdmissionCandidate(
    val id: String, val version: String, val contentHash: String, val entry: String,
    val selectedContentHash: String?, val selectedDefinitionHash: String?, val selectedToolIds: List<String>,
    val available: Boolean = true, val selectedAvailable: Boolean = true,
)

data class ProviderAdmissionDraft(
    val id: String, val version: String, val contentHash: String, val entry: String,
    val toolName: String, val toolVersion: String, val description: String, val definitionHash: String,
)

/** UI/lifecycle coordination over the existing review store and registry, not an authorization loop.
 * No command is spawned by preview, approve or restore; per-call Gateway is still mandatory.
 */
class ProviderAdmissionController(
    private val catalog: LocalProviderCatalog,
    private val reviews: ProviderReviewStore,
    private val registry: ToolRegistry,
) {
    private var owner: String? = null
    private val installed = mutableSetOf<String>()
    private val reserved = setOf("device_info", "text_digest", "ui", "workspace", "web")

    @Synchronized fun hostActive(): Boolean = owner != null
    private fun stopped() { check(owner == null) { "请先停止 Agent，再修改工具；重新打开后生效" } }

    @Synchronized fun candidates(): List<ProviderAdmissionCandidate> {
        val selected = reviews.selectedIdentities().associateBy { it.getString("id") }
        val discovered = catalog.discover().filter { it.id.lowercase() !in reserved }
        val items = discovered.map { item ->
            val pin = selected[item.id]
            ProviderAdmissionCandidate(item.id, item.version, item.directory.name, item.command.joinToString(" "),
                pin?.getString("contentHash"), pin?.getString("definitionHash"),
                pin?.getJSONArray("toolIds")?.let { a -> (0 until a.length()).map { a.getString(it) } }.orEmpty(),
                selectedAvailable = pin == null || reviews.verify(pin))
        }
        // Broken selected bytes must remain visible so the user can retire/revoke them.
        return (items + selected.filterKeys { id -> discovered.none { it.id == id } }.map { (id, pin) ->
            ProviderAdmissionCandidate(id, pin.getString("version"), pin.getString("contentHash"), "包不可用；可停用或撤销所选版本",
                pin.getString("contentHash"), pin.getString("definitionHash"),
                pin.getJSONArray("toolIds").let { a -> (0 until a.length()).map { a.getString(it) } },
                available = false, selectedAvailable = reviews.verify(pin))
        }).sortedBy { it.id }
    }

    private fun current(id: String, hash: String): LocalProviderDescriptor {
        require(id.lowercase() !in reserved) { "内置工具不能通过导入评审修改" }
        val candidate = catalog.discover().singleOrNull { it.id == id }
        require(candidate?.directory?.name == hash) { "工具包已更新或不可用，请重新检查" }
        return catalog.pinned(id, hash)
    }
    private fun declaration(id: String, name: String, version: String, description: String): ToolDefinition {
        require(name.matches(Regex("[A-Za-z][A-Za-z0-9_-]{0,63}"))) { "工具名称仅支持字母、数字、下划线和连字符" }
        require(version.length in 1..128 && version.none { it.isISOControl() }) { "工具版本无效" }
        require(description.isNotBlank() && description.length <= 4096 && description.none { it == '\u0000' }) { "请填写用途说明（最多4096字）" }
        return ToolDefinition("$id.$name", version, description, PinnedIsolatedProvider.inputSchema(),
            setOf("data-transform"), SideEffect.NONE, true)
    }

    @Synchronized fun preview(id: String, contentHash: String, toolName: String, toolVersion: String, description: String): ProviderAdmissionDraft {
        stopped()
        val item = current(id, contentHash)
        val provider = reviews.preview(item, listOf(declaration(id, toolName, toolVersion, description)))
        checkCollisions(provider)
        return ProviderAdmissionDraft(id, item.version, contentHash, item.command.joinToString(" "),
            toolName, toolVersion, description, provider.definitionHash)
    }

    @Synchronized fun approve(draft: ProviderAdmissionDraft) {
        stopped()
        val checked = preview(draft.id, draft.contentHash, draft.toolName, draft.toolVersion, draft.description)
        require(checked == draft) { "评审内容或工具包已变化，请重新检查" }
        reviews.review(current(draft.id, draft.contentHash), listOf(declaration(draft.id, draft.toolName, draft.toolVersion, draft.description)))
        // Only durable selection changes here. Carrier visibility changes at the next host start.
    }

    @Synchronized fun retire(id: String) { stopped(); reviews.retire(id) }
    @Synchronized fun revoke(id: String, contentHash: String, definitionHash: String) {
        stopped()
        val pin = reviews.selectedIdentities().single { it.getString("id") == id &&
            it.getString("contentHash") == contentHash && it.getString("definitionHash") == definitionHash }
        reviews.revoke(pin)
    }

    private fun checkCollisions(provider: PinnedIsolatedProvider) {
        val own = runBlocking { provider.tools() }.map { it.definition.id }
        require(own.none { registry.find(it) != null && provider.providerId !in installed }) { "工具名称与已注册工具冲突" }
        val others = registry.definitions().filter { it.id !in own }.map { it.id.replace('.', '_') }.toSet()
        require(own.none { it.replace('.', '_') in others }) { "工具名称与已注册工具冲突" }
        // The existing review store additionally validates cross-selected provider wire IDs on save.
    }

    /** Held for the entire supervisor lifetime, including crash backoff; UI cannot race startup. */
    @Synchronized fun beginHost(): HostLease {
        stopped(); val token = UUID.randomUUID().toString(); owner = token
        return HostLease(token)
    }

    inner class HostLease internal constructor(private val token: String) : AutoCloseable {
        fun restore() = synchronized(this@ProviderAdmissionController) {
            check(owner == token) { "Provider host lease expired" }
            val providers = reviews.selectedSnapshots().map(reviews::resolve)
            providers.forEach(::checkCollisions)
            // Fully resolve before touching visibility. These providers never spawn on tools().
            try {
                runBlocking { providers.forEach { registry.replace(it); installed.add(it.providerId) } }
            } catch (error: Exception) {
                runBlocking { installed.toList().forEach { registry.removeProvider(it); installed.remove(it) } }
                throw error
            }
        }
        /** Caller must establish Node and worker quiescence before releasing this lease. */
        override fun close() = synchronized(this@ProviderAdmissionController) {
            if (owner != token) return@synchronized
            runBlocking { installed.toList().forEach { registry.removeProvider(it); installed.remove(it) } }
            owner = null
        }
    }
}
