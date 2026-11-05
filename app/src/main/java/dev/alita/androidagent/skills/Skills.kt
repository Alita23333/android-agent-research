package dev.alita.androidagent.skills

import android.content.Context
import dev.alita.androidagent.core.*
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.InputStream
import java.security.MessageDigest
import java.util.zip.ZipInputStream

enum class SkillAvailability { AVAILABLE, MISSING_DEPENDENCY, DISABLED, INVALID, STORED }

data class SkillDescriptor(
    val id: String,
    val name: String,
    val description: String,
    val version: String,
    val hash: String,
    val source: String,
    val enabled: Boolean,
    val availability: SkillAvailability,
    val missingDependencies: List<String> = emptyList(),
    val metadata: Map<String, String> = emptyMap(),
    val directory: File,
)

data class SkillSnapshot(val descriptor: SkillDescriptor, val body: String)

interface SkillRepository {
    fun discover(): List<SkillDescriptor>
    fun inspect(id: String): SkillSnapshot?
    fun readResource(id: String, relativePath: String, maxBytes: Int = 512_000): ByteArray
    fun install(zip: InputStream, source: String): SkillDescriptor
    fun setEnabled(id: String, enabled: Boolean)
    fun delete(id: String)
}

class FileSkillRepository(context: Context, private val availableTools: () -> Set<String>) : SkillRepository {
    private val root = File(context.filesDir, "skills").apply { mkdirs() }
    private val temp = File(context.cacheDir, "skill-import").apply { mkdirs() }

    override fun discover(): List<SkillDescriptor> = root.listFiles().orEmpty()
        .filter { it.isDirectory }
        .mapNotNull { loadActive(it) }
        .sortedBy { it.name.lowercase() }

    override fun inspect(id: String): SkillSnapshot? {
        val descriptor = discover().firstOrNull { it.id == id } ?: return null
        val file = File(descriptor.directory, "SKILL.md")
        return SkillSnapshot(descriptor, parseSkill(file.readText()).second)
    }

    override fun readResource(id: String, relativePath: String, maxBytes: Int): ByteArray {
        require(!File(relativePath).isAbsolute) { "Absolute resource paths are not allowed" }
        val descriptor = discover().firstOrNull { it.id == id } ?: error("Unknown skill: $id")
        val rootPath = descriptor.directory.canonicalFile
        val target = File(rootPath, relativePath).canonicalFile
        require(target.path.startsWith(rootPath.path + File.separator)) { "Resource escapes the skill directory" }
        require(target.isFile) { "Resource not found: $relativePath" }
        require(target.length() <= maxBytes) { "Resource is larger than $maxBytes bytes" }
        return target.readBytes()
    }

    override fun install(zip: InputStream, source: String): SkillDescriptor {
        val work = File(temp, "import-${System.nanoTime()}").apply { mkdirs() }
        try {
            extractSafe(zip, work)
            val skillFile = work.walkTopDown().filter { it.isFile && it.name == "SKILL.md" }.toList().singleOrNull()
                ?: error("压缩包必须只包含一个 SKILL.md")
            val contentRoot = requireNotNull(skillFile.parentFile) { "SKILL.md has no parent directory" }
            val (metadata, body) = parseSkill(skillFile.readText())
            val id = (metadata["id"] ?: metadata["name"] ?: contentRoot.name)
                .lowercase().replace(Regex("[^a-z0-9._-]"), "-").trim('-').take(80)
            require(id.isNotBlank()) { "技能 ID 无效" }
            val hash = hashDirectory(contentRoot)
            val targetRoot = File(root, id).apply { mkdirs() }
            val versions = File(targetRoot, "versions").apply { mkdirs() }
            val target = File(versions, hash)
            if (!target.exists()) contentRoot.copyRecursively(target, overwrite = false)
            File(targetRoot, "active").writeText(hash)
            File(targetRoot, "source").writeText(source.take(1000))
            if (!File(targetRoot, "enabled").exists()) File(targetRoot, "enabled").writeText("true")
            return descriptor(id, target, hash, source, File(targetRoot, "enabled").readText().trim() == "true", metadata, body)
        } finally { work.deleteRecursively() }
    }

    override fun setEnabled(id: String, enabled: Boolean) {
        val skillRoot = File(root, id)
        require(skillRoot.isDirectory) { "Unknown skill: $id" }
        File(skillRoot, "enabled").writeText(enabled.toString())
    }

    override fun delete(id: String) {
        val target = File(root, id).canonicalFile
        require(target.parentFile == root.canonicalFile) { "Invalid skill id" }
        target.deleteRecursively()
    }

    private fun loadActive(skillRoot: File): SkillDescriptor? = runCatching {
        val hash = File(skillRoot, "active").readText().trim()
        val directory = File(File(skillRoot, "versions"), hash)
        val text = File(directory, "SKILL.md").readText()
        val (metadata, body) = parseSkill(text)
        descriptor(
            skillRoot.name, directory, hash,
            File(skillRoot, "source").takeIf { it.isFile }?.readText().orEmpty(),
            File(skillRoot, "enabled").takeIf { it.isFile }?.readText()?.trim() != "false",
            metadata, body,
        )
    }.getOrNull()

    private fun descriptor(
        id: String, directory: File, hash: String, source: String, enabled: Boolean,
        metadata: Map<String, String>, body: String,
    ): SkillDescriptor {
        val android = parseSimpleYaml(File(directory, "android.yaml"))
        val required = android["tools"].orEmpty().split(',').map { it.trim() }.filter { it.isNotEmpty() }
        val missing = required.filterNot { availableTools().contains(it) }
        val availability = when {
            !enabled -> SkillAvailability.DISABLED
            missing.isNotEmpty() -> SkillAvailability.MISSING_DEPENDENCY
            else -> SkillAvailability.AVAILABLE
        }
        return SkillDescriptor(
            id = id,
            name = metadata["name"] ?: id,
            description = metadata["description"] ?: body.lineSequence().firstOrNull { it.isNotBlank() }.orEmpty().take(240),
            version = metadata["version"] ?: hash.take(12),
            hash = hash,
            source = source,
            enabled = enabled,
            availability = availability,
            missingDependencies = missing,
            metadata = metadata,
            directory = directory,
        )
    }

    private fun extractSafe(input: InputStream, destination: File) {
        var files = 0
        var total = 0L
        ZipInputStream(input.buffered()).use { zip ->
            while (true) {
                val entry = zip.nextEntry ?: break
                files++
                require(files <= 500) { "技能压缩包文件过多" }
                val target = File(destination, entry.name).canonicalFile
                require(target.path.startsWith(destination.canonicalPath + File.separator)) { "压缩包包含非法路径" }
                if (entry.isDirectory) target.mkdirs() else {
                    target.parentFile?.mkdirs()
                    target.outputStream().use { output ->
                        val buffer = ByteArray(8192)
                        while (true) {
                            val read = zip.read(buffer)
                            if (read <= 0) break
                            total += read
                            require(total <= 20L * 1024 * 1024) { "技能压缩包解压后超过 20 MB" }
                            output.write(buffer, 0, read)
                        }
                    }
                }
                zip.closeEntry()
            }
        }
    }

    private fun parseSkill(text: String): Pair<Map<String, String>, String> {
        if (!text.startsWith("---")) return emptyMap<String, String>() to text
        val end = text.indexOf("\n---", startIndex = 3)
        if (end < 0) return emptyMap<String, String>() to text
        val header = text.substring(3, end).trim()
        val metadata = header.lineSequence().mapNotNull { line ->
            val index = line.indexOf(':')
            if (index <= 0 || line.startsWith(" ") || line.startsWith("\t")) null
            else line.substring(0, index).trim() to line.substring(index + 1).trim().trim('"', '\'')
        }.toMap()
        return metadata to text.substring(end + 4).trimStart('\r', '\n')
    }

    private fun parseSimpleYaml(file: File): Map<String, String> {
        if (!file.isFile) return emptyMap()
        val result = linkedMapOf<String, String>()
        var listKey: String? = null
        file.forEachLine { line ->
            val trimmed = line.trim()
            when {
                trimmed.startsWith("-") && listKey != null -> {
                    val current = result[listKey].orEmpty()
                    result[listKey!!] = listOf(current, trimmed.removePrefix("-").trim()).filter { it.isNotBlank() }.joinToString(",")
                }
                !line.startsWith(" ") && trimmed.contains(':') -> {
                    val index = trimmed.indexOf(':')
                    listKey = trimmed.substring(0, index).trim()
                    result[listKey!!] = trimmed.substring(index + 1).trim().removeSurrounding("[", "]")
                }
            }
        }
        return result
    }

    private fun hashDirectory(directory: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        directory.walkTopDown().filter { it.isFile }.sortedBy { it.relativeTo(directory).invariantSeparatorsPath }.forEach { file ->
            digest.update(file.relativeTo(directory).invariantSeparatorsPath.toByteArray())
            file.inputStream().use { input ->
                val buffer = ByteArray(8192)
                while (true) { val read = input.read(buffer); if (read < 0) break; digest.update(buffer, 0, read) }
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}

class SkillRuntime(private val repository: SkillRepository) {
    private val active = mutableMapOf<String, MutableMap<String, SkillSnapshot>>()

    @Synchronized fun activate(runId: String, id: String): SkillSnapshot {
        val snapshot = repository.inspect(id) ?: error("Unknown skill: $id")
        require(snapshot.descriptor.availability == SkillAvailability.AVAILABLE) {
            "Skill unavailable: ${snapshot.descriptor.missingDependencies.joinToString()}"
        }
        active.getOrPut(runId) { linkedMapOf() }[id] = snapshot
        return snapshot
    }
    @Synchronized fun active(runId: String): List<SkillSnapshot> = active[runId]?.values?.toList().orEmpty()
    @Synchronized fun clear(runId: String) { active.remove(runId) }
}

class SkillToolProvider(private val repository: SkillRepository, private val runtime: SkillRuntime) : ToolProvider {
    override val providerId = "skills"
    override suspend fun tools(): List<AgentTool> = listOf(ListTool(), InspectTool(), ActivateTool(), ResourceTool())

    private inner class ListTool : AgentTool {
        override val definition = ToolDefinition("skills.list", description = "List installed skills and availability without loading their full instructions.", inputSchema = emptySchema())
        override suspend fun execute(call: ToolCall, context: ToolContext) = ToolResult.success(call, JSONObject().put("skills", JSONArray(repository.discover().map(::summary))))
    }
    private inner class InspectTool : AgentTool {
        override val definition = ToolDefinition("skills.inspect", description = "Inspect metadata and dependency status for one skill. Does not activate it.", inputSchema = idSchema())
        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult {
            val skill = repository.inspect(call.arguments.optString("id")) ?: return ToolResult.failure(call, "NOT_FOUND", "Skill not found")
            return ToolResult.success(call, summary(skill.descriptor).put("resourcePaths", JSONArray(
                skill.descriptor.directory.walkTopDown().filter { it.isFile && it.name != "SKILL.md" }.map { it.relativeTo(skill.descriptor.directory).invariantSeparatorsPath }.toList()
            )))
        }
    }
    private inner class ActivateTool : AgentTool {
        override val definition = ToolDefinition("skills.activate", description = "Activate a skill for this run and load its complete SKILL.md instructions.", inputSchema = idSchema())
        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult = runCatching {
            val snapshot = runtime.activate(context.runId, call.arguments.getString("id"))
            ToolResult.success(call, summary(snapshot.descriptor).put("instructions", snapshot.body))
        }.getOrElse { ToolResult.failure(call, "SKILL_UNAVAILABLE", it.message ?: "Unable to activate skill") }
    }
    private inner class ResourceTool : AgentTool {
        override val definition = ToolDefinition("skills.read_resource", description = "Read a text resource from an activated skill by relative path.", inputSchema = objectSchema(
            "id" to JSONObject().put("type", "string"), "path" to JSONObject().put("type", "string")
        ), capabilities = setOf("skill-resource"))
        override suspend fun execute(call: ToolCall, context: ToolContext): ToolResult = runCatching {
            val id = call.arguments.getString("id")
            require(runtime.active(context.runId).any { it.descriptor.id == id }) { "Skill is not active" }
            val bytes = repository.readResource(id, call.arguments.getString("path"))
            ToolResult.success(call, JSONObject().put("text", bytes.toString(Charsets.UTF_8)))
        }.getOrElse { ToolResult.failure(call, "RESOURCE_ERROR", it.message ?: "Unable to read resource") }
    }

    private fun summary(skill: SkillDescriptor) = JSONObject()
        .put("id", skill.id).put("name", skill.name).put("description", skill.description)
        .put("version", skill.version).put("hash", skill.hash).put("source", skill.source)
        .put("enabled", skill.enabled).put("availability", skill.availability.name)
        .put("missingDependencies", JSONArray(skill.missingDependencies))

    private fun emptySchema() = objectSchema()
    private fun idSchema() = objectSchema("id" to JSONObject().put("type", "string").put("description", "Installed skill id"))
    private fun objectSchema(vararg properties: Pair<String, JSONObject>) = JSONObject()
        .put("type", "object").put("properties", JSONObject(properties.toMap()))
        .put("required", JSONArray(properties.map { it.first })).put("additionalProperties", false)
}
