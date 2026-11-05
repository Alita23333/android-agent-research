package dev.alita.androidagent.zcode.capability

import android.content.Context

/**
 * Always-present baseline provider: the standard Android app sandbox
 * (REQUIREMENTS §1 tier 1). Everything here is available by construction on
 * any device; runtime states that need a user grant are PENDING, not
 * UNAVAILABLE — the grant can still make them available.
 */
class StandardAndroidProvider(private val context: Context) : CapabilityProvider {

    override val id = "standard-android"

    private var workspaceOk = false
    private var sharedOk = false

    override fun refresh() {
        workspaceOk = context.filesDir.isDirectory && context.filesDir.canWrite()
        // shared storage: legacy external storage state; scoped-storage SAF always possible
        sharedOk = android.os.Environment.getExternalStorageDirectory() != null
    }

    override fun descriptors(): List<CapabilityDescriptor> {
        refresh()
        return listOf(
            CapabilityDescriptor(
                capabilityId = Capability.SHELL_APP,
                providerId = id,
                availability = Availability.AVAILABLE,
                scope = "app-uid shell via the APK-owned bash (sandbox filesystem, toybox utilities)",
                limitations = "no system-wide commands; W^X restricts exec to nativeLibraryDir binaries",
                privilege = "app",
                sideEffectClass = "SHELL_EXEC",
                health = if (workspaceOk) "ok" else "filesDir not writable",
            ),
            CapabilityDescriptor(
                capabilityId = Capability.FS_WORKSPACE,
                providerId = id,
                availability = if (workspaceOk) Availability.AVAILABLE else Availability.UNAVAILABLE,
                scope = "app-private workspace directory tree",
                limitations = "app-private only; SAF needed outside",
                privilege = "app",
                sideEffectClass = "FS_RW",
                health = if (workspaceOk) "ok" else "filesDir not writable",
            ),
            CapabilityDescriptor(
                capabilityId = Capability.FS_SHARED,
                providerId = id,
                availability = if (sharedOk) Availability.AVAILABLE else Availability.PENDING,
                scope = "shared storage via MediaStore/SAF grants",
                limitations = "per-grant access (SAF); no raw path semantics",
                privilege = "app",
                sideEffectClass = "FS_RW",
                health = "probe-ok",
            ),
            CapabilityDescriptor(
                capabilityId = Capability.NETWORK_WEB,
                providerId = id,
                availability = Availability.AVAILABLE,
                scope = "outbound http(s) through the app network stack",
                limitations = "subject to Android network permissions",
                privilege = "app",
                sideEffectClass = "NETWORK",
                health = "ok",
            ),
        )
    }
}

/** Accessibility tier (Phase 8 fills the real service; Phase 3 reports state). */
class AccessibilityProvider(private val context: Context) : CapabilityProvider {
    override val id = "accessibility"

    private fun serviceEnabled(): Boolean = try {
        val setting = android.provider.Settings.Secure.getString(
            context.contentResolver, "enabled_accessibility_services"
        ) ?: return false
        setting.split(':').any { it.contains(context.packageName, ignoreCase = true) }
    } catch (_: Throwable) { false }

    override fun refresh() {}

    override fun descriptors(): List<CapabilityDescriptor> = listOf(
        CapabilityDescriptor(
            capabilityId = Capability.UI_ACCESSIBILITY,
            providerId = id,
            availability = if (serviceEnabled()) Availability.AVAILABLE else Availability.PENDING,
            scope = "semantic accessibility tree of the foreground app",
            limitations = "requires the user to enable the accessibility service in system settings",
            privilege = "app",
            sideEffectClass = "UI_ACTUATION",
            health = if (serviceEnabled()) "service enabled" else "service not enabled (PENDING user grant)",
        )
    )
}

/** Phase9 accessibility capture. MediaProjection remains a separate future provider. */
class ScreenCaptureProvider : CapabilityProvider {
    override val id = "screen-capture"

    override fun refresh() {}

    override fun descriptors(): List<CapabilityDescriptor> = listOf(
        CapabilityDescriptor(
            capabilityId = Capability.SCREEN_CAPTURE,
            providerId = id,
            availability = if (android.os.Build.VERSION.SDK_INT < 34) Availability.UNAVAILABLE else if (dev.alita.androidagent.device.AgentAccessibilityService.instance?.serviceInfo?.capabilities
                ?.and(android.accessibilityservice.AccessibilityServiceInfo.CAPABILITY_CAN_TAKE_SCREENSHOT) != 0 &&
                dev.alita.androidagent.device.AgentAccessibilityService.instance != null) Availability.AVAILABLE else Availability.PENDING,
            scope = "compressed active-window frames via Accessibility API 34+; display-coordinate padding",
            limitations = "secure windows, black frames, magnification and stale geometry refused; MediaProjection deferred",
            privilege = "app",
            sideEffectClass = "PRIVACY_SENSITIVE_READ",
            health = if (dev.alita.androidagent.device.AgentAccessibilityService.instance != null) "service connected; re-probed per request" else "enable Accessibility service",
        )
    )
}

class VisionProvider(private val context: Context) : CapabilityProvider {
    override val id = "configured-vision"
    override fun refresh() {}
    override fun descriptors(): List<CapabilityDescriptor> {
        val config = runCatching { dev.alita.androidagent.zcode.runtime.ZCodeVisionConfigWriter.load(context) }.getOrNull()
        val ready = config?.enabled == true && config.baseUrl.isNotBlank() && config.modelId.isNotBlank()
        return listOf(CapabilityDescriptor(Capability.VISION_INVOKE, id,
            if (ready) Availability.AVAILABLE else Availability.PENDING,
            "explicit image interpretation using configured provider; text and coordinates returned to chat",
            "requires image-capable provider; network authorization, public egress and budgets rechecked per request",
            "app", "NETWORK", if (ready) "configured; provider capability validated by actual request" else "configure Vision in Settings"))
    }
}
