package dev.alita.androidagent

import android.app.UiAutomation
import android.os.ParcelFileDescriptor
import android.graphics.Bitmap
import android.os.Build
import android.view.KeyEvent
import android.view.accessibility.AccessibilityNodeInfo
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/** Real Compose controls + real system SAF + test-only read-only documents + actual model. */
@RunWith(AndroidJUnit4::class)
class SkillManagerUiDeviceTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val store get() = (context.applicationContext as AgentApplication).graph.coreSkillPackages
    private val ui get() = instrumentation.getUiAutomation(UiAutomation.FLAG_DONT_SUPPRESS_ACCESSIBILITY_SERVICES)
    private val report = JSONObject()
    private val reportFile get() = File(context.cacheDir, "skill-ui1-result.json")
    private fun save() = reportFile.writeText(report.toString(2))
    private fun stage(value: String) { report.put("stage", value); save() }
    private fun screenshot(stage: String) {
        val active = ui.rootInActiveWindow?.packageName?.toString() ?: return
        if (active != context.packageName && !active.contains("documentsui") && active != "com.android.fileexplorer") return
        val image = checkNotNull(ui.takeScreenshot())
        File(context.cacheDir, "skill-ui1-$stage.png").outputStream().use { image.compress(Bitmap.CompressFormat.PNG, 100, it) }
        image.recycle()
    }
    private fun await(message: String, timeout: Long = 15_000, condition: () -> Boolean) {
        val end = System.currentTimeMillis() + timeout
        while (System.currentTimeMillis() < end) {
            if (condition()) return
            Thread.sleep(150)
        }
        throw AssertionError(message)
    }
    private fun find(node: AccessibilityNodeInfo?, predicate: (AccessibilityNodeInfo) -> Boolean): AccessibilityNodeInfo? {
        if (node == null) return null
        if (predicate(node)) return node
        for (i in 0 until node.childCount) find(node.getChild(i), predicate)?.let { return it }
        return null
    }
    private fun clickNode(node: AccessibilityNodeInfo) {
        var target: AccessibilityNodeInfo? = node
        while (target != null && !target.isClickable && target.className?.toString() !in listOf("android.widget.Button", "android.widget.Switch")) target = target.parent
        val clickable = checkNotNull(target) { "UI control is not clickable" }
        await("UI control stayed disabled") { clickable.refresh() && clickable.isEnabled && clickable.isClickable }
        check(clickable.performAction(AccessibilityNodeInfo.ACTION_CLICK)) { "UI click was not accepted" }
    }
    private fun visibleText(text: String) = find(ui.rootInActiveWindow) { it.text?.toString() == text }
    private fun clickText(text: String) {
        await("UI text missing: $text") { visibleText(text) != null }
        clickNode(checkNotNull(visibleText(text)))
        Thread.sleep(200)
    }
    private fun control(description: String): AccessibilityNodeInfo {
        fun current() = find(ui.rootInActiveWindow) { it.contentDescription?.toString() == description && it.isVisibleToUser }
        current()?.let { return it }
        for (action in listOf(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD, AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD)) {
            repeat(12) {
                val scroll = find(ui.rootInActiveWindow) { it.isScrollable }
                if (scroll?.performAction(action) == true) Thread.sleep(180)
                current()?.let { return it }
            }
        }
        throw AssertionError("UI control missing: $description")
    }
    private fun enable(id: String) {
        val description = "启用技能 $id"
        val before = control(description)
        assertTrue(before.isEnabled); assertFalse(before.isChecked)
        clickNode(before)
        await("skill enable not reflected in UI") { find(ui.rootInActiveWindow) { it.contentDescription?.toString() == description }?.isChecked == true }
        await("skill enable not stored") { store.discover().single { it.id == id }.enabled }
    }
    private fun clearNotice() {
        visibleText("关闭")?.let { clickNode(it); Thread.sleep(200) }
    }
    private fun pick(file: String) {
        stage("picker-start:$file")
        clearNotice()
        clickText("导入 Skill ZIP")
        await("system picker did not open") { ui.rootInActiveWindow?.packageName?.toString()?.let { it.contains("documentsui") || it == "com.android.fileexplorer" } == true }
        stage("picker-open:$file")
        if (ui.rootInActiveWindow?.packageName?.toString() == "com.android.fileexplorer") {
            clickNode(checkNotNull(find(ui.rootInActiveWindow) { it.contentDescription?.toString() == "更多" }))
            clickText("查看更多文件")
            await("system document provider picker missing") { ui.rootInActiveWindow?.packageName?.toString()?.contains("documentsui") == true }
        }
        stage("picker-provider-browser:$file")
        if (visibleText(file) == null) {
            var root = visibleText("Agent test fixtures")
            if (root == null) {
                val menu = find(ui.rootInActiveWindow) {
                    it.contentDescription?.toString() in listOf("显示根目录", "Show roots", "打开导航抽屉", "Open navigation drawer") ||
                        it.viewIdResourceName?.endsWith(":id/roots_toolbar") == true
                }
                checkNotNull(menu) { "System picker roots control missing" }
                clickNode(menu)
                stage("picker-roots-open:$file")
                await("test fixture root missing") { visibleText("Agent test fixtures") != null }
                root = visibleText("Agent test fixtures")
            }
            clickNode(checkNotNull(root))
        }
        await("fixture document missing: $file") { visibleText(file) != null }
        clickNode(checkNotNull(visibleText(file)))
        stage("picker-file-clicked:$file")
        await("document result did not return") { ui.rootInActiveWindow?.packageName?.toString() in listOf(context.packageName, "com.android.fileexplorer") }
        if (ui.rootInActiveWindow?.packageName?.toString() == "com.android.fileexplorer") {
            await("OEM picker confirmation missing") { visibleText("确定")?.isEnabled == true }
            clickText("确定")
        }
        await("picker did not return to product") { ui.rootInActiveWindow?.packageName?.toString() == context.packageName }
        Thread.sleep(200)
        await("archive import did not finish") { visibleText("关闭") != null }
    }
    private fun request(route: String, body: JSONObject? = null): JSONObject {
        val token = File(context.filesDir, "runtime/bridge-token").readText().trim()
        val connection = URL("http://127.0.0.1:8765$route").openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 1500; connection.readTimeout = 35_000
            connection.setRequestProperty("X-Bridge-Token", token)
            if (body != null) {
                connection.requestMethod = "POST"; connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json")
                connection.outputStream.use { it.write(body.toString().toByteArray()) }
            }
            check(connection.responseCode == 200) { "Host HTTP ${connection.responseCode}" }
            return JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
        } finally { connection.disconnect() }
    }
    private fun rpc(method: String, params: JSONObject): JSONObject {
        val answer = request("/rpc-wait", JSONObject().put("method", method).put("params", params).put("timeoutMs", 30_000))
        check(!answer.has("error")) { "Core RPC error: $method ${answer.optJSONObject("error")}" }
        return answer.getJSONObject("result")
    }
    private fun messages(id: String) = request("/session/read?id=$id").getJSONObject("snapshot").getJSONArray("messages")
    private fun parts(messages: JSONArray, start: Int = 0): List<JSONObject> = (start until messages.length()).flatMap { index ->
        val array = messages.getJSONObject(index).getJSONArray("parts")
        (0 until array.length()).map { array.getJSONObject(it) }
    }
    private fun modelTurn(session: String, skill: String, hash: String, revision: String, start: Int = 0): Int {
        rpc("session/send", JSONObject().put("sessionId", session).put("content",
            "Use Skill to load $skill, then use Read for its references/rule.txt. Return its exact resource line. Only Skill and Read; no writing or other tools."))
        var snapshot = JSONArray()
        await("real Skill task did not complete", 120_000) {
            snapshot = messages(session)
            (start until snapshot.length()).any { snapshot.getJSONObject(it).getJSONObject("info").let { info ->
                info.optString("role") == "assistant" && info.optString("finish") == "stop"
            } }
        }
        File(context.cacheDir, "skill-ui1-$revision-$start-model.json").writeText(JSONObject().put("sessionId", session).put("messages", snapshot).toString(2))
        val fresh = parts(snapshot, start)
        val tools = fresh.filter { it.optString("type") == "tool" }
        check(tools.isNotEmpty() && tools.all { it.optString("tool") in listOf("Skill", "Read") && it.getJSONObject("state").optString("status") == "completed" })
        check(tools.any { it.optString("tool") == "Skill" && it.getJSONObject("state").getJSONObject("input").optString("skill") == skill })
        val reference = File(context.filesDir, "core-skill-packages/$skill/versions/$hash/references/rule.txt").canonicalPath
        val expected = "UI_RESOURCE_${skill}_$revision"
        val reads = tools.filter { it.optString("tool") == "Read" && it.getJSONObject("state").getJSONObject("input").optString("file_path") == reference }
        val history = parts(snapshot).any { it.optString("tool") == "Read" && it.optJSONObject("state")?.let { state ->
            state.optJSONObject("input")?.optString("file_path") == reference && state.optString("output").contains(expected)
        } == true }
        check(reads.any { it.getJSONObject("state").optString("output").contains(expected) ||
            (start > 0 && history && it.getJSONObject("state").optString("output") == "Wasted call — file unchanged since your last Read. Refer to that earlier tool_result instead.") })
        check(fresh.any { it.optString("type") == "text" && it.optString("text").contains(expected) })
        check(File(reference).readText() == "$expected\n")
        return snapshot.length()
    }
    @Test fun safImportEnableLiveUpdateDependenciesAndRetirement() {
        TestDeviceTarget.require(InstrumentationRegistry.getArguments().getString("deviceTarget"))
        try {
            report.put("verdict", "RUNNING"); save()
            // Avoid Instrumentation's legacy idle-wait launch on Android17; operate the real UI.
            stage("launch-main")
            repeat(3) {
                val active = ui.rootInActiveWindow?.packageName?.toString()
                if (active?.contains("documentsui") == true || active == "com.android.fileexplorer") {
                    ParcelFileDescriptor.AutoCloseInputStream(ui.executeShellCommand("input keyevent BACK")).use { it.readBytes() }
                    Thread.sleep(250)
                }
            }
            ParcelFileDescriptor.AutoCloseInputStream(ui.executeShellCommand("am start -f 0x10020000 -n dev.alita.androidagent/.MainActivity")).use { it.readBytes() }
            stage("main-launch-requested")
            clickText("技能")
            pick("01-skill-v1.zip")
            val first = store.discover().single { it.id.startsWith("ui-proof-") && !it.id.endsWith("-missing") }
            report.put("skill", first.id).put("v1Hash", first.hash).put("source", first.source); save()
            assertTrue(first.source.startsWith("content://dev.alita.androidagent.test.skillfixtures/"))
            assertFalse(first.enabled)
            clearNotice()
            enable(first.id)
            clearNotice()
            assertTrue(control("启用技能 ${first.id}").isChecked)
            screenshot("enabled-v1")
            clickText("任务")
            clickText("打开 Agent")
            var status = JSONObject()
            await("product runtime not ready", 30_000) { runCatching { status = request("/status"); status.optString("phase") == "ready" }.getOrDefault(false) }
            instrumentation.sendKeyDownUpSync(KeyEvent.KEYCODE_BACK)
            clickText("技能")
            val workspace = status.getString("workspace")
            val identity = JSONObject().put("workspacePath", workspace).put("workspaceKey", File(workspace).name)
            fun create(): String = rpc("session/create", JSONObject().put("workspace", identity).put("mode", "build")
                .put("model", JSONObject().put("providerId", "deepseek").put("modelId", "deepseek-flash").put("options", JSONObject().put("reasoningLevel", "disabled")))
                .put("thoughtLevel", "disabled").put("titleGenerationEnabled", false).put("dynamicWorkflowEnabled", false).put("offPeakToolEnabled", false))
                .getJSONObject("session").getString("sessionId")
            val old = create(); val count = modelTurn(old, first.id, first.hash, "1")
            report.put("oldSession", old).put("firstRealTaskPassed", true); save()
            pick("02-skill-v2.zip")
            val second = store.discover().single { it.id == first.id }
            assertFalse(second.enabled); assertNotEquals(first.hash, second.hash)
            clearNotice()
            enable(first.id)
            clearNotice()
            modelTurn(old, first.id, first.hash, "1", count)
            val newer = create(); modelTurn(newer, first.id, second.hash, "2")
            report.put("newSession", newer).put("v2Hash", second.hash).put("liveOldV1NewV2", true); save()
            screenshot("enabled-v2")
            pick("03-missing.zip")
            clearNotice()
            val missingControl = control("启用技能 ${first.id}-missing")
            assertFalse(missingControl.isEnabled); assertFalse(missingControl.isChecked)
            assertNotNull(visibleText("缺少依赖：runtimes:python, permissions:root"))
            val missing = store.discover().single { it.id == first.id + "-missing" }
            assertFalse(missing.enabled)
            report.put("missingDependencies", JSONArray(missing.missingDependencies)); save()
            screenshot("missing-dependencies")
            // Remove the two fixture cards using their actual UI buttons.
            for (id in listOf(first.id + "-missing", first.id)) {
                clickNode(control("移除技能 $id"))
                await("retired skill still listed") { store.discover().none { it.id == id } }
                clearNotice()
            }
            assertTrue(first.directory.isDirectory && second.directory.isDirectory)
            report.put("verdict", "PASS").put("actualSystemPicker", true).put("realModelTurns", 3)
                .put("retiredThroughUi", true).put("oldVersionsRetained", true)
                .put("scope", "real Compose/SAF import-enable-live-update-dependency-retirement and real Core model; no shared storage fixture or new runtime capability")
            save()
        } catch (error: Throwable) {
            report.put("verdict", "FAIL").put("error", error.toString()); save()
            runCatching { screenshot("failure") }
            throw error
        }
    }
}
