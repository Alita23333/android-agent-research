package dev.alita.androidagent.zcode.runtime

import android.content.Context
import android.os.Bundle
import android.util.Log
import android.view.accessibility.AccessibilityNodeInfo
import dev.alita.androidagent.device.AgentAccessibilityService
import dev.alita.androidagent.zcode.adapter.AndroidToolDefinition
import dev.alita.androidagent.zcode.adapter.AndroidToolRequest
import dev.alita.androidagent.zcode.adapter.MutableAndroidToolCancellation
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

/**
 * Phase 8 W4 (runbook §5.2): the Kotlin half of the Android-dispatcher route.
 * Waits for the bridge, registers the eight ui_* tools at boot (before the
 * first tools/list), then runs the strictly-sequential pull loop
 * (/carrier/next → execute → /carrier/respond). The worker is the ONLY
 * component that touches the live AccessibilityService; every model-facing
 * rule is applied by the bridge's ui-tree.cjs through the /ui/render hop
 * (amendment C6).
 */
class ZCodeCarrierWorker(
    context: Context,
    private val dispatcher: dev.alita.androidagent.zcode.adapter.AndroidToolDispatcher,
    private val diagnostic: (String) -> Unit = {},
) {
    private val ctx = context.applicationContext
    private val lifecycle = Any()
    private val generation = AtomicInteger(0)
    @Volatile private var stopping = false
    private var workerThread: Thread? = null
    private val shutdownThreads = mutableSetOf<Thread>()
    private val connections = mutableSetOf<HttpURLConnection>()
    private val monitors = mutableSetOf<Thread>()
    private var activeCancellation: MutableAndroidToolCancellation? = null
    private class ActionLease {
        var running = false
        var cancelled = false
    }
    private val actions = mutableSetOf<ActionLease>()
    private val frames = ZCodeScreenFrames(ctx)
    private var activeCallId = ""
    private var activeSession = ""
    private var activeMetadata = JSONObject()

    companion object {
        private const val TAG = "CarrierWorker"
        private const val UI_CALL_DEADLINE_MS = 20000L   // §5.4 clock 1
        private const val UI_WAIT_MAX_MS = 10000         // §2.2 A14 clamp
        private const val UI_TYPE_MAX_CHARS = 512
        private const val POLL_INTERVAL_MS = 400L
        private const val STOP_TIMEOUT_MS = 3000L
        private val DESTRUCTIVE_VOCAB = Regex(
            "erase|wipe|factory[\\s_-]?reset|delete[\\s_-]?all|clear[\\s_-]?all[\\s_-]?data|format|uninstall|remove[\\s_-]?account|停用|恢复出厂|清除全部|卸载", RegexOption.IGNORE_CASE)

        // ---- the eight tool definitions (runbook §2.2) -----------------------
        private fun prop(desc: String, type: String, extra: JSONObject? = null): JSONObject {
            val j = JSONObject().put("type", type).put("description", desc)
            if (extra != null) {
                val it2 = extra.keys()
                while (it2.hasNext()) { val k = it2.next(); j.put(k, extra.get(k)) }
            }
            return j
        }

        private val TOOLS: Array<JSONObject> = arrayOf(
            JSONObject().put("toolId", "ui_dump").put("description", "Dump the normalized semantic tree of the foreground screen. Node ids like #12 come from ui_dump and go stale after navigation. Budgets: <=300 nodes, <=20 KiB. detail=compact|full; from=\"#N\" continues a truncated dump.")
                .put("readOnly", true).put("inputSchema", JSONObject().put("type", "object").put("additionalProperties", false).put("properties", JSONObject()
                    .put("maxNodes", prop("max emitted nodes (clamped to 300)", "integer", JSONObject().put("minimum", 1).put("maximum", 600).put("default", 300)))
                    .put("detail", prop("compact (default) or full", "string", JSONObject().put("enum", JSONArray().put("compact").put("full"))))
                    .put("from", prop("continue at this node id, same generation", "string"))
                    .put("includeBounds", prop("include [l,t][r,b] tokens", "boolean", JSONObject().put("default", true)))
                    .put("raw", prop("lab-only raw metrics", "boolean", JSONObject().put("default", false))))),
            JSONObject().put("toolId", "ui_find").put("description", "Find nodes in the current snapshot by selector (text substring case-insensitive, viewId, role, clickable, editable). Zero matches returns ui_not_found plus the snapshot.")
                .put("readOnly", true).put("inputSchema", JSONObject().put("type", "object").put("additionalProperties", false).put("properties", JSONObject()
                    .put("text", prop("case-insensitive substring", "string"))
                    .put("viewId", prop("exact or pkg:id/name suffix", "string"))
                    .put("role", prop("role filter", "string"))
                    .put("clickable", prop("filter", "boolean")).put("editable", prop("filter", "boolean"))
                    .put("index", prop("nth match", "integer", JSONObject().put("minimum", 0).put("default", 0)))
                    .put("treeId", prop("generation", "string")))),
            JSONObject().put("toolId", "ui_wait").put("description", "Wait for a UI condition: window_change | text_appear | node_appear | idle. Returns matched:false + the snapshot on timeout. timeoutMs is clamped to 10000.")
                .put("readOnly", true).put("inputSchema", JSONObject().put("type", "object").put("additionalProperties", false)
                    .put("required", JSONArray().put("wait_for")).put("properties", JSONObject()
                    .put("wait_for", prop("condition", "string", JSONObject().put("enum", JSONArray().put("window_change").put("text_appear").put("node_appear").put("idle"))))
                    .put("text", prop("text_appear", "string"))
                    .put("query", prop("node_appear selector", "object"))
                    .put("package", prop("window_change filter", "string"))
                    .put("gone", prop("invert node_appear", "boolean", JSONObject().put("default", false)))
                    .put("quiet_ms", prop("idle quiet window", "integer", JSONObject().put("minimum", 100).put("maximum", 2000).put("default", 300)))
                    .put("timeoutMs", prop("clamped to 10000", "integer", JSONObject().put("minimum", 100).put("maximum", 60000).put("default", 5000)))
                    .put("pollMs", prop("accepted, clamped to 120", "integer", JSONObject().put("default", 120))))),
            JSONObject().put("toolId", "ui_click").put("description", "Click a node by {treeId,nodeId} or selector. Destructive targets (erase/wipe/uninstall/...) require confirm:\"<exact label>\". On ui_stale_node re-run ui_dump and use a fresh id.")
                .put("readOnly", false).put("inputSchema", JSONObject().put("type", "object").put("additionalProperties", false).put("properties", JSONObject()
                    .put("treeId", prop("generation from ui_dump", "string")).put("nodeId", prop("#12 | 12 | g7:12", "string"))
                    .put("text", prop("selector shortcut", "string")).put("viewId", prop("selector", "string")).put("role", prop("selector", "string"))
                    .put("index", prop("nth selector match", "integer", JSONObject().put("minimum", 0).put("default", 0)))
                    .put("confirm", prop("exact target label for a destructive target", "string"))
                    .put("timeoutMs", prop("clamped to 10000", "integer", JSONObject().put("minimum", 100).put("maximum", 60000).put("default", 1500))))),
            JSONObject().put("toolId", "ui_long_press").put("description", "Long-press a node (ACTION_LONG_CLICK, gesture fallback). Same addressing and confirm rule as ui_click.")
                .put("readOnly", false).put("inputSchema", JSONObject().put("type", "object").put("additionalProperties", false).put("properties", JSONObject()
                    .put("treeId", prop("generation", "string")).put("nodeId", prop("#12", "string"))
                    .put("text", prop("selector", "string")).put("viewId", prop("selector", "string")).put("role", prop("selector", "string"))
                    .put("index", prop("nth match", "integer", JSONObject().put("minimum", 0).put("default", 0)))
                    .put("confirm", prop("destructive-target label", "string"))
                    .put("timeoutMs", prop("clamped to 10000", "integer", JSONObject().put("minimum", 100).put("maximum", 60000).put("default", 1500))))),
            JSONObject().put("toolId", "ui_type").put("description", "Type text into an editable node (ACTION_SET_TEXT; clear:true with text:\"\" clears). Values never appear in journals for password fields.")
                .put("readOnly", false).put("inputSchema", JSONObject().put("type", "object").put("additionalProperties", false)
                    .put("required", JSONArray().put("text")).put("properties", JSONObject()
                    .put("treeId", prop("generation", "string")).put("nodeId", prop("#12", "string"))
                    .put("viewId", prop("selector", "string")).put("role", prop("selector", "string")).put("index", prop("nth match", "integer", JSONObject().put("default", 0)))
                    .put("text", prop("the text to set (max 512 chars)", "string", JSONObject().put("maxLength", 512)))
                    .put("clear", prop("explicit clear (text must be \"\")", "boolean", JSONObject().put("default", false)))
                    .put("submit", prop("none | ime_enter", "string", JSONObject().put("enum", JSONArray().put("none").put("ime_enter")).put("default", "none"))))),
            JSONObject().put("toolId", "ui_scroll").put("description", "Scroll a container (or the main list when no target given) forward/backward. at_end:true is a legitimate terminal state, not an error.")
                .put("readOnly", false).put("inputSchema", JSONObject().put("type", "object").put("additionalProperties", false)
                    .put("required", JSONArray().put("direction")).put("properties", JSONObject()
                    .put("direction", prop("forward | backward", "string", JSONObject().put("enum", JSONArray().put("forward").put("backward"))))
                    .put("treeId", prop("generation", "string")).put("nodeId", prop("#12", "string")).put("viewId", prop("selector", "string")))),
            JSONObject().put("toolId", "ui_back").put("description", "Press BACK (performGlobalAction). Verified by a window-identity change; no visible effect is reported honestly, never retried more than once.")
                .put("readOnly", false).put("inputSchema", JSONObject().put("type", "object").put("additionalProperties", false).put("properties", JSONObject()
                    .put("expectedPackage", prop("refuse if the destination differs", "string")))),
        )
    }

    fun start() = synchronized(lifecycle) {
        if (!stopping && workerThread?.isAlive == true) return@synchronized
        check(quiescentLocked()) { "Previous carrier worker has not stopped" }
        monitors.clear()
        shutdownThreads.clear()
        stopping = false
        val workerGeneration = generation.incrementAndGet()
        workerThread = Thread({
            try { runLoop(workerGeneration) }
            catch (_: InterruptedException) { /* stop invalidates this generation */ }
            catch (error: Throwable) { Log.w(TAG, "carrier worker stopped: ${error.javaClass.simpleName}") }
        }, "carrier-worker").apply {
            isDaemon = false
            start()
        }
    }

    /** False means old work is still unwinding; callers must keep admission and restart closed. */
    fun stop(): Boolean {
        val deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(STOP_TIMEOUT_MS)
        val threads = synchronized(lifecycle) {
            stopping = true
            generation.incrementAndGet()
            shutdownThreads.removeAll { !it.isAlive }
            if (shutdownThreads.isEmpty()) {
                val cancellation = activeCancellation
                val pendingConnections = connections.toList()
                val interruptedThreads = (listOfNotNull(workerThread) + monitors).filter { it.isAlive }.distinct()
                // Android Thread.interrupt() invokes the target's I/O blocker synchronously.
                // It belongs off the lifecycle lock/caller just like disconnect()/cancel().
                // Separate tasks also prevent one blocked cleanup from delaying another.
                val cleanup: List<() -> Unit> = pendingConnections.map { connection ->
                    { runCatching { connection.disconnect() }; Unit }
                } + listOfNotNull(cancellation?.let { { it.cancel() } }) + interruptedThreads.map { thread ->
                    { runCatching { thread.interrupt() }; Unit }
                }
                cleanup.forEach { block ->
                    shutdownThreads += Thread(block, "carrier-shutdown").apply { isDaemon = true; start() }
                }
            }
            listOfNotNull(workerThread) + shutdownThreads.toList() + monitors.toList()
        }
        for (thread in threads.distinct()) {
            if (thread === Thread.currentThread()) continue
            val remaining = deadline - System.nanoTime()
            if (remaining <= 0) break
            try { thread.join(TimeUnit.NANOSECONDS.toMillis(remaining).coerceAtLeast(1)) }
            catch (_: InterruptedException) { Thread.currentThread().interrupt(); return false }
        }
        return isQuiescent()
    }

    fun isQuiescent(): Boolean = synchronized(lifecycle) { quiescentLocked() }

    private fun quiescentLocked(): Boolean = workerThread?.isAlive != true &&
        shutdownThreads.none(Thread::isAlive) && monitors.none(Thread::isAlive) &&
        connections.isEmpty() && activeCancellation == null && actions.isEmpty()

    private var port = 8765
    private var token = ""

    // ---- bridge plumbing -------------------------------------------------------

    private fun discoverEndpoint(): Boolean {
        return try {
            val epFile = File(ctx.filesDir, "runtime/carrier/endpoint.json")
            if (epFile.exists()) {
                val ep = JSONObject(epFile.readText())
                port = ep.optInt("port", 8765); token = ep.optString("token", "")
                token.isNotEmpty()
            } else {
                val t = File(ctx.filesDir, "runtime/bridge-token")
                if (t.exists()) { token = t.readText().trim(); true } else false
            }
        } catch (e: Throwable) { false }
    }

    private fun bridge(method: String, path: String, body: JSONObject? = null, timeoutMs: Int = 130000): Pair<Int, JSONObject?> {
        val conn = URL("http://127.0.0.1:$port$path").openConnection() as HttpURLConnection
        synchronized(lifecycle) {
            check(!stopping && !Thread.currentThread().isInterrupted) { "ui_cancelled" }
            connections += conn
        }
        return try {
            conn.requestMethod = method
            conn.connectTimeout = 10000
            conn.readTimeout = timeoutMs
            conn.setRequestProperty("X-Bridge-Token", token)
            if (body != null) {
                conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/json")
                conn.outputStream.use { it.write(body.toString().toByteArray()) }
            }
            val code = conn.responseCode
            val text = try { conn.inputStream.bufferedReader().readText() } catch (e: Throwable) { "" }
            val json = if (text.isNotEmpty()) try { JSONObject(text) } catch (e: Throwable) { null } else null
            code to json
        } catch (e: Throwable) { -1 to null } finally {
            try { conn.disconnect() } finally { synchronized(lifecycle) { connections -= conn } }
        }
    }

    private fun runLoop(workerGeneration: Int) {
        // wait for the bridge to be ready (§5.2: register BEFORE the first tools/list)
        while (workerGeneration == generation.get()) {
            if (discoverEndpoint()) {
                val (code, st) = bridge("GET", "/status", timeoutMs = 4000)
                if (code == 200 && st?.optString("phase") == "ready") break
            }
            Thread.sleep(600)
        }
        if (workerGeneration != generation.get()) return
        val dispatcherDefinitions = runBlocking { dispatcher.definitions() }
        if (workerGeneration != generation.get()) return
        require(dispatcherDefinitions.map { it.id.replace('.', '_') }.distinct().size == dispatcherDefinitions.size) {
            "Android carrier wire tool ID collision"
        }
        val dispatcherByWireId = dispatcherDefinitions.associateBy { it.id.replace('.', '_') }
        val registeredTools = JSONArray()
        TOOLS.forEach(registeredTools::put)
        registeredTools.put(JSONObject("""{"toolId":"ui_screenshot","readOnly":true,"description":"Capture a bounded live screen observation. Returns shotId and metadata only; pixels remain private on this device. Secure windows are refused. Use ui_see to explicitly send a frame to your configured vision provider.","inputSchema":{"type":"object","additionalProperties":false,"properties":{"maxLongEdge":{"type":"integer","minimum":320,"maximum":1568}}}}"""))
        registeredTools.put(JSONObject("""{"toolId":"ui_tap","readOnly":false,"description":"Tap display pixel coordinates. When based on a vision observation, include its shotId; stale generation, rotation or session is refused. A dispatched gesture is verified against the current UI tree and is never automatically repeated.","inputSchema":{"type":"object","additionalProperties":false,"required":["x","y"],"properties":{"x":{"type":"integer","minimum":0},"y":{"type":"integer","minimum":0},"shotId":{"type":"string"},"label":{"type":"string","maxLength":200},"longPress":{"type":"boolean"},"timeoutMs":{"type":"integer","minimum":100,"maximum":10000}}}}"""))
        dispatcherDefinitions.forEach { registeredTools.put(toWireDefinition(it)) }
        if (workerGeneration != generation.get()) return
        val (rc, _) = bridge("POST", "/carrier/register", JSONObject().put("tools", registeredTools))
        Log.i(TAG, "registered ${TOOLS.size} ui tools and ${dispatcherDefinitions.size} Android tools (rc=$rc)")
        diagnostic("Carrier registered ${registeredTools.length()} tools")
        while (workerGeneration == generation.get()) {
            try {
                val (code, call) = bridge("GET", "/carrier/next", timeoutMs = 0.coerceAtLeast(120000))
                if (workerGeneration != generation.get()) return
                if (code != 200 || call == null) { Thread.sleep(POLL_INTERVAL_MS); continue }
                val callId = call.optString("callId")
                val toolId = call.optString("toolId")
                val args = call.optJSONObject("arguments") ?: JSONObject()
                activeCallId = callId
                activeSession = call.optJSONObject("meta")?.optString("sessionId").orEmpty()
                activeMetadata = call.optJSONObject("meta") ?: JSONObject()
                val result = try {
                    if (toolId.startsWith("ui_")) execute(toolId, args)
                    else executeDispatcher(callId, toolId, args, dispatcherByWireId)
                } catch (t: Throwable) {
                    val cause = generateSequence(t) { it.cause }.last()
                    val code = cause.message?.takeIf { it.matches(Regex("ui_[a-z_]+")) }
                    failEnvelope(toolId, code ?: if (toolId.startsWith("ui_")) "ui_internal" else "DISPATCH_FAILED", cause.message ?: cause.javaClass.simpleName)
                }
                if (workerGeneration != generation.get()) return
                // respond shape: text = the model-facing text (the dump block or
                // a one-line verdict); structuredContent = the full §2.3 envelope
                // (the bridge's ui_action writer reads action/treeId/nodeText/
                // verify/evidence/... from it)
                val text = result.remove("_text")?.toString()
                    ?: "${if (result.optBoolean("ok")) "ok" else "failed"}: $toolId ${result.optJSONObject("error")?.optString("code") ?: ""}"
                // a core-abandoned call may 404 — log and continue (§5.2)
                val (rc2, _) = bridge("POST", "/carrier/respond", JSONObject()
                    .put("callId", callId).put("ok", result.optBoolean("ok"))
                    .put("text", text).put("structuredContent", result)
                    .put("artifacts", result.optJSONArray("artifacts")))
                if (rc2 == 404) Log.w(TAG, "respond 404 for $callId (abandoned)")
            } catch (e: Throwable) {
                if (workerGeneration != generation.get() || Thread.currentThread().isInterrupted) return
                Log.w(TAG, "pull loop error: ${e.message}")
                Thread.sleep(1000)
            }
        }
    }

    private fun toWireDefinition(definition: AndroidToolDefinition): JSONObject = JSONObject()
        .put("toolId", definition.id.replace('.', '_'))
        .put("description", definition.description)
        .put("inputSchema", definition.inputSchema)
        .put("readOnly", definition.readOnly)
        .put("metadata", JSONObject()
            .put("canonicalToolId", definition.id)
            .put("version", definition.version)
            .apply { definition.providerContentHash?.let { put("providerContentHash", it) } }
            .apply { definition.providerDefinitionHash?.let { put("providerDefinitionHash", it) } }
            .put("capabilities", JSONArray(definition.capabilities.toList())))

    private fun executeDispatcher(
        callId: String,
        wireToolId: String,
        args: JSONObject,
        definitions: Map<String, AndroidToolDefinition>,
    ): JSONObject {
        assertCallActive() // Registered native providers share the same Gateway admission
        val definition = definitions[wireToolId]
            ?: return failEnvelope(wireToolId, "TOOL_NOT_EXPOSED", "Unknown Android carrier tool")
        val request = AndroidToolRequest(
            requestId = callId,
            toolId = definition.id,
            arguments = args,
            sessionId = activeSession,
            metadata = JSONObject().put("carrierToolId", wireToolId).apply {
                if (definition.providerContentHash != null) {
                    val hash = activeMetadata.optString("providerContentHash")
                    val declaration = activeMetadata.optString("providerDefinitionHash")
                    require(hash.matches(Regex("[a-f0-9]{64}")) && declaration.matches(Regex("[a-f0-9]{64}")))
                    put("providerContentHash", hash); put("providerDefinitionHash", declaration)
                }
            },
        )
        val cancellation = MutableAndroidToolCancellation()
        val live = java.util.concurrent.atomic.AtomicBoolean(true)
        val callId = activeCallId
        val monitor = Thread({
            try {
                while (live.get()) {
                    Thread.sleep(150)
                    val (code, response) = bridge("GET", "/carrier/active?callId=$callId", timeoutMs = 2000)
                    if (live.get() && (code != 200 || response?.optBoolean("active") != true || !response.optBoolean("authorized"))) {
                        cancellation.cancel(); break
                    }
                }
            } catch (_: InterruptedException) { }
            catch (_: Exception) { cancellation.cancel() }
        }, "provider-cancellation").apply { isDaemon = true }
        synchronized(lifecycle) {
            check(!stopping && !Thread.currentThread().isInterrupted) { "ui_cancelled" }
            monitors.removeAll { !it.isAlive }
            activeCancellation = cancellation
            monitors += monitor
            monitor.start()
        }
        val result = try { runBlocking { dispatcher.execute(request, cancellation) } }
            finally {
                live.set(false); monitor.interrupt()
                synchronized(lifecycle) { if (activeCancellation === cancellation) activeCancellation = null }
            }
        if (cancellation.isCancelled) return failEnvelope(wireToolId, "CANCELLED", "Provider call no longer active")
        assertCallActive()
        return JSONObject()
            .put("ok", result.ok)
            .put("tool", wireToolId)
            .put("action", "dispatch")
            .put("performed", result.ok)
            .put("verified", result.ok)
            .apply {
                if (result.ok) put("data", result.data) else put("error", result.error?.toJson())
                if (result.artifacts.isNotEmpty()) put("artifacts", JSONArray(result.artifacts.map { it.toJson() }))
                put("_text", if (result.ok) result.data.toString() else result.error?.message.orEmpty())
            }
    }

    // ---- envelope helpers -------------------------------------------------------

    private fun envelope(toolId: String, ok: Boolean, action: String, more: JSONObject.() -> Unit = {}): JSONObject {
        val e = JSONObject().put("ok", ok).put("tool", toolId).put("action", action)
        e.more()
        return e
    }

    private fun failEnvelope(toolId: String, code: String?, hint: String?): JSONObject =
        envelope(toolId, false, "error") {
            put("performed", false); put("verified", false)
            put("error", JSONObject().put("code", code ?: "ui_error").put("message", hint ?: code ?: "error"))
        }

    private fun renderThroughBridge(raw: JSONObject?, opts: JSONObject = JSONObject(), find: JSONObject? = null): JSONObject? {
        raw ?: return null
        val body = JSONObject().put("raw", raw).put("opts", opts)
        if (find != null) body.put("find", find)   // top-level: the bridge reads it there
        val (code, resp) = bridge("POST", "/ui/render", body, timeoutMs = 8000)
        if (code == 200 && resp != null) {
            resp.optJSONArray("nodeTargets")?.let {
                AgentAccessibilityService.instance?.installNodeTargets(raw.optInt("generation"), it)
            }
        }
        return if (code == 200) resp else null
    }

    // ---- the tool executions ----------------------------------------------------

    private fun execute(toolId: String, args: JSONObject): JSONObject {
        assertCallActive() // Gateway intent must remain bound before any UI observation/action
        val svc = AgentAccessibilityService.instance
            ?: return failEnvelope(toolId, "ui_a11y_disabled", "accessibility service not connected — enable it in system settings")
        if (toolId == "ui_screenshot") return doScreenshot(svc, args)
        return onAccessibilityExec(svc) { dispatch(svc, toolId, args) }
    }

    private fun assertCallActive() {
        check(!stopping && !Thread.currentThread().isInterrupted) { "ui_cancelled" }
        val (code, response) = bridge("GET", "/carrier/active?callId=$activeCallId", timeoutMs = 2000)
        check(code == 200 && response?.optBoolean("active") == true && response.optBoolean("authorized")) { "ui_cancelled" }
    }

    /** onExec's Future may be cancelled before an already-running callback returns. */
    private fun <T> onAccessibilityExec(svc: AgentAccessibilityService, block: () -> T): T {
        val lease = ActionLease()
        val callbackGeneration = synchronized(lifecycle) {
            check(!stopping && !Thread.currentThread().isInterrupted) { "ui_cancelled" }
            actions += lease
            generation.get()
        }
        try {
            return svc.onExec {
                synchronized(lifecycle) {
                    check(!lease.cancelled && !stopping && generation.get() == callbackGeneration) { "ui_cancelled" }
                    lease.running = true
                }
                try { block() } finally { synchronized(lifecycle) { actions -= lease } }
            }
        } finally {
            synchronized(lifecycle) {
                // A cancelled queued callback must never become runnable after restart.
                if (!lease.running) { lease.cancelled = true; actions -= lease }
            }
        }
    }

    private fun doScreenshot(svc: AgentAccessibilityService, args: JSONObject): JSONObject {
        require(args.keys().asSequence().all { it == "maxLongEdge" }) { "ui_invalid_input" }
        val edge = args.optInt("maxLongEdge", 1080)
        require(edge in 320..1568) { "ui_invalid_input" }
        assertCallActive()
        val before = onAccessibilityExec(svc) { svc.captureRaw() }
        before.error?.let { return failEnvelope("ui_screenshot", it, it) }
        val raw = requireNotNull(before.raw)
        val b = requireNotNull(raw.optJSONObject("window")?.optJSONArray("bounds"))
        val windowBounds = android.graphics.Rect(b.getInt(0), b.getInt(1), b.getInt(2), b.getInt(3))
        val image = svc.captureScreen(edge, before.frame!!.windowId, windowBounds)
        assertCallActive()
        val after = onAccessibilityExec(svc) { svc.captureRaw() }
        val gen = requireNotNull(before.raw).optInt("generation")
        check(after.raw?.optInt("generation") == gen && svc.displayGeometry().third == image.rotation) { "ui_screenshot_geometry_changed" }
        val metadata = JSONObject().put("width", image.width).put("height", image.height)
            .put("screenW", image.screenWidth).put("screenH", image.screenHeight)
            .put("screenWidth", image.screenWidth).put("screenHeight", image.screenHeight)
            .put("generation", gen).put("treeId", "g$gen").put("rotation", image.rotation)
            .put("captureScope", "active_window").put("windowBounds", b)
            .put("observationEpoch", svc.observationEpoch)
        val saved = frames.save(image.bytes, metadata, activeSession)
        try { assertCallActive() } catch (error: Throwable) { frames.purge(); throw error }
        return envelope("ui_screenshot", true, "screenshot") {
            saved.keys().forEach { put(it, saved.get(it)) }
            put("performed", false); put("verified", false); put("verify", "skipped")
            put("scale", image.width.toDouble() / image.screenWidth); put("error", JSONObject.NULL)
        }
    }

    private fun doTap(svc: AgentAccessibilityService, args: JSONObject): JSONObject {
        val tool = "ui_tap"
        if (svc.imeVisible()) return failEnvelope(tool, "ui_ime_visible", "close the keyboard and obtain a new observation before coordinate actions")
        require(args.keys().asSequence().all { it in setOf("x", "y", "shotId", "label", "longPress", "timeoutMs") }) { "ui_invalid_input" }
        require(args.opt("x") is Number && args.opt("y") is Number) { "ui_invalid_input" }
        val xd = args.getDouble("x"); val yd = args.getDouble("y")
        require(xd.isFinite() && yd.isFinite() && xd == xd.toInt().toDouble() && yd == yd.toInt().toDouble()) { "ui_invalid_input" }
        val x = xd.toInt(); val y = yd.toInt()
        val before = svc.captureRaw()
        before.error?.let { return failEnvelope(tool, it, it) }
        if (activeMetadata.optString("tapTreeId") != "g${before.raw?.optInt("generation")}" ||
            activeMetadata.optString("tapEpoch") != svc.observationEpoch)
            return failEnvelope(tool, "ui_stale_node", "target changed after Gateway preflight; inspect again")
        val geometry = svc.displayGeometry()
        if (x !in 0 until geometry.first || y !in 0 until geometry.second) return failEnvelope(tool, "ui_coordinate_out_of_bounds", "display pixel bounds exceeded")
        if (args.has("shotId")) {
            val shot = frames.resolve(args.getString("shotId"), activeSession)
                ?: return failEnvelope(tool, "ui_stale_shot", "frame expired or belongs to another session")
            if (shot.optString("observationEpoch") != svc.observationEpoch ||
                System.currentTimeMillis() - shot.optLong("capturedAt") > 30000 ||
                shot.optInt("generation") != before.raw?.optInt("generation") || shot.optInt("rotation") != geometry.third ||
                shot.optInt("screenW") != geometry.first || shot.optInt("screenH") != geometry.second)
                return failEnvelope(tool, "ui_stale_shot", "UI generation or geometry changed; inspect again")
        }
        assertCallActive()
        val performed = svc.gestureAt(android.graphics.Rect(x, y, x + 1, y + 1), args.optBoolean("longPress"))
        val deadline = System.currentTimeMillis() + args.optInt("timeoutMs", 1500).coerceIn(100, 10000)
        var after = before
        var verified = false
        while (performed && System.currentTimeMillis() < deadline && !verified) {
            Thread.sleep(100)
            after = svc.captureRaw()
            verified = after.raw != null && fingerprintChanged(before.raw!!, after.raw!!)
        }
        val rendered = renderThroughBridge(after.raw)?.optJSONObject("render")
        return envelope(tool, performed && verified, "tap") {
            put("performed", performed); put("verified", verified); put("method", "gesture_dispatch")
            put("x", x); put("y", y); put("shotId", args.optString("shotId")); put("retries", 0)
            put("treeId", "g${after.raw?.optInt("generation")}")
            put("evidence", if (verified) "UI tree changed" else "no observable tree change; gesture may have had an effect")
            put("snapshot", JSONObject().put("nodes", rendered?.optJSONArray("nodes") ?: JSONArray()))
            if (!verified) put("error", JSONObject().put("code", "ui_not_verified"))
        }
    }

    private fun dispatch(svc: AgentAccessibilityService, toolId: String, args: JSONObject): JSONObject {
        val started = System.currentTimeMillis()
        return when (toolId) {
            "ui_tap" -> doTap(svc, args)
            "ui_dump" -> doDump(svc, args, started)
            "ui_find" -> doFind(svc, args, started)
            "ui_wait" -> doWait(svc, args, started)
            "ui_click" -> doClick(svc, args, started, longPress = false)
            "ui_long_press" -> doClick(svc, args, started, longPress = true)
            "ui_type" -> doType(svc, args, started)
            "ui_scroll" -> doScroll(svc, args, started)
            "ui_back" -> doBack(svc, args, started)
            else -> failEnvelope(toolId, "ui_invalid_input", "unknown toolId $toolId")
        }
    }

    private fun clampTimeout(args: JSONObject): Pair<Long, Boolean> {
        val raw = args.optInt("timeoutMs", 5000)
        val clamped = raw > UI_WAIT_MAX_MS
        return (if (clamped) UI_WAIT_MAX_MS else raw).toLong() to clamped
    }

    private fun doDump(svc: AgentAccessibilityService, args: JSONObject, started: Long): JSONObject {
        val cap = svc.captureRaw()
        if (cap.error != null) return failEnvelope("ui_dump", cap.error, cap.error)
        val opts = JSONObject()
        if (args.has("maxNodes")) opts.put("maxNodes", args.optInt("maxNodes"))
        if (args.has("from")) opts.put("from", args.optString("from"))
        if (args.has("includeBounds")) opts.put("includeBounds", args.optBoolean("includeBounds"))
        if (args.optBoolean("raw", false)) opts.put("raw", true)
        val rendered = renderThroughBridge(cap.raw, opts)
            ?: return failEnvelope("ui_dump", "ui_internal", "bridge render hop failed")
        val r = rendered.optJSONObject("render") ?: return failEnvelope("ui_dump", "ui_internal", "no render")
        return envelope("ui_dump", true, "dump") {
            put("treeId", "g${cap.raw!!.optInt("generation")}")
            put("performed", true); put("verified", true)
            put("clamped", r.optBoolean("clamped", false))
            val geometry = svc.displayGeometry()
            put("snapshot", JSONObject().put("nodes", r.optJSONArray("nodes"))
                .put("screenW", geometry.first).put("screenH", geometry.second).put("rotation", geometry.third))
            put("nodes", r.optJSONArray("nodes"))
            put("_text", r.optString("text"))
            put("elapsedMs", System.currentTimeMillis() - started)
        }
    }

    private fun doFind(svc: AgentAccessibilityService, args: JSONObject, started: Long): JSONObject {
        val cap = svc.captureRaw()
        if (cap.error != null) return failEnvelope("ui_find", cap.error, cap.error)
        val find = JSONObject()
        for (k in listOf("text", "viewId", "role", "clickable", "editable")) if (args.has(k)) find.put(k, args.get(k))
        val rendered = renderThroughBridge(cap.raw, JSONObject(), find)
            ?: return failEnvelope("ui_find", "ui_internal", "bridge render hop failed")
        val matches = rendered.optJSONArray("matches") ?: JSONArray()
        val idx = args.optInt("index", 0)
        if (matches.length() == 0) {
            val snap = rendered.optJSONObject("render")?.optJSONArray("nodes") ?: JSONArray()
            return envelope("ui_find", false, "find") {
                put("performed", true); put("verified", true); put("matches", JSONArray())
                put("treeId", "g${cap.raw!!.optInt("generation")}")
                put("snapshot", JSONObject().put("nodes", snap))
                put("error", JSONObject().put("code", "ui_not_found").put("message", "zero matches; snapshot attached"))
                put("elapsedMs", System.currentTimeMillis() - started)
            }
        }
        val m = matches.optJSONObject(idx.coerceAtMost(matches.length() - 1)) ?: matches.optJSONObject(0)
        return envelope("ui_find", true, "find") {
            put("treeId", "g${cap.raw!!.optInt("generation")}")
            put("nodeId", "#${m.optInt("id")}")
            put("matches", matches); put("performed", true); put("verified", true)
            put("elapsedMs", System.currentTimeMillis() - started)
        }
    }

    private fun doWait(svc: AgentAccessibilityService, args: JSONObject, started: Long): JSONObject {
        val (timeoutMs, clamped) = clampTimeout(args)
        val wait_for = args.optString("wait_for")
        val baseline = svc.eventCountsSnapshot()
        val entry = svc.captureRaw()
        val entryWindow = entry.raw?.optJSONObject("window")?.toString()
        val deadline = System.currentTimeMillis() + timeoutMs
        var matched = false; var lastRender: JSONObject? = null; var source = "poll"
        while (!matched && System.currentTimeMillis() < deadline) {
            val cap = svc.captureRaw()
            if (cap.error != null) return failEnvelope("ui_wait", cap.error, cap.error)
            when (wait_for) {
                "window_change" -> {
                    val w = cap.raw?.optJSONObject("window")?.toString()
                    val pkgOk = !args.has("package") || cap.raw?.optString("app") == args.optString("package")
                    matched = w != entryWindow && pkgOk
                }
                "text_appear", "node_appear" -> {
                    val sel = if (wait_for == "text_appear") JSONObject().put("text", args.optString("text"))
                              else args.optJSONObject("query") ?: JSONObject()
                    val rendered = renderThroughBridge(cap.raw, JSONObject(), sel)
                    val n = rendered?.optJSONArray("matches")?.length() ?: 0
                    matched = if (args.optBoolean("gone", false)) n == 0 else n > 0
                    lastRender = rendered?.optJSONObject("render")
                }
                "idle" -> {
                    val quiet = args.optInt("quiet_ms", 300)
                    val since = svc.eventsSince(baseline)
                    matched = since.isEmpty() && System.currentTimeMillis() - started >= quiet * 2
                }
                else -> return failEnvelope("ui_wait", "ui_invalid_input", "wait_for must be window_change|text_appear|node_appear|idle")
            }
            if (!matched) Thread.sleep(120)
        }
        val cap = svc.captureRaw()
        val rendered = lastRender ?: renderThroughBridge(cap.raw)?.optJSONObject("render")
        val nodes = rendered?.optJSONArray("nodes") ?: JSONArray()
        return envelope("ui_wait", true, "wait") {
            put("matched", matched); put("source_of_truth", source)
            put("timeoutClamped", clamped); put("elapsedMs", System.currentTimeMillis() - started)
            put("treeId", "g${cap.raw?.optInt("generation", 0)}")
            put("events_seen", JSONObject(svc.eventsSince(baseline)))
            put("snapshot", JSONObject().put("nodes", nodes))
            put("performed", true); put("verified", matched)
        }
    }

    /** Resolve the addressed node: {treeId,nodeId} or selector (§2.2). */
    private fun resolve(svc: AgentAccessibilityService, args: JSONObject, kind: String): Pair<AgentAccessibilityService.ResolveResult, JSONObject> {
        val cap = svc.captureRaw()
        if (cap.error != null) return AgentAccessibilityService.ResolveResult(null, null, cap.error) to JSONObject()
        if (args.has("nodeId")) {
            val r = svc.resolveTarget(args.optString("treeId").takeIf { it.isNotEmpty() }, args.optString("nodeId"),
                requireClickable = kind == "click", requireEditable = kind == "type", requireScrollable = kind == "scroll")
            return r to (cap.raw ?: JSONObject())
        }
        // selector shortcut: render+find, then address the match by id
        val sel = JSONObject()
        for (k in listOf("text", "viewId", "role")) if (args.has(k)) sel.put(k, args.get(k))
        if (sel.length() == 0) return AgentAccessibilityService.ResolveResult(null, null, "ui_invalid_input", "nodeId or a selector required") to JSONObject()
        val rendered = renderThroughBridge(cap.raw, JSONObject(), sel)
            ?: return AgentAccessibilityService.ResolveResult(null, null, "ui_internal", "render hop failed") to JSONObject()
        val matches = rendered.optJSONArray("matches") ?: JSONArray()
        if (matches.length() == 0) return AgentAccessibilityService.ResolveResult(null, null, "ui_not_found", "selector matched nothing") to JSONObject()
        val m = matches.optJSONObject(args.optInt("index", 0).coerceAtMost(matches.length() - 1))
        val r = svc.resolveTarget(null, "#${m.optInt("id")}",
            requireClickable = kind == "click", requireEditable = kind == "type", requireScrollable = kind == "scroll")
        return r to (cap.raw ?: JSONObject())
    }

    private fun doClick(svc: AgentAccessibilityService, args: JSONObject, started: Long, longPress: Boolean): JSONObject {
        val tool = if (longPress) "ui_long_press" else "ui_click"
        val beforeCap = svc.captureRaw()
        if (beforeCap.error != null) return failEnvelope(tool, beforeCap.error, beforeCap.error)
        val before = JSONObject()
            .put("treeId", "g${beforeCap.raw!!.optInt("generation")}")
            .put("app", beforeCap.raw!!.optString("app"))
            .put("screen", beforeCap.raw!!.optString("screen"))
        val (res, _) = resolve(svc, args, "click")
        if (res.error != null) return failEnvelope(tool, res.error, res.hint)
        val node = res.node!!
        val label = node.text?.toString() ?: node.contentDescription?.toString() ?: ""
        // §4.6 stage 1: the worker alone sees the tree — refuse a destructive
        // label unless the exact confirm string is carried (stage 2 = Gateway)
        if (DESTRUCTIVE_VOCAB.containsMatchIn(label) && args.optString("confirm") != label) {
            return envelope(tool, false, if (longPress) "long_press" else "click") {
                put("performed", false); put("verified", false); put("before", before)
                put("error", JSONObject().put("code", "ui_hard_confirm_required")
                    .put("message", "destructive target: re-issue with confirm:\"$label\""))
            }
        }
        var method = "action"
        var performed = svc.performNodeAction(node,
            if (longPress) AccessibilityNodeInfo.ACTION_LONG_CLICK else AccessibilityNodeInfo.ACTION_CLICK)
        if (!performed) {
            val b = android.graphics.Rect().also { node.getBoundsInScreen(it) }
            performed = svc.gestureAt(b, longPress)
            method = "gesture"
        }
        // verify (§4.2): fresh snapshot vs before — checked flip / node gone / window change
        var evidence: String? = null; var verified = false
        val vDeadline = System.currentTimeMillis() + 1500
        while (!verified && System.currentTimeMillis() < vDeadline) {
            Thread.sleep(100)
            val after = svc.captureRaw()
            val a = after.raw ?: continue
            if (a.optJSONObject("window")?.toString() != beforeCap.raw?.optJSONObject("window")?.toString()) {
                verified = true; evidence = "window changed"
            } else if (fingerprintChanged(beforeCap.raw!!, a)) {
                verified = true; evidence = "tree changed"
            }
        }
        val afterCap = svc.captureRaw()
        val afterJ = JSONObject()
            .put("treeId", "g${afterCap.raw?.optInt("generation", 0)}")
            .put("app", afterCap.raw?.optString("app", ""))
            .put("screen", afterCap.raw?.optString("screen", ""))
        val afterRender = renderThroughBridge(afterCap.raw)?.optJSONObject("render")
        return envelope(tool, performed && verified, if (longPress) "long_press" else "click") {
            put("treeId", before.optString("treeId")); put("nodeId", args.optString("nodeId"))
            put("performed", performed); put("verified", verified); put("method", method)
            put("evidence", evidence ?: "no observable change")
            put("nodeText", label.take(200))
            put("before", before); put("after", afterJ)
            put("retries", 0)
            put("snapshot", JSONObject().put("nodes", afterRender?.optJSONArray("nodes") ?: JSONArray()))
            if (!verified) put("error", JSONObject().put("code", "ui_not_verified").put("message", evidence ?: "no observable change within the verify window"))
            put("elapsedMs", System.currentTimeMillis() - started)
        }
    }

    private fun fingerprintChanged(a: JSONObject, b: JSONObject): Boolean {
        // coarse: compare screen + window + first-level child count + label hash
        return a.optString("screen") != b.optString("screen") ||
            a.optJSONObject("window")?.toString() != b.optJSONObject("window")?.toString() ||
            treeHash(a) != treeHash(b)
    }

    private fun treeHash(raw: JSONObject): String {
        val sb = StringBuilder()
        fun walk(j: JSONObject) {
            sb.append(j.optString("t")).append('|').append(j.optString("cd")).append('|')
                .append(j.optBoolean("chk")).append('|')
            val kids = j.optJSONArray("children") ?: return
            for (i in 0 until kids.length()) walk(kids.getJSONObject(i))
        }
        raw.optJSONArray("nodes")?.optJSONObject(0)?.let { walk(it) }
        return Integer.toHexString(sb.toString().hashCode())
    }

    private fun doType(svc: AgentAccessibilityService, args: JSONObject, started: Long): JSONObject {
        val text = args.optString("text")
        if (text.length > UI_TYPE_MAX_CHARS) return failEnvelope("ui_type", "ui_text_too_long", "max 512 chars")
        val clear = args.optBoolean("clear", false)
        if (clear && text.isNotEmpty()) return failEnvelope("ui_type", "ui_invalid_input", "clear:true requires text:\"\"")
        // ui_type: `text` is the PAYLOAD, never a selector key — strip it
        // before resolving (measured: text polluted the selector and every
        // type on a fresh field failed with ui_not_found)
        val selArgs = JSONObject(args.toString()).also {
            it.remove("text"); it.remove("clear"); it.remove("submit")
        }
        val (res, _) = resolve(svc, selArgs, "type")
        if (res.error != null) return failEnvelope("ui_type", res.error, res.hint)
        val node = res.node!!
        val isPwd = node.isPassword
        val value = if (clear) "" else text
        val b = Bundle()
        b.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, value)
        val performed = svc.performNodeAction(node, AccessibilityNodeInfo.ACTION_SET_TEXT, b)
        var verified = false; var observed: String? = null
        if (performed) {
            node.refresh()
            observed = node.text?.toString()
            verified = observed == value
        }
        var submitPerformed: Boolean? = null
        if (verified && args.optString("submit") == "ime_enter" && android.os.Build.VERSION.SDK_INT >= 30) {
            // API 30 exposes the object form only (runbook §4.1 — no int constant)
            submitPerformed = svc.performNodeAction(node,
                AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.id)
        }
        return envelope("ui_type", performed && verified, "type") {
            put("performed", performed); put("verified", verified)
            put("nodeId", args.optString("nodeId")); put("nodeText", "")
            if (isPwd) { put("passwordNode", true); put("observed", "•••") }
            else { put("observed", observed); put("requested", value) }
            put("evidence", if (verified) "text equals requested" else "text mismatch (maxLength/filter?)")
            if (submitPerformed != null) put("submitPerformed", submitPerformed)
            if (!verified) put("error", JSONObject().put("code", "ui_not_verified").put("message", "set-text did not read back"))
            put("elapsedMs", System.currentTimeMillis() - started)
        }
    }

    private fun doScroll(svc: AgentAccessibilityService, args: JSONObject, started: Long): JSONObject {
        val forward = args.optString("direction") == "forward"
        if (args.optString("direction") !in listOf("forward", "backward"))
            return failEnvelope("ui_scroll", "ui_invalid_input", "direction must be forward|backward")
        val beforeCap = svc.captureRaw()
        if (beforeCap.error != null) return failEnvelope("ui_scroll", beforeCap.error, beforeCap.error)
        val (res, _) = resolve(svc, args, "scroll")
        var method = "action"; var performed = false
        if (res.error == null && res.node != null) {
            performed = svc.performNodeAction(res.node!!,
                if (forward) AccessibilityNodeInfo.ACTION_SCROLL_FORWARD else AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD)
        } else if (res.error == "ui_not_actionable" || res.error == "ui_not_found" || res.error == "ui_invalid_input") {
            // no target given / not scrollable: swipe the main window bounds
            val w = beforeCap.raw?.optJSONObject("window")?.optJSONArray("bounds")
            if (w != null && w.length() == 4) {
                val r = android.graphics.Rect(w.getInt(0), w.getInt(1), w.getInt(2), w.getInt(3))
                performed = svc.swipeInBounds(r, forward); method = "gesture"
            }
        } else return failEnvelope("ui_scroll", res.error, res.hint)
        if (!performed && res.node != null) {
            val b = android.graphics.Rect().also { res.node!!.getBoundsInScreen(it) }
            performed = svc.swipeInBounds(b, forward); method = "gesture"
        }
        // settle + verify (§4.2): first visible descendant texts changed
        Thread.sleep(300)
        val afterCap = svc.captureRaw()
        val changed = fingerprintChanged(beforeCap.raw ?: JSONObject(), afterCap.raw ?: JSONObject())
        val atEnd = performed && !changed
        return envelope("ui_scroll", performed && (changed || atEnd), "scroll") {
            put("performed", performed); put("verified", changed)
            put("method", method); put("at_end", atEnd)
            put("evidence", if (changed) "visible content changed" else if (atEnd) "no further movement (at end)" else "no change")
            put("treeId", "g${beforeCap.raw?.optInt("generation", 0)}")
            put("nodeId", args.optString("nodeId"))
            if (atEnd) put("error", JSONObject().put("code", "ui_nothing_to_scroll").put("message", "terminal state: no further movement $args-direction"))
            put("elapsedMs", System.currentTimeMillis() - started)
        }
    }

    private fun doBack(svc: AgentAccessibilityService, args: JSONObject, started: Long): JSONObject {
        val beforeCap = svc.captureRaw()
        if (beforeCap.error != null) return failEnvelope("ui_back", beforeCap.error, beforeCap.error)
        val beforeW = beforeCap.raw?.optJSONObject("window")?.toString()
        val beforeScreen = beforeCap.raw?.optString("screen")
        val performed = svc.globalBack()
        Thread.sleep(400)
        val afterCap = svc.captureRaw()
        val afterW = afterCap.raw?.optJSONObject("window")?.toString()
        val afterScreen = afterCap.raw?.optString("screen")
        val verified = performed && (afterW != beforeW || afterScreen != beforeScreen)
        val appNow = afterCap.raw?.optString("app", "")
        if (args.has("expectedPackage") && verified && appNow != args.optString("expectedPackage")) {
            return envelope("ui_back", false, "back") {
                put("performed", performed); put("verified", false)
                put("error", JSONObject().put("code", "ui_unexpected_destination")
                    .put("message", "landed on $appNow, expected ${args.optString("expectedPackage")}"))
                put("elapsedMs", System.currentTimeMillis() - started)
            }
        }
        return envelope("ui_back", performed && verified, "back") {
            put("performed", performed); put("verified", verified)
            put("evidence", if (verified) "window identity changed" else "back had no visible effect")
            put("snapshot", JSONObject().put("nodes", JSONArray()))
            if (!verified) put("error", JSONObject().put("code", "ui_not_verified").put("message", "no visible effect"))
            put("elapsedMs", System.currentTimeMillis() - started)
        }
    }
}

