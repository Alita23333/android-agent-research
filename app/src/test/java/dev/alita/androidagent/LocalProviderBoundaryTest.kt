package dev.alita.androidagent

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import dev.alita.androidagent.core.*
import dev.alita.androidagent.tools.JsonRpcStdioProvider
import dev.alita.androidagent.tools.LocalProviderCatalog
import kotlinx.coroutines.*
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File

@RunWith(RobolectricTestRunner::class)
@Config(application = AgentApplication::class, sdk = [35])
class LocalProviderBoundaryTest {
    private val context: Context = ApplicationProvider.getApplicationContext()
    private val artifacts = object : ArtifactStore {
        override fun create(runId: String, name: String, mimeType: String, bytes: ByteArray) =
            ArtifactRef("test", name, mimeType, "unused", bytes.size.toLong())
    }
    private fun fixture(mode: String = "normal", limit: Int = 1024, timeout: Long = 1500, beforeStart: () -> Unit = {},
        declarations: List<ToolDefinition>? = null, factoryStarts: java.util.concurrent.atomic.AtomicInteger? = null,
        wrapProcess: ((Process) -> Process)? = null): JsonRpcStdioProvider {
        val directory = File(context.cacheDir, "rpc-boundary-${System.nanoTime()}").apply { mkdirs() }
        val script = File(directory, "provider.py")
        script.writeText("""
            import json,sys,time,os
            mode=sys.argv[1]
            for line in sys.stdin:
                r=json.loads(line)
                if r['method']=='initialize':
                    if mode=='init-hang': time.sleep(30)
                    name='probe'
                    if mode=='changed' and os.path.exists('crashed'): name='replacement'
                    tool={'name':name,'description':'fixed test','inputSchema':{'type':'object'},'sideEffect':'NONE','supportsCancellation':True}
                    if mode=='schema-order': tool['inputSchema']={'additionalProperties':False,'properties':{'value':{'description':'text','type':'string'}},'type':'object'}
                    if mode=='bad-effect': tool['sideEffect']='UNKNOWN_MUTATION'
                    result={'protocolVersion':'2.0' if mode=='major' else '1.0','tools':[tool]}
                    if mode=='minor': result['protocolVersion']='1.5'
                    if mode=='duplicate': result['tools'].append(tool)
                else:
                    if mode=='must-not-call': sys.exit(77)
                    a=r['params']['arguments']
                    if a.get('crash'): open('crashed','w').close(); sys.exit(3)
                    if a.get('wait'): time.sleep(a['wait'])
                    if mode=='oversize': sys.stdout.write('x'*20000); sys.stdout.flush(); continue
                    if mode=='invalid-utf8': sys.stdout.buffer.write(b'\xff\n');sys.stdout.flush();continue
                    result={'ok':True,'data':{'answer':42}}
                    if mode=='missing-ok': del result['ok']
                reply={'jsonrpc':'2.0','id':r['id'],'result':result}
                if r['method']!='initialize':
                    if mode=='version': reply['jsonrpc']='1.0'
                    if mode=='string-id': reply['id']=str(r['id'])
                    if mode=='both': reply['error']={'code':-1,'message':'bad'}
                print(json.dumps(reply),flush=True)
        """.trimIndent())
        val command = listOf(System.getenv("TEST_PROVIDER_PYTHON") ?: "python", "-u", script.absolutePath, mode)
        return JsonRpcStdioProvider("fixture", command,
            directory, maxMessageBytes = limit, requestTimeoutMs = timeout, beforeStart = beforeStart,
            declaredTools = declarations, processFactory = if (factoryStarts != null || wrapProcess != null) {
                { factoryStarts?.incrementAndGet(); val child = ProcessBuilder(command).directory(directory).start()
                    wrapProcess?.invoke(child) ?: child }
            } else null)
    }
    private suspend fun call(tool: AgentTool, args: JSONObject = JSONObject(), signal: CancellationSignal = CancellationSignal()) =
        tool.execute(ToolCall(toolId = tool.definition.id, arguments = args), ToolContext("test", signal, artifacts))

    @Test fun cancellationDuringFactoryStartupUsesOriginalSignalAndReturnsCancelled() = runBlocking {
        val entered = java.util.concurrent.CountDownLatch(1)
        val stopped = java.util.concurrent.atomic.AtomicInteger()
        val observed = java.util.concurrent.atomic.AtomicReference<CancellationSignal>()
        val root = File(context.cacheDir, "cancel-start-${System.nanoTime()}").apply { mkdirs() }
        val definition = ToolDefinition("fixture.probe", "1.0.0", "fixed test", JSONObject().put("type", "object"), emptySet(), SideEffect.NONE, true)
        val provider = JsonRpcStdioProvider("fixture", listOf("must-not-execute"), root,
            declaredTools = listOf(definition), cancellableProcessFactory = { signal ->
                observed.set(signal)
                dev.alita.androidagent.execution.IsolatedProviderProcess.launch(object : dev.alita.androidagent.execution.IsolatedProviderProcess.Endpoint {
                    lateinit var events: dev.alita.androidagent.execution.IsolatedProviderProcess.Events
                    override fun stdin() = java.io.ByteArrayOutputStream()
                    override fun stdout() = java.io.ByteArrayInputStream(byteArrayOf())
                    override fun stderr() = java.io.ByteArrayInputStream(byteArrayOf())
                    override fun start(events: dev.alita.androidagent.execution.IsolatedProviderProcess.Events) { this.events = events; entered.countDown() }
                    override fun terminate() { stopped.incrementAndGet(); events.exited(137) }
                    override fun close() { }
                }, 10000, signal::isCancelled)
            })
        try {
            val tool = provider.tools().single(); assertNull(observed.get())
            val signal = CancellationSignal()
            val pending = async(Dispatchers.IO) { call(tool, signal = signal) }
            assertTrue(withContext(Dispatchers.IO) { entered.await(2, java.util.concurrent.TimeUnit.SECONDS) })
            assertSame(signal, observed.get()); signal.cancel()
            val result = withTimeout(1500) { pending.await() }
            assertFalse(result.ok); assertEquals("CANCELLED", result.error!!.code)
            assertFalse(result.error!!.retryable); assertEquals(1, stopped.get())
        } finally { provider.close() }
    }

    @Test fun cancellationWhileFactoryReturnsKillsProcessBeforeHandshake() = runBlocking {
        val signal = CancellationSignal(); val killed = java.util.concurrent.atomic.AtomicInteger()
        val reads = java.util.concurrent.atomic.AtomicInteger(); val writes = java.util.concurrent.atomic.AtomicInteger()
        val root = File(context.cacheDir, "cancel-return-${System.nanoTime()}").apply { mkdirs() }
        val process = object : Process() {
            override fun getInputStream() = object : java.io.ByteArrayInputStream(byteArrayOf()) {
                override fun available(): Int { reads.incrementAndGet(); return super.available() }
            }
            override fun getErrorStream() = java.io.ByteArrayInputStream(byteArrayOf())
            override fun getOutputStream() = object : java.io.ByteArrayOutputStream() {
                override fun write(bytes: ByteArray) { writes.incrementAndGet(); super.write(bytes) }
            }
            override fun waitFor() = 137
            override fun exitValue() = 137
            override fun destroy() { killed.incrementAndGet() }
            override fun destroyForcibly(): Process { destroy(); return this }
        }
        val definition = ToolDefinition("fixture.probe", "1.0.0", "fixed test", JSONObject().put("type", "object"), emptySet(), SideEffect.NONE, true)
        val provider = JsonRpcStdioProvider("fixture", listOf("must-not-execute"), root,
            declaredTools = listOf(definition), cancellableProcessFactory = { signal.cancel(); process })
        try {
            assertEquals("CANCELLED", call(provider.tools().single(), signal = signal).error!!.code)
            assertEquals(1, killed.get())
            assertEquals(0, reads.get()); assertEquals(0, writes.get())
        } finally { provider.close() }
    }

    @Test fun selectedBackendFailureNeverExecutesOwnerUidFallback() = runBlocking {
        val root = File(context.cacheDir, "no-fallback-${System.nanoTime()}").apply { mkdirs() }
        val marker = File(root, "owner-process-must-not-start")
        val definition = ToolDefinition("fixture.probe", "1.0.0", "fixed test", JSONObject().put("type", "object"), emptySet(), SideEffect.NONE, true)
        val provider = JsonRpcStdioProvider("fixture",
            listOf(System.getenv("TEST_PROVIDER_PYTHON") ?: "python", "-c", "open('owner-process-must-not-start','w').close()"), root,
            declaredTools = listOf(definition), processFactory = { throw java.io.IOException("isolated bind rejected") })
        try {
            val result = call(provider.tools().single())
            assertFalse(result.ok); assertEquals("PROVIDER_START_FAILED", result.error!!.code)
            assertFalse(result.error!!.retryable); assertFalse(marker.exists())
        } finally { provider.close() }
    }

    @Test fun processFacadeUsesExistingProtocolCancellationAndFreshSessionRecovery() = runBlocking {
        val processes = java.util.concurrent.CopyOnWriteArrayList<Process>()
        val provider = fixture(wrapProcess = { child ->
            dev.alita.androidagent.execution.IsolatedProviderProcess.launch(
                object : dev.alita.androidagent.execution.IsolatedProviderProcess.Endpoint {
                    override fun stdin() = child.outputStream
                    override fun stdout() = child.inputStream
                    override fun stderr() = child.errorStream
                    override fun start(events: dev.alita.androidagent.execution.IsolatedProviderProcess.Events) {
                        Thread({ events.exited(child.waitFor()) }, "test-child-death").apply { isDaemon = true; start() }
                        events.ready()
                    }
                    override fun terminate() { child.destroyForcibly() }
                    override fun close() { /* Pipe readers own their streams. */ }
                }, 1000).also { processes.add(it) }
        })
        try {
            val tool = provider.tools().single()
            val first = call(tool); assertTrue(first.ok)
            val signal = CancellationSignal()
            val pending = async(Dispatchers.IO) { call(tool, JSONObject().put("wait", 30), signal) }
            delay(150); signal.cancel()
            assertEquals("CANCELLED", withTimeout(2500) { pending.await() }.error!!.code)
            assertTrue(processes.first().waitFor(2, java.util.concurrent.TimeUnit.SECONDS))
            assertFalse(processes.first().isAlive)
            val next = call(tool); assertTrue(next.ok)
            assertEquals(2, processes.size)
            assertNotEquals(first.data.getJSONObject("_localProvider").getString("processInstanceId"),
                next.data.getJSONObject("_localProvider").getString("processInstanceId"))
        } finally { provider.close(); processes.forEach { assertTrue(it.waitFor(2, java.util.concurrent.TimeUnit.SECONDS)) } }
    }

    @Test fun rejectsUnsupportedMajorDuplicateToolsAndUnknownSideEffect() = runBlocking {
        for (mode in listOf("major", "duplicate", "bad-effect")) {
            val provider = fixture(mode)
            try { provider.tools(); fail("accepted $mode") } catch (_: IllegalArgumentException) { }
            finally { provider.close() }
        }
    }
    @Test fun validatesEveryResponseEnvelopeAndResultShape() = runBlocking {
        for (mode in listOf("version", "string-id", "both", "missing-ok", "invalid-utf8")) {
            val provider = fixture(mode)
            try { val result = call(provider.tools().single()); assertFalse(mode, result.ok); assertEquals("PROVIDER_PROTOCOL_ERROR", result.error!!.code) }
            finally { provider.close() }
        }
    }
    @Test fun oversizedUnterminatedStdoutIsRejectedBeforeReadLineAllocation() = runBlocking {
        val provider = fixture("oversize", limit = 512)
        try { assertEquals("PROVIDER_OUTPUT_LIMIT", call(provider.tools().single()).error!!.code) }
        finally { provider.close() }
    }
    @Test fun responseDeadlineAndCancellationReturnWithinBound() = runBlocking {
        val provider = fixture(timeout = 500)
        try {
            val tool = provider.tools().single()
            val start = System.nanoTime()
            assertEquals("PROVIDER_TIMEOUT", call(tool, JSONObject().put("wait", 30)).error!!.code)
            assertTrue((System.nanoTime() - start) / 1_000_000 < 2500)
            val signal = CancellationSignal()
            val pending = async(Dispatchers.IO) { call(tool, JSONObject().put("wait", 30), signal) }
            delay(150); signal.cancel()
            assertEquals("CANCELLED", withTimeout(2500) { pending.await() }.error!!.code)
            assertTrue(call(tool).ok) // fresh process must negotiate before tools/call
        } finally { provider.close() }
    }
    @Test fun initializationAlsoHasDeadline() = runBlocking {
        val provider = fixture("init-hang", timeout = 500)
        val start = System.nanoTime()
        try { provider.tools(); fail("hung initialization accepted") } catch (_: Exception) { }
        finally { provider.close() }
        assertTrue((System.nanoTime() - start) / 1_000_000 < 2500)
    }
    @Test fun oldCancellationCannotKillACompletedRequestsNextCall() = runBlocking {
        val provider = fixture()
        try {
            val tool = provider.tools().single(); val old = CancellationSignal()
            assertTrue(call(tool, signal = old).ok)
            val next = async(Dispatchers.IO) { call(tool, JSONObject().put("wait", 0.3)) }
            delay(100); old.cancel(); assertTrue(next.await().ok)
        } finally { provider.close() }
    }
    @Test fun crashRecoveryRenegotiatesAndRefusesChangedDefinitions() = runBlocking {
        for (mode in listOf("normal", "changed")) {
            val provider = fixture(mode)
            try {
                val tool = provider.tools().single()
                assertFalse(call(tool, JSONObject().put("crash", true)).ok)
                val recovered = call(tool)
                if (mode == "normal") assertTrue(recovered.ok) else assertEquals("PROVIDER_PROTOCOL_ERROR", recovered.error!!.code)
            } finally { provider.close() }
        }
    }
    @Test fun recordsActualCompatibleMinorVersion() = runBlocking {
        val p = fixture("minor")
        try { assertEquals("1.5", call(p.tools().single()).data.getJSONObject("_localProvider").getString("protocolVersion")) }
        finally { p.close() }
    }
    private fun declaration() = ToolDefinition("fixture.probe", description = "fixed test",
        inputSchema = JSONObject().put("type", "object"), sideEffect = SideEffect.NONE, supportsCancellation = true)

    @Test fun declaredDiscoveryAndRegistryRegistrationDoNotStartProcessOrInvokeHook() = runBlocking {
        var hooks = 0; val starts = java.util.concurrent.atomic.AtomicInteger()
        val provider = fixture(declarations = listOf(declaration()), beforeStart = { hooks++ }, factoryStarts = starts)
        try {
            val registry = ToolRegistry(); registry.register(provider)
            assertEquals(0, starts.get()); assertEquals(0, hooks)
            assertEquals(listOf("fixture.probe"), registry.definitions().map { it.id })
            assertTrue(call(registry.find("fixture.probe")!!).ok)
            assertEquals(1, starts.get()); assertEquals(1, hooks)
            assertTrue(call(provider.tools().single()).ok); assertEquals(1, starts.get())
        } finally { provider.close() }
    }

    @Test fun mismatchedDeclaredMetadataFailsBeforeRemoteToolCall() = runBlocking {
        val base = declaration()
        for (different in listOf(base.copy(version = "2"), base.copy(description = "different"),
            base.copy(capabilities = setOf("root")), base.copy(sideEffect = SideEffect.SYSTEM),
            base.copy(supportsCancellation = false), base.copy(inputSchema = JSONObject().put("type", "object").put("additionalProperties", false)))) {
            val provider = fixture("must-not-call", declarations = listOf(different))
            try {
                val failed = call(provider.tools().single())
                assertFalse(failed.ok); assertEquals("PROVIDER_DEFINITION_MISMATCH", failed.error!!.code)
                assertFalse(failed.error!!.retryable)
            } finally { provider.close() }
        }
    }

    @Test fun declarationSchemaKeyOrderIsSemanticNotSerializedOrder() = runBlocking {
        val schema = JSONObject("""{"type":"object","properties":{"value":{"type":"string","description":"text"}},"additionalProperties":false}""")
        val provider = fixture("schema-order", declarations = listOf(declaration().copy(inputSchema = schema)))
        try { assertTrue(call(provider.tools().single()).ok) } finally { provider.close() }
    }

    @Test fun declarationInputsAndDiscoveryResultsAreIndependentSnapshots() = runBlocking {
        val schema = JSONObject().put("type", "object"); val caps = mutableSetOf<String>()
        val provider = fixture(declarations = listOf(declaration().copy(inputSchema = schema, capabilities = caps)))
        try {
            schema.put("extra", true); caps.add("root")
            val first = provider.tools().single(); assertFalse(first.definition.inputSchema.has("extra")); assertTrue(first.definition.capabilities.isEmpty())
            first.definition.inputSchema.put("changed", true)
            val second = provider.tools().single(); assertFalse(second.definition.inputSchema.has("changed"))
            assertTrue(call(second).ok)
        } finally { provider.close() }
    }

    @Test fun declaredDiscoveryCancellationDoesNotStartBackend() = runBlocking {
        val starts = java.util.concurrent.atomic.AtomicInteger()
        val provider = fixture(declarations = listOf(declaration()), factoryStarts = starts)
        try {
            val signal = CancellationSignal().apply { cancel() }
            assertEquals("CANCELLED", call(provider.tools().single(), signal = signal).error!!.code)
            assertEquals(0, starts.get())
        } finally { provider.close() }
    }

    @Test fun declaredVersionIsStillRequiredAfterProcessCrash() = runBlocking {
        val provider = fixture("changed", declarations = listOf(declaration()))
        try {
            val tool = provider.tools().single()
            assertFalse(call(tool, JSONObject().put("crash", true)).ok)
            assertEquals("PROVIDER_DEFINITION_MISMATCH", call(tool).error!!.code)
        } finally { provider.close() }
    }
    @Test fun failedPinVerificationBlocksCrashRecoveryWithExplicitNonRetryableError() = runBlocking {
        var starts = 0
        val provider = fixture(beforeStart = { require(++starts == 1) { "pinned bytes changed" } })
        try {
            val tool = provider.tools().single()
            assertEquals(1, starts)
            assertFalse(call(tool, JSONObject().put("crash", true)).ok)
            val failed = call(tool)
            assertFalse(failed.ok)
            assertEquals("PROVIDER_INTEGRITY_FAILED", failed.error!!.code)
            assertFalse(failed.error!!.retryable)
            assertEquals(2, starts)
        } finally { provider.close() }
    }
    @Test fun bundledVersionTamperingIsRejectedBeforeExecution() {
        val catalog = LocalProviderCatalog(context)
        val descriptor = catalog.installBundled("providers/device-info")
        val file = File(descriptor.directory, "provider.sh"); val original = file.readBytes()
        try {
            file.appendText("\n# injected fixture\n")
            try { catalog.installBundled("providers/device-info"); fail("tampered version accepted") }
            catch (_: IllegalArgumentException) { }
        } finally { file.writeBytes(original) }
    }
    @Test fun importedArchiveIsInertAcrossApplicationStartup() {
        val marker = File(context.cacheDir, "unexpected-execution-${System.nanoTime()}")
        val python = System.getenv("TEST_PROVIDER_PYTHON") ?: "python"
        val manifest = JSONObject().put("id", "unapproved").put("command", org.json.JSONArray()
            .put(python).put("-u").put("${'$'}{DIR}/provider.py"))
        val script = "import json,sys\nopen(" + JSONObject.quote(marker.absolutePath) + ", 'w').write('executed')\n" +
            "for line in sys.stdin:\n r=json.loads(line);print(json.dumps({'jsonrpc':'2.0','id':r['id'],'result':{'protocolVersion':'1.0','tools':[]}}),flush=True)\n"
        val bytes = java.io.ByteArrayOutputStream()
        java.util.zip.ZipOutputStream(bytes).use { zip ->
            for ((name, data) in listOf("provider.json" to manifest.toString(), "provider.py" to script)) {
                zip.putNextEntry(java.util.zip.ZipEntry(name));zip.write(data.toByteArray());zip.closeEntry()
            }
        }
        LocalProviderCatalog(context).install(bytes.toByteArray().inputStream())
        (context as AgentApplication).onCreate()
        assertFalse("unapproved provider was started", marker.exists())
    }
}
