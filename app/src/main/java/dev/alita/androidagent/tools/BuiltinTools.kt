package dev.alita.androidagent.tools

import android.content.Context
import dev.alita.androidagent.core.*
import dev.alita.androidagent.execution.ExecutionBackend
import dev.alita.androidagent.execution.ExecutionRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

class BuiltinToolProvider(
    context: Context,
    private val shell: ExecutionBackend,
    private val rootShell: ExecutionBackend,
) : ToolProvider {
    override val providerId = "builtin"
    private val workspace = File(context.filesDir, "workspace").apply { mkdirs() }.canonicalFile

    override suspend fun tools(): List<AgentTool> = listOf(
        ShellTool("shell.exec", shell, SideEffect.REVERSIBLE, "Run an Android shell command in the agent workspace."),
        ShellTool("shell.root", rootShell, SideEffect.REVERSIBLE, "Run a command through su. Use only when Android app permissions are insufficient."),
        StartShellTool(), StatusShellTool(), CancelShellTool(),
        ListFilesTool(), ReadFileTool(), WriteFileTool(), ReplaceFileTool(), SearchFilesTool(), HttpGetTool(),
    )

    private inner class ShellTool(
        id: String,
        private val backend: ExecutionBackend,
        sideEffect: SideEffect,
        description: String,
    ) : AgentTool {
        override val definition = ToolDefinition(id, description = description, inputSchema = schema(
            "command" to string("Shell command"),
            "timeoutSeconds" to JSONObject().put("type", "integer").put("minimum", 1).put("maximum", 600)
                .put("description", "Optional timeout from 1 to 600 seconds"),
        ), capabilities = setOf(if (id == "shell.root") "root" else "shell"), sideEffect = sideEffect, supportsCancellation = true)

        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult = runCatching {
            val timeout = call.arguments.optInt("timeoutSeconds", 60).coerceIn(1, 600) * 1000L
            val result = backend.execute(ExecutionRequest(call.arguments.getString("command"), workspace, timeoutMillis = timeout), context.cancellation)
            ToolResult.success(call, executionJson(result))
        }.getOrElse { ToolResult.failure(call, "EXECUTION_FAILED", it.message ?: "Command failed", retryable = true) }
    }

    private inner class StartShellTool : AgentTool {
        override val definition = ToolDefinition("shell.start", description = "Start a long-running shell command and return an execution id.", inputSchema = schema("command" to string("Shell command")), capabilities = setOf("shell"), sideEffect = SideEffect.REVERSIBLE, supportsCancellation = true)
        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult = runCatching {
            val id = shell.start(ExecutionRequest(call.arguments.getString("command"), workspace, timeoutMillis = Long.MAX_VALUE))
            ToolResult.success(call, JSONObject().put("executionId", id).put("running", true))
        }.getOrElse { ToolResult.failure(call, "START_FAILED", it.message ?: "Unable to start command") }
    }

    private inner class StatusShellTool : AgentTool {
        override val definition = ToolDefinition("shell.status", description = "Read current output and status for a long-running command.", inputSchema = schema("executionId" to string("Execution id returned by shell.start")), capabilities = setOf("shell"))
        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult {
            val result = shell.status(call.arguments.optString("executionId"))
                ?: return ToolResult.failure(call, "NOT_FOUND", "Execution not found or already collected")
            return ToolResult.success(call, executionJson(result))
        }
    }

    private inner class CancelShellTool : AgentTool {
        override val definition = ToolDefinition("shell.cancel", description = "Cancel a long-running command and its child processes.", inputSchema = schema("executionId" to string("Execution id")), capabilities = setOf("shell"), sideEffect = SideEffect.REVERSIBLE)
        override suspend fun execute(call: ToolCall, context: ToolContext) = ToolResult.success(call, JSONObject().put("cancelled", shell.cancel(call.arguments.optString("executionId"))))
    }

    private inner class ListFilesTool : AgentTool {
        override val definition = ToolDefinition("files.list", description = "List files in a directory inside the agent workspace.", inputSchema = schema("path" to string("Workspace-relative directory; use . for root")), capabilities = setOf("workspace-read"))
        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult = runCatching {
            val directory = resolve(call.arguments.getString("path"))
            require(directory.isDirectory) { "Not a directory" }
            ToolResult.success(call, JSONObject().put("entries", JSONArray(directory.listFiles().orEmpty().sortedBy { it.name }.map {
                JSONObject().put("name", it.name).put("directory", it.isDirectory).put("size", if (it.isFile) it.length() else 0)
            })))
        }.getOrElse { ToolResult.failure(call, "FILE_ERROR", it.message ?: "Unable to list files") }
    }

    private inner class ReadFileTool : AgentTool {
        override val definition = ToolDefinition("files.read", description = "Read a UTF-8 text file inside the agent workspace.", inputSchema = schema("path" to string("Workspace-relative file path")), capabilities = setOf("workspace-read"))
        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult = runCatching {
            val file = resolve(call.arguments.getString("path")); require(file.isFile) { "File not found" }; require(file.length() <= 1_048_576) { "File exceeds 1 MB" }
            ToolResult.success(call, JSONObject().put("path", relative(file)).put("content", file.readText()).put("size", file.length()))
        }.getOrElse { ToolResult.failure(call, "FILE_ERROR", it.message ?: "Unable to read file") }
    }

    private inner class WriteFileTool : AgentTool {
        override val definition = ToolDefinition("files.write", description = "Write a UTF-8 text file in the agent workspace, creating parent directories.", inputSchema = schema(
            "path" to string("Workspace-relative file path"), "content" to string("Complete UTF-8 content")
        ), capabilities = setOf("workspace-write"), sideEffect = SideEffect.REVERSIBLE)
        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult = runCatching {
            val file = resolve(call.arguments.getString("path")); file.parentFile?.mkdirs(); file.writeText(call.arguments.getString("content"))
            ToolResult.success(call, JSONObject().put("path", relative(file)).put("size", file.length()))
        }.getOrElse { ToolResult.failure(call, "FILE_ERROR", it.message ?: "Unable to write file") }
    }

    private inner class ReplaceFileTool : AgentTool {
        override val definition = ToolDefinition("files.replace", description = "Replace one exact text occurrence in a workspace file. Fails if the old text is absent or occurs more than once.", inputSchema = schema(
            "path" to string("Workspace-relative file path"), "old" to string("Exact old text"), "new" to string("Replacement text")
        ), capabilities = setOf("workspace-write"), sideEffect = SideEffect.REVERSIBLE)
        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult = runCatching {
            val file = resolve(call.arguments.getString("path")); val content = file.readText(); val old = call.arguments.getString("old")
            val first = content.indexOf(old); require(first >= 0) { "Old text not found" }; require(content.indexOf(old, first + old.length) < 0) { "Old text is not unique" }
            file.writeText(content.replaceRange(first, first + old.length, call.arguments.getString("new")))
            ToolResult.success(call, JSONObject().put("path", relative(file)).put("size", file.length()))
        }.getOrElse { ToolResult.failure(call, "FILE_ERROR", it.message ?: "Unable to replace text") }
    }

    private inner class SearchFilesTool : AgentTool {
        override val definition = ToolDefinition("files.search", description = "Search UTF-8 workspace files using a regular expression.", inputSchema = schema(
            "query" to string("Regular expression"), "path" to string("Workspace-relative directory")
        ), capabilities = setOf("workspace-read"))
        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult = runCatching {
            val regex = Regex(call.arguments.getString("query")); val start = resolve(call.arguments.getString("path")); var count = 0
            val matches = JSONArray()
            start.walkTopDown().filter { it.isFile && it.length() <= 1_048_576 }.forEach { file ->
                if (count >= 200) return@forEach
                runCatching { file.useLines { lines -> lines.forEachIndexed { index, line ->
                    if (count < 200 && regex.containsMatchIn(line)) { matches.put(JSONObject().put("path", relative(file)).put("line", index + 1).put("text", line.take(500))); count++ }
                } } }
            }
            ToolResult.success(call, JSONObject().put("matches", matches).put("truncated", count >= 200))
        }.getOrElse { ToolResult.failure(call, "SEARCH_ERROR", it.message ?: "Search failed") }
    }

    private inner class HttpGetTool : AgentTool {
        override val definition = ToolDefinition("http.get", description = "Make an HTTPS GET request and return text up to 1 MB.", inputSchema = schema("url" to string("HTTPS URL")), capabilities = setOf("network"))
        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult = withContext(Dispatchers.IO) {
            runCatching {
                val url = URL(call.arguments.getString("url")); require(url.protocol == "https") { "Only HTTPS is allowed" }
                val connection = (url.openConnection() as HttpURLConnection).apply { connectTimeout = 20_000; readTimeout = 60_000; instanceFollowRedirects = true }
                val bytes = connection.inputStream.use { input ->
                    val output = ByteArrayOutputStream()
                    val buffer = ByteArray(8192)
                    while (output.size() <= 1_048_576) {
                        val read = input.read(buffer)
                        if (read < 0) break
                        output.write(buffer, 0, read)
                    }
                    output.toByteArray()
                }
                require(connection.url.protocol == "https") { "Redirected to a non-HTTPS URL" }
                require(bytes.size <= 1_048_576) { "Response exceeds 1 MB" }
                ToolResult.success(call, JSONObject().put("status", connection.responseCode).put("contentType", connection.contentType).put("body", bytes.toString(Charsets.UTF_8)))
            }.getOrElse { ToolResult.failure(call, "HTTP_ERROR", it.message ?: "Request failed", retryable = true) }
        }
    }

    private fun resolve(path: String): File {
        val target = File(workspace, path.ifBlank { "." }).canonicalFile
        require(target == workspace || target.path.startsWith(workspace.path + File.separator)) { "Path escapes workspace" }
        return target
    }
    private fun relative(file: File) = file.relativeTo(workspace).invariantSeparatorsPath
    private fun string(description: String) = JSONObject().put("type", "string").put("description", description)
    private fun schema(vararg properties: Pair<String, JSONObject>) = JSONObject().put("type", "object")
        .put("properties", JSONObject(properties.toMap()))
        .put("required", JSONArray(properties.filterNot { it.first == "timeoutSeconds" }.map { it.first }))
        .put("additionalProperties", false)
    private fun executionJson(result: dev.alita.androidagent.execution.ExecutionResult) = JSONObject()
        .put("executionId", result.executionId).put("exitCode", result.exitCode).put("output", result.output)
        .put("running", result.running).put("timedOut", result.timedOut).put("truncated", result.truncated)
}
