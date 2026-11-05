package dev.alita.androidagent

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import dev.alita.androidagent.core.AgentTool
import dev.alita.androidagent.core.ArtifactStore
import dev.alita.androidagent.core.CancellationSignal
import dev.alita.androidagent.core.SideEffect
import dev.alita.androidagent.core.ToolCall
import dev.alita.androidagent.core.ToolContext
import dev.alita.androidagent.core.ToolDefinition
import dev.alita.androidagent.core.ToolRegistry
import dev.alita.androidagent.core.ToolResult
import dev.alita.androidagent.device.DeviceToolProvider
import dev.alita.androidagent.tools.JsonRpcStdioProvider
import dev.alita.androidagent.tools.LocalProviderCatalog
import dev.alita.androidagent.tools.LocalToolProtocol
import dev.alita.androidagent.zcode.adapter.AndroidToolDefinition
import dev.alita.androidagent.zcode.adapter.AndroidToolRequest
import dev.alita.androidagent.zcode.adapter.AndroidToolResult
import dev.alita.androidagent.zcode.adapter.InMemoryZCodeToolCarrier
import dev.alita.androidagent.zcode.adapter.MutableAndroidToolCancellation
import dev.alita.androidagent.zcode.adapter.NeverCancelled
import dev.alita.androidagent.zcode.adapter.ReadOnlyToolDispatcher
import dev.alita.androidagent.zcode.adapter.ZCodeToolCarrierAdapter
import dev.alita.androidagent.zcode.adapter.ZCodeToolMapping
import dev.alita.androidagent.zcode.runtime.ZCodeProtocol
import dev.alita.androidagent.zcode.runtime.ZCodeRuntimeBundle
import dev.alita.androidagent.zcode.runtime.ZCodeRuntimePreparation
import dev.alita.androidagent.zcode.runtime.ZCodeProviderConfigWriter
import dev.alita.androidagent.zcode.runtime.SearchBackend
import dev.alita.androidagent.zcode.runtime.SearchConfig
import dev.alita.androidagent.zcode.runtime.ZCodeSearchConfigWriter
import dev.alita.androidagent.zcode.runtime.WorkspaceRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File

@RunWith(RobolectricTestRunner::class)
@Config(application = AgentApplication::class, sdk = [35])
class ZCodeIntegrationContractTest {
    private val context: Context = ApplicationProvider.getApplicationContext()

    @Test fun zcodeProtocolUsesNdjsonWithoutJsonRpc() {
        val message = ZCodeProtocol.request("session/create", JSONObject().put("thoughtLevel", "disabled"), "42")
        val line = ZCodeProtocol.encode(message)
        assertFalse(line.contains("jsonrpc"))
        assertEquals("session/create", ZCodeProtocol.decode(line).getString("method"))
        assertThrows(IllegalArgumentException::class.java) {
            ZCodeProtocol.encode(JSONObject().put("jsonrpc", "2.0").put("id", 1))
        }
    }

    @Test fun zcodeToolMappingPreservesSchemaErrorsAndArtifacts() {
        val definition = AndroidToolDefinition(
            id = "device_info.identity",
            version = "1.0.0",
            description = "identity",
            inputSchema = JSONObject().put("type", "object"),
            capabilities = setOf("device-read"),
            readOnly = true,
        )
        val encoded = ZCodeToolMapping.encodeDefinition(definition)
        assertEquals("device_info.identity", encoded.getString("name"))
        assertTrue(encoded.getJSONObject("metadata").getBoolean("readOnly"))

        val request = ZCodeToolMapping.decodeCall(JSONObject()
            .put("callId", "call-1")
            .put("name", "device_info.identity")
            .put("arguments", JSONObject()))
        val failure = AndroidToolResult.failure(request, "UNAVAILABLE", "missing", retryable = true)
        val wire = ZCodeToolMapping.encodeResult(failure)
        assertTrue(wire.getBoolean("isError"))
        assertEquals("UNAVAILABLE", wire.getJSONObject("structuredContent").getJSONObject("error").getString("code"))
    }

    @Test fun carrierPublishesOnlyReadOnlySliceAndRoutesResults() = runBlocking {
        val registry = ToolRegistry().apply {
            register(FakeTool("device_info.identity", JSONObject().put("model", "MODEL_ANDROID17")))
            register(FakeTool("ui.inspect", JSONObject().put("observationId", "obs-1")))
            register(FakeTool("shell.root", JSONObject(), SideEffect.SYSTEM))
        }
        val dispatcher = ReadOnlyToolDispatcher(registry, NoArtifacts)
        val carrier = InMemoryZCodeToolCarrier()
        ZCodeToolCarrierAdapter(carrier, dispatcher).start()

        assertEquals(listOf("device_info.identity"), carrier.definitions.map { it.getString("name") })
        val response = carrier.invoke(JSONObject()
            .put("callId", "call-identity")
            .put("name", "device_info.identity")
            .put("arguments", JSONObject()))
        assertFalse(response.getBoolean("isError"))
        assertEquals("MODEL_ANDROID17", response.getJSONObject("structuredContent").getJSONObject("data").getString("model"))

        val denied = dispatcher.execute(AndroidToolRequest(toolId = "shell.root"), NeverCancelled)
        assertEquals("TOOL_NOT_EXPOSED", denied.error!!.code)
    }

    @Test fun localToolProtocolMappingKeepsJsonRpcBoundarySeparate() {
        val initialize = LocalToolProtocol.initializeRequest(7)
        assertEquals("2.0", initialize.getString("jsonrpc"))
        assertEquals("initialize", initialize.getString("method"))

        val request = AndroidToolRequest(requestId = "local-1", toolId = "device_info.identity")
        val call = LocalToolProtocol.toolCallRequest(8, request)
        assertEquals("identity", call.getJSONObject("params").getString("name"))
        val result = LocalToolProtocol.decodeToolResult(request, JSONObject()
            .put("ok", false)
            .put("error", JSONObject().put("code", "NO_DEVICE").put("message", "missing")))
        assertEquals("NO_DEVICE", result.error!!.code)
    }

    @Test fun localProviderCancellationTerminatesProcessAndReturnsCancelled() = runBlocking {
        val directory = File(context.cacheDir, "rpc-cancel-${System.nanoTime()}").apply { mkdirs() }
        try {
            val script = File(directory, "provider.py")
            script.writeText("""
                import json, sys, time
                for line in sys.stdin:
                    request = json.loads(line)
                    if request['method'] == 'initialize':
                        result = {'protocolVersion':'1.0','tools':[{'name':'wait','description':'Wait','inputSchema':{'type':'object'},'supportsCancellation':True}]}
                    else:
                        time.sleep(30)
                        result = {'ok':True,'data':{'finished':True}}
                    print(json.dumps({'jsonrpc':'2.0','id':request['id'],'result':result}), flush=True)
            """.trimIndent())
            val provider = JsonRpcStdioProvider("canceltest", listOf("python", "-u", script.absolutePath), directory)
            val tool = provider.tools().single()
            val cancellation = CancellationSignal()
            val pending = async(Dispatchers.IO) {
                tool.execute(ToolCall(toolId = tool.definition.id), ToolContext("run", cancellation, NoArtifacts))
            }
            delay(200)
            cancellation.cancel()
            val result = withTimeout(5_000) { pending.await() }
            assertFalse(result.ok)
            assertEquals("CANCELLED", result.error!!.code)
            provider.close()
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test fun bundledIdentityProviderIsPreparedForProductInstall() {
        val catalog = LocalProviderCatalog(context)
        val descriptor = catalog.installBundled("providers/device-info")
        assertEquals("device_info", descriptor.id)
        assertTrue(File(descriptor.directory, "provider.sh").isFile)
        assertEquals("/system/bin/sh", descriptor.command.first())
    }

    @Test fun uiInspectIsReadOnlyAndFailsClearlyWithoutAccessibilityService() = runBlocking {
        val tool = DeviceToolProvider(context).tools().single { it.definition.id == "ui.inspect" }
        assertEquals(SideEffect.NONE, tool.definition.sideEffect)
        assertTrue("accessibility.inspect" in tool.definition.capabilities)
        val result = tool.execute(ToolCall(toolId = "ui.inspect"), ToolContext("test", CancellationSignal(), NoArtifacts))
        assertFalse(result.ok)
        assertEquals("ACCESSIBILITY_UNAVAILABLE", result.error!!.code)
    }

    @Test fun runtimePayloadIsPackagedAndJvmFailsClosedWithoutAndroidNativeDir() {
        val prepared = ZCodeRuntimeBundle(context).prepare()
        assertTrue(prepared is ZCodeRuntimePreparation.Missing)
        val missing = (prepared as ZCodeRuntimePreparation.Missing).files
        assertTrue(missing.any { it.endsWith("libnode.so") })
        assertTrue(missing.any { it.endsWith("libbash.so") })
    }

    @Test fun phase8GatewayBootstrapCarrierSearchAndInlineToolsArePackaged() {
        val gateway = context.assets.open("zcode-runtime/gateway.cjs").bufferedReader().use { it.readText() }
        val bootstrap = context.assets.open("zcode-runtime/bootstrap.cjs").bufferedReader().use { it.readText() }
        val carrier = context.assets.open("zcode-runtime/android-carrier.cjs").bufferedReader().use { it.readText() }
        val search = context.assets.open("zcode-runtime/web-search.cjs").bufferedReader().use { it.readText() }
        assertTrue(gateway.contains("class Gateway"))
        assertTrue(gateway.contains("hard-confirm answered without token"))
        assertTrue(bootstrap.contains("interaction/requestPermission"))
        assertTrue(bootstrap.contains("config-disable pack written"))
        assertTrue(bootstrap.contains("/workspaces/switch"))
        assertTrue(bootstrap.contains("/carrier/register"))
        assertTrue(bootstrap.contains("/gateway/network"))
        assertTrue(bootstrap.contains("/gateway/rules"))
        assertTrue(bootstrap.contains("/search/status"))
        assertTrue(bootstrap.contains("INLINE_DISPATCH"))
        assertTrue(bootstrap.contains("require(\"./workspace-files.cjs\")"))
        assertTrue(bootstrap.contains("/ui/render"))
        assertTrue(bootstrap.contains("structuredContent, artifacts, error"))
        assertTrue(bootstrap.contains("mcp.servers"))
        assertTrue(bootstrap.contains("active-workspace"))
        assertTrue(carrier.contains("tools/call"))
        assertTrue(search.contains("search_egress_blocked"))
        assertTrue(search.contains("assertPublicHost"))
        assertTrue(gateway.contains("create table if not exists network_request"))
        assertTrue(gateway.contains("create table if not exists allow_rule"))
        assertTrue(gateway.contains("create table if not exists write_txn"))
        assertTrue(gateway.contains("SCHEMA_VERSION = 3"))
        assertFalse(gateway.contains("factory body"))
    }

    @Test fun phase7SearchSettingsValidateProductionBoundaries() {
        val valid = SearchConfig(listOf(SearchBackend(
            id = "brave", name = "Brave", baseUrl = "https://api.search.brave.com/res/v1",
        )))
        ZCodeSearchConfigWriter.validate(valid)
        assertThrows(IllegalArgumentException::class.java) {
            ZCodeSearchConfigWriter.validate(SearchConfig(listOf(SearchBackend(
                id = "brave", name = "Brave", baseUrl = "http://127.0.0.1:18083",
            ))))
        }
        assertThrows(IllegalArgumentException::class.java) {
            ZCodeSearchConfigWriter.validate(SearchConfig(listOf(SearchBackend(
                id = "custom", name = "Custom", baseUrl = "https://example.com", enabled = true,
            ))))
        }
    }

    @Test fun emptySearchSettingsMaterializeWithoutASecret() {
        context.getSharedPreferences("agent-settings", Context.MODE_PRIVATE).edit().clear().commit()
        assertTrue(ZCodeSearchConfigWriter.materialize(context))
        val file = File(context.filesDir, "runtime/search/search_config.json")
        val root = JSONObject(file.readText())
        assertEquals(1, root.getInt("schemaVersion"))
        assertEquals(0, root.getJSONArray("backends").length())
        assertFalse(file.readText().contains("apiKey", ignoreCase = true))
    }

    @Test fun workspaceRepositoryPersistsSelectionAndRejectsTraversal() {
        val files = File(context.cacheDir, "workspace-test-${System.nanoTime()}").apply { mkdirs() }
        try {
            val repository = WorkspaceRepository(files)
            assertEquals("default", repository.activeName())
            assertEquals("project-alpha", repository.createAndSwitch("project-alpha"))
            assertEquals("project-alpha", WorkspaceRepository(files).activeName())
            assertTrue("project-alpha" in repository.list())
            assertThrows(IllegalArgumentException::class.java) { repository.createAndSwitch("../evil") }
            assertThrows(IllegalArgumentException::class.java) { repository.file("project-alpha", "../escape") }
        } finally {
            files.deleteRecursively()
        }
    }

    @Test fun providerWriterEmitsStrictEmptyRegistryWithoutAKey() {
        context.getSharedPreferences("agent-settings", Context.MODE_PRIVATE).edit().clear().commit()
        val file = ZCodeProviderConfigWriter.materialize(context)
        val root = JSONObject(file.readText())
        assertEquals(1, root.getInt("schemaVersion"))
        val config = root.getJSONObject("config")
        assertEquals(0, config.getJSONObject("providerConfigRules").getJSONArray("providerRules").length())
        assertEquals(0, config.getJSONObject("modelConfigRules").getJSONArray("providerModelRules").length())
        assertEquals(0, config.getJSONObject("modelConfigRules").getJSONArray("manualProviderModelRules").length())
    }

    @Test fun androidCancellationMapsAcrossCarrierDispatcher() = runBlocking {
        val registry = ToolRegistry().apply { register(CancellableFakeTool()) }
        val dispatcher = ReadOnlyToolDispatcher(registry, NoArtifacts)
        val cancellation = MutableAndroidToolCancellation()
        val pending = async(Dispatchers.Default) {
            dispatcher.execute(AndroidToolRequest(toolId = "device_info.identity"), cancellation)
        }
        delay(100)
        cancellation.cancel()
        val result = withTimeout(3_000) { pending.await() }
        assertFalse(result.ok)
        assertEquals("CANCELLED", result.error!!.code)
    }

    private class FakeTool(
        id: String,
        private val payload: JSONObject,
        sideEffect: SideEffect = SideEffect.NONE,
    ) : AgentTool {
        override val definition = ToolDefinition(
            id = id,
            description = id,
            inputSchema = JSONObject().put("type", "object"),
            capabilities = setOf("device-read"),
            sideEffect = sideEffect,
        )
        override suspend fun execute(call: ToolCall, context: ToolContext) = ToolResult.success(call, payload)
    }

    private class CancellableFakeTool : AgentTool {
        override val definition = ToolDefinition(
            id = "device_info.identity",
            description = "wait",
            inputSchema = JSONObject().put("type", "object"),
            capabilities = setOf("device-read"),
            supportsCancellation = true,
        )
        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult {
            while (!context.cancellation.isCancelled()) delay(10)
            context.cancellation.throwIfCancelled()
            return ToolResult.success(call)
        }
    }

    private object NoArtifacts : ArtifactStore {
        override fun create(runId: String, name: String, mimeType: String, bytes: ByteArray) = error("unused")
    }
}
