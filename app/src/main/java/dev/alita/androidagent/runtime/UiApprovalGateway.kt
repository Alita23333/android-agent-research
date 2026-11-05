package dev.alita.androidagent.runtime

import dev.alita.androidagent.core.*
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

data class PendingApproval(
    val runId: String,
    val call: ToolCall,
    val title: String,
    val explanation: String,
    internal val result: CompletableDeferred<Boolean>,
)

class UiApprovalGateway(private val runStore: RunStore) : ApprovalGateway {
    private val mutablePending = MutableStateFlow<PendingApproval?>(null)
    val pending: StateFlow<PendingApproval?> = mutablePending

    override suspend fun request(runId: String, call: ToolCall, decision: PolicyDecision.Confirm): Boolean {
        runStore.updateStatus(runId, RunStatus.WAITING_APPROVAL)
        val deferred = CompletableDeferred<Boolean>()
        mutablePending.value = PendingApproval(runId, call, decision.title, decision.explanation, deferred)
        return try { deferred.await() } finally {
            mutablePending.value = null
            runStore.updateStatus(runId, RunStatus.RUNNING)
        }
    }

    fun resolve(allow: Boolean) { mutablePending.value?.result?.complete(allow) }
}
