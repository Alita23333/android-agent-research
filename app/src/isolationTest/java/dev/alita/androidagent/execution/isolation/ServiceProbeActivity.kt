package dev.alita.androidagent.execution.isolation

import android.app.Activity
import android.os.Bundle
import android.os.Build
import android.widget.TextView
import dev.alita.androidagent.AgentApplication
import dev.alita.androidagent.core.*
import dev.alita.androidagent.tools.JsonRpcStdioProvider
import kotlinx.coroutines.*
import org.json.JSONObject
import org.json.JSONArray
import java.io.File
import java.net.ServerSocket
import java.net.Socket
import java.net.InetAddress
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.TimeUnit

/** Only in the separate isolationTest application ID; no production debug entry is added. */
class ServiceProbeActivity : Activity() {
    private val result = JSONObject()
    private lateinit var label: TextView
    private fun save(verdict: String, stage: String) {
        result.put("verdict", verdict).put("stage", stage)
        File(filesDir, "service-probe-result.json").outputStream().use { it.write(result.toString(2).toByteArray()); it.fd.sync() }
        runOnUiThread { label.text = "$verdict: $stage" }
    }
    override fun onCreate(state: Bundle?) {
        super.onCreate(state); label = TextView(this); setContentView(label)
        Thread({ runBlocking { probe() } }, "product-service-probe").start()
    }
    private suspend fun probe() {
        val processes = CopyOnWriteArrayList<Process>()
        val identities = CopyOnWriteArrayList<JSONObject>()
        var provider: JsonRpcStdioProvider? = null
        var server: ServerSocket? = null
        try {
            result.put("runId", intent.getStringExtra("runId"))
            dev.alita.androidagent.TestDeviceTarget.require(intent.getStringExtra("deviceTarget"))
            check((application as AgentApplication).hasInitializedGraph)
            result.put("ownerGraphInitialized", true).put("ownerUid", android.os.Process.myUid())
            save("RUNNING", "verified_product_runtime_launch")
            val runtime = IsolatedNodeRuntime(this)
            val script = assets.open("provider-service-fixture.cjs").use { it.readBytes() }
            val pin = IsolatedNodeRuntime.hash(script)
            val observer: (Bundle) -> Unit = { identity ->
                check(identity.getBoolean("isolated") && !identity.getBoolean("graphInitialized"))
                check(identity.getInt("uid") != android.os.Process.myUid())
                identities.add(JSONObject().put("uid", identity.getInt("uid")).put("pid", identity.getInt("pid"))
                    .put("isolated", true).put("graphInitialized", false))
            }
            val sentinel = File(filesDir, "owner-service-sentinel.txt").apply { writeText("OWNER_SERVICE_FIXTURE") }
            server = ServerSocket(0, 1, InetAddress.getByName("127.0.0.1"))
            server.soTimeout = 2000
            Socket("127.0.0.1", server.localPort).use { owner -> server.accept().use { check(owner.isConnected) } }
            val args = JSONObject().put("privatePath", sentinel.absolutePath).put("port", server.localPort)
            val definition = ToolDefinition("isolated_fixture.probe", "1.0.0", "isolated product fixture",
                JSONObject().put("type", "object"), emptySet(), SideEffect.NONE, true)
            provider = JsonRpcStdioProvider("isolated_fixture", listOf("must-not-execute"), cacheDir,
                declaredTools = listOf(definition), cancellableProcessFactory = { signal ->
                    runtime.launch(script, pin, signal::isCancelled, observer, 60000).also { processes.add(it) }
                })
            val tool = provider.tools().single(); check(processes.isEmpty())
            suspend fun call(arguments: JSONObject = args, signal: CancellationSignal = CancellationSignal()) =
                tool.execute(ToolCall(toolId = definition.id, arguments = arguments),
                    ToolContext("service-probe", signal, (application as AgentApplication).graph.artifactStore))
            val first = call(); check(first.ok) { first.error.toString() }
            val data = first.data
            check(data.getInt("uid") == identities.first().getInt("uid"))
            check(data.getString("node") == "v24.18.0" && data.getString("unicode") == "安卓🧪")
            check(data.getJSONArray("fdLimits").toString() == "[\"512\",\"512\"]")
            check(data.getJSONArray("coreLimits").toString() == "[\"0\",\"0\"]")
            check(data.getLong("heapLimit") in 1..(128L * 1024 * 1024))
            check(data.getJSONArray("envKeys").toString() == "[\"HOME\",\"OPENSSL_CONF\",\"PATH\"]")
            check(!data.getJSONObject("privateRead").getBoolean("allowed") && !data.getJSONObject("privateWrite").getBoolean("allowed"))
            check(!data.getJSONObject("network").getBoolean("allowed") && data.getJSONObject("network").getString("code") in listOf("EACCES", "EPERM"))
            check(sentinel.readText() == "OWNER_SERVICE_FIXTURE")
            check(data.getString("sha256") == IsolatedNodeRuntime.hash("product-service-fixture".toByteArray()))
            result.put("firstResult", data).put("nonExecutingDiscovery", true).put("ownerNetworkPositiveControl", true).put("resourceReadback", true)
            try { runtime.launch(script, pin, { false }, observer, 60000); error("concurrent instance admitted") }
            catch (expected: java.io.IOException) { check(expected.message!!.contains("busy")); result.put("instanceExclusion", true) }
            val signal = CancellationSignal()
            val pending = CoroutineScope(Dispatchers.IO).async { call(JSONObject().put("wait", true), signal) }
            delay(150); signal.cancel()
            check(withTimeout(3000) { pending.await() }.error?.code == "CANCELLED")
            check(processes.first().waitFor(3, TimeUnit.SECONDS))
            val second = call(); check(second.ok) { second.error.toString() }
            check(first.data.getJSONObject("_localProvider").getString("processInstanceId") != second.data.getJSONObject("_localProvider").getString("processInstanceId"))
            result.put("cancelAndRecovery", true).put("secondResult", second.data)
            provider.close(); check(processes.last().waitFor(3, TimeUnit.SECONDS))
            val idle = "setInterval(()=>{},1000)".toByteArray()
            val timed = runtime.launch(idle, IsolatedNodeRuntime.hash(idle), { false }, observer, 700).also { processes.add(it) }
            check(timed.waitFor(4, TimeUnit.SECONDS)); check(!timed.isAlive)
            timed.outputStream.close(); timed.inputStream.close(); timed.errorStream.close()
            result.put("wallLimitDeath", true).put("wallLimitExit", timed.exitValue())
            val natural = "console.log('安卓🧪')".toByteArray()
            val finished = runtime.launch(natural, IsolatedNodeRuntime.hash(natural), { false }, observer, 10000).also { processes.add(it) }
            check(finished.waitFor(4, TimeUnit.SECONDS)); check(finished.exitValue() == 0)
            check(finished.inputStream.bufferedReader().readText().trim() == "安卓🧪")
            finished.outputStream.close(); finished.inputStream.close(); finished.errorStream.close()
            result.put("naturalExit", 0)
            try { runtime.launch(script, "0".repeat(64), { false }, observer, 60000); error("wrong script pin accepted") }
            catch (expected: java.io.IOException) { check(expected.message!!.contains("pin rejected")); result.put("wrongScriptPinRejected", true) }
            result.put("identities", JSONArray(identities)).put("processes", processes.size)
            save("PASS", "product_isolated_backend_and_existing_local_protocol")
        } catch (failure: Throwable) {
            result.put("failure", failure.javaClass.name + ": " + failure.message)
            result.put("identities", JSONArray(identities)); save("FAIL", "product_service_probe_failed")
        } finally {
            provider?.close(); processes.forEach { it.destroyForcibly() }; server?.close()
        }
    }
}
