package dev.alita.androidagent

import android.os.Build
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** Explicit, test-only package fixture. Uses the real host store; never calls a model. */
@RunWith(AndroidJUnit4::class)
class ManagedSkillBindingFixtureTest {
    @Test fun prepareReviewedFixture() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val args = InstrumentationRegistry.getArguments()
        val context = instrumentation.targetContext
        TestDeviceTarget.require(InstrumentationRegistry.getArguments().getString("deviceTarget"))
        val id = requireNotNull(args.getString("fixtureId"))
        require(id.matches(Regex("bound-proof-[0-9]{10,22}")))
        val action = args.getString("fixtureAction") ?: "install"
        val store = (context.applicationContext as AgentApplication).graph.coreSkillPackages
        if (action == "retire") {
            store.retire(id)
            assertTrue(store.discover().none { it.id == id })
            return
        }
        require(action == "install")
        val revision = requireNotNull(args.getString("revision"))
        require(revision in listOf("1", "2"))
        val proof = "RESOURCE_${id}_$revision"
        val bytes = ByteArrayOutputStream()
        ZipOutputStream(bytes).use { zip ->
            val files = listOf(
                "SKILL.md" to "---\nname: $id\ndescription: Read the immutable reference for a controlled acceptance task\nversion: $revision\n---\nRead references/rule.txt using the Read tool. Reply with the exact resource line and version $revision. Do not write files or use other tools.\n",
                "references/rule.txt" to "$proof\n",
            )
            files.forEach { (name, text) -> zip.putNextEntry(ZipEntry(name)); zip.write(text.toByteArray()); zip.closeEntry() }
        }
        val item = store.install(ByteArrayInputStream(bytes.toByteArray()), "test-only-fixture:$id:$revision")
        assertFalse(item.enabled)
        store.setEnabled(id, true)
        assertTrue(store.discover().single { it.id == id }.enabled)
        val pin = store.pin(id)
        assertEquals("$proof\n", store.read(pin, "references/rule.txt").decodeToString())
        val inventory = JSONObject(File(context.filesDir, "core-skill-inventory.json").readText())
        val packages = inventory.getJSONArray("packages")
        val pkg = (0 until packages.length()).map { packages.getJSONObject(it) }.single { it.getString("id") == id }
        assertTrue(pkg.getBoolean("enabled")); assertEquals(item.hash, pkg.getString("candidate"))
        File(context.cacheDir, "$id-$revision-receipt.json").writeText(JSONObject()
            .put("id", id).put("revision", revision).put("hash", item.hash).put("source", item.source)
            .put("directory", item.directory.canonicalPath).put("proof", proof)
            .put("retainedVersions", pkg.getJSONArray("versions").length()).toString(2))
    }
}
