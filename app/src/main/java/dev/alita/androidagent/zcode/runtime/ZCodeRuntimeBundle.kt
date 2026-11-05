package dev.alita.androidagent.zcode.runtime

import android.content.Context
import org.json.JSONObject
import java.io.File
import java.io.InputStream
import java.security.MessageDigest
import java.security.SecureRandom

sealed interface ZCodeRuntimePreparation {
    data class Ready(val layout: ZCodeRuntimeLayout) : ZCodeRuntimePreparation
    data class Missing(val files: List<String>) : ZCodeRuntimePreparation
    data class Invalid(val reason: String) : ZCodeRuntimePreparation
}

data class ZCodeRuntimeLayout(
    val version: String,
    val node: File,
    val bash: File,
    val root: File,
    val entrypoint: File,
    val gateway: File,
    val carrier: File,
    val webSearch: File,
    val workspaceFiles: File,
    val uiTree: File,
    val visionPipeline: File,
    val zcodeBundle: File,
    val builtinConfig: File,
    val contentHash: String,
)

/** Installs and verifies the SHA-pinned Route-A runtime payload. */
class ZCodeRuntimeBundle(private val context: Context) {
    private val assetRoot = "zcode-runtime"
    private val destination = File(context.filesDir, "runtime")

    fun prepare(): ZCodeRuntimePreparation {
        val requiredAssets = listOf(
            "$assetRoot/runtime-manifest.json",
            "$assetRoot/payload-SHA256SUMS.txt",
            "$assetRoot/bootstrap.cjs",
            "$assetRoot/skill-session-bindings.cjs",
            "$assetRoot/provider-review-bindings.cjs",
            "$assetRoot/gateway.cjs",
            "$assetRoot/carrier-authorization.cjs",
            "$assetRoot/android-carrier.cjs",
            "$assetRoot/web-search.cjs",
            "$assetRoot/workspace-files.cjs",
            "$assetRoot/workspace-analysis.cjs",
            "$assetRoot/analysis-worker.cjs",
            "$assetRoot/ui-tree.cjs",
            "$assetRoot/vision-pipeline.cjs",
            "$assetRoot/zcode.cjs",
            "$assetRoot/provider/zcode-builtin.json",
            "providers/text-digest/provider.json",
            "providers/text-digest/provider.cjs",
        )
        val missing = requiredAssets.filterNot(::assetExists).toMutableList()
        val nativeDir = context.applicationInfo.nativeLibraryDir?.let(::File)
            ?: File(context.filesDir, "missing-native-library-dir")
        val node = File(nativeDir, "libnode.so")
        val bash = File(nativeDir, "libbash.so")
        if (!node.isFile) missing += "jniLibs/arm64-v8a/libnode.so"
        if (!bash.isFile) missing += "jniLibs/arm64-v8a/libbash.so"
        if (missing.isNotEmpty()) return ZCodeRuntimePreparation.Missing(missing)

        return runCatching {
            val manifest = readAssetJson("$assetRoot/runtime-manifest.json")
            val version = manifest.getString("version")
            require(version == "0.16.9-runtime5") { "Unsupported runtime payload version: $version" }
            val entrypointArg = manifest.getJSONObject("entrypoint").getJSONArray("args").getString(0)
            val entrypointName = safeRelative(entrypointArg.substringAfterLast('/'))
            val sumsText = context.assets.open("$assetRoot/payload-SHA256SUMS.txt")
                .bufferedReader().use { it.readText() }
            val sums = parseSums(sumsText)
            require(sums.isNotEmpty()) { "Runtime SHA-256 manifest is empty" }
            verifyPackagedPayload(sums, node, bash)
            val payloadHash = sha256(sumsText.byteInputStream())

            val stateFile = File(destination, ".bundle-state.json")
            val installed = runCatching { JSONObject(stateFile.readText()) }.getOrNull()
            val reusable = installed?.optString("runtimeVersion") == version &&
                installed.optString("payloadManifestSha256") == payloadHash &&
                verifyInstalledPayload(sums)
            if (!reusable) installPayload(sums, version, payloadHash)

            ZCodeRuntimePreparation.Ready(ZCodeRuntimeLayout(
                version = version,
                node = node,
                bash = bash,
                root = destination,
                entrypoint = File(destination, entrypointName).requireInside(destination),
                gateway = File(destination, "gateway.cjs").requireInside(destination),
                carrier = File(destination, "android-carrier.cjs").requireInside(destination),
                webSearch = File(destination, "web-search.cjs").requireInside(destination),
                workspaceFiles = File(destination, "workspace-files.cjs").requireInside(destination),
                uiTree = File(destination, "ui-tree.cjs").requireInside(destination),
                visionPipeline = File(destination, "vision-pipeline.cjs").requireInside(destination),
                zcodeBundle = File(destination, "zcode.cjs").requireInside(destination),
                builtinConfig = File(destination, "provider/zcode-builtin.json").requireInside(destination),
                contentHash = payloadHash,
            ).also(::validateLayout))
        }.getOrElse { ZCodeRuntimePreparation.Invalid(it.message ?: it.javaClass.simpleName) }
    }

    fun processBuilder(layout: ZCodeRuntimeLayout): ProcessBuilder {
        val files = context.filesDir
        val cache = File(context.cacheDir, "tmp").apply { mkdirs() }
        val logs = File(files, "logs").apply { mkdirs() }
        val personal = File(layout.root, "provider/personal_provider_config.json")
        val nativeDir = requireNotNull(context.applicationInfo.nativeLibraryDir) { "Native library directory unavailable" }
        return ProcessBuilder(layout.node.absolutePath, layout.entrypoint.absolutePath)
            .directory(files)
            .redirectErrorStream(false)
            .apply {
                environment().apply {
                    this["HOME"] = files.absolutePath
                    this["SPIKE_ROOT"] = files.absolutePath
                    this["SPIKE_MODE"] = "real"
                    this["SPIKE_HTTP_PORT"] = "8765"
                    this["SHELL"] = layout.bash.absolutePath
                    this["PATH"] = "$nativeDir:/system/bin:/system/xbin"
                    this["LD_LIBRARY_PATH"] = listOf(
                        File(layout.root, "shell-lib").absolutePath,
                        File(layout.root, "lib").absolutePath,
                    ).joinToString(File.pathSeparator)
                    this["TMPDIR"] = cache.absolutePath
                    this["CLAUDE_CODE_TMPDIR"] = cache.absolutePath
                    this["OPENSSL_CONF"] = "/dev/null"
                    this["ZCODE_STORAGE_DIR"] = files.absolutePath
                    this["ZCODE_LOG_DIR"] = logs.absolutePath
                    this["ZCODE_BUILTIN_PROVIDER_CONFIG_FILE"] = layout.builtinConfig.absolutePath
                    this["ZCODE_PERSONAL_PROVIDER_CONFIG_FILE"] = personal.absolutePath
                    this["BRIDGE_TOKEN"] = bridgeToken()
                    this["GATEWAY_MODE"] = "ask"
                    this["DEFAULT_THOUGHT_LEVEL"] = "disabled"
                    this["CARRIER_ENABLED"] = "1"
                    this["CARRIER_CALL_TIMEOUT_MS"] = "120000"
                }
            }
    }

    fun bridgeToken(): String {
        val file = File(destination, "bridge-token")
        if (file.isFile) return file.readText().trim()
        file.parentFile?.mkdirs()
        val token = ByteArray(24).also(SecureRandom()::nextBytes).joinToString("") { "%02x".format(it) }
        file.writeText(token)
        file.setReadable(false, false)
        file.setReadable(true, true)
        return token
    }

    private fun installPayload(sums: Map<String, String>, version: String, payloadHash: String) {
        val staging = File(context.cacheDir, "zcode-runtime-${System.nanoTime()}")
        try {
            staging.deleteRecursively()
            staging.mkdirs()
            copyAssetTree(assetRoot, staging)
            verifyStagedPayload(staging, sums)
            destination.deleteRecursively()
            destination.mkdirs()
            overlay(staging, destination)
            File(destination, ".bundle-state.json").writeText(JSONObject()
                .put("runtimeVersion", version)
                .put("payloadManifestSha256", payloadHash)
                .toString(2))
        } finally {
            staging.deleteRecursively()
        }
    }

    private fun verifyPackagedPayload(sums: Map<String, String>, node: File, bash: File) {
        sums.forEach { (path, expected) ->
            when {
                path.startsWith("assets/") -> {
                    val relative = path.removePrefix("assets/")
                    val actual = context.assets.open(relative).use(::sha256)
                    require(actual.equals(expected, true)) { "Packaged runtime hash mismatch: $relative" }
                }
                path == "jniLibs/arm64-v8a/libnode.so" -> require(fileSha256(node).equals(expected, true)) {
                    "Packaged Node hash mismatch"
                }
                path == "jniLibs/arm64-v8a/libbash.so" -> require(fileSha256(bash).equals(expected, true)) {
                    "Packaged Bash hash mismatch"
                }
            }
        }
    }

    private fun verifyStagedPayload(staging: File, sums: Map<String, String>) {
        sums.filterKeys { it.startsWith("assets/zcode-runtime/") }.forEach { (path, expected) ->
            val file = File(staging, path.removePrefix("assets/zcode-runtime/")).requireInside(staging)
            require(file.isFile && fileSha256(file).equals(expected, true)) { "Staged runtime hash mismatch: $path" }
        }
    }

    private fun verifyInstalledPayload(sums: Map<String, String>): Boolean = runCatching {
        sums.filterKeys {
            it.startsWith("assets/zcode-runtime/") &&
                it != "assets/zcode-runtime/provider/personal_provider_config.json"
        }.all { (path, expected) ->
            val file = File(destination, path.removePrefix("assets/zcode-runtime/")).requireInside(destination)
            file.isFile && fileSha256(file).equals(expected, true)
        }
    }.getOrDefault(false)

    private fun parseSums(text: String): Map<String, String> = text.lineSequence().mapNotNull { line ->
        val match = Regex("^([0-9A-Fa-f]{64})  (.+)$").matchEntire(line.trim()) ?: return@mapNotNull null
        match.groupValues[2] to match.groupValues[1].uppercase()
    }.toMap()

    private fun validateLayout(layout: ZCodeRuntimeLayout) {
        require(layout.entrypoint.isFile) { "Runtime entrypoint is missing" }
        require(layout.gateway.isFile) { "Gateway is missing" }
        require(layout.carrier.isFile) { "Android carrier is missing" }
        require(layout.webSearch.isFile) { "Web search runtime is missing" }
        require(layout.workspaceFiles.isFile) { "Workspace file runtime is missing" }
        require(layout.uiTree.isFile) { "UI tree runtime is missing" }
        require(layout.visionPipeline.isFile) { "Vision runtime is missing" }
        require(layout.zcodeBundle.isFile && layout.zcodeBundle.length() == 14_820_819L) { "ZCode bundle is missing or invalid" }
        require(layout.builtinConfig.isFile && layout.builtinConfig.length() == 188_476L) { "ZCode builtin config is missing or invalid" }
        require(File(layout.root, "lib").listFiles().orEmpty().count(File::isFile) == 9) { "Node dependency set is incomplete" }
        require(File(layout.root, "shell-lib").listFiles().orEmpty().count(File::isFile) == 6) { "Bash dependency set is incomplete" }
    }

    private fun readAssetJson(path: String) = context.assets.open(path).bufferedReader().use { JSONObject(it.readText()) }

    private fun assetExists(path: String): Boolean = runCatching { context.assets.open(path).close(); true }.getOrDefault(false)

    private fun copyAssetTree(path: String, target: File) {
        val children = context.assets.list(path).orEmpty()
        require(children.isNotEmpty()) { "Runtime asset directory is empty: $path" }
        children.forEach { child ->
            val childPath = "$path/$child"
            val nested = context.assets.list(childPath).orEmpty()
            val output = File(target, child)
            if (nested.isNotEmpty()) {
                output.mkdirs()
                copyAssetTree(childPath, output)
            } else {
                output.parentFile?.mkdirs()
                context.assets.open(childPath).use { input -> output.outputStream().use(input::copyTo) }
            }
        }
    }

    private fun overlay(source: File, target: File) {
        source.walkTopDown().forEach { file ->
            val relative = file.relativeTo(source)
            val output = File(target, relative.path)
            if (file.isDirectory) output.mkdirs() else {
                output.parentFile?.mkdirs()
                file.copyTo(output, overwrite = true)
            }
        }
    }

    private fun safeRelative(path: String): String {
        require(path.isNotBlank() && !File(path).isAbsolute && ".." !in path.split('/', '\\')) { "Invalid runtime path" }
        return path
    }

    private fun fileSha256(file: File): String = file.inputStream().use(::sha256)

    private fun sha256(input: InputStream): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
        while (true) {
            val count = input.read(buffer)
            if (count < 0) break
            if (count > 0) digest.update(buffer, 0, count)
        }
        return digest.digest().joinToString("") { "%02X".format(it) }
    }

    private fun File.requireInside(root: File): File = canonicalFile.also {
        require(it.path.startsWith(root.canonicalPath + File.separator)) { "Runtime path escaped bundle" }
    }
}
