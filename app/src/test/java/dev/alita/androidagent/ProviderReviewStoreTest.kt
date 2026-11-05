package dev.alita.androidagent

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import dev.alita.androidagent.core.*
import dev.alita.androidagent.tools.*
import dev.alita.androidagent.zcode.adapter.*
import kotlinx.coroutines.runBlocking
import org.json.*
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.*
import java.util.zip.*

@RunWith(RobolectricTestRunner::class)
@Config(application = Application::class, sdk = [35])
class ProviderReviewStoreTest {
    private val app: Application = ApplicationProvider.getApplicationContext()
    private val base = File(app.cacheDir, "reviews-${System.nanoTime()}").apply { mkdirs() }
    private val catalog = LocalProviderCatalog(app, File(base, "packages"), File(base, "imports"))
    private val reviewFile = File(base, "provider-reviews.json")
    private var launches = 0
    private fun store() = ProviderReviewStore(catalog, reviewFile) { pin, defs ->
        PinnedIsolatedProvider.reviewed(catalog, pin, defs) { _, _, _ -> launches++; error("must not execute") }
    }
    private fun definition(id: String = "fixture", suffix: String = "compute", version: String = "1") =
        ToolDefinition("$id.$suffix", version, "Explicit host review", PinnedIsolatedProvider.inputSchema(), setOf("data-transform"), SideEffect.NONE, true)
    private fun install(version: String = "v1", id: String = "fixture"): LocalProviderDescriptor {
        val json = JSONObject().put("id", id).put("version", version).put("command", JSONArray(listOf("${'$'}{APK_NODE}", "${'$'}{DIR}/provider.cjs")))
        val bytes = ByteArrayOutputStream()
        ZipOutputStream(bytes).use { out -> listOf("provider.json" to json.toString(), "provider.cjs" to "inert-$version").forEach { (name, text) ->
            out.putNextEntry(ZipEntry(name)); out.write(text.toByteArray()); out.closeEntry()
        } }
        return catalog.install(bytes.toByteArray().inputStream())
    }
    private fun reject(block: () -> Unit) { try { block(); fail("must reject") } catch (_: Exception) { } }
    private val workspaceRoot = File(base, "workspaces").apply { mkdirs() }
    private val workspace = File(workspaceRoot, "default").apply { mkdirs() }
    private val index = File(base, "sessions-index.json")
    private fun row(pin: JSONObject, session: String = "old") = JSONObject().put("sessionId", session)
        .put("managedProviderBindingVersion", 1).put("managedProviderWorkspace", workspace.absolutePath)
        .put("managedProviders", JSONArray().put(pin))
    private fun request(pin: JSONObject, session: String = "old") = AndroidToolRequest(toolId = "fixture.compute", sessionId = session,
        metadata = JSONObject().put("providerContentHash", pin.getString("contentHash")).put("providerDefinitionHash", pin.getString("definitionHash")))

    @Test fun importNeverCreatesReviewOrSpawns() {
        install(); assertTrue(store().selectedSnapshots().isEmpty()); assertFalse(reviewFile.exists()); assertEquals(0, launches)
    }
    @Test fun updateAndReconstructedStoreRetainExactOldBytesAndReview() = runBlocking {
        val old = store().review(install(), listOf(definition())).sessionSnapshot()
        val newer = store().review(install("v2"), listOf(definition())).sessionSnapshot()
        val restarted = store()
        assertEquals(newer.toString(), restarted.selectedSnapshots().single().toString())
        assertTrue(restarted.verify(old)); assertTrue(restarted.verify(newer))
        assertEquals(old.getString("contentHash"), catalog.pinned("fixture", old.getString("contentHash")).directory.name)
        assertEquals(old.getString("contentHash"), restarted.resolve(old).contentHash); assertEquals(0, launches)
    }
    @Test fun declarationIdentityIsIndependentOfPackageAndOriginalMutableInputs() {
        val pin = install(); val d = definition(); val old = store().review(pin, listOf(d)).sessionSnapshot()
        d.inputSchema.put("mutated", true)
        val updated = store().review(pin, listOf(definition(version = "2"))).sessionSnapshot()
        assertEquals(old.getString("contentHash"), updated.getString("contentHash"))
        assertNotEquals(old.getString("definitionHash"), updated.getString("definitionHash")); assertTrue(store().verify(old))
        store().selectedSnapshots().single().getJSONArray("toolIds").put("fixture.forbidden")
        assertEquals(1, store().selectedSnapshots().single().getJSONArray("toolIds").length())
    }
    @Test fun retirementPreservesOldSessionButRevocationBlocksIt() {
        val pin = store().review(install(), listOf(definition())).sessionSnapshot()
        store().retire("fixture"); assertTrue(store().selectedSnapshots().isEmpty()); assertTrue(store().verify(pin))
        store().revoke(pin); assertFalse(store().verify(pin)); assertTrue(store().selectedSnapshots().isEmpty()); assertEquals(0, launches)
    }
    @Test fun packageTamperRejectedDuringSelectionAndResolution() {
        val item = install(); val pin = store().review(item, listOf(definition())).sessionSnapshot()
        File(item.directory, "provider.cjs").appendText("tamper")
        assertFalse(store().verify(pin)); reject { store().selectedSnapshots() }; reject { store().resolve(pin) }; assertEquals(0, launches)
    }
    @Test fun invalidDeclarationsCannotOverwritePreviouslyReviewedSelection() {
        val item = install(); store().review(item, listOf(definition())); val bytes = reviewFile.readBytes()
        reject { store().review(item, listOf(definition().copy(capabilities = setOf("root")))) }
        assertArrayEquals(bytes, reviewFile.readBytes()); assertEquals(0, launches)
    }
    @Test fun wireCollisionCannotOverwriteExistingReviewFile() {
        store().review(install(id = "foo_bar"), listOf(definition("foo_bar", "inspect"))); val bytes = reviewFile.readBytes()
        reject { store().review(install(id = "foo"), listOf(definition("foo", "bar_inspect"))) }
        assertArrayEquals(bytes, reviewFile.readBytes())
    }
    @Test fun modifiedHostDeclarationOrSnapshotCannotResolve() {
        val pin = store().review(install(), listOf(definition())).sessionSnapshot()
        val json = JSONObject(reviewFile.readText()); json.getJSONArray("reviews").getJSONObject(0).getJSONArray("definitions").getJSONObject(0).put("description", "tamper")
        reviewFile.writeText(json.toString()); assertFalse(store().verify(pin)); assertEquals(0, launches)
    }
    @Test fun orphanSelectionAndInvalidSchemaFailClosed() {
        store().review(install(), listOf(definition()))
        val original = JSONObject(reviewFile.readText()); val bad = JSONObject(original.toString()).put("schemaVersion", 2)
        reviewFile.writeText(bad.toString()); reject { store().selectedSnapshots() }
        original.put("reviews", JSONArray()); reviewFile.writeText(original.toString()); reject { store().selectedSnapshots() }
    }
    @Test fun resolverUsesSessionRowNotNewSelectionOrCallerVersion() {
        val old = store().review(install(), listOf(definition())).sessionSnapshot()
        val newer = store().review(install("v2"), listOf(definition())).sessionSnapshot()
        index.writeText(JSONArray().put(row(old)).put(row(newer, "new")).toString())
        val tool = store().resolveSession(request(old), index, workspaceRoot) as PinnedIsolatedProvider.BoundTool
        assertEquals(old.getString("contentHash"), tool.packageHash)
        reject { store().resolveSession(request(newer), index, workspaceRoot) }
        reject { store().resolveSession(request(old, "missing"), index, workspaceRoot) }
        val wrong = request(old).copy(metadata = JSONObject().put("providerContentHash", old.getString("contentHash")).put("providerDefinitionHash", "b".repeat(64)))
        reject { store().resolveSession(wrong, index, workspaceRoot) }; assertEquals(0, launches)
    }
    @Test fun resolverRejectsWorkspaceEscapeMissingBindingAndDuplicateSession() {
        val pin = store().review(install(), listOf(definition())).sessionSnapshot()
        index.writeText(JSONArray().put(row(pin).put("managedProviderWorkspace", base.absolutePath)).toString())
        reject { store().resolveSession(request(pin), index, workspaceRoot) }
        index.writeText(JSONArray().put(row(pin).put("managedProviderBindingVersion", 2)).toString())
        reject { store().resolveSession(request(pin), index, workspaceRoot) }
        index.writeText(JSONArray().put(row(pin)).put(row(pin)).toString())
        reject { store().resolveSession(request(pin), index, workspaceRoot) }
    }
    @Test fun metadataDirectoryRejectedWithoutMutatingSentinel() {
        reviewFile.mkdir(); val sentinel = File(reviewFile, "sentinel").apply { writeText("keep") }
        reject { store().review(install(), listOf(definition())) }; assertEquals("keep", sentinel.readText())
        assertTrue(base.listFiles().orEmpty().none { it.name.startsWith(".provider-review-") })
    }
}
