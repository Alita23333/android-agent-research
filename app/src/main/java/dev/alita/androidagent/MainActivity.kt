package dev.alita.androidagent

import android.Manifest
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dev.alita.androidagent.model.ModelSettings
import dev.alita.androidagent.skills.SkillAvailability
import dev.alita.androidagent.zcode.runtime.ZCodeActivity
import dev.alita.androidagent.zcode.runtime.SearchBackend
import dev.alita.androidagent.zcode.runtime.SearchConfig
import dev.alita.androidagent.zcode.runtime.SearchNetwork
import dev.alita.androidagent.zcode.runtime.ZCodeSearchConfigWriter
import dev.alita.androidagent.zcode.runtime.WorkspaceActivity
import dev.alita.androidagent.zcode.runtime.VisionConfig

class MainActivity : ComponentActivity() {
    private val viewModel: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= 33) registerForActivityResult(ActivityResultContracts.RequestPermission()) {}.launch(Manifest.permission.POST_NOTIFICATIONS)
        setContent { AgentApp(
            viewModel,
            onAccessibilitySettings = { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) },
            onZCodeRuntime = { startActivity(Intent(this, ZCodeActivity::class.java)) },
            onWorkspaces = { startActivity(Intent(this, WorkspaceActivity::class.java)) },
        ) }
    }
}

private enum class Screen(val label: String) { CHAT("任务"), SKILLS("技能"), PROVIDERS("工具"), SETTINGS("设置") }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AgentApp(viewModel: MainViewModel, onAccessibilitySettings: () -> Unit, onZCodeRuntime: () -> Unit, onWorkspaces: () -> Unit) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val approval by viewModel.pendingApproval.collectAsStateWithLifecycle()
    var screen by remember { mutableStateOf(Screen.CHAT) }
    MaterialTheme(colorScheme = lightColorScheme(primary = androidx.compose.ui.graphics.Color(0xFF3157D5))) {
        Scaffold(
            topBar = { TopAppBar(title = { Text("Android Agent") }, actions = {
                if (state.running) TextButton(onClick = viewModel::cancel) { Text("停止") }
            }) },
            bottomBar = { NavigationBar {
                Screen.entries.forEach { item -> NavigationBarItem(
                    selected = screen == item, onClick = { screen = item }, icon = { Text(if (screen == item) "●" else "○") }, label = { Text(item.label) }
                ) }
            } },
            snackbarHost = { SnackbarHost(remember { SnackbarHostState() }) },
        ) { padding ->
            Box(Modifier.padding(padding).fillMaxSize()) {
                when (screen) {
                    Screen.CHAT -> if (BuildConfig.LEGACY_DIAGNOSTICS) {
                        ChatScreen(state, viewModel::send)
                    } else {
                        ProductionAgentScreen(onZCodeRuntime)
                    }
                    Screen.SKILLS -> SkillsScreen(state, viewModel::importSkill, viewModel::setSkillEnabled, viewModel::deleteSkill)
                    Screen.PROVIDERS -> ProviderManagementScreen(state, viewModel::refreshProviders,
                        viewModel::importProvider, viewModel::previewProvider, viewModel::approveProvider,
                        viewModel::clearProviderDraft, viewModel::retireProvider, viewModel::revokeProvider,
                        viewModel::stopAgentForProviderManagement)
                    Screen.SETTINGS -> SettingsScreen(
                        viewModel.settings(), viewModel.searchSettings(), viewModel::saveSettings,
                        viewModel::saveSearchSettings, viewModel::runDiagnostics,
                        onAccessibilitySettings, onZCodeRuntime, onWorkspaces,
                        viewModel.visionSettings(), viewModel::saveVisionSettings,
                        viewModel::useCurrentModelForVision,
                    )
                }
                val message = state.error ?: state.notice
                if (message != null) Surface(
                    modifier = Modifier.align(Alignment.TopCenter).padding(12.dp), color = if (state.error != null) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.secondaryContainer,
                    shape = MaterialTheme.shapes.medium, shadowElevation = 4.dp,
                ) { Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(message, Modifier.weight(1f)); TextButton(onClick = viewModel::clearNotice) { Text("关闭") }
                } }
            }
        }
        approval?.let { pending -> AlertDialog(
            onDismissRequest = {},
            title = { Text(pending.title) },
            text = { Column { Text(pending.explanation); Spacer(Modifier.height(8.dp)); Text("工具：${pending.call.toolId}", fontWeight = FontWeight.Bold); Text(pending.call.arguments.toString(2)) } },
            confirmButton = { Button(onClick = { viewModel.resolveApproval(true) }) { Text("允许这一次") } },
            dismissButton = { TextButton(onClick = { viewModel.resolveApproval(false) }) { Text("拒绝") } },
        ) }
    }
}

@Composable
private fun ProductionAgentScreen(openZCodeRuntime: () -> Unit) {
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("ZCode Agent", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(12.dp))
        Text("任务、工具、工作区与恢复状态由 ZCode runtime 统一管理。")
        Spacer(Modifier.height(20.dp))
        Button(onClick = openZCodeRuntime) { Text("打开 Agent") }
    }
}

@Composable
private fun ChatScreen(state: MainUiState, send: (String) -> Unit) {
    var input by remember { mutableStateOf("") }
    Column(Modifier.fillMaxSize().padding(12.dp)) {
        LazyColumn(Modifier.weight(1f).fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (state.messages.isEmpty()) item {
                Text("告诉我你想在手机上完成什么。文件、命令和界面操作都会显示真实执行结果。", style = MaterialTheme.typography.bodyLarge)
            }
            items(state.messages) { item -> Surface(
                color = if (item.role == "你") MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant,
                shape = MaterialTheme.shapes.medium,
                modifier = Modifier.fillMaxWidth(if (item.role == "你") 0.92f else 1f),
            ) { Column(Modifier.padding(12.dp)) { Text(item.role, fontWeight = FontWeight.Bold); Text(item.text) } }
            }
            state.currentTool?.let { tool -> item { LinearProgressIndicator(Modifier.fillMaxWidth()); Text("正在运行 $tool", style = MaterialTheme.typography.bodySmall) } }
        }
        Row(verticalAlignment = Alignment.Bottom) {
            OutlinedTextField(input, { input = it }, Modifier.weight(1f), enabled = !state.running, label = { Text("任务") }, minLines = 1, maxLines = 5)
            Spacer(Modifier.width(8.dp))
            Button(onClick = { val value = input; input = ""; send(value) }, enabled = input.isNotBlank() && !state.running) { Text("运行") }
        }
    }
}

@Composable
private fun SkillsScreen(state: MainUiState, importSkill: (android.net.Uri) -> Unit, setEnabled: (String, Boolean) -> Unit, delete: (String) -> Unit) {
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let(importSkill) }
    Column(Modifier.fillMaxSize().padding(12.dp)) {
        Button(enabled = !state.skillsBusy, onClick = { picker.launch(arrayOf("application/zip", "application/octet-stream", "application/x-zip-compressed")) }) { Text("导入 Skill ZIP") }
        Text("启用后供新会话使用；已有会话保留原版本。更新后请重新启用。导入不会执行脚本或授予权限。", style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(vertical = 8.dp))
        if (state.skillsBusy) LinearProgressIndicator(Modifier.fillMaxWidth())
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(state.skills, key = { it.id }) { skill -> Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) { Text(skill.name, fontWeight = FontWeight.Bold); Text("${skill.id} · ${skill.version}", style = MaterialTheme.typography.bodySmall) }
                    Switch(checked = skill.enabled,
                        enabled = !state.skillsBusy && (skill.enabled || skill.availability in setOf(SkillAvailability.AVAILABLE, SkillAvailability.STORED)),
                        modifier = Modifier.semantics { contentDescription = "启用技能 ${skill.name}" },
                        onCheckedChange = { setEnabled(skill.id, it) })
                }
                Text(skill.description)
                Text(when (skill.availability) {
                    SkillAvailability.AVAILABLE -> "可用"
                    SkillAvailability.STORED -> "已保存，尚未启用"
                    SkillAvailability.MISSING_DEPENDENCY -> "缺少依赖：${skill.missingDependencies.joinToString()}"
                    SkillAvailability.DISABLED -> "已停用"
                    SkillAvailability.INVALID -> "技能包无效"
                }, color = if (skill.availability in setOf(SkillAvailability.AVAILABLE, SkillAvailability.STORED)) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error)
                Text("版本校验：${skill.hash.take(16)} · 来源：${skill.source}", style = MaterialTheme.typography.bodySmall)
                TextButton(enabled = !state.skillsBusy,
                    modifier = Modifier.semantics { contentDescription = "移除技能 ${skill.name}" },
                    onClick = { delete(skill.id) }) { Text("从列表移除") }
            } }
            }
        }
    }
}

@Composable
private fun SettingsScreen(
    initial: ModelSettings,
    initialSearch: SearchConfig,
    save: (String, String, String) -> Unit,
    saveSearch: (SearchConfig, String) -> Unit,
    runDiagnostics: () -> Unit,
    openAccessibility: () -> Unit,
    openZCodeRuntime: () -> Unit,
    openWorkspaces: () -> Unit,
    initialVision: VisionConfig,
    saveVision: (VisionConfig, String) -> Unit,
    useCurrentModelForVision: () -> Unit,
) {
    var baseUrl by remember(initial) { mutableStateOf(initial.baseUrl) }
    var apiKey by remember(initial) { mutableStateOf(initial.apiKey) }
    var model by remember(initial) { mutableStateOf(initial.model) }
    val firstSearch = initialSearch.backends.firstOrNull()
    var searchId by remember(initialSearch) { mutableStateOf(firstSearch?.id ?: "brave") }
    var searchUrl by remember(initialSearch) { mutableStateOf(firstSearch?.baseUrl ?: ZCodeSearchConfigWriter.defaultBaseUrl("brave")) }
    var searchKey by remember(initialSearch) { mutableStateOf("") }
    var searchCount by remember(initialSearch) { mutableStateOf((firstSearch?.defaultCount ?: 8).toString()) }
    var searchTimeout by remember(initialSearch) { mutableStateOf((firstSearch?.timeoutMs ?: 60_000).toString()) }
    var searchCap by remember(initialSearch) { mutableStateOf((initialSearch.sessionCap ?: firstSearch?.sessionCap ?: 60).toString()) }
    var searchProxy by remember(initialSearch) { mutableStateOf(initialSearch.network.httpProxy.orEmpty()) }
    var searchNoProxy by remember(initialSearch) { mutableStateOf(initialSearch.network.noProxy.orEmpty()) }
    var visionEnabled by remember { mutableStateOf(initialVision.enabled) }
    var visionUrl by remember { mutableStateOf(initialVision.baseUrl) }
    var visionModel by remember { mutableStateOf(initialVision.modelId) }
    var visionKey by remember { mutableStateOf("") }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("模型接口", style = MaterialTheme.typography.titleMedium)
        OutlinedTextField(baseUrl, { baseUrl = it }, Modifier.fillMaxWidth(), label = { Text("兼容接口地址") }, singleLine = true)
        OutlinedTextField(model, { model = it }, Modifier.fillMaxWidth(), label = { Text("模型名称") }, singleLine = true)
        OutlinedTextField(apiKey, { apiKey = it }, Modifier.fillMaxWidth(), label = { Text("API Key") }, singleLine = true, visualTransformation = PasswordVisualTransformation())
        Button(onClick = { save(baseUrl, apiKey, model) }) { Text("保存") }
        OutlinedButton(onClick = openZCodeRuntime) { Text("打开 ZCode Runtime") }
        OutlinedButton(onClick = openWorkspaces) { Text("管理 ZCode 工作区与文件") }
        HorizontalDivider()
        Text("联网搜索", style = MaterialTheme.typography.titleMedium)
        Text("ZCode 通过宿主 web_search 工具调用你配置的搜索服务。API Key 保存在 Android Keystore；搜索结果属于不可信外部数据。", style = MaterialTheme.typography.bodySmall)
        OutlinedTextField(searchId, {
            searchId = it.trim().lowercase()
            if (searchUrl.isBlank() || searchUrl in setOf(ZCodeSearchConfigWriter.defaultBaseUrl("brave"), ZCodeSearchConfigWriter.defaultBaseUrl("tavily"))) {
                searchUrl = ZCodeSearchConfigWriter.defaultBaseUrl(searchId)
            }
        }, Modifier.fillMaxWidth(), label = { Text("搜索服务（brave 或 tavily）") }, singleLine = true)
        OutlinedTextField(searchUrl, { searchUrl = it }, Modifier.fillMaxWidth(), label = { Text("搜索接口地址（仅 HTTPS）") }, singleLine = true)
        OutlinedTextField(searchKey, { searchKey = it }, Modifier.fillMaxWidth(), label = { Text("搜索 API Key（留空保留已保存值）") }, singleLine = true, visualTransformation = PasswordVisualTransformation())
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(searchCount, { searchCount = it }, Modifier.weight(1f), label = { Text("结果数 1-20") }, singleLine = true)
            OutlinedTextField(searchTimeout, { searchTimeout = it }, Modifier.weight(1f), label = { Text("超时 ms") }, singleLine = true)
        }
        OutlinedTextField(searchCap, { searchCap = it }, Modifier.fillMaxWidth(), label = { Text("每会话每小时上限") }, singleLine = true)
        OutlinedTextField(searchProxy, { searchProxy = it }, Modifier.fillMaxWidth(), label = { Text("HTTP(S) 代理（可选）") }, singleLine = true)
        OutlinedTextField(searchNoProxy, { searchNoProxy = it }, Modifier.fillMaxWidth(), label = { Text("不走代理的主机（可选）") }, singleLine = true)
        Button(onClick = {
            val count = searchCount.toIntOrNull()?.coerceIn(1, 20) ?: 8
            val timeout = searchTimeout.toIntOrNull()?.coerceIn(1_000, 120_000) ?: 60_000
            val cap = searchCap.toIntOrNull()?.coerceIn(1, 10_000) ?: 60
            saveSearch(
                SearchConfig(
                    backends = listOf(SearchBackend(searchId, searchId.replaceFirstChar(Char::uppercase), true, searchUrl, count, timeout, cap)),
                    network = SearchNetwork(searchProxy.takeIf(String::isNotBlank), searchNoProxy.takeIf(String::isNotBlank)),
                    sessionCap = cap,
                ),
                searchKey,
            )
            searchKey = ""
        }) { Text("保存搜索设置") }
        HorizontalDivider()
        Text("屏幕视觉", style = MaterialTheme.typography.titleMedium)
        Text("仅在明确调用视觉工具时，将当前截图发送给此服务。聊天模型收到文字和位置结果；请配置支持图片输入的独立模型。", style = MaterialTheme.typography.bodySmall)
        OutlinedButton(onClick = useCurrentModelForVision) { Text("沿用当前模型（需支持图片输入）") }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Switch(visionEnabled, { visionEnabled = it }); Text("启用视觉服务")
        }
        OutlinedTextField(visionUrl, { visionUrl = it }, Modifier.fillMaxWidth(), label = { Text("视觉接口地址（HTTPS，包含 /v1）") }, singleLine = true)
        OutlinedTextField(visionModel, { visionModel = it }, Modifier.fillMaxWidth(), label = { Text("视觉模型名称") }, singleLine = true)
        OutlinedTextField(visionKey, { visionKey = it }, Modifier.fillMaxWidth(), label = { Text("视觉 API Key（同一服务留空保留）") }, singleLine = true, visualTransformation = PasswordVisualTransformation())
        Button(onClick = {
            saveVision(VisionConfig(visionEnabled, "custom", visionUrl.trim(), visionModel.trim()), visionKey)
            visionKey = ""
        }) { Text("保存视觉设置") }
        HorizontalDivider()
        Text("设备控制", style = MaterialTheme.typography.titleMedium)
        Text("启用无障碍服务后，Agent 才能读取控件并执行点击、输入和手势。")
        OutlinedButton(onClick = openAccessibility) { Text("打开无障碍设置") }
        Text("root 命令通过 su 单独执行。高风险命令会显示具体参数并等待确认。", style = MaterialTheme.typography.bodySmall)
        OutlinedButton(onClick = runDiagnostics) { Text("检测 Shell 与 root") }
        HorizontalDivider()
        Text("本地工具协议", style = MaterialTheme.typography.titleMedium)
        Text("请在“工具”页面导入和评审工具包。导入只保存文件，不执行程序或进行协议握手。当前仅支持经过明确评审的隔离纯数据工具；每次调用仍须经过既有授权检查。")
    }
}
