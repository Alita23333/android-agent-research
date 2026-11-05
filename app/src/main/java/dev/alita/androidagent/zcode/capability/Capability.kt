package dev.alita.androidagent.zcode.capability

import org.json.JSONArray
import org.json.JSONObject

/**
 * Phase 3 capability framework (ARCHITECTURE §3/§9).
 *
 * The Agent Core asks for a CAPABILITY and the resolver picks a provider —
 * never "is this device rooted". Providers report availability, scope,
 * limitations, privilege level and runtime health; the same capability id can
 * be satisfied by different providers on different devices.
 */
object Capability {
    /** Canonical capability ids (REQUIREMENTS §9 groups; extend as phases land). */
    val SHELL_APP = "shell.app"
    val SHELL_SHELL_UID = "shell.shell_uid"
    val SHELL_ROOT = "shell.root"
    val FS_WORKSPACE = "filesystem.workspace"
    val FS_SHARED = "filesystem.shared"
    val FS_APP_PRIVATE = "filesystem.app_private"
    val FS_SYSTEM = "filesystem.system"
    val UI_ACCESSIBILITY = "ui.accessibility"
    val SCREEN_CAPTURE = "screen.capture"
    val VISION_INVOKE = "vision.invoke"
    val PACKAGE_MANAGE = "package.manage"
    val PROCESS_INSPECT = "process.inspect"
    val NETWORK_WEB = "network.web"
}

enum class Availability { AVAILABLE, PENDING, UNAVAILABLE, UNKNOWN }

/** One capability as reported by one provider. */
data class CapabilityDescriptor(
    val capabilityId: String,
    val providerId: String,
    val availability: Availability,
    /** What the capability can reach through THIS provider (human-readable). */
    val scope: String,
    /** Known constraints (e.g. "SAF grants only", "MediaProjection consent"). */
    val limitations: String,
    /** app | shell | root — privilege tier of this provider. */
    val privilege: String,
    /** Side-effect class for the future Tool Gateway risk engine. */
    val sideEffectClass: String,
    /** Health note from the last probe (timestamped freshness is provider-side). */
    val health: String
) {
    fun toJson(): JSONObject = JSONObject()
        .put("capabilityId", capabilityId)
        .put("providerId", providerId)
        .put("availability", availability.name)
        .put("scope", scope)
        .put("limitations", limitations)
        .put("privilege", privilege)
        .put("sideEffectClass", sideEffectClass)
        .put("health", health)
}

/**
 * A provider satisfies one or more capabilities. Probes must be cheap and
 * side-effect free; refresh() re-runs availability probes.
 */
interface CapabilityProvider {
    /** Stable provider id, e.g. "standard-android", "shizuku", "root". */
    val id: String
    /** One descriptor per capability this provider can satisfy. */
    fun descriptors(): List<CapabilityDescriptor>
    /** Re-probe runtime state ( binder alive, su present, service enabled…). */
    fun refresh()
}

/**
 * Resolves capability requests to a provider WITHOUT the caller knowing which
 * provider answers. Preference order per capability: AVAILABLE beats PENDING
 * beats UNKNOWN beats UNAVAILABLE; among equals, lower privilege wins (least
 * privilege principle — an app-tier answer is preferred over root when both
 * can satisfy the capability).
 */
class CapabilityResolver(providers: List<CapabilityProvider>) {

    private val providers = ArrayList(providers)

    private val privilegeRank = mapOf("app" to 0, "shell" to 1, "root" to 2)
    private val availabilityRank = mapOf(
        Availability.AVAILABLE to 0,
        Availability.PENDING to 1,
        Availability.UNKNOWN to 2,
        Availability.UNAVAILABLE to 3,
    )

    fun resolve(capabilityId: String): CapabilityDescriptor? =
        providers.flatMap { it.descriptors() }
            .filter { it.capabilityId == capabilityId }
            .minWithOrNull(
                compareBy(
                    { availabilityRank[it.availability] ?: 9 },
                    { privilegeRank[it.privilege] ?: 9 },
                )
            )

    fun resolveAll(): Map<String, CapabilityDescriptor> {
        val out = LinkedHashMap<String, CapabilityDescriptor>()
        for (d in providers.flatMap { it.descriptors() }) {
            val cur = out[d.capabilityId]
            if (cur == null || better(d, cur)) out[d.capabilityId] = d
        }
        return out
    }

    /** Every provider's view — for the UI's capability panel. */
    fun allDescriptors(): List<CapabilityDescriptor> =
        providers.flatMap { it.descriptors() }.sortedBy { it.capabilityId }

    fun refreshAll() = providers.forEach { it.refresh() }

    private fun better(a: CapabilityDescriptor, b: CapabilityDescriptor): Boolean {
        val aa = availabilityRank[a.availability] ?: 9
        val ba = availabilityRank[b.availability] ?: 9
        if (aa != ba) return aa < ba
        return (privilegeRank[a.privilege] ?: 9) < (privilegeRank[b.privilege] ?: 9)
    }

    fun toJson(): JSONObject {
        val all = JSONArray()
        allDescriptors().forEach { all.put(it.toJson()) }
        val resolved = JSONObject()
        resolveAll().forEach { (k, v) -> resolved.put(k, v.toJson()) }
        return JSONObject()
            .put("providers", JSONArray(providers.map { it.id }))
            .put("all", all)
            .put("resolved", resolved)
            .put("generatedAt", System.currentTimeMillis())
    }
}
