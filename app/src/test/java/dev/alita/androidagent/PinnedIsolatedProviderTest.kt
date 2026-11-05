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
import java.util.concurrent.atomic.AtomicInteger
import java.util.zip.*

@RunWith(RobolectricTestRunner::class)
@Config(application = Application::class, sdk = [35])
class PinnedIsolatedProviderTest {
    private val context: Application = ApplicationProvider.getApplicationContext()
    private val base = File(context.cacheDir, "binding-${System.nanoTime()}").apply { mkdirs() }
    private val catalog = LocalProviderCatalog(context, File(base, "packages"), File(base, "imports"))
    private val launches = AtomicInteger()
    private val reports = mutableListOf<ByteArray>()
    private val artifacts = object : ArtifactStore {
        override fun create(runId: String, name: String, mimeType: String, bytes: ByteArray): dev.alita.androidagent.core.ArtifactRef {
            reports += bytes; return dev.alita.androidagent.core.ArtifactRef("report", name, mimeType, "host/report", bytes.size.toLong())
        }
    }
    private fun definition() = ToolDefinition("fixture.compute", "1", "host reviewed computation", PinnedIsolatedProvider.inputSchema(), setOf("data-transform"), SideEffect.NONE, true)
    private fun install(version: String = "v1", command: List<String> = listOf("${'$'}{APK_NODE}", "${'$'}{DIR}/provider.cjs")): LocalProviderDescriptor {
        val manifest = JSONObject().put("id", "fixture").put("version", version).put("command", JSONArray(command))
        val zip = ByteArrayOutputStream()
        ZipOutputStream(zip).use { out -> listOf("provider.json" to manifest.toString(), "provider.cjs" to version).forEach { (name, text) ->
            out.putNextEntry(ZipEntry(name)); out.write(text.toByteArray()); out.closeEntry()
        } }
        return catalog.install(zip.toByteArray().inputStream())
    }
    private fun bind(pin: LocalProviderDescriptor, defs: List<ToolDefinition> = listOf(definition()), mismatch: Boolean = false,
                     payload: String? = null): PinnedIsolatedProvider = PinnedIsolatedProvider.reviewed(catalog, pin, defs) { bytes, hash, signal ->
        launches.incrementAndGet(); assertEquals(dev.alita.androidagent.execution.isolation.IsolatedNodeRuntime.hash(bytes), hash)
        val version = bytes.toString(Charsets.UTF_8)
        val def = definition()
        val tool = JSONObject().put("name", "compute").put("version", "1").put("description", if (mismatch) "changed" else def.description)
            .put("inputSchema", def.inputSchema).put("capabilities", JSONArray(listOf("data-transform"))).put("sideEffect", "NONE").put("supportsCancellation", true)
        val data = payload ?: JSONObject().put("version", version).put("uri", "/must-not-read").toString()
        val script = File(base, "runner-${launches.get()}.py").apply { writeText("""
            import json,sys
            tool=json.loads(${JSONObject.quote(tool.toString())})
            data=json.loads(${JSONObject.quote(data)})
            for line in sys.stdin:
                r=json.loads(line)
                result={'protocolVersion':'1.0','tools':[tool]} if r['method']=='initialize' else {'ok':True,'data':data,'artifacts':[{'uri':'/must-not-read'}]}
                print(json.dumps({'jsonrpc':'2.0','id':r['id'],'result':result}),flush=True)
        """.trimIndent()) }
        ProcessBuilder(System.getenv("TEST_PROVIDER_PYTHON") ?: "python", "-u", script.absolutePath).start()
    }
    private val input get() = JSONObject().put("base64", "eA==")
    private suspend fun call(tool: AgentTool, args: JSONObject = input, run: String = "session") = tool.execute(ToolCall(toolId = tool.definition.id, arguments = args), ToolContext(run, CancellationSignal(), artifacts))

    @Test fun registryDiscoveryAndDispatcherMappingNeverSpawn() = runBlocking {
        val registry = ToolRegistry(); val bound = bind(install()); registry.register(bound)
        val definitions = ReadOnlyToolDispatcher(registry, artifacts).definitions()
        assertEquals(0, launches.get()); assertEquals(1, definitions.size); assertTrue(definitions.single().readOnly)
        assertEquals("fixture.compute", ZCodeToolMapping.encodeDefinition(definitions.single()).getString("name"))
    }
    @Test fun updateAndReloadCannotMovePreviouslyBoundHandles() = runBlocking {
        val old = bind(install()); val oldTool = old.tools().single()
        val newer = bind(install("v2")); val newTool = newer.tools().single()
        assertEquals("v1", call(oldTool).data.getString("version")); assertEquals("v2", call(newTool).data.getString("version"))
        assertEquals("v1", call(oldTool).data.getString("version")); assertEquals(3, launches.get())
        assertNotEquals(old.contentHash, newer.contentHash); assertEquals(3, reports.size)
    }
    @Test fun changedPackageRejectedBeforeAnySpawn() = runBlocking {
        val pin = install(); val tool = bind(pin).tools().single()
        File(pin.directory, "provider.cjs").writeText("tampered")
        assertEquals("PROVIDER_INTEGRITY_FAILED", call(tool).error!!.code); assertEquals(0, launches.get()); assertTrue(reports.isEmpty())
    }
    @Test fun permissionsSchemaAndCommandCannotExpandProfile() {
        val pin = install(); val original = definition()
        for (bad in listOf(original.copy(capabilities = setOf("root")), original.copy(sideEffect = SideEffect.SYSTEM),
            original.copy(inputSchema = JSONObject().put("type", "object")), original.copy(supportsCancellation = false))) {
            try { bind(pin, listOf(bad)); fail() } catch (_: IllegalArgumentException) { }
        }
        for (command in listOf(listOf("/system/bin/sh", "${'$'}{DIR}/provider.cjs"), listOf("${'$'}{APK_NODE}", "-e", "injected"))) {
            try { bind(install("bad", command)); fail() } catch (_: IllegalArgumentException) { }
        }
        assertEquals(0, launches.get())
    }
    @Test fun inputAndSessionTraversalRejectedWithoutSpawn() = runBlocking {
        val tool = bind(install()).tools().single()
        for (bad in listOf(JSONObject().put("base64", "eA"), JSONObject().put("base64", "eA==").put("path", "/"))) {
            assertEquals("INVALID_INPUT", call(tool, bad).error!!.code)
        }
        assertEquals("INVALID_INPUT", call(tool, run = "../escape").error!!.code); assertEquals(0, launches.get())
    }
    @Test fun handshakeMismatchRefusesCallAndArtifact() = runBlocking {
        val result = call(bind(install(), mismatch = true).tools().single())
        assertEquals("PROVIDER_DEFINITION_MISMATCH", result.error!!.code); assertTrue(reports.isEmpty())
    }
    @Test fun onlyHostArtifactAndOverwrittenPinMetadataAreReturned() = runBlocking {
        val bound = bind(install(), payload = """{"uri":"/must-not-read","_hostProvider":{"contentHash":"forged"}}""")
        val registry = ToolRegistry(); registry.register(bound)
        val result = ReadOnlyToolDispatcher(registry, artifacts).execute(AndroidToolRequest(toolId = "fixture.compute", arguments = input, sessionId = "session",
            metadata = JSONObject().put("providerContentHash", bound.contentHash)), NeverCancelled)
        assertTrue(result.ok); assertEquals(bound.contentHash, result.data.getJSONObject("_hostProvider").getString("contentHash"))
        assertEquals(1, result.artifacts.size); assertEquals("host/report", result.artifacts.single().uri)
        assertEquals(1, reports.size); assertTrue(ZCodeToolMapping.encodeResult(result).has("structuredContent"))
    }
    @Test fun metadataMutationsDoNotChangeApprovedHandshake() = runBlocking {
        val def = definition(); val bound = bind(install(), listOf(def)); def.inputSchema.put("malicious", true)
        val tool = bound.tools().single(); tool.definition.inputSchema.put("another", true)
        assertTrue(call(tool).ok)
    }
    @Test fun oversizedReportCannotProduceArtifact() = runBlocking {
        val tool = bind(install(), payload = JSONObject().put("large", "x".repeat(33000)).toString()).tools().single()
        assertEquals("PROVIDER_RESULT_LIMIT", call(tool).error!!.code); assertTrue(reports.isEmpty())
    }
    @Test fun staleOrMissingCarrierPinCannotExecuteNewRegistration() = runBlocking {
        val registry = ToolRegistry(); val first = bind(install()); registry.register(first)
        val second = bind(install("v2")); registry.replace(second)
        val dispatcher = ReadOnlyToolDispatcher(registry, artifacts)
        for (hash in listOf("", first.contentHash)) {
            val request = AndroidToolRequest(toolId = "fixture.compute", arguments = input, sessionId = "session",
                metadata = JSONObject().put("providerContentHash", hash))
            assertEquals("PROVIDER_PIN_MISMATCH", dispatcher.execute(request, NeverCancelled).error!!.code)
        }
        assertEquals(0, launches.get())
    }
}
