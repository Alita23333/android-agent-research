package dev.alita.androidagent.zcode.capability

import android.content.Context

/**
 * Shizuku provider (Phase 3 stub — real binder integration is Phase 10).
 * Presence probe only: is the Shizuku app installed / is the binder alive.
 * A missing Shizuku is UNAVAILABLE (not PENDING): the user must install it.
 */
class ShizukuProvider(private val context: Context) : CapabilityProvider {

    override val id = "shizuku"

    private var installed = false
    private var binderAlive = false

    override fun refresh() {
        installed = try {
            context.packageManager.getPackageInfo("moe.shizuku.privileged.api", 0)
            true
        } catch (_: Throwable) {
            try {
                context.packageManager.getPackageInfo("rikka.shizuku", 0)
                true
            } catch (_: Throwable) { false }
        }
        // binder liveness needs the Shizuku API dependency (Phase 10); a
        // started Shizuku exposes a binder through a content provider trick —
        // approximated here by the installed flag only, honestly reported.
        binderAlive = installed
    }

    override fun descriptors(): List<CapabilityDescriptor> {
        refresh()
        val availability = when {
            !installed -> Availability.UNAVAILABLE
            binderAlive -> Availability.PENDING // installed; binder handshake lands in Phase 10
            else -> Availability.PENDING
        }
        val note = when {
            !installed -> "Shizuku app not installed"
            else -> "installed; activation + binder handshake pending (Phase 10)"
        }
        return listOf(
            CapabilityDescriptor(
                capabilityId = Capability.SHELL_SHELL_UID,
                providerId = id,
                availability = availability,
                scope = "shell-uid (adb-tier) commands: pm/dumpsys/am/settings, package ops",
                limitations = "requires Shizuku app + activation (wireless debugging or root); breaks when Shizuku stops",
                privilege = "shell",
                sideEffectClass = "SHELL_EXEC",
                health = note,
            ),
            CapabilityDescriptor(
                capabilityId = Capability.PACKAGE_MANAGE,
                providerId = id,
                availability = availability,
                scope = "package install/uninstall/query at shell privilege",
                limitations = "same Shizuku activation constraints",
                privilege = "shell",
                sideEffectClass = "PRIVILEGED_WRITE",
                health = note,
            ),
        )
    }
}

/**
 * Root provider (Phase 3 stub — full integration is Phase 11). Real probe:
 * is a `su` binary resolvable and willing to answer (non-interactive -c id).
 */
class RootProvider : CapabilityProvider {

    override val id = "root"

    private var suPresent = false
    private var grantable = false

    override fun refresh() {
        suPresent = listOf("/system/bin/su", "/system/xbin/su", "/sbin/su", "/su/bin/su", "/system/sbin/su")
            .any { java.io.File(it).canExecute() }
        grantable = false
        if (suPresent) {
            try {
                val p = ProcessBuilder(listOf("su", "-c", "id")).redirectErrorStream(true).start()
                val out = p.inputStream.bufferedReader().readText()
                p.waitFor()
                grantable = out.contains("uid=0")
            } catch (_: Throwable) {
            }
        }
    }

    override fun descriptors(): List<CapabilityDescriptor> {
        refresh()
        val availability = when {
            grantable -> Availability.AVAILABLE
            suPresent -> Availability.PENDING
            else -> Availability.UNAVAILABLE
        }
        val note = when {
            grantable -> "su grants non-interactively (uid=0 verified)"
            suPresent -> "su present but requires interactive grant"
            else -> "no su binary on PATH"
        }
        return listOf(
            CapabilityDescriptor(
                capabilityId = Capability.SHELL_ROOT,
                providerId = id,
                availability = availability,
                scope = "root shell: /proc, /sys, app-private data of other apps, system/vendor/product trees",
                limitations = "magisk-style grants may be per-app; unknown commands get stricter policy upstream",
                privilege = "root",
                sideEffectClass = "SHELL_EXEC_HIGH_PRIVILEGE",
                health = note,
            ),
            CapabilityDescriptor(
                capabilityId = Capability.FS_SYSTEM,
                providerId = id,
                availability = availability,
                scope = "read system/vendor/product partitions; write where overlays permit",
                limitations = "verity/overlay constraints per ROM",
                privilege = "root",
                sideEffectClass = "PRIVILEGED_WRITE",
                health = note,
            ),
            CapabilityDescriptor(
                capabilityId = Capability.PROCESS_INSPECT,
                providerId = id,
                availability = availability,
                scope = "full process table, /proc of any uid",
                limitations = "kernel hideproc variants may mask entries",
                privilege = "root",
                sideEffectClass = "READ_ONLY",
                health = note,
            ),
        )
    }
}

