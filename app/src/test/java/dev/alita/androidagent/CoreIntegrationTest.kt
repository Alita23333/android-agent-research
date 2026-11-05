package dev.alita.androidagent

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import dev.alita.androidagent.core.*
import dev.alita.androidagent.execution.ExecutionRequest
import dev.alita.androidagent.execution.ProcessExecutionBackend
import dev.alita.androidagent.skills.FileSkillRepository
import dev.alita.androidagent.skills.SkillAvailability
import dev.alita.androidagent.tools.JsonRpcStdioProvider
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

@RunWith(RobolectricTestRunner::class)
@Config(application = AgentApplication::class, sdk = [35])
class CoreIntegrationTest {
    private val context: Context = ApplicationProvider.getApplicationContext()

    @Test fun registryRejectsToolIdCollision() {
        val registry = ToolRegistry()
        registry.register(FakeTool("demo.echo"))
        assertThrows(IllegalArgumentException::class.java) { registry.register(FakeTool("demo.echo")) }
    }

    @Test fun registryReplacesOneProviderWithoutChangingAgentLoop() = runBlocking {
        val registry = ToolRegistry()
        registry.register(FakeProvider("demo", FakeTool("demo.value", "v1")))
        registry.replace(FakeProvider("demo", FakeTool("demo.value", "v2")))
        assertEquals("v2", registry.find("demo.value")!!.definition.version)
    }

    @Test fun policyRequiresConfirmationForDangerousRootCommand() {
        val definition = ToolDefinition("shell.root", description = "root", inputSchema = JSONObject())
        val dangerous = ToolCall(toolId = "shell.root", arguments = JSONObject().put("command", "rm -rf /data/local/tmp/example"))
        assertTrue(DefaultPolicyEngine().evaluate(definition, dangerous) is PolicyDecision.Confirm)
        val safe = ToolCall(toolId = "shell.root", arguments = JSONObject().put("command", "id"))
        assertEquals(PolicyDecision.Allow, DefaultPolicyEngine().evaluate(definition, safe))
    }

    @Test fun skillInstallSnapshotsVersionsAndReportsMissingTools() {
        val repository = FileSkillRepository(context) { setOf("files.read") }
        val id = "test-snapshot-skill"
        runCatching { repository.delete(id) }
        try {
            val first = repository.install(zipOf(mapOf(
                "skill/SKILL.md" to "---\nname: $id\nversion: 1.0.0\ndescription: first\n---\nFirst body",
                "skill/android.yaml" to "tools:\n  - files.read",
            )).inputStream(), "test")
            val oldSnapshot = repository.inspect(id)!!
            assertEquals(SkillAvailability.AVAILABLE, first.availability)
            assertEquals("First body", oldSnapshot.body)

            val second = repository.install(zipOf(mapOf(
                "skill/SKILL.md" to "---\nname: $id\nversion: 2.0.0\ndescription: second\n---\nSecond body",
                "skill/android.yaml" to "tools:\n  - missing.tool",
            )).inputStream(), "test")
            assertEquals(SkillAvailability.MISSING_DEPENDENCY, second.availability)
            assertEquals("First body", oldSnapshot.body)
            assertEquals("Second body", repository.inspect(id)!!.body)
        } finally { runCatching { repository.delete(id) } }
    }

    @Test fun skillZipRejectsPathTraversal() {
        val repository = FileSkillRepository(context) { emptySet() }
        val malicious = zipOf(mapOf("../SKILL.md" to "---\nname: bad\n---\nbad"))
        assertThrows(IllegalArgumentException::class.java) { repository.install(malicious.inputStream(), "test") }
    }

    @Test fun processBackendReturnsOutputAndExitCode() = runBlocking {
        val windows = System.getProperty("os.name").orEmpty().startsWith("Windows", ignoreCase = true)
        val backend = ProcessExecutionBackend("test") { command -> if (windows) listOf("powershell", "-NoProfile", "-Command", command) else listOf("/bin/sh", "-c", command) }
        val command = if (windows) "[Console]::Write('agent-ok')" else "printf agent-ok"
        val result = backend.execute(ExecutionRequest(command, context.cacheDir), CancellationSignal())
        assertEquals(0, result.exitCode)
        assertEquals("agent-ok", result.output)
        assertFalse(result.running)
    }

    @Test fun jsonRpcProviderNegotiatesAndCallsTool() = runBlocking {
        val directory = File(context.cacheDir, "rpc-${System.nanoTime()}").apply { mkdirs() }
        try {
            val script = File(directory, "provider.py")
            script.writeText("""
                import json, sys
                for line in sys.stdin:
                    request = json.loads(line)
                    if request['method'] == 'initialize':
                        result = {'protocolVersion':'1.0','tools':[{'name':'echo','description':'Echo','inputSchema':{'type':'object'}}]}
                    else:
                        result = {'ok':True,'data':{'value':'pong'}}
                    print(json.dumps({'jsonrpc':'2.0','id':request['id'],'result':result}), flush=True)
            """.trimIndent())
            val provider = JsonRpcStdioProvider("testprovider", listOf("python", "-u", script.absolutePath), directory)
            val tool = provider.tools().single()
            assertEquals("testprovider.echo", tool.definition.id)
            val call = ToolCall(toolId = tool.definition.id)
            val result = tool.execute(call, ToolContext("run", CancellationSignal(), NoArtifacts))
            assertTrue(result.ok)
            assertEquals("pong", result.data.getString("value"))
            provider.close()
        } finally { directory.deleteRecursively() }
    }

    private fun zipOf(entries: Map<String, String>): ByteArray {
        val output = ByteArrayOutputStream()
        ZipOutputStream(output).use { zip -> entries.forEach { (name, content) ->
            zip.putNextEntry(ZipEntry(name)); zip.write(content.toByteArray()); zip.closeEntry()
        } }
        return output.toByteArray()
    }

    private class FakeTool(id: String, version: String = "1.0.0") : AgentTool {
        override val definition = ToolDefinition(id, version = version, description = "test", inputSchema = JSONObject())
        override suspend fun execute(call: ToolCall, context: ToolContext) = ToolResult.success(call)
    }

    private class FakeProvider(override val providerId: String, private vararg val provided: AgentTool) : ToolProvider {
        override suspend fun tools() = provided.toList()
    }

    private object NoArtifacts : ArtifactStore {
        override fun create(runId: String, name: String, mimeType: String, bytes: ByteArray) = error("unused")
    }
}
