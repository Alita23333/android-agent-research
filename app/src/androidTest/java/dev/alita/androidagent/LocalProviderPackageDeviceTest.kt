package dev.alita.androidagent

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.alita.androidagent.tools.LocalProviderCatalog
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.file.Files
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** Private cache storage tests only. No Core, model, Gateway invocation or provider execution. */
@RunWith(AndroidJUnit4::class)
class LocalProviderPackageDeviceTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val base = File(context.cacheDir, "provider-package-device-${System.nanoTime()}").apply { mkdirs() }
    private val root = File(base, "packages")
    private fun catalog() = LocalProviderCatalog(context, root, File(base, "imports"))
    private fun manifest(version: String = "1", id: String = "fixture") = JSONObject().put("id", id)
        .put("version", version).put("command", JSONArray().put("must-not-execute").put("${'$'}{DIR}/provider.cjs")).toString()
    private fun archive(version: String = "1", id: String = "fixture", extras: List<Pair<String, String>> = emptyList()): ByteArray {
        val bytes = ByteArrayOutputStream()
        ZipOutputStream(bytes).use { zip ->
            for ((name, body) in listOf("provider.json" to manifest(version, id), "provider.cjs" to "inert-$version") + extras) {
                zip.putNextEntry(ZipEntry(name)); zip.write(body.toByteArray()); zip.closeEntry()
            }
        }
        return bytes.toByteArray()
    }
    private fun rejects(block: () -> Unit) { try { block(); fail("Expected rejection") } catch (_: Exception) {} }

    @Test fun updateReloadAndOldPinRetainExactBytesWithoutLaunchingAnything() = runBlocking {
        val catalog = catalog(); val old = catalog.install(archive().inputStream())
        val next = catalog.install(archive("2").inputStream())
        assertNotEquals(old.directory, next.directory)
        assertEquals("inert-1", File(old.directory, "provider.cjs").readText())
        assertEquals(next, catalog().discover().single())
        catalog.load(old).close() // factory only, must-not-execute is deliberately nonexistent
        assertEquals(old, catalog.install(archive().inputStream()))
        assertEquals(old.directory.name, File(root, "fixture/active").readText())
        assertTrue(File(base, "imports").listFiles().orEmpty().isEmpty())
    }

    @Test fun pathsConflictsAndReservedIdsLeaveSelectionUnchanged() {
        val catalog = catalog(); val old = catalog.install(archive().inputStream())
        for (bad in listOf("../escape", "dir/../escape", "dir\\file", "/escape")) rejects {
            catalog.install(archive(extras = listOf(bad to "bad")).inputStream())
        }
        rejects { catalog.install(archive(extras = listOf("Data/a" to "1", "data/b" to "2")).inputStream()) }
        for (id in listOf("device_info", "text_digest", "DEVICE_INFO")) rejects { catalog.install(archive(id = id).inputStream()) }
        assertEquals(old, catalog.discover().single())
        assertFalse(File(base, "escape").exists())
    }

    @Test fun physicalLinksAndPostFactoryTamperingCannotReachProcessStart() = runBlocking {
        val catalog = catalog(); val item = catalog.install(archive().inputStream())
        val provider = catalog.load(item)
        val outside = File(base, "outside").apply { mkdirs() }
        val sentinel = File(outside, "sentinel").apply { writeText("safe") }
        val link = File(item.directory, "escape")
        Files.createSymbolicLink(link.toPath(), outside.toPath())
        rejects { catalog.load(item) }; rejects { catalog.delete(item.id) }
        assertTrue(catalog.discover().isEmpty()); assertEquals("safe", sentinel.readText())
        Files.delete(link.toPath())
        File(item.directory, "provider.cjs").appendText("tampered")
        try { provider.tools(); fail("tampered package executed") }
        catch (e: Exception) { assertTrue(e.message.orEmpty().contains("版本内容已变化")) }
        finally { provider.close() }
        assertTrue(catalog.discover().isEmpty())
        val pointer = File(root, "fixture/active"); assertTrue(pointer.delete())
        Files.createSymbolicLink(pointer.toPath(), sentinel.toPath())
        rejects { catalog.install(archive("2").inputStream()) }
        assertEquals("safe", sentinel.readText())
    }

    @Test fun failedAtomicPointerReplacementDoesNotDestroyRetainedVersionOrOutsideData() {
        val catalog = catalog(); val old = catalog.install(archive().inputStream())
        val pointer = File(root, "fixture/active"); assertTrue(pointer.delete()); assertTrue(pointer.mkdir())
        File(pointer, "sentinel").writeText("preserved")
        rejects { catalog.install(archive("2").inputStream()) }
        assertEquals("preserved", File(pointer, "sentinel").readText())
        assertEquals("inert-1", File(old.directory, "provider.cjs").readText())
        assertTrue(catalog.discover().isEmpty())
        assertTrue(File(root, "fixture").listFiles().orEmpty().none { it.name.startsWith(".active-") || it.name.startsWith(".commit-") })
    }
}
