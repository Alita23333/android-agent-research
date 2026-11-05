// Diagnostic: dump session-store table counts and recent session rows.
// Run on-device via the app-owned node: see scripts/verify notes.
const { DatabaseSync } = require("node:sqlite");
const fs = require("node:fs");
const candidates = ["files/.zcode/cli/db/db.sqlite", ".zcode/cli/db/db.sqlite"];
const p = candidates.find((c) => fs.existsSync(c)) || candidates[0];
const db = new DatabaseSync(p, { readOnly: true });
const tables = db
  .prepare("select name from sqlite_master where type='table' order by name")
  .all()
  .map((r) => r.name);
for (const t of tables) {
  const c = db.prepare(`select count(*) as n from "${t}"`).get();
  console.log(t, c.n);
}
try {
  const rows = db.prepare("select id, title, directory from session order by time_created desc limit 5").all();
  console.log("recent sessions:", JSON.stringify(rows, null, 1));
} catch (e) {
  console.log("session query failed:", e.message);
}

