package dev.alita.androidagent

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import dev.alita.androidagent.core.AgentTool
import dev.alita.androidagent.core.SideEffect
import dev.alita.androidagent.core.ToolCall
import dev.alita.androidagent.core.ToolContext
import dev.alita.androidagent.core.ToolDefinition
import dev.alita.androidagent.core.ToolRegistry
import dev.alita.androidagent.core.ToolResult
import dev.alita.androidagent.tools.LocalProviderCatalog
import dev.alita.androidagent.tools.LocalProviderDescriptor
import dev.alita.androidagent.tools.PinnedIsolatedProvider
import dev.alita.androidagent.tools.ProviderAdmissionController
import dev.alita.androidagent.tools.ProviderReviewStore
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
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
class ProviderAdmissionControllerTest {
    private val app: Application = ApplicationProvider.getApplicationContext()
    private val base = File(app.cacheDir, "admission-${System.nanoTime()}").apply { mkdirs() }
    private val catalog = LocalProviderCatalog(app, File(base, "packages"), File(base, "imports"))
    private val reviewFile = File(base, "provider-reviews.json")
    private var launches = 0
    private fun store() = ProviderReviewStore(catalog, reviewFile) { pin, definitions ->
        PinnedIsolatedProvider.reviewed(catalog, pin, definitions) { _, _, _ ->
            launches++
            error("Admission, review and visibility restoration must never execute a provider")
        }
    }
    private val reviews = store()
    private val registry = ToolRegistry()
    private val controller = ProviderAdmissionController(catalog, reviews, registry)

    private fun install(version: String = "v1", id: String = "fixture"): LocalProviderDescriptor {
        val descriptor = JSONObject().put("id", id).put("version", version).put("command",
            JSONArray(listOf("${'$'}{APK_NODE}", "${'$'}{DIR}/provider.cjs")))
        val bytes = ByteArrayOutputStream()
        ZipOutputStream(bytes).use { out ->
            listOf("provider.json" to descriptor.toString(), "provider.cjs" to "inert-$version").forEach { (name, text) ->
                out.putNextEntry(ZipEntry(name)); out.write(text.toByteArray()); out.closeEntry()
            }
        }
        return catalog.install(bytes.toByteArray().inputStream())
    }
    private fun preview(item: LocalProviderDescriptor, name: String = "compute", target: ProviderAdmissionController = controller) =
        target.preview(item.id, item.directory.name, name, "1", "Explicitly reviewed / data transform 🧪")
    private fun fixed(id: String = "device_info.identity") = object : AgentTool {
        override val definition = ToolDefinition(id, description = "Existing fixed host tool", inputSchema = JSONObject())
        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult = error("must not execute")
    }
    private fun reject(block: () -> Unit) {
        try { block(); fail("Operation must be rejected") } catch (_: Exception) { }
    }
    private fun assertDefinitions(vararg ids: String) {
        assertEquals(ids.toSet(), registry.definitions().map { it.id }.toSet())
    }
    @After fun noAdmissionPathExecutedCode() {
        assertEquals("All tested admission/lifecycle paths must remain inert", 0, launches)
    }

    @Test fun installationAndPreviewStayInertUntilExplicitApprovalAndNextHostStart() {
        val item = install()
        assertEquals(listOf("fixture"), controller.candidates().map { it.id })
        assertNull(controller.candidates().single().selectedContentHash)
        val draft = preview(item)
        assertFalse(reviewFile.exists())
        assertDefinitions()
        assertEquals(item.directory.name, draft.contentHash)

        controller.approve(draft)
        assertTrue(reviewFile.isFile)
        assertEquals(draft.contentHash, store().selectedSnapshots().single().getString("contentHash"))
        assertDefinitions()
        controller.beginHost().use { lease ->
            assertTrue(controller.hostActive())
            assertDefinitions()
            lease.restore()
            val tool = registry.find("fixture.compute") as PinnedIsolatedProvider.BoundTool
            assertEquals(draft.contentHash, tool.packageHash)
            assertEquals(draft.definitionHash, tool.reviewedDefinitionHash)
        }
        assertFalse(controller.hostActive())
        assertDefinitions()
        assertEquals(draft.contentHash, reviews.selectedSnapshots().single().getString("contentHash"))
    }

    @Test fun leaseCleanupOnlyRemovesImportedToolsAndExpiredLeaseCannotRestoreOrCloseNewOwner() {
        val fixed = fixed().also(registry::register)
        controller.approve(preview(install()))
        val oldLease = controller.beginHost()
        oldLease.restore()
        assertDefinitions("device_info.identity", "fixture.compute")
        oldLease.close()
        assertDefinitions("device_info.identity")
        assertSame(fixed, registry.find("device_info.identity"))

        controller.beginHost().use { currentLease ->
            reject { oldLease.restore() }
            oldLease.close()
            assertTrue(controller.hostActive())
            currentLease.restore()
            assertDefinitions("device_info.identity", "fixture.compute")
        }
        assertDefinitions("device_info.identity")
    }

    @Test fun activeLeaseLocksReviewChangesEvenBeforeRestoration() {
        val item = install()
        val draft = preview(item)
        controller.approve(draft)
        val bytes = reviewFile.readBytes()
        controller.beginHost().use { lease ->
            reject { preview(item) }
            reject { controller.approve(draft) }
            reject { controller.retire(item.id) }
            reject { controller.revoke(item.id, draft.contentHash, draft.definitionHash) }
            reject { controller.beginHost() }
            assertArrayEquals(bytes, reviewFile.readBytes())
            lease.restore()
            assertDefinitions("fixture.compute")
        }
        controller.retire(item.id)
        assertTrue(reviews.selectedSnapshots().isEmpty())
    }

    @Test fun staleUpdatedDraftCannotReplacePreviouslySelectedVersion() {
        val oldDraft = preview(install())
        controller.approve(oldDraft)
        val retained = reviewFile.readBytes()
        val pending = preview(install("v2"))
        install("v3")
        reject { controller.approve(pending) }
        assertArrayEquals(retained, reviewFile.readBytes())
        assertEquals(oldDraft.contentHash, reviews.selectedSnapshots().single().getString("contentHash"))
        assertDefinitions()
    }

    @Test fun packageTamperingAndForgedDraftFieldsCannotCommitApproval() {
        val item = install()
        val draft = preview(item)
        listOf(
            draft.copy(entry = "/system/bin/sh"),
            draft.copy(version = "forged-version"),
            draft.copy(definitionHash = "a".repeat(64)),
            draft.copy(toolName = "other-tool"),
            draft.copy(description = "Changed after preview"),
        ).forEach { reject { controller.approve(it) } }
        assertFalse(reviewFile.exists())
        File(item.directory, "provider.cjs").appendText("tampered after preview")
        reject { controller.approve(draft) }
        assertFalse(reviewFile.exists())
        assertDefinitions()
    }

    @Test fun allSelectedPackagesAreValidatedBeforeAnyStartupVisibility() {
        val fixed = fixed().also(registry::register)
        controller.approve(preview(install(id = "first")))
        val last = install(id = "second")
        controller.approve(preview(last))
        File(last.directory, "provider.cjs").appendText("tampered")
        controller.beginHost().use { lease ->
            reject { lease.restore() }
            assertDefinitions("device_info.identity")
            assertSame(fixed, registry.find("device_info.identity"))
        }
    }

    @Test fun revokedSelectedMetadataFailsClosedBeforeRegistryMutation() {
        registry.register(fixed())
        controller.approve(preview(install(id = "first")))
        controller.approve(preview(install(id = "second")))
        val json = JSONObject(reviewFile.readText())
        json.getJSONArray("reviews").getJSONObject(1).put("revoked", true)
        reviewFile.writeText(json.toString()) // Simulate an inconsistent selected pointer; normal revoke removes it.
        controller.beginHost().use { lease ->
            reject { lease.restore() }
            assertDefinitions("device_info.identity")
        }
    }

    @Test fun startupCollisionWithExistingFixedToolCannotLeavePartialImportedVisibility() {
        controller.approve(preview(install(id = "first")))
        controller.approve(preview(install(id = "second")))
        val fixed = fixed("second.compute").also(registry::register)
        controller.beginHost().use { lease ->
            reject { lease.restore() }
            assertDefinitions("second.compute")
            assertSame(fixed, registry.find("second.compute"))
        }
    }

    @Test fun reconstructedControllerRestoresSelectedPinEvenWhenCatalogHasNewerUnreviewedPackage() {
        val oldDraft = preview(install())
        controller.approve(oldDraft)
        controller.beginHost().use { it.restore() }
        install("v2") // Installation changes catalog selection, not explicit review selection.
        val restartedRegistry = ToolRegistry()
        val restarted = ProviderAdmissionController(catalog, store(), restartedRegistry)
        restarted.beginHost().use { lease ->
            lease.restore()
            val tool = restartedRegistry.find("fixture.compute") as PinnedIsolatedProvider.BoundTool
            assertEquals(oldDraft.contentHash, tool.packageHash)
            assertEquals(oldDraft.definitionHash, tool.reviewedDefinitionHash)
            assertEquals(oldDraft.contentHash, restarted.candidates().single().selectedContentHash)
            assertNotEquals(oldDraft.contentHash, restarted.candidates().single().contentHash)
        }
        assertTrue(restartedRegistry.definitions().isEmpty())
    }

    @Test fun retirementPreservesOldPinWhileRevocationRefusesFutureResolution() {
        val draft = preview(install())
        controller.approve(draft)
        val pin = reviews.selectedSnapshots().single()
        controller.retire(draft.id)
        assertTrue(reviews.selectedSnapshots().isEmpty())
        assertTrue(reviews.verify(pin))
        controller.beginHost().use { it.restore(); assertDefinitions() }

        controller.approve(draft)
        controller.revoke(draft.id, draft.contentHash, draft.definitionHash)
        assertTrue(reviews.selectedSnapshots().isEmpty())
        assertFalse(reviews.verify(pin))
        controller.beginHost().use { it.restore(); assertDefinitions() }
    }

    @Test fun brokenSelectedPackageRemainsVisibleForExplicitRevocation() {
        val item = install()
        val draft = preview(item)
        controller.approve(draft)
        File(item.directory, "provider.cjs").appendText("tampered")
        val visible = controller.candidates().single()
        assertFalse(visible.available)
        assertFalse(visible.selectedAvailable)
        assertEquals(draft.contentHash, visible.selectedContentHash)
        controller.revoke(visible.id, visible.selectedContentHash!!, visible.selectedDefinitionHash!!)
        assertTrue(controller.candidates().isEmpty())
        assertTrue(reviews.selectedIdentities().isEmpty())
    }

    @Test fun hostGeneratedDeclarationHasFixedSchemaAndCapabilitiesAndInvalidNamesCannotAlterSelection() {
        val item = install()
        val draft = preview(item)
        controller.approve(draft)
        val before = reviewFile.readBytes()
        for (name in listOf("root.exec", "../write", "compute/path", "", "1compute", "x".repeat(65))) {
            reject { preview(item, name) }
        }
        reject { controller.preview(item.id, item.directory.name, "compute", "bad\nversion", "description") }
        reject { controller.preview(item.id, item.directory.name, "compute", "1", " ") }
        assertArrayEquals(before, reviewFile.readBytes())
        val provider = reviews.resolve(reviews.selectedSnapshots().single())
        val declaration = provider.declarations().getJSONObject(0)
        assertEquals("NONE", declaration.getString("sideEffect"))
        assertEquals(listOf("data-transform"), (0 until declaration.getJSONArray("capabilities").length()).map {
            declaration.getJSONArray("capabilities").getString(it)
        })
        assertTrue(declaration.getBoolean("supportsCancellation"))
        assertEquals(PinnedIsolatedProvider.canonical(PinnedIsolatedProvider.inputSchema()),
            PinnedIsolatedProvider.canonical(declaration.getJSONObject("inputSchema")))
    }
}
