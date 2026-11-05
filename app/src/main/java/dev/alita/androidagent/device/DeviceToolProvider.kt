package dev.alita.androidagent.device

import android.accessibilityservice.AccessibilityService
import android.content.Context
import android.content.Intent
import dev.alita.androidagent.core.*
import org.json.JSONArray
import org.json.JSONObject

class DeviceToolProvider(private val context: Context) : ToolProvider {
    override val providerId = "device"
    override suspend fun tools(): List<AgentTool> = listOf(Inspect(), Observe(), Click(), InputText(), Swipe(), GlobalAction(), Screenshot(), LaunchApp(), InstalledApps())

    private fun service() = AgentAccessibilityService.current() ?: error("Android Agent 无障碍服务未启用或未连接")

    private inner class Inspect : AgentTool {
        override val definition = ToolDefinition(
            "ui.inspect",
            description = "Read the current Android accessibility windows and semantic control tree without changing device state.",
            inputSchema = schema(),
            capabilities = setOf("accessibility.inspect", "device-read"),
            sideEffect = SideEffect.NONE,
            supportsCancellation = false,
        )
        override suspend fun execute(call: ToolCall, context: ToolContext) = runCatching {
            val observation = service().observe()
            ToolResult.success(call, JSONObject()
                .put("observationId", observation.optString("snapshotId"))
                .put("package", observation.optString("package"))
                .put("windows", observation.optJSONArray("windows") ?: JSONArray())
                .put("truncated", observation.optBoolean("truncated")))
        }.getOrElse {
            ToolResult.failure(call, "ACCESSIBILITY_UNAVAILABLE", it.message ?: "Unable to inspect screen")
        }
    }

    private inner class Observe : AgentTool {
        override val definition = ToolDefinition("device.observe", description = "Read the current Android accessibility window and control tree. Call again after the UI changes.", inputSchema = schema(), capabilities = setOf("device-ui"))
        override suspend fun execute(call: ToolCall, context: ToolContext) = runCatching { ToolResult.success(call, service().observe()) }
            .getOrElse { ToolResult.failure(call, "ACCESSIBILITY_UNAVAILABLE", it.message ?: "Unable to observe screen") }
    }
    private inner class Click : AgentTool {
        override val definition = ToolDefinition("device.click", description = "Click a node from the latest device.observe snapshot.", inputSchema = schema("snapshotId" to str(), "nodeId" to str()), capabilities = setOf("device-ui"), sideEffect = SideEffect.REVERSIBLE)
        override suspend fun execute(call: ToolCall, context: ToolContext) = runCatching { ToolResult.success(call, JSONObject().put("performed", service().click(call.arguments.getString("snapshotId"), call.arguments.getString("nodeId")))) }
            .getOrElse { ToolResult.failure(call, "UI_ACTION_FAILED", it.message ?: "Click failed", true) }
    }
    private inner class InputText : AgentTool {
        override val definition = ToolDefinition("device.input_text", description = "Replace text in an editable node from the latest observation.", inputSchema = schema("snapshotId" to str(), "nodeId" to str(), "text" to str()), capabilities = setOf("device-ui"), sideEffect = SideEffect.REVERSIBLE)
        override suspend fun execute(call: ToolCall, context: ToolContext) = runCatching { ToolResult.success(call, JSONObject().put("performed", service().inputText(call.arguments.getString("snapshotId"), call.arguments.getString("nodeId"), call.arguments.getString("text")))) }
            .getOrElse { ToolResult.failure(call, "UI_ACTION_FAILED", it.message ?: "Text input failed", true) }
    }
    private inner class Swipe : AgentTool {
        override val definition = ToolDefinition("device.swipe", description = "Perform a coordinate gesture when no semantic accessibility action is available.", inputSchema = schema(
            "x1" to num(), "y1" to num(), "x2" to num(), "y2" to num(), "durationMs" to integer()
        ), capabilities = setOf("device-ui"), sideEffect = SideEffect.REVERSIBLE)
        override suspend fun execute(call: ToolCall, context: ToolContext) = runCatching { ToolResult.success(call, JSONObject().put("performed", service().gesture(
            call.arguments.getDouble("x1").toFloat(), call.arguments.getDouble("y1").toFloat(), call.arguments.getDouble("x2").toFloat(), call.arguments.getDouble("y2").toFloat(), call.arguments.getLong("durationMs")
        ))) }.getOrElse { ToolResult.failure(call, "UI_ACTION_FAILED", it.message ?: "Gesture failed", true) }
    }
    private inner class GlobalAction : AgentTool {
        override val definition = ToolDefinition("device.global_action", description = "Perform Android back, home, recents or notifications global action.", inputSchema = JSONObject()
            .put("type", "object").put("properties", JSONObject().put("action", JSONObject().put("type", "string").put("enum", JSONArray(listOf("back", "home", "recents", "notifications")))))
            .put("required", JSONArray(listOf("action"))).put("additionalProperties", false), capabilities = setOf("device-ui"), sideEffect = SideEffect.REVERSIBLE)
        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult {
            val action = when (call.arguments.optString("action")) {
                "back" -> AccessibilityService.GLOBAL_ACTION_BACK
                "home" -> AccessibilityService.GLOBAL_ACTION_HOME
                "recents" -> AccessibilityService.GLOBAL_ACTION_RECENTS
                "notifications" -> AccessibilityService.GLOBAL_ACTION_NOTIFICATIONS
                else -> return ToolResult.failure(call, "INVALID_ARGUMENT", "Unknown global action")
            }
            return ToolResult.success(call, JSONObject().put("performed", service().performGlobalAction(action)))
        }
    }
    private inner class Screenshot : AgentTool {
        override val definition = ToolDefinition("device.screenshot", description = "Capture the current screen as a PNG artifact.", inputSchema = schema(), capabilities = setOf("device-ui"))
        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult = runCatching {
            val bytes = service().screenshotPng(); require(bytes.isNotEmpty()) { "Screenshot failed or was blocked" }
            val artifact = context.artifactStore.create(context.runId, "screenshot.png", "image/png", bytes)
            ToolResult.success(call, JSONObject().put("artifact", artifact.toJson()), listOf(artifact))
        }.getOrElse { ToolResult.failure(call, "SCREENSHOT_FAILED", it.message ?: "Screenshot failed", true) }
    }
    private inner class LaunchApp : AgentTool {
        override val definition = ToolDefinition("device.launch_app", description = "Launch an installed Android app by package name.", inputSchema = schema("package" to str()), capabilities = setOf("device-ui"), sideEffect = SideEffect.REVERSIBLE)
        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult {
            val packageName = call.arguments.optString("package")
            val intent = this@DeviceToolProvider.context.packageManager.getLaunchIntentForPackage(packageName)
                ?: return ToolResult.failure(call, "APP_NOT_FOUND", "No launchable app for $packageName")
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            this@DeviceToolProvider.context.startActivity(intent)
            return ToolResult.success(call, JSONObject().put("launched", packageName))
        }
    }
    private inner class InstalledApps : AgentTool {
        override val definition = ToolDefinition("device.apps", description = "List launchable installed Android applications.", inputSchema = schema(), capabilities = setOf("device-read"))
        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult {
            val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
            val apps = this@DeviceToolProvider.context.packageManager.queryIntentActivities(intent, 0).map {
                JSONObject().put("label", it.loadLabel(this@DeviceToolProvider.context.packageManager).toString()).put("package", it.activityInfo.packageName)
            }.sortedBy { it.optString("label") }
            return ToolResult.success(call, JSONObject().put("apps", JSONArray(apps)))
        }
    }

    private fun str() = JSONObject().put("type", "string")
    private fun num() = JSONObject().put("type", "number")
    private fun integer() = JSONObject().put("type", "integer")
    private fun schema(vararg properties: Pair<String, JSONObject>) = JSONObject().put("type", "object")
        .put("properties", JSONObject(properties.toMap())).put("required", JSONArray(properties.map { it.first })).put("additionalProperties", false)
}
