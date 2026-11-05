package dev.alita.androidagent

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.alita.androidagent.skills.CoreSkillPackageStore
import dev.alita.androidagent.skills.SkillAvailability
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** App UID/package storage proof only. Does not start Core or project model-visible skills. */
@RunWith(AndroidJUnit4::class)
class CoreSkillPackageDeviceTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private fun zip(version: Int, vararg extra: Pair<String, ByteArray>): ByteArrayInputStream {
        val data = ByteArrayOutputStream()
        ZipOutputStream(data).use { out ->
            val files = listOf("SKILL.md" to "---\nname: phone-fixture\ndescription: Data only fixture\nversion: $version\n---\nRead references/rule.txt\n".toByteArray(),
                "references/rule.txt" to "rule-$version".toByteArray()) + extra
            files.forEach { (name, bytes) -> out.putNextEntry(ZipEntry(name)); out.write(bytes); out.closeEntry() }
        }
        return ByteArrayInputStream(data.toByteArray())
    }
    private fun rejects(block: () -> Unit) { try { block(); fail("Expected rejection") } catch (_: Exception) {} }
    @Test fun updateReloadRetireKeepsPinnedBytesAndSource() {
        val root = File(context.cacheDir, "skill-package-device-${System.nanoTime()}")
        val store = CoreSkillPackageStore(root)
        val old = store.install(zip(1), "fixture-v1"); val pin = store.pin(old.id)
        val fresh = store.install(zip(2), "fixture-v2")
        assertNotEquals(old.hash, fresh.hash); assertFalse(fresh.enabled)
        assertEquals(SkillAvailability.STORED, fresh.availability)
        val reload = CoreSkillPackageStore(root)
        assertEquals("rule-1", reload.read(pin, "references/rule.txt").decodeToString())
        assertEquals("rule-2", reload.read(reload.pin(old.id), "references/rule.txt").decodeToString())
        reload.retire(old.id); assertTrue(reload.discover().isEmpty())
        assertEquals("rule-1", reload.read(pin, "references/rule.txt").decodeToString())
        assertEquals("fixture-v1", pin.source)
    }
    @Test fun missingDependenciesInertScriptAndTraversalRejected() {
        val root = File(context.cacheDir, "skill-package-device-${System.nanoTime()}")
        val store = CoreSkillPackageStore(root)
        val marker = File(root, "executed")
        val item = store.install(zip(1, "android.yaml" to "runtimes: [python]\npermissions: [root]\n".toByteArray(),
            "scripts/install.sh" to "touch '${marker.absolutePath}'".toByteArray()), "test")
        assertEquals(setOf("runtimes:python", "permissions:root"), item.missingDependencies.toSet())
        assertFalse(marker.exists()); assertFalse(item.enabled); rejects { store.pin(item.id) }
        rejects { store.install(zip(2, "../escape" to byteArrayOf(1)), "bad") }
        assertEquals(item.hash, store.discover().single().hash)
    }
    @Test fun symlinkAndMutatedVersionCannotBeRead() {
        val root = File(context.cacheDir, "skill-package-device-${System.nanoTime()}")
        val store = CoreSkillPackageStore(root); val item = store.install(zip(1), "test")
        val pin = store.pin(item.id)
        val outside = File(context.cacheDir, "skill-outside-${System.nanoTime()}").apply { writeText("outside") }
        java.nio.file.Files.createSymbolicLink(File(item.directory, "references/link").toPath(), outside.toPath())
        rejects { store.read(pin, "references/link") }
        File(item.directory, "references/link").delete()
        File(item.directory, "references/rule.txt").writeText("mutated")
        rejects { store.read(pin, "references/rule.txt") }
    }
}
