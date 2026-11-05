package dev.alita.androidagent

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.alita.androidagent.core.*
import dev.alita.androidagent.tools.JsonRpcStdioProvider
import kotlinx.coroutines.*
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

@RunWith(AndroidJUnit4::class)
class LocalProviderDeviceTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val artifacts = object : ArtifactStore {
        override fun create(runId: String, name: String, mimeType: String, bytes: ByteArray) = ArtifactRef("test", name, mimeType, "unused", bytes.size.toLong())
    }
    private fun fixture(mode: String): JsonRpcStdioProvider {
        val directory = File(context.cacheDir, "provider-probe-${System.nanoTime()}").apply { mkdirs() }
        val script = File(directory, "probe.cjs")
        script.writeText("""
            const readline=require('node:readline');const fs=require('node:fs');const mode=process.argv[2];
            readline.createInterface({input:process.stdin}).on('line',async line=>{
              const r=JSON.parse(line);let result;
              if(r.method==='initialize'){
                let name=mode==='changed'&&fs.existsSync('crashed')?'different':'probe';
                const tool={name,description:'fixed probe',inputSchema:{type:'object'},sideEffect:'NONE',supportsCancellation:true};
                if(mode==='effect')tool.sideEffect='UNKNOWN';
                result={protocolVersion:mode==='major'?'2.0':'1.0',tools:[tool]};
              }else{
                if(r.params.arguments.crash){fs.writeFileSync('crashed','1');process.exit(3);}
                if(r.params.arguments.wait)await new Promise(ok=>setTimeout(ok,r.params.arguments.wait));
                if(mode==='oversize'){process.stdout.write('x'.repeat(20000));return;}
                result={ok:true,data:{answer:42}};
              }
              const reply={jsonrpc:'2.0',id:r.id,result};
              if(mode==='id'&&r.method!=='initialize')reply.id=String(r.id);
              process.stdout.write(JSON.stringify(reply)+'\n');
            });
        """.trimIndent())
        return JsonRpcStdioProvider("probe", listOf(File(context.applicationInfo.nativeLibraryDir, "libnode.so").absolutePath, script.absolutePath, mode),
            directory, maxMessageBytes = 512, requestTimeoutMs = 1500,
            environment = mapOf("LD_LIBRARY_PATH" to File(context.filesDir, "runtime/lib").absolutePath, "OPENSSL_CONF" to "/dev/null"))
    }
    private suspend fun call(tool: AgentTool, args: JSONObject = JSONObject(), signal: CancellationSignal = CancellationSignal()) =
        tool.execute(ToolCall(toolId = tool.definition.id, arguments = args), ToolContext("test", signal, artifacts))
    @Test fun majorAndUnknownEffectFailClosed() = runBlocking {
        for (mode in listOf("major", "effect")) {
            val p = fixture(mode)
            try { p.tools(); fail("accepted $mode") } catch (_: IllegalArgumentException) { } finally { p.close() }
        }
    }
    @Test fun oversizeAndWrongIdFailClosed() = runBlocking {
        for (mode in listOf("oversize", "id")) {
            val p = fixture(mode)
            try { assertEquals(if (mode == "oversize") "PROVIDER_OUTPUT_LIMIT" else "PROVIDER_PROTOCOL_ERROR", call(p.tools().single()).error!!.code) }
            finally { p.close() }
        }
    }
    @Test fun actualTimeoutAndCancellationRecover() = runBlocking {
        val p = fixture("normal")
        try {
            val t = p.tools().single()
            val start = System.nanoTime()
            assertEquals("PROVIDER_TIMEOUT", call(t, JSONObject().put("wait", 30000)).error!!.code)
            assertTrue((System.nanoTime() - start) / 1_000_000 < 4000)
            val signal = CancellationSignal()
            val pending = async(Dispatchers.IO) { call(t, JSONObject().put("wait", 30000), signal) }
            delay(200); signal.cancel()
            assertEquals("CANCELLED", withTimeout(2500) { pending.await() }.error!!.code)
            assertTrue(call(t).ok)
        } finally { p.close() }
    }
    @Test fun completedRequestCancellationCannotKillNextRequest() = runBlocking {
        val p = fixture("normal")
        try {
            val t = p.tools().single(); val old = CancellationSignal()
            assertTrue(call(t, signal = old).ok)
            val next = async(Dispatchers.IO) { call(t, JSONObject().put("wait", 300)) }
            delay(100); old.cancel(); assertTrue(next.await().ok)
        } finally { p.close() }
    }
    @Test fun crashRequiresNewNegotiationAndStableDefinitions() = runBlocking {
        for (mode in listOf("normal", "changed")) {
            val p = fixture(mode)
            try {
                val t = p.tools().single(); assertFalse(call(t, JSONObject().put("crash", true)).ok)
                val recovered = call(t)
                if (mode == "normal") assertTrue(recovered.ok) else assertEquals("PROVIDER_PROTOCOL_ERROR", recovered.error!!.code)
            } finally { p.close() }
        }
    }
}
