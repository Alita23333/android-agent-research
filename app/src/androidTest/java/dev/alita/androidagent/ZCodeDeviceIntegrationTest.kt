package dev.alita.androidagent

import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.alita.androidagent.core.CancellationSignal
import dev.alita.androidagent.core.ToolCall
import dev.alita.androidagent.core.ToolContext
import dev.alita.androidagent.tools.LocalProviderCatalog
import dev.alita.androidagent.model.ModelSettings
import dev.alita.androidagent.model.SecureSettings
import dev.alita.androidagent.zcode.adapter.AndroidToolRequest
import dev.alita.androidagent.zcode.adapter.NeverCancelled
import dev.alita.androidagent.zcode.runtime.ZCodeRuntimeBundle
import dev.alita.androidagent.zcode.runtime.ZCodeRuntimePreparation
import dev.alita.androidagent.zcode.runtime.SearchBackend
import dev.alita.androidagent.zcode.runtime.SearchConfig
import dev.alita.androidagent.zcode.runtime.ZCodeSearchConfigWriter
import dev.alita.androidagent.zcode.runtime.WorkspaceRepository
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.json.JSONObject
import java.io.File

@RunWith(AndroidJUnit4::class)
class ZCodeDeviceIntegrationTest {
    private val application: AgentApplication = ApplicationProvider.getApplicationContext()
    private val target get() = TestDeviceTarget.require(InstrumentationRegistry.getArguments().getString("deviceTarget"))

    @Before fun verifySelectedDevice() { target }

    @Test fun apkOwnedIdentityProviderReturnsTargetDevice() = runBlocking {
        val catalog = LocalProviderCatalog(application)
        val descriptor = catalog.installBundled("providers/device-info")
        val provider = catalog.load(descriptor)
        try {
            val tool = provider.tools().single { it.definition.id == "device_info.identity" }
            val result = tool.execute(
                ToolCall(toolId = tool.definition.id),
                ToolContext("device-test", CancellationSignal(), application.graph.artifactStore),
            )
            assertTrue(result.toJson().toString(), result.ok)
            assertEquals(target.model, result.data.getString("model"))
            assertEquals(target.abi, result.data.getString("abi"))
            assertEquals(target.sdk.toString(), result.data.getString("api"))
        } finally {
            provider.close()
        }
    }

    @Test fun productionDispatcherPublishesOnlyTwoReadOnlyTools() = runBlocking {
        val definitions = application.graph.zcodeReadOnlyDispatcher.definitions()
        assertEquals(setOf("device_info.identity", "ui.inspect"), definitions.map { it.id }.toSet())
        assertTrue(definitions.all { it.readOnly })
        val denied = application.graph.zcodeReadOnlyDispatcher.execute(
            AndroidToolRequest(toolId = "shell.root"),
            NeverCancelled,
        )
        assertFalse(denied.ok)
        assertEquals("TOOL_NOT_EXPOSED", denied.error!!.code)
    }

    @Test fun zcodeRuntimePayloadValidatesOnTargetDevice() {
        val preparation = ZCodeRuntimeBundle(application).prepare()
        assertTrue(preparation.toString(), preparation is ZCodeRuntimePreparation.Ready)
        val layout = (preparation as ZCodeRuntimePreparation.Ready).layout
        assertEquals("0.16.9-runtime3", layout.version)
        assertTrue(layout.node.isFile)
        assertTrue(layout.bash.isFile)
        assertTrue(layout.carrier.isFile)
        assertTrue(layout.webSearch.isFile)
        assertEquals(14_820_819L, layout.zcodeBundle.length())
        assertEquals(188_476L, layout.builtinConfig.length())
    }

    @Test fun phase5WorkspaceSelectionPersistsInAppPrivateStorage() {
        val repository = WorkspaceRepository(application.filesDir)
        val name = "device-acceptance"
        repository.createAndSwitch(name)
        assertEquals(name, WorkspaceRepository(application.filesDir).activeName())
        assertTrue(name in repository.list())
        repository.switch("default")
    }

    @Test fun seedApprovedProviderCredentialFromPrivateFixture() {
        val fixture = File(application.filesDir, "test-provider.json")
        assumeTrue("Private test-provider fixture was not staged", fixture.isFile)
        val json = JSONObject(fixture.readText())
        SecureSettings(application).save(ModelSettings(
            baseUrl = json.getString("baseUrl"),
            apiKey = json.getString("apiKey"),
            model = json.getString("modelId"),
        ))
        fixture.delete()
        val materialized = dev.alita.androidagent.zcode.runtime.ZCodeProviderConfigWriter.materialize(application)
        val root = JSONObject(materialized.readText())
        val providers = root.getJSONObject("config").getJSONObject("providerConfigRules").getJSONArray("providerRules")
        assertEquals(1, providers.length())
        assertEquals("deepseek", providers.getJSONObject(0).getString("providerId"))
    }

    @Test fun seedApprovedSearchCredentialFromPrivateFixture() {
        val fixture = File(application.filesDir, "test-search-provider.json")
        assumeTrue("Private test-search-provider fixture was not staged", fixture.isFile)
        val json = JSONObject(fixture.readText())
        val id = json.getString("backendId")
        val config = SearchConfig(listOf(SearchBackend(
            id = id,
            name = json.optString("name", id.replaceFirstChar(Char::uppercase)),
            enabled = true,
            baseUrl = json.optString("baseUrl", ZCodeSearchConfigWriter.defaultBaseUrl(id)),
            defaultCount = json.optInt("defaultCount", 8),
            timeoutMs = json.optInt("timeoutMs", 60_000),
            sessionCap = json.optInt("sessionCap", 60),
        )))
        ZCodeSearchConfigWriter.save(application, config, mapOf(id to json.getString("apiKey")))
        fixture.delete()
        assertTrue(ZCodeSearchConfigWriter.materialize(application))
        val materialized = JSONObject(File(application.filesDir, "runtime/search/search_config.json").readText())
        assertEquals(id, materialized.getJSONArray("backends").getJSONObject(0).getString("id"))
        assertTrue(materialized.getJSONObject("_keys").getString(id).isNotBlank())
    }
}
