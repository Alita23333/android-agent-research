package dev.alita.androidagent

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import dev.alita.androidagent.skills.*
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.json.JSONObject

@RunWith(RobolectricTestRunner::class)
@Config(application = Application::class, sdk = [35])
class CoreSkillPackageStoreTest {
    private val context: Application = ApplicationProvider.getApplicationContext()
    private fun store(inventory: () -> SkillDependencyInventory = { SkillDependencyInventory() }) =
        CoreSkillPackageStore(File(context.cacheDir, "skill-package-${System.nanoTime()}"), inventory)
    private fun archive(vararg files: Pair<String, ByteArray>): ByteArrayInputStream {
        val bytes = ByteArrayOutputStream()
        ZipOutputStream(bytes).use { zip -> files.forEach { (name, data) -> zip.putNextEntry(ZipEntry(name)); zip.write(data); zip.closeEntry() } }
        return ByteArrayInputStream(bytes.toByteArray())
    }
    private fun skill(version: String = "1", extra: String = "") =
        "---\nname: example\ndescription: Example guided task\nversion: $version\n$extra---\nRead references/rule.txt; never execute during import.\n".toByteArray()
    private fun install(store: CoreSkillPackageStore, version: String = "1", rule: String = "old", extra: String = "") =
        store.install(archive("wrapper/SKILL.md" to skill(version, extra), "wrapper/references/rule.txt" to rule.toByteArray()), "content://fixture/$version")
    private fun rejects(block: () -> Unit) { try { block(); fail("Expected rejection") } catch (_: Exception) {} }

    @Test fun publishedSelectionRequiresEnableAndUpdatesKeepOldVersions() {
        val base = File(context.cacheDir, "skill-inventory-${System.nanoTime()}").apply { mkdirs() }
        val inventory = File(base, "inventory.json")
        val store = CoreSkillPackageStore(File(base, "packages"), inventoryFile = inventory)
        val first = install(store)
        fun published() = JSONObject(inventory.readText()).getJSONArray("packages").getJSONObject(0)
        assertFalse(published().getBoolean("enabled"))
        store.setEnabled(first.id, true)
        assertTrue(published().getBoolean("enabled"))
        assertTrue(store.discover().single().enabled)
        val second = install(store, "2", "new")
        assertFalse(published().getBoolean("enabled"))
        assertEquals(second.hash, published().getString("candidate"))
        assertEquals(2, published().getJSONArray("versions").length())
        store.setEnabled(first.id, true)
        install(store, "2", "new")
        assertTrue(published().getBoolean("enabled"))
        store.retire(first.id)
        assertTrue(published().getBoolean("removed")); assertFalse(published().getBoolean("enabled"))
        assertEquals(2, published().getJSONArray("versions").length())
        assertEquals("old", store.read(CoreSkillPackageStore.Pin(first.id, first.hash, first.version, first.source), "references/rule.txt").decodeToString())
    }

    @Test fun unavailablePackagesCannotBeEnabledOrPublishedAsAvailable() {
        val base = File(context.cacheDir, "skill-inventory-dependency-${System.nanoTime()}").apply { mkdirs() }
        val inventory = File(base, "inventory.json")
        val store = CoreSkillPackageStore(File(base, "packages"), inventoryFile = inventory)
        val item = store.install(archive("SKILL.md" to skill(), "android.yaml" to "permissions: [root]\n".toByteArray()), "test")
        rejects { store.setEnabled(item.id, true) }
        val pkg = JSONObject(inventory.readText()).getJSONArray("packages").getJSONObject(0)
        assertFalse(pkg.getBoolean("enabled"))
        assertFalse(pkg.getJSONArray("versions").getJSONObject(0).getBoolean("available"))
        assertEquals("permissions:root", pkg.getJSONArray("versions").getJSONObject(0).getJSONArray("missingDependencies").getString(0))
    }

    @Test fun versionsPinsProvenanceAndRetirementSurviveReload() {
        val root = File(context.cacheDir, "skill-reload-${System.nanoTime()}")
        val store = CoreSkillPackageStore(root)
        val old = install(store); val pin = store.pin(old.id)
        val newer = install(store, "2", "new")
        assertNotEquals(old.hash, newer.hash)
        assertEquals("old", store.read(pin, "references/rule.txt").decodeToString())
        val reloaded = CoreSkillPackageStore(root)
        assertEquals("new", reloaded.read(reloaded.pin("example"), "references/rule.txt").decodeToString())
        assertEquals("content://fixture/1", pin.source)
        reloaded.retire("example"); assertTrue(reloaded.discover().isEmpty())
        assertEquals("old", reloaded.read(pin, "references/rule.txt").decodeToString())
        rejects { reloaded.pin("example") }
        assertFalse(old.enabled); assertEquals(SkillAvailability.STORED, old.availability)
    }
    @Test fun identicalImportPreservesOriginAndVersionTamperFails() {
        val store = store(); val first = install(store)
        val second = store.install(archive("SKILL.md" to skill(), "references/rule.txt" to "old".toByteArray()), "different-source")
        assertEquals(first.hash, second.hash); assertEquals(first.source, second.source)
        File(first.directory, "references/rule.txt").writeText("tampered")
        rejects { store.discover() }; rejects { install(store) }
    }
    @Test fun dependencyRequestNeverGrantsRootAndDoesNotInstallAnything() {
        var available = SkillDependencyInventory()
        val store = store { available }
        store.install(archive("SKILL.md" to skill(), "android.yaml" to
            "runtimes: [node24, python]\ntools:\n  - text_digest.inspect\npermissions: [root]\nplatforms: [android]\n".toByteArray()), "test")
        assertEquals(setOf("runtimes:node24", "runtimes:python", "tools:text_digest.inspect", "permissions:root"), store.discover().single().missingDependencies.toSet())
        rejects { store.pin("example") }
        available = SkillDependencyInventory(runtimes = setOf("node24", "python"), tools = setOf("text_digest.inspect"))
        assertEquals(listOf("permissions:root"), store.discover().single().missingDependencies)
        assertFalse(store.discover().single().enabled)
    }
    @Test fun malformedSupplementRemainsStoredButUnavailable() {
        for (yaml in listOf("runtime: python", "tools: [x,]", "tools: []\ntools: []", "runtimes:\n  python: true")) {
            val store = store()
            val d = store.install(archive("SKILL.md" to skill(), "android.yaml" to yaml.toByteArray()), "test")
            assertEquals(SkillAvailability.MISSING_DEPENDENCY, d.availability)
            assertTrue(d.missingDependencies.single().startsWith("android.yaml:"))
            rejects { store.pin(d.id) }
        }
    }
    @Test fun traversalAbsoluteBackslashCaseCollisionAndOutsideSiblingsRejected() {
        for (bad in listOf("../escape", "/absolute", "a/../../escape", "a\\evil", "C:/evil", "a//evil", "./evil")) {
            val store = store(); rejects { store.install(archive("SKILL.md" to skill(), bad to byteArrayOf(1)), "test") }
            assertTrue(store.discover().isEmpty())
        }
        rejects { store().install(archive("SKILL.md" to skill(), "Refs/a" to byteArrayOf(), "refs/b" to byteArrayOf()), "test") }
        rejects { store().install(archive("folder/SKILL.md" to skill(), "outside" to byteArrayOf()), "test") }
    }
    @Test fun limitsMissingMetadataInvalidUtf8AndMultipleSkillsRejected() {
        for (bytes in listOf("---\nname: example\n---\n".toByteArray(), byteArrayOf(-1), ByteArray(100001))) {
            rejects { store().install(archive("SKILL.md" to bytes), "test") }
        }
        rejects { store().install(archive("SKILL.md" to skill(), "other/SKILL.md" to skill()), "test") }
        rejects { store().install(archive("SKILL.md" to skill(), "large" to ByteArray(20*1024*1024)), "test") }
    }
    @Test fun unknownMetadataAndBlockDescriptionRetainedWithoutExecution() {
        val store = store()
        val text = "---\nname: example\ndescription: >-\n  first line\n  second line\nfuture_field: whatever\n---\nbody\n".toByteArray()
        val d = store.install(archive("SKILL.md" to text, "scripts/install.sh" to "exit 99".toByteArray()), "test")
        assertEquals("first line second line", d.description); assertEquals("whatever", d.metadata["future_field"])
        assertArrayEquals(text, store.read(store.pin(d.id), "SKILL.md"))
        assertFalse(d.enabled)
    }
    @Test fun resourceContainmentAndSizeEnforced() {
        val store = store(); val d = install(store); val pin = store.pin(d.id)
        rejects { store.read(pin, "../SKILL.md") }; rejects { store.read(pin, "references/rule.txt", 1) }
    }
}
