package dev.alita.androidagent.zcode.runtime

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import java.io.File

/**
 * Phase 5 host-owned workspace surface. Shared-storage access stays behind the
 * system document picker; the model only sees app-private workspace files.
 */
class WorkspaceActivity : Activity() {
    private val repository by lazy { WorkspaceRepository(filesDir) }
    private lateinit var status: TextView
    private var pendingExportName: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        pendingExportName = savedInstanceState?.getString(STATE_EXPORT_NAME)
        val padding = (16 * resources.displayMetrics.density).toInt()
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(padding, padding, padding, padding)
        }
        status = TextView(this).apply { textSize = 15f }
        root.addView(status)
        root.addView(actionButton("新建工作区", ::showCreateDialog))
        root.addView(actionButton("切换工作区", ::showSwitchDialog))
        root.addView(actionButton("从手机导入文件", ::importFile))
        root.addView(actionButton("导出工作区文件", ::showExportDialog))
        setContentView(root)
        refresh()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putString(STATE_EXPORT_NAME, pendingExportName)
        super.onSaveInstanceState(outState)
    }

    private fun actionButton(label: String, action: () -> Unit) =
        Button(this).apply { text = label; setOnClickListener { action() } }

    private fun refresh() {
        val active = repository.activeName()
        val workspaces = repository.list()
        val files = repository.files(active)
        status.text = buildString {
            append("当前工作区：").append(active).append('\n')
            append("工作区：").append(workspaces.joinToString().ifEmpty { "无" }).append('\n')
            append("文件（").append(files.size).append("）：")
            append(files.take(12).joinToString().ifEmpty { "无" })
        }
    }

    private fun showCreateDialog() {
        val input = EditText(this).apply { hint = "例如：project-alpha"; isSingleLine = true }
        AlertDialog.Builder(this)
            .setTitle("新建工作区")
            .setView(input)
            .setPositiveButton("创建") { _, _ ->
                runCatching { repository.createAndSwitch(input.text.toString()) }
                    .onSuccess { toast("已创建并切换到 $it"); refresh() }
                    .onFailure { toast(it.message ?: "工作区名称无效") }
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun showSwitchDialog() {
        val names = repository.list()
        if (names.isEmpty()) return toast("还没有工作区")
        AlertDialog.Builder(this)
            .setTitle("切换工作区")
            .setItems(names.toTypedArray()) { _, index ->
                repository.switch(names[index])
                toast("已切换到 ${names[index]}；新会话立即使用，运行中的会话重启后使用")
                refresh()
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun importFile() {
        startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "*/*"
        }, REQUEST_IMPORT)
    }

    private fun showExportDialog() {
        val files = repository.files(repository.activeName())
        if (files.isEmpty()) return toast("当前工作区没有可导出的文件")
        AlertDialog.Builder(this)
            .setTitle("选择要导出的文件")
            .setItems(files.toTypedArray()) { _, index ->
                val name = files[index]
                startActivityForResult(Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "application/octet-stream"
                    putExtra(Intent.EXTRA_TITLE, name)
                }, REQUEST_EXPORT)
                pendingExportName = name
            }
            .setNegativeButton("取消", null)
            .show()
    }

    @Deprecated("Activity result API retained for the small handoff-compatible host surface")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        val uri = data?.data ?: return
        if (resultCode != RESULT_OK) return
        runCatching {
            when (requestCode) {
                REQUEST_IMPORT -> importFrom(uri)
                REQUEST_EXPORT -> exportTo(uri)
            }
        }.onSuccess { refresh() }.onFailure { toast(it.message ?: "文件操作失败") }
    }

    private fun importFrom(uri: Uri) {
        val displayName = contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) cursor.getString(0) else null
        }
        val name = repository.safeFileName(displayName ?: "imported-${System.currentTimeMillis()}")
        val destination = repository.file(repository.activeName(), name)
        val input = requireNotNull(contentResolver.openInputStream(uri)) { "无法读取所选文件" }
        input.use { source -> destination.outputStream().use(source::copyTo) }
        toast("已导入 $name")
    }

    private fun exportTo(uri: Uri) {
        val name = requireNotNull(pendingExportName) { "没有待导出的文件" }
        val source = repository.file(repository.activeName(), name)
        val output = requireNotNull(contentResolver.openOutputStream(uri)) { "无法写入所选位置" }
        output.use { destination -> source.inputStream().use { it.copyTo(destination) } }
        pendingExportName = null
        toast("已导出 $name")
    }

    private fun toast(message: String) = Toast.makeText(this, message, Toast.LENGTH_SHORT).show()

    companion object {
        private const val REQUEST_IMPORT = 1001
        private const val REQUEST_EXPORT = 1002
        private const val STATE_EXPORT_NAME = "workspace-export-name"
    }
}

internal class WorkspaceRepository(private val filesDir: File) {
    private val root = File(filesDir, "workspaces")
    private val activeFile = File(filesDir, "active-workspace")

    init {
        root.mkdirs()
        File(root, activeName()).mkdirs()
    }

    fun activeName(): String = activeFile.takeIf(File::isFile)?.readText()?.trim()
        ?.takeIf(::isValidName) ?: "default"

    fun list(): List<String> = root.listFiles()
        .orEmpty()
        .filter(File::isDirectory)
        .map(File::getName)
        .filter(::isValidName)
        .sorted()

    fun files(workspace: String): List<String> = directory(workspace).listFiles()
        .orEmpty()
        .filter(File::isFile)
        .map(File::getName)
        .sorted()

    fun createAndSwitch(name: String): String {
        val normalized = name.trim()
        require(isValidName(normalized)) { "名称只能包含字母、数字、点、下划线和连字符，且不能包含 .." }
        directory(normalized).mkdirs()
        writeActive(normalized)
        return normalized
    }

    fun switch(name: String) {
        require(directory(name).isDirectory) { "工作区不存在" }
        writeActive(name)
    }

    fun safeFileName(name: String): String {
        require('/' !in name && '\\' !in name && ".." !in name) { "文件名无效" }
        require(name.none { it == '\u0000' || it.code < 0x20 || it.code == 0x7f }) { "文件名包含控制字符" }
        val normalized = name.trim().ifEmpty { "imported-file" }
        require(normalized != "." && normalized != "..") { "文件名无效" }
        require(normalized.toByteArray(Charsets.UTF_8).size <= 255) { "文件名过长" }
        return normalized
    }

    fun file(workspace: String, name: String): File {
        val safe = safeFileName(name)
        return File(directory(workspace), safe).canonicalFile.also { output ->
            require(output.parentFile == directory(workspace).canonicalFile) { "文件路径越界" }
        }
    }

    private fun directory(name: String): File {
        require(isValidName(name)) { "工作区名称无效" }
        return File(root, name)
    }

    private fun writeActive(name: String) {
        val temporary = File(filesDir, "active-workspace.tmp")
        temporary.writeText(name)
        require(temporary.renameTo(activeFile) || runCatching {
            temporary.copyTo(activeFile, overwrite = true)
            temporary.delete()
        }.isSuccess) { "无法保存当前工作区" }
    }

    private fun isValidName(name: String): Boolean =
        name.isNotBlank() && name.length <= 64 && ".." !in name && name.matches(Regex("[A-Za-z0-9._-]+"))
}
