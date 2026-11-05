package dev.alita.androidagent.core

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONObject
import java.util.concurrent.ConcurrentHashMap

interface ToolProvider {
    val providerId: String
    suspend fun tools(): List<AgentTool>
    suspend fun close() = Unit
}

class ToolRegistry {
    private val tools = ConcurrentHashMap<String, AgentTool>()
    private val providerToolIds = mutableMapOf<String, Set<String>>()
    private val providers = mutableMapOf<String, ToolProvider>()

    @Synchronized fun register(tool: AgentTool) {
        val old = tools.putIfAbsent(tool.definition.id, tool)
        require(old == null) { "Tool id collision: ${tool.definition.id}" }
    }

    suspend fun register(provider: ToolProvider) = installProvider(provider, replace = false)

    suspend fun replace(provider: ToolProvider) = installProvider(provider, replace = true)

    /** Host lifecycle cleanup; callers must first stop all consumers of this provider. */
    suspend fun removeProvider(providerId: String) {
        val previous = synchronized(this) {
            providerToolIds.remove(providerId).orEmpty().forEach(tools::remove)
            providers.remove(providerId)
        }
        previous?.close()
    }

    private suspend fun installProvider(provider: ToolProvider, replace: Boolean) {
        // Complete protocol negotiation before touching the active registry.
        val candidates = provider.tools()
        val ids = candidates.map { it.definition.id }
        require(ids.size == ids.toSet().size) { "Provider ${provider.providerId} returned duplicate tool ids" }
        var previous: ToolProvider? = null
        synchronized(this) {
            val owned = providerToolIds[provider.providerId].orEmpty()
            if (!replace) require(owned.isEmpty()) { "Provider already registered: ${provider.providerId}" }
            ids.forEach { id ->
                require(tools[id] == null || id in owned) { "Tool id collision: $id" }
            }
            if (replace) owned.forEach(tools::remove)
            candidates.forEach { tools[it.definition.id] = it }
            previous = providers.put(provider.providerId, provider)
            providerToolIds[provider.providerId] = ids.toSet()
        }
        if (previous !== provider) previous?.close()
    }

    fun find(id: String): AgentTool? = tools[id]
    fun definitions(): List<ToolDefinition> = tools.values.map { it.definition }.sortedBy { it.id }
}

sealed interface PolicyDecision {
    data object Allow : PolicyDecision
    data class Confirm(val title: String, val explanation: String) : PolicyDecision
    data class Deny(val reason: String) : PolicyDecision
}

interface PolicyEngine {
    fun evaluate(definition: ToolDefinition, call: ToolCall): PolicyDecision
}

class DefaultPolicyEngine : PolicyEngine {
    private val dangerousShell = Regex(
        "(?i)(\\brm\\s+(-[^ ]*r[^ ]*f|-[^ ]*f[^ ]*r)|\\bmkfs\\b|\\bdd\\s+.*\\bof=/dev/|setenforce\\s+0|pm\\s+uninstall|reboot|shutdown)"
    )

    override fun evaluate(definition: ToolDefinition, call: ToolCall): PolicyDecision {
        if (definition.id == "shell.root" && dangerousShell.containsMatchIn(call.arguments.optString("command"))) {
            return PolicyDecision.Confirm("确认高风险 root 命令", call.arguments.optString("command"))
        }
        return when (definition.sideEffect) {
            SideEffect.EXTERNAL -> PolicyDecision.Confirm("确认外部操作", definition.description)
            SideEffect.DESTRUCTIVE -> PolicyDecision.Confirm("确认删除或覆盖", definition.description)
            SideEffect.SYSTEM -> PolicyDecision.Confirm("确认系统修改", definition.description)
            else -> PolicyDecision.Allow
        }
    }
}

interface ApprovalGateway {
    suspend fun request(runId: String, call: ToolCall, decision: PolicyDecision.Confirm): Boolean
}

class ToolExecutor(
    private val registry: ToolRegistry,
    private val policy: PolicyEngine,
    private val approvals: ApprovalGateway,
    private val store: RunStore,
    private val artifactStore: ArtifactStore,
) {
    private val deviceMutex = Mutex()

    suspend fun execute(runId: String, call: ToolCall, cancellation: CancellationSignal): ToolResult {
        val tool = registry.find(call.toolId)
            ?: return ToolResult.failure(call, "TOOL_NOT_FOUND", "Unknown tool: ${call.toolId}")
        val definition = tool.definition
        when (val decision = policy.evaluate(definition, call)) {
            is PolicyDecision.Deny -> return ToolResult.failure(call, "POLICY_DENIED", decision.reason)
            is PolicyDecision.Confirm -> {
                store.append(runId, "approval.requested", JSONObject().put("tool", call.toolId).put("arguments", call.arguments))
                if (!approvals.request(runId, call, decision)) {
                    store.append(runId, "approval.denied", JSONObject().put("tool", call.toolId))
                    return ToolResult.failure(call, "USER_DENIED", "User denied this operation")
                }
            }
            PolicyDecision.Allow -> Unit
        }
        cancellation.throwIfCancelled()
        store.append(runId, "tool.started", JSONObject().put("callId", call.callId).put("tool", call.toolId).put("arguments", call.arguments))
        val context = ToolContext(runId, cancellation, artifactStore)
        val execute = suspend {
            runCatching { tool.execute(call, context) }.getOrElse {
                ToolResult.failure(call, "TOOL_CRASHED", it.message ?: it.javaClass.simpleName, retryable = true)
            }
        }
        val result = if (definition.capabilities.contains("device-ui")) deviceMutex.withLock { execute() } else execute()
        store.append(runId, "tool.finished", JSONObject().put("callId", call.callId).put("tool", call.toolId).put("result", result.toJson()))
        return result
    }
}
