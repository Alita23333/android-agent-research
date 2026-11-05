package dev.alita.androidagent.zcode.runtime

import android.app.Activity
import android.os.Bundle
import android.widget.ArrayAdapter
import android.widget.ListView
import android.widget.LinearLayout
import android.widget.TextView

/**
 * TEST-ONLY fixture (Codex test task 2026-10-04, item A): a genuinely
 * scrollable long list with DISTINCT, ordered, greppable item labels so a
 * positive scroll can be proven by RE-OBSERVATION (visible item set changes),
 * not by trusting the gesture return value. 300 items; each row reads
 * "longlist-item-%03d-of-300" so before/after dumps identify position shifts.
 *
 * Not exported to production surfaces beyond adb/test starts; no model-visible
 * tool, runtime, policy or gateway change is involved.
 */
class LongListActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val items = (0 until ITEM_COUNT).map { i -> "longlist-item-%03d-of-%03d".format(i, ITEM_COUNT) }
        val list = ListView(this).apply {
            adapter = ArrayAdapter(this@LongListActivity, android.R.layout.simple_list_item_1, items)
            id = android.view.View.generateViewId()
        }
        val header = TextView(this).apply {
            text = "longlist-fixture-header count=$ITEM_COUNT"
            textSize = 14f
            setPadding(24, 32, 24, 16)
        }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            addView(header)
            addView(list, LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.MATCH_PARENT))
        }
        setContentView(root)
    }
    companion object { const val ITEM_COUNT = 300 }
}
