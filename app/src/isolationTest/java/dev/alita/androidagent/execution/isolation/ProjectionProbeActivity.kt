package dev.alita.androidagent.execution.isolation

import android.app.Activity
import android.os.Build
import android.os.Bundle
import android.widget.TextView
import dev.alita.androidagent.AgentApplication
import dev.alita.androidagent.BuildConfig
import dev.alita.androidagent.core.*
import dev.alita.androidagent.tools.*
import dev.alita.androidagent.zcode.runtime.*
import kotlinx.coroutines.runBlocking
import org.json.*
import java.io.*
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.zip.*

/** Separate test APK only. Real Core sessions and Gateway, explicit fixture answers; no model. */
class ProjectionProbeActivity : Activity() {
    private val result = JSONObject()
    private var token = ""
    private var stage = "initial"
    private fun save(verdict: String) {
        result.put("verdict", verdict).put("stage", stage)
        File(filesDir, "projection-probe-result.json").outputStream().use {
            it.write(result.toString(2).toByteArray()); it.fd.sync()
        }
    }
    private fun request(route: String, body: JSONObject? = null): JSONObject {
        val connection = URL("http://127.0.0.1:8766$route").openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 2000; connection.readTimeout = 25000
            connection.setRequestProperty("X-Bridge-Token", token)
            if (body != null) {
                connection.requestMethod = "POST"; connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json")
                connection.outputStream.use { it.write(body.toString().toByteArray()) }
            }
            val code = connection.responseCode
            val text = (if (code < 400) connection.inputStream else connection.errorStream).bufferedReader().use { it.readText() }
            check(code == 200) { "HTTP $code ${text.take(1500)}" }
            return JSONObject(text)
        } finally { connection.disconnect() }
    }
    private fun rpc(method: String, params: JSONObject): JSONObject {
        val response = request("/rpc-wait", JSONObject().put("method", method).put("params", params).put("timeoutMs", 15000))
        check(!response.has("error")) { response.toString() }
        return response.getJSONObject("result")
    }
    override fun onCreate(state: Bundle?) {
        super.onCreate(state); setContentView(TextView(this).apply { text = "Provider projection / Core / Gateway fixture" })
        Thread({ runBlocking {
            var core: Process? = null
            var worker: ZCodeCarrierWorker? = null
            var childPid = 0
            val executor = Executors.newSingleThreadExecutor()
            val diagnostics = StringBuilder()
            try {
                check(BuildConfig.APPLICATION_ID == "dev.alita.androidagent.isolationtest")
                dev.alita.androidagent.TestDeviceTarget.require(intent.getStringExtra("deviceTarget"))
                result.put("runId", intent.getStringExtra("runId")); save("RUNNING")
                val graph = (application as AgentApplication).graph
                val id = "data_${System.nanoTime()}"
                val description = "计算 / Android 🧪 </script>"
                val definition = ToolDefinition("$id.compute", "1", description,
                    PinnedIsolatedProvider.inputSchema(), setOf("data-transform"), SideEffect.NONE, true)
                fun publish(version: String): PinnedIsolatedProvider {
                    val script = """
                        const rl=require('node:readline'),crypto=require('node:crypto');
                        rl.createInterface({input:process.stdin}).on('line',line=>{
                          const r=JSON.parse(line);let result;
                          if(r.method==='initialize')result={protocolVersion:'1.0',tools:[{name:'compute',version:'1',description:${JSONObject.quote(description)},inputSchema:${definition.inputSchema},capabilities:['data-transform'],sideEffect:'NONE',supportsCancellation:true}]};
                          else{const bytes=Buffer.from(r.params.arguments.base64,'base64');result={ok:true,data:{version:'$version',bytes:bytes.length,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),uid:process.getuid(),pid:process.pid}};}
                          process.stdout.write(JSON.stringify({jsonrpc:'2.0',id:r.id,result})+'\n');
                        });
                    """.trimIndent()
                    val manifest = JSONObject().put("id", id).put("version", version)
                        .put("command", JSONArray(listOf("${'$'}{APK_NODE}", "${'$'}{DIR}/provider.cjs")))
                    val bytes = ByteArrayOutputStream()
                    ZipOutputStream(bytes).use { out ->
                        listOf("provider.json" to manifest.toString(), "provider.cjs" to script).forEach { (name, body) ->
                            out.putNextEntry(ZipEntry(name)); out.write(body.toByteArray()); out.closeEntry()
                        }
                    }
                    return graph.reviewedProviders.review(graph.providers.install(bytes.toByteArray().inputStream()), listOf(definition))
                }
                stage = "prepare-runtime"; save("RUNNING")
                graph.coreSkillPackages.publishInventory()
                val bundle = ZCodeRuntimeBundle(this@ProjectionProbeActivity)
                val preparation = bundle.prepare()
                check(preparation is ZCodeRuntimePreparation.Ready) { preparation.toString() }
                val builder = bundle.processBuilder(preparation.layout)
                token = builder.environment().getValue("BRIDGE_TOKEN")
                builder.environment()["SPIKE_HTTP_PORT"] = "8766"
                builder.environment()["TMPDIR"] = cacheDir.canonicalPath
                builder.environment()["CLAUDE_CODE_TMPDIR"] = cacheDir.canonicalPath
                builder.redirectErrorStream(true)
                val process = builder.start(); core = process
                Thread { process.inputStream.bufferedReader().useLines { lines -> lines.forEach { line ->
                    synchronized(diagnostics) { diagnostics.append(line).append('\n'); if (diagnostics.length > 12000) diagnostics.delete(0, diagnostics.length - 12000) }
                } } }.start()
                stage = "wait-core"; save("RUNNING")
                var ready = false
                repeat(150) {
                    if (!ready) {
                        try { val s = request("/status"); childPid = s.optInt("childPid"); ready = s.optString("phase") == "ready" } catch (_: Exception) { }
                        if (!ready) Thread.sleep(200)
                    }
                }
                check(ready) { "Core ready deadline" }
                val workspace = JSONObject().put("workspacePath", File(filesDir, "workspaces/default").absolutePath).put("workspaceKey", "default")
                fun create(): String = rpc("session/create", JSONObject().put("workspace", workspace).put("mode", "build")
                    .put("titleGenerationEnabled", false).put("dynamicWorkflowEnabled", false).put("offPeakToolEnabled", false)
                    .put("importedHistory", JSONObject().put("source", "claudeCode").put("title", "No-model provider projection fixture")
                        .put("messages", JSONArray().put(JSONObject().put("role", "user").put("content", "Protocol fixture only; do not request a model response.")))))
                    .getJSONObject("session").getString("sessionId")
                stage = "core-create-v1"; save("RUNNING")
                val v1 = publish("v1"); val old = create()
                stage = "core-create-v2"; save("RUNNING")
                val v2 = publish("v2"); graph.registry.register(v2); val newer = create()
                result.put("oldPin", v1.sessionSnapshot()).put("newPin", v2.sessionSnapshot()).put("oldSession", old).put("newSession", newer)
                worker = ZCodeCarrierWorker(this@ProjectionProbeActivity, graph.zcodeReadOnlyDispatcher)
                worker.start()
                val wire = "$id.compute".replace('.', '_')
                var registered = false
                repeat(100) {
                    if (!registered) {
                        registered = request("/carrier/tools").toString().contains(wire)
                        if (!registered) Thread.sleep(200)
                    }
                }
                check(registered) { "worker registration deadline" }
                val reports = JSONArray()
                fun resume(session: String) {
                    rpc("session/resume", JSONObject().put("sessionId", session).put("workspace", workspace)
                        .put("dynamicWorkflowEnabled", false).put("offPeakToolEnabled", false))
                }
                fun invoke(session: String, pin: JSONObject, version: String, number: Int) {
                    resume(session)
                    val args = JSONObject().put("base64", "aGVsbG8=")
                    val future = executor.submit<JSONObject> { request("/carrier/call", JSONObject().put("toolId", wire).put("arguments", args)
                        .put("meta", JSONObject().put("sessionId", session).put("providerContentHash", "f".repeat(64)).put("providerDefinitionHash", "e".repeat(64)))) }
                    var answer: JSONObject? = null
                    repeat(100) {
                        if (answer == null) {
                            val pending = request("/gateway/pending").getJSONArray("pending")
                            for (i in 0 until pending.length()) {
                                val item = pending.getJSONObject(i)
                                if (item.optString("toolName") == "mcp__android-host__$wire") answer = item
                            }
                            if (answer == null) Thread.sleep(100)
                        }
                    }
                    val prompt = checkNotNull(answer) { "explicit Gateway prompt missing" }
                    check(prompt.getString("risk") == "PRIVILEGED" && !prompt.optBoolean("hardConfirm"))
                    request("/respond", JSONObject().put("requestId", prompt.getString("requestId")).put("decision", "allow"))
                    val response = future.get(25, TimeUnit.SECONDS)
                    check(response.getBoolean("ok")) { response.toString() }
                    val data = response.getJSONObject("structuredContent").getJSONObject("data")
                    check(data.getString("version") == version && data.getInt("bytes") == 5)
                    check(data.getInt("uid") != android.os.Process.myUid())
                    val provenance = data.getJSONObject("_hostProvider")
                    check(provenance.getString("contentHash") == pin.getString("contentHash"))
                    check(provenance.getString("definitionHash") == pin.getString("definitionHash"))
                    val operations = request("/gateway/journal?limit=100").getJSONArray("operations")
                    val matches = (0 until operations.length()).map { operations.getJSONObject(it) }.filter {
                        it.optString("session") == session && it.optString("tool") == "mcp__android-host__$wire" && it.optString("result") == "ok"
                    }
                    check(matches.size == number)
                    check(matches.all { it.getString("detail").contains("provider_sha256=" + pin.getString("contentHash")) &&
                        it.getString("detail").contains("declaration_sha256=" + pin.getString("definitionHash")) })
                    reports.put(JSONObject().put("sessionId", session).put("expectedVersion", version).put("response", response)
                        .put("approval", prompt).put("operations", JSONArray(matches)))
                    result.put("reports", reports); save("RUNNING")
                }
                stage = "old-session-v1"; save("RUNNING"); invoke(old, v1.sessionSnapshot(), "v1", 1)
                rpc("session/close", JSONObject().put("sessionId", old))
                stage = "resumed-session-v1"; save("RUNNING"); invoke(old, v1.sessionSnapshot(), "v1", 2)
                stage = "new-session-v2"; save("RUNNING"); invoke(newer, v2.sessionSnapshot(), "v2", 1)
                stage = "complete"; save("PASS_SCOPED_CORE_GATEWAY_PROVIDER_TRANSPORT")
            } catch (e: Throwable) {
                result.put("error", e.stackTraceToString().replace(token.ifEmpty { "__absent__" }, "[redacted]"))
                synchronized(diagnostics) { result.put("diagnostics", diagnostics.toString().replace(token.ifEmpty { "__absent__" }, "[redacted]")) }
                save("FAIL")
            } finally {
                worker?.stop(); executor.shutdownNow()
                if (childPid > 0) runCatching { android.os.Process.sendSignal(childPid, 15) }
                core?.destroy(); core?.waitFor(5, TimeUnit.SECONDS)
                if (core?.isAlive == true) core?.destroyForcibly()
            }
        } }, "provider-projection-probe").start()
    }
}
