package dev.alita.androidagent

import android.app.Application
import android.content.Intent
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import dev.alita.androidagent.core.AgentUpdate
import dev.alita.androidagent.core.CancellationSignal
import dev.alita.androidagent.core.ToolCall
import dev.alita.androidagent.core.ToolContext
import dev.alita.androidagent.device.AgentAccessibilityService
import org.json.JSONObject
import dev.alita.androidagent.model.ModelSettings
import dev.alita.androidagent.runtime.AgentForegroundService
import dev.alita.androidagent.zcode.runtime.SearchConfig
import dev.alita.androidagent.zcode.runtime.ZCodeSearchConfigWriter
import dev.alita.androidagent.zcode.runtime.VisionConfig
import dev.alita.androidagent.zcode.runtime.ZCodeVisionConfigWriter
import dev.alita.androidagent.zcode.runtime.ZCodeHostService
import dev.alita.androidagent.skills.SkillDescriptor
import dev.alita.androidagent.tools.ProviderAdmissionCandidate
import dev.alita.androidagent.tools.ProviderAdmissionDraft
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class ChatItem(val role: String, val text: String)
data class MainUiState(
    val messages: List<ChatItem> = emptyList(),
    val running: Boolean = false,
    val currentTool: String? = null,
    val error: String? = null,
    val skills: List<SkillDescriptor> = emptyList(),
    val notice: String? = null,
    val skillsBusy: Boolean = false,
    val providers: List<ProviderAdmissionCandidate> = emptyList(),
    val providersBusy: Boolean = false,
    val providersHostActive: Boolean = false,
    val providerDraft: ProviderAdmissionDraft? = null,
)

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val graph = (application as AgentApplication).graph
    private fun installedSkills() = if (BuildConfig.LEGACY_DIAGNOSTICS) graph.skills.discover() else graph.coreSkillPackages.discover()
    private val mutableState = MutableStateFlow(MainUiState())
    val state: StateFlow<MainUiState> = mutableState.asStateFlow()
    val pendingApproval = graph.approvals.pending

    init { changeSkills { null } }

    /** Serialize UI mutations and keep archive/hash work off the main thread. */
    private fun changeSkills(operation: () -> String?) {
        if (mutableState.value.skillsBusy) return
        mutableState.value = mutableState.value.copy(skillsBusy = true, error = null, notice = null)
        viewModelScope.launch {
            try {
                val (notice, skills) = withContext(Dispatchers.IO) { operation() to installedSkills() }
                mutableState.value = mutableState.value.copy(skills = skills, notice = notice)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                mutableState.value = mutableState.value.copy(error = error.message ?: "技能操作未完成")
            } finally {
                mutableState.value = mutableState.value.copy(skillsBusy = false)
            }
        }
    }

    fun settings(): ModelSettings = graph.settings.load()
    fun searchSettings(): SearchConfig = ZCodeSearchConfigWriter.load(getApplication()) ?: SearchConfig(emptyList())
    fun visionSettings(): VisionConfig = ZCodeVisionConfigWriter.load(getApplication())
    fun useCurrentModelForVision() {
        val current = graph.settings.load()
        saveVisionSettings(VisionConfig(true, "custom", current.baseUrl, current.model), current.apiKey)
    }
    fun saveVisionSettings(config: VisionConfig, key: String) {
        runCatching { ZCodeVisionConfigWriter.saveFromUi(getApplication(), config, key) }
            .onSuccess { mutableState.value = mutableState.value.copy(notice = "视觉设置已加密保存", error = null) }
            .onFailure { mutableState.value = mutableState.value.copy(error = it.message ?: "视觉设置保存失败") }
    }
    fun saveSettings(baseUrl: String, apiKey: String, model: String) {
        graph.settings.save(ModelSettings(baseUrl, apiKey, model))
        mutableState.value = mutableState.value.copy(notice = "模型设置已保存", error = null)
    }

    fun saveSearchSettings(config: SearchConfig, apiKey: String) {
        runCatching { ZCodeSearchConfigWriter.saveFromUi(getApplication(), config, apiKey) }
            .onSuccess { mutableState.value = mutableState.value.copy(notice = "搜索设置已加密保存，并将在下一次搜索调用生效", error = null) }
            .onFailure { mutableState.value = mutableState.value.copy(error = it.message ?: "搜索设置保存失败") }
    }

    fun send(goal: String) {
        if (goal.isBlank() || mutableState.value.running) return
        mutableState.value = mutableState.value.copy(
            messages = mutableState.value.messages + ChatItem("你", goal), running = true, currentTool = null, error = null, notice = null
        )
        AgentForegroundService.start(getApplication())
        viewModelScope.launch {
            try {
                graph.engine.run(goal) { update ->
                    when (update) {
                        is AgentUpdate.Started -> Unit
                        is AgentUpdate.ModelText -> appendAssistant(update.text)
                        is AgentUpdate.ToolStarted -> mutableState.value = mutableState.value.copy(currentTool = update.id)
                        is AgentUpdate.ToolFinished -> mutableState.value = mutableState.value.copy(currentTool = null)
                        is AgentUpdate.Finished -> mutableState.value = mutableState.value.copy(running = false, currentTool = null)
                        is AgentUpdate.Failed -> mutableState.value = mutableState.value.copy(running = false, currentTool = null, error = update.message)
                    }
                }
            } catch (_: CancellationException) {
                mutableState.value = mutableState.value.copy(running = false, currentTool = null)
            } catch (error: Throwable) {
                mutableState.value = mutableState.value.copy(running = false, currentTool = null, error = error.message ?: "任务失败")
            } finally { AgentForegroundService.stop(getApplication()) }
        }
    }

    fun cancel() = graph.engine.cancel()
    fun resolveApproval(allow: Boolean) = graph.approvals.resolve(allow)

    fun importSkill(uri: Uri) {
        changeSkills {
            val skill = getApplication<Application>().contentResolver.openInputStream(uri).use { input ->
                requireNotNull(input) { "无法读取文件" }
                if (BuildConfig.LEGACY_DIAGNOSTICS) graph.skills.install(input, uri.toString())
                else graph.coreSkillPackages.install(input, uri.toString())
            }
            when {
                skill.missingDependencies.isNotEmpty() -> "已保存技能包：${skill.name}，缺少依赖，无法启用"
                skill.enabled -> "已保存技能包：${skill.name}，保持启用"
                else -> "已保存技能包：${skill.name}，请按需启用；已有会话保留原版本"
            }
        }
    }

    fun importProvider(uri: Uri) {
        changeProviders {
            val descriptor = getApplication<Application>().contentResolver.openInputStream(uri).use { input ->
                requireNotNull(input) { "无法读取文件" }; graph.providers.install(input)
            }
            // Import is inert in every build: do not load a protocol process or mutate the registry.
            ProviderUiChange(notice = "已保存工具包：${descriptor.id}；导入不会启用或运行工具")
        }
    }

    private data class ProviderUiChange(val notice: String? = null, val draft: ProviderAdmissionDraft? = null)

    /** Independent from skill work; serialize archive, review and hashing work away from the UI. */
    private fun changeProviders(operation: () -> ProviderUiChange) {
        if (mutableState.value.providersBusy) return
        mutableState.value = mutableState.value.copy(providersBusy = true, providerDraft = null, error = null, notice = null)
        viewModelScope.launch {
            try {
                val (change, candidates, active) = withContext(Dispatchers.IO) {
                    Triple(operation(), graph.providerAdmission.candidates(), graph.providerAdmission.hostActive())
                }
                mutableState.value = mutableState.value.copy(providers = candidates, providersHostActive = active,
                    providerDraft = change.draft, notice = change.notice)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                val active = withContext(Dispatchers.IO) { graph.providerAdmission.hostActive() }
                mutableState.value = mutableState.value.copy(providersHostActive = active,
                    error = error.message ?: "工具包操作未完成")
            } finally {
                mutableState.value = mutableState.value.copy(providersBusy = false)
            }
        }
    }

    fun refreshProviders() = changeProviders { ProviderUiChange() }

    fun stopAgentForProviderManagement() {
        val application = getApplication<Application>()
        runCatching {
            application.startService(Intent(application, ZCodeHostService::class.java).setAction(ZCodeHostService.ACTION_STOP))
        }.onSuccess {
            mutableState.value = mutableState.value.copy(notice = "已请求停止 Agent；请稍候点击刷新，停止完成后即可修改工具", error = null)
        }.onFailure {
            mutableState.value = mutableState.value.copy(error = it.message ?: "无法请求停止 Agent")
        }
    }

    fun previewProvider(id: String, contentHash: String, name: String, version: String, description: String) = changeProviders {
        ProviderUiChange(draft = graph.providerAdmission.preview(id, contentHash, name, version, description))
    }

    fun approveProvider(draft: ProviderAdmissionDraft) = changeProviders {
        graph.providerAdmission.approve(draft)
        ProviderUiChange(notice = "已准入工具：${draft.id}.${draft.toolName}；重新打开 Agent 后供新会话使用，已有会话保留原版本")
    }

    fun retireProvider(id: String) = changeProviders {
        graph.providerAdmission.retire(id)
        ProviderUiChange(notice = "已停用：$id；不再用于新会话，保留已有会话的版本记录")
    }

    fun revokeProvider(id: String, contentHash: String, definitionHash: String) = changeProviders {
        graph.providerAdmission.revoke(id, contentHash, definitionHash)
        ProviderUiChange(notice = "已撤销所选版本：$id；后续调用不能再启用该版本，不保证中断已经开始的调用")
    }

    fun clearProviderDraft() { mutableState.value = mutableState.value.copy(providerDraft = null) }

    fun setSkillEnabled(id: String, enabled: Boolean) {
        changeSkills {
            if (BuildConfig.LEGACY_DIAGNOSTICS) graph.skills.setEnabled(id, enabled)
            else graph.coreSkillPackages.setEnabled(id, enabled)
            if (enabled) "已启用，将用于新会话；已有会话保留原版本" else "已停用；已有会话保留原版本"
        }
    }

    fun deleteSkill(id: String) {
        changeSkills {
            if (BuildConfig.LEGACY_DIAGNOSTICS) graph.skills.delete(id) else graph.coreSkillPackages.retire(id)
            "已从技能列表移除；已有会话保留原版本"
        }
    }

    fun clearNotice() { mutableState.value = mutableState.value.copy(notice = null, error = null) }

    fun runDiagnostics() {
        viewModelScope.launch {
            val context = ToolContext("diagnostic", CancellationSignal(), graph.artifactStore)
            val shell = graph.registry.find("shell.exec")
            val root = graph.registry.find("shell.root")
            val normal = shell?.execute(ToolCall(toolId = "shell.exec", arguments = JSONObject().put("command", "id")), context)
            val privileged = root?.execute(ToolCall(toolId = "shell.root", arguments = JSONObject().put("command", "id")), context)
            val accessibility = runCatching { AgentAccessibilityService.current()?.observe() }.getOrNull()
            val text = buildString {
                append("Shell: ").append(normal?.data?.optString("output")?.trim().orEmpty())
                append("\nRoot: ").append(privileged?.data?.optString("output")?.trim().orEmpty())
                if (privileged?.data?.optInt("exitCode", -1) != 0) append("\n请在 KernelSU 管理器中授予 Android Agent root 权限后重试。")
                append("\n无障碍: ")
                if (accessibility == null) append("未连接，请在系统无障碍设置中启用 Android Agent device control")
                else append("已连接，读取到 ").append(accessibility.optJSONArray("windows")?.length() ?: 0)
                    .append(" 个窗口，当前包：").append(accessibility.optString("package", "未知"))
            }
            mutableState.value = mutableState.value.copy(notice = text, error = null)
        }
    }

    private fun appendAssistant(delta: String) {
        val messages = mutableState.value.messages.toMutableList()
        if (messages.lastOrNull()?.role == "Agent") {
            messages[messages.lastIndex] = messages.last().copy(text = messages.last().text + delta)
        } else messages += ChatItem("Agent", delta)
        mutableState.value = mutableState.value.copy(messages = messages)
    }
}
