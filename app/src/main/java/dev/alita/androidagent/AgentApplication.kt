package dev.alita.androidagent

import android.app.Application
import dev.alita.androidagent.core.*
import dev.alita.androidagent.device.DeviceToolProvider
import dev.alita.androidagent.execution.ProcessExecutionBackend
import dev.alita.androidagent.model.OpenAiCompatibleProvider
import dev.alita.androidagent.model.SecureSettings
import dev.alita.androidagent.runtime.UiApprovalGateway
import dev.alita.androidagent.skills.FileSkillRepository
import dev.alita.androidagent.skills.SkillRuntime
import dev.alita.androidagent.skills.SkillToolProvider
import dev.alita.androidagent.skills.CoreSkillPackageStore
import dev.alita.androidagent.tools.BuiltinToolProvider
import dev.alita.androidagent.tools.LocalProviderCatalog
import dev.alita.androidagent.tools.ProviderReviewStore
import dev.alita.androidagent.tools.ProviderAdmissionController
import kotlinx.coroutines.runBlocking
import dev.alita.androidagent.zcode.adapter.AndroidToolDispatcher
import dev.alita.androidagent.zcode.adapter.ReadOnlyToolDispatcher

class AgentApplication : Application() {
    lateinit var graph: AgentGraph
        private set
    val hasInitializedGraph: Boolean get() = ::graph.isInitialized

    override fun onCreate() {
        super.onCreate()
        // Isolated services must not open owner settings/database or start owner-UID tools.
        // This check precedes every graph/context access; it grants no new tool admission.
        if (android.os.Process.isIsolated()) return
        val registry = ToolRegistry()
        val store = SqliteRunStore(this)
        val artifacts = FileArtifactStore(this)
        val settings = SecureSettings(this)
        val approvals = UiApprovalGateway(store)
        val shell = ProcessExecutionBackend("android-shell") { command -> listOf("/system/bin/sh", "-c", command) }
        val root = ProcessExecutionBackend("root-shell") { command -> listOf("su", "-c", command) }
        val skills = FileSkillRepository(this) { registry.definitions().map { it.id }.toSet() }
        val providers = LocalProviderCatalog(this)
        val skillRuntime = SkillRuntime(skills)
        // A process death can leave a run marked as active even though its model
        // request or child process no longer exists. Preserve the record, but
        // never replay a potentially state-changing action automatically.
        store.recentRuns().filter { it.status == RunStatus.RUNNING || it.status == RunStatus.WAITING_APPROVAL }.forEach { run ->
            store.updateStatus(run.id, RunStatus.WAITING_USER)
            store.append(run.id, "run.recovered", org.json.JSONObject()
                .put("reason", "application_restarted")
                .put("action", "manual_review_required"))
        }
        runBlocking {
            if (BuildConfig.LEGACY_DIAGNOSTICS) {
                registry.register(BuiltinToolProvider(this@AgentApplication, shell, root))
            }
            registry.register(DeviceToolProvider(this@AgentApplication))
            registry.register(SkillToolProvider(skills, skillRuntime))
            if (BuildConfig.LEGACY_DIAGNOSTICS) {
                runCatching { providers.installBundled("providers/device-info") }
                providers.discover().forEach { descriptor -> runCatching { registry.register(providers.load(descriptor)) } }
            } else {
                // Imported archives are inert until a production host admission path exists.
                // Do not execute every discovered manifest merely because the app restarted.
                runCatching {
                    val bundled = providers.installBundled("providers/device-info")
                    registry.register(providers.load(bundled))
                }
            }
        }
        val executor = ToolExecutor(registry, DefaultPolicyEngine(), approvals, store, artifacts)
        val reviewedProviders = ProviderReviewStore(this, providers)
        val zcodeReadOnlyDispatcher = ReadOnlyToolDispatcher(registry, artifacts) { request ->
            reviewedProviders.resolveSession(request, java.io.File(filesDir, "sessions-index.json"), java.io.File(filesDir, "workspaces"))
        }
        val engine = AgentEngine(
            modelFactory = { OpenAiCompatibleProvider(settings.load()) },
            registry = registry,
            executor = executor,
            runStore = store,
            skillRepository = skills,
            skillRuntime = skillRuntime,
        )
        graph = AgentGraph(registry, store, artifacts, settings, skills, providers, approvals, engine, zcodeReadOnlyDispatcher,
            CoreSkillPackageStore(java.io.File(filesDir, "core-skill-packages"), inventoryFile = java.io.File(filesDir, "core-skill-inventory.json")), reviewedProviders,
            ProviderAdmissionController(providers, reviewedProviders, registry))
    }
}

data class AgentGraph(
    val registry: ToolRegistry,
    val runStore: RunStore,
    val artifactStore: ArtifactStore,
    val settings: SecureSettings,
    val skills: FileSkillRepository,
    val providers: LocalProviderCatalog,
    val approvals: UiApprovalGateway,
    val engine: AgentEngine,
    val zcodeReadOnlyDispatcher: AndroidToolDispatcher,
    val coreSkillPackages: CoreSkillPackageStore,
    val reviewedProviders: ProviderReviewStore,
    val providerAdmission: ProviderAdmissionController,
)
