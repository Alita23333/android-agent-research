package dev.alita.androidagent.core

import dev.alita.androidagent.skills.SkillRepository
import dev.alita.androidagent.skills.SkillRuntime
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONObject

sealed interface AgentUpdate {
    data class Started(val runId: String) : AgentUpdate
    data class ModelText(val text: String) : AgentUpdate
    data class ToolStarted(val id: String) : AgentUpdate
    data class ToolFinished(val id: String, val ok: Boolean) : AgentUpdate
    data class Finished(val text: String) : AgentUpdate
    data class Failed(val message: String) : AgentUpdate
}

class AgentEngine(
    private val modelFactory: () -> ModelProvider,
    private val registry: ToolRegistry,
    private val executor: ToolExecutor,
    private val runStore: RunStore,
    private val skillRepository: SkillRepository,
    private val skillRuntime: SkillRuntime,
    private val contextAssembler: ContextAssembler = ContextAssembler(),
) {
    private val runMutex = Mutex()
    @Volatile private var activeCancellation: CancellationSignal? = null
    @Volatile var activeRunId: String? = null
        private set

    suspend fun run(goal: String, onUpdate: suspend (AgentUpdate) -> Unit): String = runMutex.withLock {
        val record = runStore.create(goal)
        val cancellation = CancellationSignal()
        activeCancellation = cancellation
        activeRunId = record.id
        runStore.updateStatus(record.id, RunStatus.RUNNING)
        onUpdate(AgentUpdate.Started(record.id))
        val messages = mutableListOf(
            AgentMessage(AgentRole.SYSTEM, contextAssembler.systemPrompt(skillRepository.discover())),
            AgentMessage(AgentRole.USER, goal),
        )
        runStore.append(record.id, "message.user", JSONObject().put("content", goal))
        var finalText = ""
        try {
            val model = modelFactory()
            require(model.capabilities.toolCalls) { "当前模型适配器不支持工具调用" }
            repeat(MAX_TOOL_ROUNDS) {
                cancellation.throwIfCancelled()
                val streamed = StringBuilder()
                val response = model.complete(ModelRequest(messages, registry.definitions())) { event ->
                    when (event) {
                        is ModelEvent.TextDelta -> { streamed.append(event.text); onUpdate(AgentUpdate.ModelText(event.text)) }
                        is ModelEvent.Status -> Unit
                    }
                }
                messages += AgentMessage(AgentRole.ASSISTANT, response.text.ifBlank { null }, response.toolCalls)
                if (response.text.isNotBlank()) {
                    finalText = response.text
                    runStore.append(record.id, "message.assistant", JSONObject().put("content", response.text))
                    if (streamed.isEmpty()) onUpdate(AgentUpdate.ModelText(response.text))
                }
                if (response.toolCalls.isEmpty()) {
                    runStore.updateStatus(record.id, RunStatus.COMPLETED)
                    onUpdate(AgentUpdate.Finished(finalText))
                    return@withLock finalText
                }
                response.toolCalls.forEach { call ->
                    cancellation.throwIfCancelled()
                    onUpdate(AgentUpdate.ToolStarted(call.toolId))
                    val result = executor.execute(record.id, call, cancellation)
                    onUpdate(AgentUpdate.ToolFinished(call.toolId, result.ok))
                    messages += AgentMessage(AgentRole.TOOL, result.toJson().toString(), toolCallId = call.callId)
                }
            }
            error("已达到每轮 $MAX_TOOL_ROUNDS 次工具调用限制")
        } catch (error: Throwable) {
            if (error is InterruptedException || error is CancellationException || cancellation.isCancelled()) {
                runStore.updateStatus(record.id, RunStatus.CANCELLED)
                onUpdate(AgentUpdate.Failed("任务已取消"))
                throw CancellationException("Task cancelled", error)
            }
            runStore.append(record.id, "run.error", JSONObject().put("message", error.message ?: error.javaClass.simpleName))
            runStore.updateStatus(record.id, RunStatus.FAILED)
            onUpdate(AgentUpdate.Failed(error.message ?: "任务失败"))
            throw error
        } finally {
            skillRuntime.clear(record.id)
            activeRunId = null
            activeCancellation = null
        }
    }

    fun cancel() = activeCancellation?.cancel()

    companion object { const val MAX_TOOL_ROUNDS = 30 }
}
