package dev.alita.androidagent.tools

import android.content.Context
import dev.alita.androidagent.core.ToolProvider
import org.json.JSONObject
import java.io.File
import java.io.InputStream
import java.security.MessageDigest
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.nio.file.StandardCopyOption.ATOMIC_MOVE
import java.nio.file.StandardCopyOption.REPLACE_EXISTING
import java.util.Locale
import java.util.UUID
import java.util.zip.ZipInputStream

data class LocalProviderDescriptor(val id: String, val version: String, val directory: File, val command: List<String>)

/** Storage selection is not production admission. Imported candidates remain inert. */
class LocalProviderCatalog internal constructor(context: Context, private val root: File, private val temp: File) {
    constructor(context: Context) : this(context, File(context.filesDir, "tool-providers"), File(context.cacheDir, "provider-import"))
    private val appContext = context.applicationContext
    private val reserved = setOf("device_info", "text_digest")
    init { ensureDirectory(root); ensureDirectory(temp) }

    @Synchronized fun discover(): List<LocalProviderDescriptor> = root.listFiles().orEmpty().filter { !it.name.startsWith('.') }.mapNotNull { providerRoot ->
        runCatching {
            val pointer = inside(root, "${providerRoot.name}/active")
            require(Files.isRegularFile(pointer.toPath(), NOFOLLOW_LINKS) && pointer.length() in 64..65)
            val active = pointer.readText().trim()
            require(active.matches(Regex("[a-f0-9]{64}")))
            val item = descriptor(inside(root, "${providerRoot.name}/versions/$active"))
            verifyPin(item)
            item
        }.getOrNull()
    }.sortedBy { it.id }

    /** Resolve immutable bytes directly; the mutable active pointer is not consulted. */
    @Synchronized fun pinned(id: String, contentHash: String): LocalProviderDescriptor {
        require(id.matches(Regex("[a-zA-Z][a-zA-Z0-9_-]{1,48}")) && contentHash.matches(Regex("[a-f0-9]{64}")))
        val item = descriptor(inside(root, "$id/versions/$contentHash"))
        require(item.id == id)
        verifyPin(item)
        return item
    }

    @Synchronized fun load(descriptor: LocalProviderDescriptor): ToolProvider {
        verifyPin(descriptor)
        val command = descriptor.command.map { value ->
            value.replace("${'$'}{DIR}", descriptor.directory.absolutePath)
                .replace("${'$'}{APK_NODE}", File(appContext.applicationInfo.nativeLibraryDir, "libnode.so").absolutePath)
        }
        val environment = if (descriptor.command.any { it.contains("${'$'}{APK_NODE}") }) mapOf(
            "LD_LIBRARY_PATH" to File(appContext.filesDir, "runtime/lib").absolutePath,
            "OPENSSL_CONF" to "/dev/null",
        ) else emptyMap()
        return JsonRpcStdioProvider(descriptor.id, command, descriptor.directory, environment = environment,
            beforeStart = { verifyPin(descriptor) })
    }

    /** Read one pinned Node entry, never follow the mutable active pointer or spawn its command. */
    @Synchronized internal fun readPinnedNodeEntry(item: LocalProviderDescriptor): ByteArray {
        verifyPin(item)
        require(item.command.size == 2 && item.command[0] == "${'$'}{APK_NODE}") { "Isolated profile requires one Node entry, no flags or shell" }
        val relative = item.command[1].removePrefix("${'$'}{DIR}/")
        require(item.command[1] == "${'$'}{DIR}/$relative" && relative.endsWith(".cjs")) { "Node entry must be a package-relative .cjs file" }
        val entry = inside(item.directory, relative)
        require(Files.isRegularFile(entry.toPath(), NOFOLLOW_LINKS) && entry.length() in 1..262144) { "Isolated script size/type rejected" }
        val bytes = entry.readBytes()
        require(bytes.size in 1..262144 && bytes.none { it == 0.toByte() })
        Charsets.UTF_8.newDecoder().onMalformedInput(java.nio.charset.CodingErrorAction.REPORT)
            .onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT).decode(java.nio.ByteBuffer.wrap(bytes))
        verifyPin(item)
        return bytes
    }

    @Synchronized fun install(input: InputStream): LocalProviderDescriptor {
        ensureDirectory(temp)
        val work = File(temp, "import-${UUID.randomUUID()}").apply { check(mkdir()) }
        try {
            extract(input, work)
            val manifests = work.walkTopDown().filter { it.isFile && it.name == "provider.json" }.toList()
            require(manifests.size == 1) { "工具包必须只包含一个 provider.json" }
            val source = requireNotNull(manifests.single().parentFile)
            require(work.walkTopDown().filter { it.isFile }.all { it.toPath().startsWith(source.toPath()) }) {
                "工具包包含提供者目录外的文件"
            }
            return commit(source, bundled = false)
        } finally { work.deleteRecursively() }
    }

    /** Installs an APK-owned provider without granting it any extra capability. */
    @Synchronized fun installBundled(assetDirectory: String): LocalProviderDescriptor {
        require(assetDirectory in setOf("providers/device-info", "providers/text-digest"))
        ensureDirectory(temp)
        val work = File(temp, "bundled-${UUID.randomUUID()}").apply { check(mkdir()) }
        try {
            copyAssetDirectory(assetDirectory.trim('/'), work)
            require(File(work, "provider.json").isFile) { "Bundled provider is missing provider.json" }
            return commit(work, bundled = true)
        } finally { work.deleteRecursively() }
    }

    @Synchronized fun delete(id: String) {
        require(id.matches(Regex("[a-zA-Z][a-zA-Z0-9_-]{1,48}")) && id.lowercase(Locale.ROOT) !in reserved)
        val target = inside(root, id)
        if (!target.exists()) return
        checkedTree(target)
        check(target.deleteRecursively())
    }

    private fun descriptor(directory: File): LocalProviderDescriptor {
        val file = inside(directory, "provider.json")
        require(Files.isRegularFile(file.toPath(), NOFOLLOW_LINKS) && file.length() in 1..65_536)
        val decoder = Charsets.UTF_8.newDecoder().onMalformedInput(java.nio.charset.CodingErrorAction.REPORT)
            .onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT)
        val json = JSONObject(decoder.decode(java.nio.ByteBuffer.wrap(file.readBytes())).toString())
        require(json.get("id") is String && json.getString("id").matches(Regex("[a-zA-Z][a-zA-Z0-9_-]{1,48}")))
        val version = if (json.has("version")) { require(json.get("version") is String); json.getString("version") } else "1.0.0"
        require(version.length in 1..128 && version.none { it.isISOControl() })
        val commandArray = json.getJSONArray("command")
        require(commandArray.length() in 1..64)
        val command = (0 until commandArray.length()).map {
            require(commandArray.get(it) is String)
            commandArray.getString(it).also { arg -> require(arg.length <= 4096 && arg.none { c -> c.isISOControl() }) }
        }
        require(command.first().isNotBlank()) { "Provider command is empty" }
        return LocalProviderDescriptor(json.getString("id"), version, directory, command)
    }

    private fun commit(source: File, bundled: Boolean): LocalProviderDescriptor {
        val id = descriptor(source).id
        require(bundled || id.lowercase(Locale.ROOT) !in reserved) { "导入包不能覆盖内置工具提供者" }
        val hash = hash(source)
        ensureDirectory(root)
        val providerRoot = inside(root, id).also(::ensureDirectory)
        val versions = inside(providerRoot, "versions").also(::ensureDirectory)
        val target = inside(versions, hash)
        if (!target.exists()) {
            val stage = File(providerRoot, ".commit-${UUID.randomUUID()}")
            try {
                require(source.copyRecursively(stage, overwrite = false))
                require(hash(stage) == hash) { "工具包复制校验失败" }
                Files.move(stage.toPath(), target.toPath(), ATOMIC_MOVE)
            } finally { stage.deleteRecursively() }
        }
        val installed = descriptor(target)
        verifyPin(installed)
        val pointer = inside(providerRoot, "active")
        val temporary = File(providerRoot, ".active-${UUID.randomUUID()}")
        try {
            java.io.FileOutputStream(temporary).use { it.write(hash.toByteArray(Charsets.US_ASCII)); it.fd.sync() }
            Files.move(temporary.toPath(), pointer.toPath(), ATOMIC_MOVE, REPLACE_EXISTING)
        } finally { temporary.delete() }
        return installed
    }

    private fun copyAssetDirectory(path: String, destination: File) {
        val children = appContext.assets.list(path).orEmpty()
        require(children.isNotEmpty()) { "Bundled provider assets are missing: $path" }
        children.forEach { name ->
            val childPath = "$path/$name"
            val nested = appContext.assets.list(childPath).orEmpty()
            val target = File(destination, name)
            if (nested.isNotEmpty()) {
                target.mkdirs()
                copyAssetDirectory(childPath, target)
            } else {
                target.parentFile?.mkdirs()
                appContext.assets.open(childPath).use { input -> target.outputStream().use(input::copyTo) }
            }
        }
    }

    private fun extract(input: InputStream, destination: File) {
        var count = 0
        var total = 0L
        val seen = mutableSetOf<String>()
        ZipInputStream(input.buffered()).use { zip ->
            while (true) {
                val entry = zip.nextEntry ?: break
                require(++count <= 200) { "工具包文件过多" }
                val name = entry.name.removeSuffix("/")
                require(name.length in 1..4096 && name.split('/').size <= 32 && !name.startsWith('/') && '\\' !in name && ':' !in name &&
                    name.none { it.isISOControl() } && name.split('/').all { it.isNotEmpty() && it != "." && it != ".." }) { "工具包包含非法路径" }
                require(seen.add(name.lowercase(Locale.ROOT))) { "工具包包含重复或大小写冲突路径" }
                var parent = destination
                name.split('/').forEach { part ->
                    require(parent.listFiles().orEmpty().none { it.name.equals(part, true) && it.name != part }) { "工具包路径大小写冲突" }
                    parent = File(parent, part)
                }
                val target = inside(destination, name)
                if (entry.isDirectory) require(target.mkdirs() || target.isDirectory) else {
                    require(target.parentFile!!.mkdirs() || target.parentFile!!.isDirectory)
                    require(!target.exists()) { "工具包文件路径冲突" }
                    target.outputStream().use { output ->
                        val buffer = ByteArray(8192)
                        while (true) {
                            val read = zip.read(buffer); if (read < 0) break
                            total += read; require(total <= 20L * 1024 * 1024) { "工具包解压后超过 20 MB" }
                            output.write(buffer, 0, read)
                        }
                    }
                }
            }
        }
    }

    private fun hash(directory: File): String {
        val tree = checkedTree(directory)
        val digest = MessageDigest.getInstance("SHA-256")
        digest.update("AndroidLocalProvider-content-v2\n".toByteArray())
        var total = 0L
        tree.filter { it.isFile }.sortedBy { it.relativeTo(directory).path }.forEach { file ->
            val name = file.relativeTo(directory).invariantSeparatorsPath.toByteArray(Charsets.UTF_8)
            digest.update(java.nio.ByteBuffer.allocate(4).putInt(name.size).array())
            digest.update(name)
            digest.update(java.nio.ByteBuffer.allocate(8).putLong(file.length()).array())
            file.inputStream().use { input ->
                val bytes = ByteArray(8192)
                while (true) {
                    val read = input.read(bytes); if (read < 0) break
                    total += read; require(total <= 20L * 1024 * 1024)
                    digest.update(bytes, 0, read)
                }
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun verifyPin(item: LocalProviderDescriptor) {
        require(item.id.matches(Regex("[a-zA-Z][a-zA-Z0-9_-]{1,48}")))
        val pin = item.directory.name
        require(pin.matches(Regex("[a-f0-9]{64}")))
        val directory = inside(root, "${item.id}/versions/$pin")
        require(item.directory == directory && descriptor(directory) == item && hash(directory) == pin) {
            "工具包描述或版本内容已变化"
        }
    }

    private fun ensureDirectory(directory: File) {
        require(!Files.isSymbolicLink(directory.toPath())) { "工具包路径不能是符号链接" }
        require(directory.mkdirs() || Files.isDirectory(directory.toPath(), NOFOLLOW_LINKS))
    }

    private fun inside(parent: File, relative: String): File {
        require(!File(relative).isAbsolute && relative.split('/').all { it.isNotEmpty() && it != "." && it != ".." })
        require(!Files.isSymbolicLink(parent.toPath()))
        var result = parent
        for (part in relative.split('/')) {
            result = File(result, part)
            require(!Files.isSymbolicLink(result.toPath())) { "工具包路径不能是符号链接" }
        }
        require(result.canonicalPath.startsWith(parent.canonicalPath + File.separator))
        return result
    }

    private fun checkedTree(directory: File): List<File> {
        require(Files.isDirectory(directory.toPath(), NOFOLLOW_LINKS))
        val result = mutableListOf<File>()
        directory.walkTopDown().onEnter { dir -> require(!Files.isSymbolicLink(dir.toPath())); true }.forEach { file ->
            require(result.size < 401 && !Files.isSymbolicLink(file.toPath()))
            require(Files.isRegularFile(file.toPath(), NOFOLLOW_LINKS) || Files.isDirectory(file.toPath(), NOFOLLOW_LINKS))
            result.add(file)
        }
        return result
    }
}
