package dev.alita.androidagent

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import dev.alita.androidagent.tools.LocalProviderCatalog
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

@RunWith(RobolectricTestRunner::class)
@Config(application = Application::class, sdk = [35])
class LocalProviderPackageTest {
    private val context: Application = ApplicationProvider.getApplicationContext()
    private val base = File(context.cacheDir, "provider-package-${System.nanoTime()}").apply { mkdirs() }
    private val root = File(base, "packages")
    private fun catalog() = LocalProviderCatalog(context, root, File(base, "imports"))
    private fun manifest(id: String = "fixture", version: String = "1") = JSONObject().put("id", id)
        .put("version", version).put("command", JSONArray().put("not-executable-fixture").put("${'$'}{DIR}/provider.cjs")).toString()
    private fun zip(vararg entries: Pair<String, ByteArray>): ByteArray {
        val bytes = ByteArrayOutputStream()
        ZipOutputStream(bytes).use { out -> entries.forEach { (name, body) ->
            out.putNextEntry(ZipEntry(name)); out.write(body); out.closeEntry()
        } }
        return bytes.toByteArray()
    }
    private fun archive(id: String = "fixture", version: String = "1", script: String = "inert") =
        zip("provider.json" to manifest(id, version).toByteArray(), "provider.cjs" to script.toByteArray())
    private fun rejects(block: () -> Unit) {
        try { block(); fail("Expected package rejection") } catch (_: Exception) { }
    }

    @Test fun inertImportUpdateAndReloadKeepOriginalPinnedBytes() {
        val catalog = catalog()
        val old = catalog.install(archive().inputStream())
        val newer = catalog.install(archive(version = "2", script = "new").inputStream())
        assertNotEquals(old.directory, newer.directory)
        assertEquals("inert", File(old.directory, "provider.cjs").readText())
        assertEquals(newer, catalog().discover().single())
        assertEquals(old, catalog.install(archive().inputStream()))
        assertEquals(old.directory.name, File(root, "fixture/active").readText())
        assertTrue(File(newer.directory, "provider.cjs").exists())
        assertTrue(File(base, "imports").listFiles().orEmpty().isEmpty())
    }

    @Test fun traversalAndNonPortableArchiveNamesDoNotReplaceSelection() {
        val catalog = catalog(); val old = catalog.install(archive().inputStream())
        for (bad in listOf("../escape", "/escape", "dir/../escape", "dir//file", "dir\\file", "C:/escape", "dir/./file")) {
            rejects { catalog.install(zip("provider.json" to manifest().toByteArray(), bad to byteArrayOf(1)).inputStream()) }
            assertEquals(old, catalog.discover().single())
        }
        assertFalse(File(base, "escape").exists())
    }

    @Test fun duplicateCaseAndFileDirectoryConflictsAreRejected() {
        val catalog = catalog()
        for (entries in listOf(arrayOf("Data/a" to byteArrayOf(1), "data/b" to byteArrayOf(2)),
            arrayOf("file" to byteArrayOf(1), "FILE" to byteArrayOf(2)),
            arrayOf("file" to byteArrayOf(1), "file/child" to byteArrayOf(2)),
            arrayOf("file/child" to byteArrayOf(1), "file" to byteArrayOf(2)))) {
            rejects { catalog.install(zip("provider.json" to manifest().toByteArray(), *entries).inputStream()) }
        }
        // Raw ZIP can contain two byte-identical names although ZipOutputStream forbids writing them.
        val duplicate = zip("provider.json" to manifest().toByteArray(), "same1" to byteArrayOf(1), "same2" to byteArrayOf(2))
        val needle = "same2".toByteArray()
        for (i in 0..duplicate.size - needle.size) if (duplicate.copyOfRange(i, i + needle.size).contentEquals(needle)) duplicate[i + 4] = '1'.code.toByte()
        rejects { catalog.install(duplicate.inputStream()) }
        assertTrue(catalog.discover().isEmpty())
    }

    @Test fun wrappedPackagesRejectDiscardedSiblingsAndMultipleManifests() {
        val catalog = catalog()
        val good = zip("wrapper/provider.json" to manifest().toByteArray(), "wrapper/provider.cjs" to byteArrayOf(1))
        assertEquals("fixture", catalog.install(good.inputStream()).id)
        rejects { catalog.install(zip("wrapper/provider.json" to manifest().toByteArray(), "outside" to byteArrayOf(1)).inputStream()) }
        rejects { catalog.install(zip("provider.json" to manifest().toByteArray(), "nested/provider.json" to manifest().toByteArray()).inputStream()) }
    }

    @Test fun malformedManifestAndUtf8KeepPreviousSelection() {
        val catalog = catalog(); val old = catalog.install(archive().inputStream())
        val bad = listOf(JSONObject(manifest()).put("command", JSONArray()),
            JSONObject(manifest()).put("command", JSONArray().put(123)),
            JSONObject(manifest()).put("command", JSONArray().put("")),
            JSONObject(manifest()).put("command", JSONArray().put("bad\u0000command")),
            JSONObject(manifest()).put("version", 1), JSONObject(manifest()).put("id", "../outside"))
        for (json in bad) rejects { catalog.install(zip("provider.json" to json.toString().toByteArray()).inputStream()) }
        rejects { catalog.install(zip("provider.json" to byteArrayOf(0xff.toByte())).inputStream()) }
        rejects { catalog.install(zip("provider.json" to ByteArray(65_537) { 32 }).inputStream()) }
        assertEquals(old, catalog.discover().single())
    }

    @Test fun archiveEntryAndByteBudgetsAreBounded() {
        val catalog = catalog()
        val many = (0..199).map { "file$it" to byteArrayOf(1) }.toTypedArray()
        rejects { catalog.install(zip("provider.json" to manifest().toByteArray(), *many).inputStream()) }
        rejects { catalog.install(archive(script = "x".repeat(20 * 1024 * 1024)).inputStream()) }
        assertTrue(catalog.discover().isEmpty())
    }

    @Test fun importedNamespacesCannotReplaceBundledProviders() {
        val catalog = catalog()
        for (id in listOf("device_info", "text_digest", "DEVICE_INFO", "Text_Digest")) rejects { catalog.install(archive(id).inputStream()) }
        assertTrue(catalog.discover().isEmpty())
    }

    @Test fun modifiedBytesAndForgedDescriptorAreRejectedBeforeLoad() {
        val catalog = catalog(); val item = catalog.install(archive().inputStream())
        rejects { catalog.load(item.copy(command = listOf("another-command"))) }
        rejects { catalog.load(item.copy(directory = File(base, "elsewhere"))) }
        File(item.directory, "provider.cjs").appendText("changed")
        rejects { catalog.load(item) }; rejects { catalog.install(archive().inputStream()) }
        assertTrue(catalog.discover().isEmpty())
    }

    @Test fun verificationRepeatsAfterFactoryCreationBeforeProcessStart() = runBlocking {
        val catalog = catalog(); val item = catalog.install(archive().inputStream())
        val provider = catalog.load(item) // does NOT start not-executable-fixture
        File(item.directory, "provider.cjs").appendText("changed-after-load")
        try { provider.tools(); fail("tampered content reached process launch") }
        catch (e: Exception) { assertTrue(e.message.orEmpty().contains("版本内容已变化")) }
        finally { provider.close() }
    }

    @Test fun corruptOrEscapingPointersAreUnavailable() {
        val catalog = catalog(); val item = catalog.install(archive().inputStream())
        val pointer = File(root, "fixture/active")
        for (value in listOf("../outside", "a".repeat(64), "a".repeat(1000))) {
            pointer.writeText(value); assertTrue(catalog.discover().isEmpty())
        }
        catalog.install(archive().inputStream())
        assertEquals(item, catalog.discover().single())
        assertTrue(File(root, "fixture").listFiles().orEmpty().none { it.name.startsWith(".active-") || it.name.startsWith(".commit-") })
    }

    @Test fun pointerCommitFailureKeepsPreviousPointerAndPinnedVersion() {
        val catalog = catalog(); val old = catalog.install(archive().inputStream())
        val pointer = File(root, "fixture/active")
        assertTrue(pointer.delete()); assertTrue(pointer.mkdir())
        File(pointer, "sentinel").writeText("preserved")
        rejects { catalog.install(archive(version = "2", script = "new").inputStream()) }
        assertEquals("preserved", File(pointer, "sentinel").readText())
        assertEquals("inert", File(old.directory, "provider.cjs").readText())
        assertTrue(catalog.discover().isEmpty())
    }

}
