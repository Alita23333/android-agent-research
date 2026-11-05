package dev.alita.androidagent

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Phase8 contracts must survive the runtime5 upgrade. */
@RunWith(RobolectricTestRunner::class)
@Config(application = AgentApplication::class, sdk = [35])
class Phase8WorkspaceMutationScaffoldTest {
    private val context: Context = ApplicationProvider.getApplicationContext()
    private fun asset(name: String) = context.assets.open("zcode-runtime/$name").bufferedReader().use { it.readText() }

    @Test fun runtime5AndJournalV3ArePinned() {
        assertEquals("0.16.9-runtime5", JSONObject(asset("runtime-manifest.json")).getString("version"))
        val gateway = asset("gateway.cjs")
        assertTrue(gateway.contains("SCHEMA_VERSION = 3"))
        assertTrue(gateway.contains("create table if not exists write_txn"))
        assertTrue(gateway.contains("pragma synchronous"))
    }

    @Test fun exactWorkspaceToolFamilyIsBridgeInline() {
        val tools = asset("workspace-files.cjs")
        listOf("workspace_file_create", "workspace_file_overwrite", "workspace_file_append", "workspace_file_delete")
            .forEach { assertTrue("missing $it", tools.contains(it)) }
        val bootstrap = asset("bootstrap.cjs")
        assertTrue(bootstrap.contains("INLINE_DISPATCH"))
        assertTrue(bootstrap.contains("WS_TOOLS"))
        assertFalse(bootstrap.contains("files/workspace/"))
    }

    @Test fun mutationsUseIntentBackupVerifyAndRollbackContracts() {
        val gateway = asset("gateway.cjs")
        listOf("claimWorkspaceIntent", "runWorkspaceMutation", "backup_failed", "before_hash", "after_hash",
            "rollback_precondition_failed", "rollback_backup_integrity_mismatch", "uncertain", "abandoned")
            .forEach { assertTrue("missing $it", gateway.contains(it)) }
    }

    @Test fun containmentAndTraversalFailClosedArePackaged() {
        val gateway = asset("gateway.cjs")
        val tools = asset("workspace-files.cjs")
        listOf("resolveWorkspaceTarget", "path_traversal_rejected", "path_absolute_rejected", "path_symlink_rejected", "path_reserved")
            .forEach { token -> assertTrue("missing $token", gateway.contains(token) || tools.contains(token)) }
    }

    @Test fun normalizedUiTreeRuntimeIsPackaged() {
        val bootstrap = asset("bootstrap.cjs")
        assertTrue(bootstrap.contains("/ui/render"))
        val uiTree = asset("ui-tree.cjs")
        assertTrue(uiTree.contains("renderSnapshot"))
        assertTrue(uiTree.contains("UI_DUMP_MAX_BYTES = 20480"))
    }
}
