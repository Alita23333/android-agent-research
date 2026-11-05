package dev.alita.androidagent.execution.isolation

import android.app.Activity
import android.os.Build
import android.os.Bundle
import android.widget.TextView
import dev.alita.androidagent.AgentApplication
import dev.alita.androidagent.BuildConfig
import dev.alita.androidagent.tools.LocalProviderDescriptor
import dev.alita.androidagent.tools.PinnedIsolatedProvider
import dev.alita.androidagent.tools.ProviderAdmissionController
import dev.alita.androidagent.tools.ProviderAdmissionDraft
import dev.alita.androidagent.zcode.runtime.ZCodeCarrierWorker
import dev.alita.androidagent.zcode.runtime.ZCodeRuntimeBundle
import dev.alita.androidagent.zcode.runtime.ZCodeRuntimePreparation
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** Separate test APK only: production admission API and real restart transport, not UI/model acceptance. */
class AdmissionProbeActivity : Activity() {
    private val result = JSONObject()
    private var token = ""
    private var stage = "initial"
    private val checks = JSONObject()
    private fun save(verdict: String) {
        result.put("verdict", verdict).put("stage", stage).put("checks", checks)
        File(filesDir, "admission-probe-result.json").outputStream().use {
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
    private fun sha(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
    private fun redact(text: String) = text.replace(token.ifEmpty { "__absent__" }, "[redacted]")

    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        setContentView(TextView(this).apply { text = "Provider admission / restart / Core / Gateway fixture" })
        Thread({ runBlocking {
            var core: Process? = null
            var worker: ZCodeCarrierWorker? = null
            var lease: ProviderAdmissionController.HostLease? = null
            var childPid = 0
            val executor = Executors.newSingleThreadExecutor()
            val diagnostics = StringBuilder()
            val shutdowns = JSONArray()
            var finalVerdict = "FAIL"
            var finalCleanup: (() -> Unit)? = null
            try {
                check(BuildConfig.APPLICATION_ID == "dev.alita.androidagent.isolationtest")
                dev.alita.androidagent.TestDeviceTarget.require(intent.getStringExtra("deviceTarget"))
                result.put("runId", intent.getStringExtra("runId"))
                    .put("scope", "Production controller methods, actual Core-created sessions, explicit fixture Gateway answers; no model/UI/production installation")
                save("RUNNING")
                val graph = (application as AgentApplication).graph
                val admission = graph.providerAdmission
                check(!admission.hostActive()) { "Another test-host owner is active" }
                val fixedRegistry = graph.registry.definitions().map { it.id }.sorted()
                val id = "data_${System.nanoTime()}"
                val canonicalId = "$id.compute"
                val wire = canonicalId.replace('.', '_')
                val description = "计算 / Android 🧪 </script>"
                val reports = JSONArray()
                val starts = JSONArray()
                result.put("providerId", id).put("initialRegistry", JSONArray(fixedRegistry))
                fun selectedOwn(): JSONObject? = graph.reviewedProviders.selectedIdentities().singleOrNull { it.getString("id") == id }
                fun registryIds() = graph.registry.definitions().map { it.id }.sorted()
                fun sessionRow(session: String): JSONObject {
                    val rows = JSONArray(File(filesDir, "sessions-index.json").readText())
                    return (0 until rows.length()).map { rows.getJSONObject(it) }.single { it.getString("sessionId") == session }
                }
                fun pinned(session: String): JSONObject {
                    val pins = sessionRow(session).getJSONArray("managedProviders")
                    return (0 until pins.length()).map { pins.getJSONObject(it) }.single { it.getString("id") == id }
                }
                fun install(version: String): LocalProviderDescriptor {
                    val script = """
                        const rl=require('node:readline'),crypto=require('node:crypto');
                        rl.createInterface({input:process.stdin}).on('line',line=>{
                          const r=JSON.parse(line);let result;
                          if(r.method==='initialize')result={protocolVersion:'1.0',tools:[{name:'compute',version:'1',description:${JSONObject.quote(description)},inputSchema:${PinnedIsolatedProvider.inputSchema()},capabilities:['data-transform'],sideEffect:'NONE',supportsCancellation:true}]};
                          else{const bytes=Buffer.from(r.params.arguments.base64,'base64');result={ok:true,data:{version:'$version',bytes:bytes.length,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),uid:process.getuid(),pid:process.pid}};}
                          process.stdout.write(JSON.stringify({jsonrpc:'2.0',id:r.id,result})+'\n');
                        });
                    """.trimIndent()
                    val manifest = JSONObject().put("id", id).put("version", version)
                        .put("command", JSONArray(listOf("${'$'}{APK_NODE}", "${'$'}{DIR}/provider.cjs")))
                    val archive = ByteArrayOutputStream()
                    ZipOutputStream(archive).use { out ->
                        listOf("provider.json" to manifest.toString(), "provider.cjs" to script).forEach { (name, body) ->
                            out.putNextEntry(ZipEntry(name)); out.write(body.toByteArray()); out.closeEntry()
                        }
                    }
                    return graph.providers.install(archive.toByteArray().inputStream())
                }
                fun preview(item: LocalProviderDescriptor): ProviderAdmissionDraft = admission.preview(id, item.directory.name, "compute", "1", description)
                fun snapshot(draft: ProviderAdmissionDraft) = JSONObject().put("id", id).put("version", draft.version)
                    .put("contentHash", draft.contentHash).put("definitionHash", draft.definitionHash).put("toolIds", JSONArray().put(canonicalId))
                fun childAlive(): Boolean = childPid > 0 && File("/proc/$childPid").exists()
                fun signalOwnedChild(signal: Int) {
                    if (!childAlive()) return
                    val status = try { File("/proc/$childPid/status").readText() }
                    catch (e: java.io.FileNotFoundException) { if (!childAlive()) return else throw e }
                    val uid = Regex("""(?m)^Uid:\s+(\d+)""").find(status)?.groupValues?.get(1)?.toInt()
                    check(uid == android.os.Process.myUid()) { "Refuse signal: Core child no longer belongs to this test UID" }
                    android.os.Process.sendSignal(childPid, signal)
                }
                fun stopAndRelease(reason: String) {
                    val stopped = JSONObject().put("reason", reason).put("childPid", childPid)
                    var carrierStopped = worker?.stop() ?: true
                    stopped.put("initialWorkerStopReturned", carrierStopped)
                    if (childAlive()) signalOwnedChild(15)
                    // Leave the owning bootstrap alive briefly so it can reap its own Core child.
                    repeat(30) { if (childAlive()) Thread.sleep(100) }
                    if (childAlive()) signalOwnedChild(9)
                    repeat(20) { if (childAlive()) Thread.sleep(100) }
                    core?.let { process ->
                        process.destroy()
                        if (!process.waitFor(5, TimeUnit.SECONDS)) process.destroyForcibly()
                        process.waitFor(5, TimeUnit.SECONDS)
                    }
                    val childStopped = !childAlive()
                    val bootstrapStopped = core?.isAlive != true
                    carrierStopped = worker?.stop() ?: true
                    stopped.put("workerStopReturned", carrierStopped).put("workerQuiescent", worker?.isQuiescent() ?: true)
                    stopped.put("childStopped", childStopped).put("bootstrapStopped", bootstrapStopped)
                    val quiescent = carrierStopped && (worker?.isQuiescent() != false) && childStopped && bootstrapStopped
                    stopped.put("quiescent", quiescent)
                    shutdowns.put(stopped); result.put("shutdowns", shutdowns)
                    // Retain the lease if any old work remains; mutation must stay closed.
                    check(quiescent) { "Test runtime did not quiesce; admission lease remains held" }
                    lease?.close()
                    stopped.put("leaseReleased", !admission.hostActive()).put("registryAfterRelease", JSONArray(registryIds()))
                    check(!admission.hostActive() && registryIds() == fixedRegistry) { "Imported visibility remained after stop" }
                    if (reason == "v1-before-update") {
                        checks.put("firstStopQuiescent", true).put("registryRemovedOnStop", true)
                    } else if (reason == "finally" && finalVerdict.startsWith("PASS_")) checks.put("secondStopQuiescent", true)
                    worker = null; core = null; childPid = 0; lease = null
                }
                finalCleanup = { stopAndRelease("finally") }

                stage = "import-v1-inert"; save("RUNNING")
                val reviewFile = File(filesDir, "provider-reviews.json")
                val beforeImport = if (reviewFile.isFile) reviewFile.readBytes() else null
                val item1 = install("v1")
                check(selectedOwn() == null && graph.registry.find(canonicalId) == null && core == null)
                check(if (beforeImport == null) !reviewFile.exists() else beforeImport.contentEquals(reviewFile.readBytes()))
                checks.put("inertImport", true)
                val draft1 = preview(item1)
                check(selectedOwn() == null && graph.registry.find(canonicalId) == null)
                check(if (beforeImport == null) !reviewFile.exists() else beforeImport.contentEquals(reviewFile.readBytes()))
                checks.put("previewInert", true)
                result.put("inertImportAndPreview", JSONObject().put("contentHash", item1.directory.name)
                    .put("selectedOwn", JSONObject.NULL).put("registryAbsent", true).put("runtimeNotStarted", true)
                    .put("reviewFileUnchanged", true))

                stage = "approve-v1-durable-only"; save("RUNNING")
                admission.approve(draft1)
                val pin1 = snapshot(draft1)
                check(PinnedIsolatedProvider.canonical(checkNotNull(selectedOwn())) == PinnedIsolatedProvider.canonical(pin1))
                check(selectedOwn()?.getString("definitionHash") == draft1.definitionHash && graph.registry.find(canonicalId) == null)
                checks.put("approveDeferred", true)
                result.put("oldPin", pin1).put("approvedV1RegistryAbsent", true)

                stage = "prepare-runtime"; save("RUNNING")
                graph.coreSkillPackages.publishInventory()
                val bundle = ZCodeRuntimeBundle(this@AdmissionProbeActivity)
                val preparation = bundle.prepare()
                check(preparation is ZCodeRuntimePreparation.Ready) { preparation.toString() }
                result.put("runtimeVersion", preparation.layout.version).put("runtimePayloadHash", preparation.layout.contentHash)
                fun startHost(expected: JSONObject) {
                    check(core == null && worker == null && lease == null)
                    lease = admission.beginHost()
                    checkNotNull(lease).restore()
                    val visible = graph.registry.find(canonicalId) as PinnedIsolatedProvider.BoundTool
                    check(visible.packageHash == expected.getString("contentHash") && visible.reviewedDefinitionHash == expected.getString("definitionHash"))
                    val builder = bundle.processBuilder(preparation.layout)
                    token = builder.environment().getValue("BRIDGE_TOKEN")
                    builder.environment()["SPIKE_HTTP_PORT"] = "8766"
                    builder.environment()["TMPDIR"] = cacheDir.canonicalPath
                    builder.environment()["CLAUDE_CODE_TMPDIR"] = cacheDir.canonicalPath
                    builder.redirectErrorStream(true)
                    val process = builder.start(); core = process
                    Thread {
                        try {
                            process.inputStream.bufferedReader().useLines { lines -> lines.forEach { line ->
                                synchronized(diagnostics) { diagnostics.append(line).append('\n'); if (diagnostics.length > 12000) diagnostics.delete(0, diagnostics.length - 12000) }
                            } }
                        } catch (_: java.io.IOException) {
                            // Closing a test-owned Process pipe is normal during teardown.
                            // An uncaught reader exception would kill the whole Android test app.
                        }
                    }.start()
                    var ready = false
                    repeat(150) {
                        if (!ready) {
                            try { val status = request("/status"); childPid = status.optInt("childPid"); ready = status.optString("phase") == "ready" } catch (_: Exception) { }
                            if (!ready) Thread.sleep(200)
                        }
                    }
                    check(ready && childPid > 0) { "Core ready deadline" }
                    worker = ZCodeCarrierWorker(this@AdmissionProbeActivity, graph.zcodeReadOnlyDispatcher).also { it.start() }
                    var registered = false
                    var registeredMetadata: JSONObject? = null
                    repeat(100) {
                        if (!registered) {
                            val tools = request("/carrier/tools").getJSONArray("tools")
                            val own = (0 until tools.length()).map { tools.getJSONObject(it) }.singleOrNull { it.optString("toolId") == wire }
                            if (own != null) {
                                val metadata = own.getJSONObject("metadata")
                                check(metadata.getString("providerContentHash") == expected.getString("contentHash") &&
                                    metadata.getString("providerDefinitionHash") == expected.getString("definitionHash"))
                                registeredMetadata = metadata
                                registered = true
                            }
                            if (!registered) Thread.sleep(200)
                        }
                    }
                    check(registered) { "worker registration deadline" }
                    starts.put(JSONObject().put("childPid", childPid).put("registeredContentHash", visible.packageHash)
                        .put("registeredDefinitionHash", visible.reviewedDefinitionHash).put("registry", JSONArray(registryIds()))
                        .put("carrierMetadata", registeredMetadata))
                    result.put("starts", starts)
                }
                val workspace = JSONObject().put("workspacePath", File(filesDir, "workspaces/default").absolutePath).put("workspaceKey", "default")
                fun create(): String = rpc("session/create", JSONObject().put("workspace", workspace).put("mode", "build")
                    .put("titleGenerationEnabled", false).put("dynamicWorkflowEnabled", false).put("offPeakToolEnabled", false)
                    .put("importedHistory", JSONObject().put("source", "claudeCode").put("title", "No-model provider admission fixture")
                        .put("messages", JSONArray().put(JSONObject().put("role", "user").put("content", "Protocol fixture only; do not request a model response.")))))
                    .getJSONObject("session").getString("sessionId")
                fun resume(session: String) = rpc("session/resume", JSONObject().put("sessionId", session).put("workspace", workspace)
                    .put("dynamicWorkflowEnabled", false).put("offPeakToolEnabled", false))
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
                    check(data.getString("sha256") == sha("hello".toByteArray()))
                    check(data.getInt("uid") != android.os.Process.myUid())
                    val provenance = data.getJSONObject("_hostProvider")
                    check(provenance.getString("contentHash") == pin.getString("contentHash"))
                    check(provenance.getString("definitionHash") == pin.getString("definitionHash"))
                    val artifacts = response.getJSONArray("artifacts")
                    check(artifacts.length() == 1)
                    val artifact = artifacts.getJSONObject(0)
                    val physical = File(artifact.getString("uri"))
                    check(physical.canonicalPath.startsWith(File(filesDir, "artifacts/$session").canonicalPath + File.separator))
                    val bytes = physical.readBytes()
                    check(bytes.size.toLong() == artifact.getLong("size"))
                    val report = JSONObject(bytes.toString(Charsets.UTF_8))
                    val callId = report.getString("callId")
                    check(PinnedIsolatedProvider.canonical(report.getJSONObject("data")) == PinnedIsolatedProvider.canonical(data))
                    val operations = request("/gateway/journal?limit=100").getJSONArray("operations")
                    val sessionMatches = (0 until operations.length()).map { operations.getJSONObject(it) }.filter {
                        it.optString("session") == session && it.optString("tool") == "mcp__android-host__$wire" && it.optString("result") == "ok"
                    }
                    check(sessionMatches.size == number)
                    val joined = sessionMatches.filter { it.getString("detail").contains("call_id=$callId ") }
                    check(joined.size == 1 && joined.single().getString("decision") == "allow")
                    check(joined.single().getString("detail").contains("provider_sha256=" + pin.getString("contentHash")) &&
                        joined.single().getString("detail").contains("declaration_sha256=" + pin.getString("definitionHash")))
                    reports.put(JSONObject().put("sessionId", session).put("expectedVersion", version).put("response", response)
                        .put("approval", prompt).put("operations", JSONArray(sessionMatches)).put("joinedOperation", joined.single())
                        .put("physicalReportSha256", sha(bytes)).put("callId", callId))
                    result.put("reports", reports); save("RUNNING")
                }

                stage = "start-v1-host"; save("RUNNING"); startHost(pin1)
                stage = "core-create-v1"; save("RUNNING")
                val old = create()
                check(pinned(old).getString("contentHash") == draft1.contentHash && pinned(old).getString("definitionHash") == draft1.definitionHash)
                result.put("oldSession", old).put("firstSessionRow", sessionRow(old))
                stage = "active-lease-gates"; save("RUNNING")
                val beforeGates = reviewFile.readBytes()
                val gates = JSONArray()
                for ((name, operation) in listOf<Pair<String, () -> Unit>>(
                    "preview" to { preview(item1); Unit },
                    "approve" to { admission.approve(draft1) },
                    "retire" to { admission.retire(id) },
                    "revoke" to { admission.revoke(id, draft1.contentHash, draft1.definitionHash) },
                )) {
                    var error: Exception? = null
                    try { operation() } catch (e: Exception) { error = e }
                    check(error != null) { "Admission mutation $name escaped active lease" }
                    gates.put(JSONObject().put("operation", name).put("rejected", true).put("error", error?.javaClass?.simpleName))
                }
                check(beforeGates.contentEquals(reviewFile.readBytes()))
                checks.put("activeMutationsRejected", true)
                result.put("activeLeaseGates", gates).put("gateReviewFileUnchanged", true)
                stage = "old-session-v1"; save("RUNNING"); invoke(old, pin1, "v1", 1)
                rpc("session/close", JSONObject().put("sessionId", old))
                stage = "stop-v1-runtime-and-release"; save("RUNNING"); stopAndRelease("v1-before-update")

                stage = "approve-v2-while-stopped"; save("RUNNING")
                val item2 = install("v2")
                check(selectedOwn()?.getString("contentHash") == draft1.contentHash && graph.registry.find(canonicalId) == null)
                val draft2 = preview(item2)
                admission.approve(draft2)
                val pin2 = snapshot(draft2)
                check(selectedOwn()?.getString("contentHash") == draft2.contentHash && graph.registry.find(canonicalId) == null)
                check(draft1.contentHash != draft2.contentHash)
                result.put("newPin", pin2).put("approvedV2RegistryAbsent", true)
                stage = "restart-v2-host"; save("RUNNING"); startHost(pin2)
                stage = "restore-old-session-v1"; save("RUNNING")
                invoke(old, pin1, "v1", 2)
                check(pinned(old).getString("contentHash") == draft1.contentHash && pinned(old).getString("definitionHash") == draft1.definitionHash)
                checks.put("oldPinRetainedAcrossRestart", true)
                result.put("restoredSessionRow", sessionRow(old))
                stage = "core-create-new-session-v2"; save("RUNNING")
                val newer = create()
                check(newer != old && pinned(newer).getString("contentHash") == draft2.contentHash && pinned(newer).getString("definitionHash") == draft2.definitionHash)
                result.put("newSession", newer).put("newSessionRow", sessionRow(newer))
                invoke(newer, pin2, "v2", 1)
                stage = "complete"
                finalVerdict = "PASS_SCOPED_ADMISSION_CORE_RESTART_TRANSPORT"
            } catch (e: Throwable) {
                result.put("error", redact(e.stackTraceToString()))
                synchronized(diagnostics) { result.put("diagnostics", redact(diagnostics.toString())) }
            } finally {
                executor.shutdownNow()
                try { finalCleanup?.invoke() }
                catch (e: Throwable) {
                    finalVerdict = "FAIL"
                    result.put("cleanupError", redact(e.stackTraceToString()))
                }
                result.put("shutdowns", shutdowns)
                save(finalVerdict)
            }
        } }, "provider-admission-probe").start()
    }
}
