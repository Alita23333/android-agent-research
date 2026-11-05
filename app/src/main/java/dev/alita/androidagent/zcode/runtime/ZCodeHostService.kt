package dev.alita.androidagent.zcode.runtime

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.Binder
import android.os.IBinder
import androidx.core.app.NotificationCompat
import dev.alita.androidagent.MainActivity
import dev.alita.androidagent.AgentApplication
import dev.alita.androidagent.R
import dev.alita.androidagent.tools.ProviderAdmissionController
import dev.alita.androidagent.zcode.capability.AccessibilityProvider
import dev.alita.androidagent.zcode.capability.CapabilityResolver
import dev.alita.androidagent.zcode.capability.RootProvider
import dev.alita.androidagent.zcode.capability.ScreenCaptureProvider
import dev.alita.androidagent.zcode.capability.ShizukuProvider
import dev.alita.androidagent.zcode.capability.StandardAndroidProvider
import dev.alita.androidagent.zcode.capability.VisionProvider
import java.io.BufferedReader
import java.io.File
import java.io.InputStreamReader
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.atomic.AtomicBoolean

sealed interface ZCodeHostStatus {
    data object Stopped : ZCodeHostStatus
    data object Starting : ZCodeHostStatus
    data class MissingRuntime(val files: List<String>) : ZCodeHostStatus
    data class InvalidRuntime(val reason: String) : ZCodeHostStatus
    data class Running(val version: String, val pid: Long, val contentHash: String) : ZCodeHostStatus
    data class Restarting(val reason: String, val attempt: Int) : ZCodeHostStatus
}

/**
 * Owns and supervises the APK-owned Node bridge independently of Activity
 * lifetime. The production protocol boundary is the token-gated loopback
 * Gateway; this service only owns process lifecycle and diagnostics.
 */
class ZCodeHostService : Service() {
    private val binder = LocalBinder()
    private val requested = AtomicBoolean(false)
    private val diagnostics = CopyOnWriteArrayList<String>()
    private val carrierWorker by lazy {
        ZCodeCarrierWorker(
            this,
            (application as AgentApplication).graph.zcodeReadOnlyDispatcher,
            ::appendDiagnostic,
        )
    }
    @Volatile private var process: Process? = null
    @Volatile private var supervisor: Thread? = null
    @Volatile private var admissionLease: ProviderAdmissionController.HostLease? = null
    @Volatile private var currentStatus: ZCodeHostStatus = ZCodeHostStatus.Stopped

    override fun onCreate() {
        super.onCreate()
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(CHANNEL, "ZCode runtime", NotificationManager.IMPORTANCE_LOW)
        )
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            Thread({ if (stopRuntime()) stopSelf(startId) }, "zcode-stop").start()
            return START_NOT_STICKY
        }
        startForeground(NOTIFICATION_ID, notification("正在准备 ZCode runtime"))
        ensureStarted()
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder = binder

    @Synchronized
    fun ensureStarted(): ZCodeHostStatus {
        if (requested.get() || process?.isAlive == true || supervisor?.isAlive == true) return currentStatus
        publishCapabilities()
        when (val prepared = ZCodeRuntimeBundle(this).prepare()) {
            is ZCodeRuntimePreparation.Missing -> setStatus(ZCodeHostStatus.MissingRuntime(prepared.files))
            is ZCodeRuntimePreparation.Invalid -> setStatus(ZCodeHostStatus.InvalidRuntime(prepared.reason))
            is ZCodeRuntimePreparation.Ready -> {
                val lease = runCatching { (application as AgentApplication).graph.providerAdmission.beginHost() }
                    .getOrElse {
                        setStatus(ZCodeHostStatus.InvalidRuntime(it.message ?: "工具管理尚未就绪"))
                        return currentStatus
                    }
                requested.set(true)
                admissionLease = lease
                setStatus(ZCodeHostStatus.Starting)
                supervisor = Thread({ supervise(prepared.layout, lease) }, "zcode-supervisor").apply {
                    isDaemon = true
                    start()
                }
            }
        }
        return currentStatus
    }

    private fun supervise(initialLayout: ZCodeRuntimeLayout, lease: ProviderAdmissionController.HostLease) {
        try { superviseLoop(initialLayout, lease) }
        finally {
            requested.set(false)
            if (carrierWorker.stop() && process?.isAlive != true) {
                lease.close()
                admissionLease = null
                if (currentStatus !is ZCodeHostStatus.InvalidRuntime && currentStatus !is ZCodeHostStatus.MissingRuntime)
                    setStatus(ZCodeHostStatus.Stopped)
            } else {
                setStatus(ZCodeHostStatus.InvalidRuntime("旧工具仍在结束中，工具管理继续锁定；请稍后重新打开应用"))
            }
        }
    }

    private fun superviseLoop(initialLayout: ZCodeRuntimeLayout, lease: ProviderAdmissionController.HostLease) {
        var layout = initialLayout
        var attempt = 0
        var backoffMs = 2_000L
        while (requested.get()) {
            val exit = runOnce(layout, lease)
            if (!carrierWorker.isQuiescent() || process?.isAlive == true) {
                requested.set(false)
                setStatus(ZCodeHostStatus.InvalidRuntime("旧运行尚未结束，拒绝启动新的工具列表"))
                break
            }
            if (!requested.get()) break
            attempt += 1
            setStatus(ZCodeHostStatus.Restarting("ZCode process exited: $exit", attempt))
            try {
                Thread.sleep(backoffMs)
            } catch (_: InterruptedException) {
                if (!requested.get()) break
            }
            backoffMs = (backoffMs * 2).coerceAtMost(30_000L)
            when (val refreshed = ZCodeRuntimeBundle(this).prepare()) {
                is ZCodeRuntimePreparation.Ready -> layout = refreshed.layout
                is ZCodeRuntimePreparation.Missing -> {
                    requested.set(false)
                    setStatus(ZCodeHostStatus.MissingRuntime(refreshed.files))
                }
                is ZCodeRuntimePreparation.Invalid -> {
                    requested.set(false)
                    setStatus(ZCodeHostStatus.InvalidRuntime(refreshed.reason))
                }
            }
        }
        if (currentStatus is ZCodeHostStatus.Running || currentStatus is ZCodeHostStatus.Starting) {
            setStatus(ZCodeHostStatus.Stopped)
        }
    }

    private fun runOnce(layout: ZCodeRuntimeLayout, lease: ProviderAdmissionController.HostLease): Int = try {
        // Load the fixed, APK-owned local provider only after runtime SHA validation/extraction.
        // Reuse the existing registry/dispatcher; no additional task loop or provider protocol.
        val graph = (application as AgentApplication).graph
        val digest = graph.providers.installBundled("providers/text-digest")
        kotlinx.coroutines.runBlocking { graph.registry.replace(graph.providers.load(digest)) }
        lease.restore() // Exact reviewed selections only, before Node/worker publish any tools.
        graph.coreSkillPackages.publishInventory()
        ZCodeScreenFrames(this).purge()
        ZCodeVisionConfigWriter.materialize(this)
        ZCodeProviderConfigWriter.materialize(this)
        check(ZCodeSearchConfigWriter.materialize(this)) {
            ZCodeSearchConfigWriter.lastMaterializeError ?: "Unable to materialize search configuration"
        }
        check(requested.get()) { "Runtime startup cancelled" }
        val started = ZCodeRuntimeBundle(this).processBuilder(layout)
            .redirectErrorStream(true)
            .start()
        process = started
        check(requested.get()) { "Runtime startup cancelled" }
        val pid = runCatching { started.javaClass.getMethod("pid").invoke(started) as Long }.getOrDefault(-1L)
        setStatus(ZCodeHostStatus.Running(layout.version, pid, layout.contentHash))
        carrierWorker.start()
        BufferedReader(InputStreamReader(started.inputStream)).useLines { lines ->
            lines.forEach(::appendDiagnostic)
        }
        started.waitFor()
    } catch (error: Throwable) {
        appendDiagnostic("ZCode launch failed: ${error.message ?: error.javaClass.simpleName}")
        127
    } finally {
        carrierWorker.stop()
        process?.let { running ->
            if (running.isAlive) running.destroy()
            runCatching { running.waitFor(2500, java.util.concurrent.TimeUnit.MILLISECONDS) }
            if (running.isAlive) running.destroyForcibly()
            runCatching { running.waitFor(500, java.util.concurrent.TimeUnit.MILLISECONDS) }
        }
        ZCodeScreenFrames(this).purge()
        if (process?.isAlive != true) process = null
    }

    @Synchronized
    fun stopRuntime(): Boolean {
        requested.set(false)
        if (process?.isAlive == true) {
            // Keep the existing bridge alive long enough to close the admitted operation.
            // Destroying it first can kill every child yet leave the journal result null.
            runCatching { kotlinx.coroutines.runBlocking {
                val client = ZCodeGatewayClient(this@ZCodeHostService)
                val session = client.status().optString("activeSession")
                if (session.matches(Regex("[A-Za-z0-9_-]{1,128}")) && session != "null") {
                    client.rpc(org.json.JSONObject().put("id", "host_stop_${System.nanoTime()}")
                        .put("method", "session/stop")
                        .put("params", org.json.JSONObject().put("sessionId", session)))
                }
            } }.onFailure { appendDiagnostic("Active session cancellation could not be confirmed before host shutdown") }
        }
        carrierWorker.stop()
        val supervising = supervisor
        supervising?.interrupt()
        process?.let { running ->
            running.destroy()
            val deadline = System.nanoTime() + 2_500_000_000L
            while (running.isAlive && System.nanoTime() < deadline) {
                try {
                    Thread.sleep(50)
                } catch (_: InterruptedException) {
                    break
                }
            }
            if (running.isAlive) running.destroyForcibly()
        }
        if (supervising != Thread.currentThread()) runCatching { supervising?.join(3500) }
        if (process?.isAlive != true) process = null
        if (supervising?.isAlive != true && carrierWorker.isQuiescent() && process?.isAlive != true) {
            admissionLease?.close()
            admissionLease = null
        }
        if (supervising?.isAlive != true && carrierWorker.isQuiescent() &&
            !(application as AgentApplication).graph.providerAdmission.hostActive()) {
            supervisor = null
            setStatus(ZCodeHostStatus.Stopped)
        } else setStatus(ZCodeHostStatus.InvalidRuntime("正在结束旧任务，尚不能修改工具"))
        return currentStatus == ZCodeHostStatus.Stopped
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        appendDiagnostic("Activity task removed; foreground runtime remains owned by service")
        super.onTaskRemoved(rootIntent)
    }

    override fun onDestroy() {
        // Platform teardown must not block Android's main thread on provider/HTTP cleanup.
        Thread({ stopRuntime() }, "zcode-destroy").start()
        super.onDestroy()
    }

    private fun publishCapabilities() {
        runCatching {
            val resolver = CapabilityResolver(listOf(
                StandardAndroidProvider(this),
                AccessibilityProvider(this),
                ScreenCaptureProvider(),
                VisionProvider(this),
                ShizukuProvider(this),
                RootProvider(),
            ))
            File(filesDir, "capabilities.json").writeText(resolver.toJson().toString(2))
        }.onFailure { appendDiagnostic("Capability snapshot failed: ${it.message}") }
    }

    private fun appendDiagnostic(line: String) {
        diagnostics += line.take(2_000)
        while (diagnostics.size > 300) diagnostics.removeAt(0)
    }

    private fun setStatus(status: ZCodeHostStatus) {
        currentStatus = status
        val text = when (status) {
            ZCodeHostStatus.Stopped -> "ZCode runtime 已停止"
            ZCodeHostStatus.Starting -> "ZCode runtime 正在启动"
            is ZCodeHostStatus.Running -> "ZCode ${status.version} 正在运行"
            is ZCodeHostStatus.Restarting -> "ZCode runtime 正在重启（${status.attempt}）"
            is ZCodeHostStatus.MissingRuntime -> "等待 ZCode runtime 组件"
            is ZCodeHostStatus.InvalidRuntime -> "ZCode runtime 无效"
        }
        getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification(text))
    }

    private fun notification(text: String) = NotificationCompat.Builder(this, CHANNEL)
        .setSmallIcon(R.drawable.ic_agent)
        .setContentTitle("Android Agent · ZCode")
        .setContentText(text)
        .setOngoing(requested.get())
        .setContentIntent(PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        ))
        .build()

    inner class LocalBinder : Binder() {
        fun service(): ZCodeHostService = this@ZCodeHostService
        fun status(): ZCodeHostStatus = currentStatus
        fun diagnostics(): List<String> = diagnostics.toList()
    }

    companion object {
        const val ACTION_STOP = "dev.alita.androidagent.zcode.STOP"
        private const val CHANNEL = "zcode-runtime"
        private const val NOTIFICATION_ID = 1002
    }
}
