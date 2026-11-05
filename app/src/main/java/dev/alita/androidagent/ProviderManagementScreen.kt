package dev.alita.androidagent

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import dev.alita.androidagent.tools.ProviderAdmissionCandidate
import dev.alita.androidagent.tools.ProviderAdmissionDraft

/** Trusted host declarations are entered here; imported code is never run to obtain its own grant. */
@Composable
internal fun ProviderManagementScreen(
    state: MainUiState,
    refresh: () -> Unit,
    importProvider: (Uri) -> Unit,
    preview: (String, String, String, String, String) -> Unit,
    approve: (ProviderAdmissionDraft) -> Unit,
    clearDraft: () -> Unit,
    retire: (String) -> Unit,
    revoke: (String, String, String) -> Unit,
    stopAgent: () -> Unit,
) {
    LaunchedEffect(Unit) { refresh() }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let(importProvider) }
    var editing by remember { mutableStateOf<ProviderAdmissionCandidate?>(null) }
    var retiring by remember { mutableStateOf<ProviderAdmissionCandidate?>(null) }
    var revoking by remember { mutableStateOf<ProviderAdmissionCandidate?>(null) }
    var editName by remember { mutableStateOf("") }
    var editVersion by remember { mutableStateOf("1") }
    var editDescription by remember { mutableStateOf("") }
    val canModify = !state.providersBusy && !state.providersHostActive
    LaunchedEffect(state.providerDraft) {
        state.providerDraft?.let { draft ->
            if (editing == null) {
                editing = state.providers.firstOrNull { it.id == draft.id && it.contentHash == draft.contentHash }
                editName = draft.toolName; editVersion = draft.toolVersion; editDescription = draft.description
            }
        }
    }

    Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("独立本地工具", style = MaterialTheme.typography.titleLarge)
        Text("导入只保存文件，不执行工具、不进行协议握手，也不授予权限。评审时请依据你信任的源码填写声明，当前每个包仅支持一个纯数据工具。", style = MaterialTheme.typography.bodySmall)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(enabled = !state.providersBusy, onClick = {
                picker.launch(arrayOf("application/zip", "application/octet-stream", "application/x-zip-compressed"))
            }) { Text("导入工具 ZIP") }
            TextButton(enabled = !state.providersBusy, onClick = refresh) { Text("刷新") }
        }
        if (state.providersHostActive) {
            Text("Agent 正在运行。请先停止，再修改工具；重新打开 Agent 后生效。导入文件不会改变运行中的工具版本。", color = MaterialTheme.colorScheme.primary)
            OutlinedButton(enabled = !state.providersBusy, onClick = stopAgent) { Text("停止 Agent 以管理工具") }
        } else {
            Text("Agent 已停止，可修改准入。重新打开后，新会话使用所选版本；已有会话保留绑定记录。", style = MaterialTheme.typography.bodySmall)
        }
        if (state.providersBusy) LinearProgressIndicator(Modifier.fillMaxWidth())
        LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (state.providers.isEmpty() && !state.providersBusy) item { Text("尚无可评审的工具包。先导入包含 provider.json 和 Node 程序的 ZIP。") }
            items(state.providers, key = { "${it.id}:${it.contentHash}" }) { candidate ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("${candidate.id} · ${candidate.version}", fontWeight = FontWeight.Bold)
                        Text("来源：本机导入包，发布者未经验证", style = MaterialTheme.typography.bodySmall)
                        Text("包内容 SHA-256：${candidate.contentHash}", style = MaterialTheme.typography.bodySmall)
                        Text("入口：${candidate.entry}", style = MaterialTheme.typography.bodySmall)
                        val selectedHere = candidate.contentHash == candidate.selectedContentHash
                        Text(when {
                            !candidate.selectedAvailable -> "所选版本校验失败；启动将拒绝加载，请停用或撤销"
                            selectedHere -> "已准入：${candidate.selectedToolIds.joinToString()}"
                            candidate.selectedContentHash != null -> "已保存，当前准入的是另一个版本"
                            else -> "已保存，尚未准入"
                        }, color = MaterialTheme.colorScheme.primary)
                        if (candidate.selectedContentHash != null) {
                            Text("所选包 SHA-256：${candidate.selectedContentHash}", style = MaterialTheme.typography.bodySmall)
                            Text("所选声明 SHA-256：${candidate.selectedDefinitionHash}", style = MaterialTheme.typography.bodySmall)
                        }
                        OutlinedButton(enabled = canModify && candidate.available, onClick = {
                            clearDraft(); editName = ""; editVersion = "1"; editDescription = ""; editing = candidate
                        }) { Text("填写声明并评审") }
                        if (candidate.selectedContentHash != null && candidate.selectedDefinitionHash != null) {
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                TextButton(enabled = canModify, onClick = { retiring = candidate }) { Text("停用新会话") }
                                TextButton(enabled = canModify, onClick = { revoking = candidate }) { Text("撤销所选版本") }
                            }
                        }
                    }
                }
            }
        }
    }

    editing?.let { candidate ->
        if (state.providerDraft == null) ProviderReviewEditor(candidate, canModify,
            editName, editVersion, editDescription, state.error, onDismiss = {
            if (!state.providersBusy) { editing = null; clearDraft() }
        }, onCheck = { name, version, description ->
            editName = name; editVersion = version; editDescription = description
            preview(candidate.id, candidate.contentHash, name, version, description)
        })
    }
    state.providerDraft?.let { draft ->
        AlertDialog(
            onDismissRequest = { if (!state.providersBusy) clearDraft() },
            title = { Text("确认准入此版本") },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("工具：${draft.id}.${draft.toolName} · ${draft.toolVersion}", fontWeight = FontWeight.Bold)
                    Text("包版本：${draft.version}")
                    Text("包内容 SHA-256：${draft.contentHash}")
                    Text("声明 SHA-256：${draft.definitionHash}")
                    Text("入口：${draft.entry}")
                    Text("供模型使用的说明：\n${draft.description}")
                    Text("限定为 data-transform：只接收最多 21848 个字符的 base64 数据（解码后最多 16 KiB）。隔离进程不直接获得网络、文件或 root 能力；这不代表任意脚本都可安全导入。每次调用仍经过 Gateway 授权与记录，准入不会自动允许高风险操作。")
                    Text("检查和准入均不运行包内程序。重新打开 Agent 后向新会话提供此声明，已有会话保留原版本绑定。")
                }
            },
            confirmButton = { Button(enabled = canModify, onClick = { editing = null; approve(draft) }) { Text("确认准入") } },
            dismissButton = { TextButton(enabled = !state.providersBusy, onClick = clearDraft) { Text("返回修改") } },
        )
    }
    retiring?.let { candidate ->
        AlertDialog(
            onDismissRequest = { retiring = null }, title = { Text("停用新会话？") },
            text = { Text("将取消 ${candidate.id} 的所选版本，不删除包文件、评审记录或已有会话绑定。重新打开 Agent 后，新会话不再发现该工具；已有会话可能因工具不再可见而无法继续调用。") },
            confirmButton = { Button(enabled = canModify, onClick = { retiring = null; retire(candidate.id) }) { Text("确认停用") } },
            dismissButton = { TextButton(onClick = { retiring = null }) { Text("取消") } },
        )
    }
    revoking?.let { candidate ->
        AlertDialog(
            onDismissRequest = { revoking = null }, title = { Text("撤销所选版本？") },
            text = { Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("${candidate.id}：后续解析将拒绝这个已评审版本，包括已有会话。不会删除包文件，不保证中断已经取得执行句柄的调用。")
                Text("包内容 SHA-256：${candidate.selectedContentHash}")
                Text("声明 SHA-256：${candidate.selectedDefinitionHash}")
            } },
            confirmButton = { Button(enabled = canModify, onClick = {
                revoking = null
                val contentHash = candidate.selectedContentHash
                val definitionHash = candidate.selectedDefinitionHash
                if (contentHash != null && definitionHash != null) revoke(candidate.id, contentHash, definitionHash)
            }) { Text("确认撤销") } },
            dismissButton = { TextButton(onClick = { revoking = null }) { Text("取消") } },
        )
    }
}

@Composable
private fun ProviderReviewEditor(
    candidate: ProviderAdmissionCandidate,
    enabled: Boolean,
    initialName: String,
    initialVersion: String,
    initialDescription: String,
    error: String?,
    onDismiss: () -> Unit,
    onCheck: (String, String, String) -> Unit,
) {
    var name by remember(candidate.id, candidate.contentHash) { mutableStateOf(initialName) }
    var version by remember(candidate.id, candidate.contentHash) { mutableStateOf(initialVersion) }
    var description by remember(candidate.id, candidate.contentHash) { mutableStateOf(initialDescription) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("评审 ${candidate.id}") },
        text = { Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("请从已审阅源码确定协议名称、版本和用途；不会运行程序或采纳程序自行声明的权限。")
            Text("包内容 SHA-256：${candidate.contentHash}", style = MaterialTheme.typography.bodySmall)
            OutlinedTextField(name, { name = it }, Modifier.fillMaxWidth(), enabled = enabled,
                label = { Text("工具协议名称（不含包名前缀）") }, singleLine = true)
            OutlinedTextField(version, { version = it }, Modifier.fillMaxWidth(), enabled = enabled,
                label = { Text("工具协议版本") }, singleLine = true)
            OutlinedTextField(description, { description = it }, Modifier.fillMaxWidth(), enabled = enabled,
                label = { Text("供模型使用的用途说明") }, minLines = 3, maxLines = 8)
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Text("当前仅支持一个纯数据工具，输入格式固定为有上限的 base64 数据。下一步将展示精确声明与哈希供确认。", style = MaterialTheme.typography.bodySmall)
        } },
        confirmButton = { Button(enabled = enabled && name.isNotBlank() && version.isNotBlank() && description.isNotBlank(),
            onClick = { onCheck(name.trim(), version.trim(), description.trim()) }) { Text("检查") } },
        dismissButton = { TextButton(enabled = enabled, onClick = onDismiss) { Text("取消") } },
    )
}
