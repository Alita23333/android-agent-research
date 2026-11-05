package dev.alita.androidagent.execution.isolation

import android.app.Activity
import android.os.*
import android.content.*
import android.widget.TextView
import androidx.core.content.ContextCompat
import dev.alita.androidagent.AgentApplication
import dev.alita.androidagent.BuildConfig
import dev.alita.androidagent.zcode.runtime.*
import kotlinx.coroutines.runBlocking
import org.json.*
import java.io.File
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** Actual product Service in separate test package; no model/key copy or manual child signal. */
class HostLifecycleProbeActivity : Activity() {
    private val report = JSONObject()
    private fun save(verdict: String) {
        report.put("verdict", verdict)
        File(filesDir, "host-lifecycle-result.json").writeText(report.toString(2))
    }
    override fun onCreate(state: Bundle?) {
        super.onCreate(state); setContentView(TextView(this).apply { text = "Actual Service lifecycle test" })
        Thread {
            var bound = false
            var host: ZCodeHostService? = null
            val connected = CountDownLatch(1)
            val connection = object : ServiceConnection {
                override fun onServiceConnected(name: ComponentName, binder: IBinder) {
                    host = (binder as ZCodeHostService.LocalBinder).service(); connected.countDown()
                }
                override fun onServiceDisconnected(name: ComponentName) { }
            }
            try {
                check(BuildConfig.APPLICATION_ID == "dev.alita.androidagent.isolationtest")
                dev.alita.androidagent.TestDeviceTarget.require(intent.getStringExtra("deviceTarget"))
                report.put("runId", intent.getStringExtra("runId")).put("stage", "preflight"); save("RUNNING")
                if (intent.getBooleanExtra("prepareUiOnly", false)) {
                    val id = "aa_000_${Long.MAX_VALUE - System.nanoTime()}"
                    val manifest = JSONObject().put("id", id).put("version", "ui1")
                        .put("command", JSONArray(listOf("${'$'}{APK_NODE}", "${'$'}{DIR}/provider.cjs")))
                    val archive = java.io.ByteArrayOutputStream()
                    java.util.zip.ZipOutputStream(archive).use { zip ->
                        listOf("provider.json" to manifest.toString(), "provider.cjs" to "throw Error('UI-only fixture: do not execute');").forEach { (name, body) ->
                            zip.putNextEntry(java.util.zip.ZipEntry(name)); zip.write(body.toByteArray()); zip.closeEntry()
                        }
                    }
                    val pin = (application as AgentApplication).graph.providers.install(archive.toByteArray().inputStream())
                    File(filesDir, "ui-admission-fixture.json").writeText(JSONObject().put("id", id).put("contentHash", pin.directory.name).toString())
                    report.put("stage", "ui-fixture-prepared"); save("PASS_UI_FIXTURE_PREPARED")
                    return@Thread
                }
                val occupied = runCatching { Socket().use { it.connect(InetSocketAddress("127.0.0.1", 8765), 500) }; true }.getOrDefault(false)
                check(!occupied) { "Port8765 occupied; refuse touching an existing host" }
                val ready = CountDownLatch(1)
                runOnUiThread {
                    ContextCompat.startForegroundService(this, Intent(this, ZCodeHostService::class.java))
                    bound = bindService(Intent(this, ZCodeHostService::class.java), connection, Context.BIND_AUTO_CREATE)
                    ready.countDown()
                }
                check(ready.await(10, TimeUnit.SECONDS) && connected.await(10, TimeUnit.SECONDS))
                val binderHost = checkNotNull(host)
                val graph = (application as AgentApplication).graph
                val cycles = JSONArray(); report.put("cycles", cycles)
                repeat(2) { cycle ->
                    if (cycle > 0) binderHost.ensureStarted()
                    report.put("stage", "wait-ready-$cycle"); save("RUNNING")
                    var live: JSONObject? = null
                    repeat(80) {
                        if (live == null) {
                            val status = runCatching { runBlocking { ZCodeGatewayClient(this@HostLifecycleProbeActivity).status() } }.getOrNull()
                            if (status?.optString("phase") == "ready" && status.optInt("childPid") > 0) live = status
                            else Thread.sleep(250)
                        }
                    }
                    check(live != null) { "Service startup not ready: ${binderHost.javaClass.simpleName}; diagnostics=${binderHostDiagnostic(binderHost)}" }
                    val core = live!!.getInt("childPid")
                    val status = File("/proc/$core/status").readText()
                    val parent = Regex("""(?m)^PPid:\s+(\d+)""").find(status)!!.groupValues[1].toInt()
                    val uid = Regex("""(?m)^Uid:\s+(\d+)""").find(status)!!.groupValues[1].toInt()
                    check(uid == android.os.Process.myUid() && parent != android.os.Process.myPid())
                    check(graph.providerAdmission.hostActive())
                    val row = JSONObject().put("corePid", core).put("bootstrapPid", parent).put("ownerUid", uid)
                    cycles.put(row); report.put("stage", "stop-$cycle"); save("RUNNING")
                    val started = android.os.SystemClock.elapsedRealtime()
                    // Call actual Service API. No fixture-owned Process.destroy or kill(childPid).
                    val stopped = binderHost.stopRuntime()
                    row.put("stopReturned", stopped).put("stopDurationMs", android.os.SystemClock.elapsedRealtime() - started)
                    repeat(40) { if (File("/proc/$core").exists() || File("/proc/$parent").exists()) Thread.sleep(100) }
                    row.put("coreGone", !File("/proc/$core").exists()).put("bootstrapGone", !File("/proc/$parent").exists())
                        .put("admissionUnlocked", !graph.providerAdmission.hostActive())
                    save("RUNNING")
                    check(stopped && row.getBoolean("coreGone") && row.getBoolean("bootstrapGone") && row.getBoolean("admissionUnlocked"))
                }
                report.put("scope", "Actual Service API, idle real Core and bootstrap exit; no model or active MCP descendant/cancellation proof")
                report.put("stage", "complete"); save("PASS_SCOPED_ACTUAL_SERVICE_IDLE_CORE_EXIT")
            } catch (error: Throwable) {
                report.put("error", error.javaClass.simpleName + ": " + error.message?.take(500)); save("FAIL")
            } finally {
                // Test driver force-stops only this separate UID after collecting results.
                if (bound) runOnUiThread { unbindService(connection) }
            }
        }.start()
    }
    private fun binderHostDiagnostic(service: ZCodeHostService): String =
        // Only lifecycle status, never model settings, provider config or bridge credentials.
        service.LocalBinder().status().toString()
}
