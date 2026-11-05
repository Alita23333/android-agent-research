const fs = require("node:fs");
const path = require("node:path");
const { DatabaseSync } = require("node:sqlite");

const gatewayFile = path.resolve(process.argv[2] || "app/src/main/assets/zcode-runtime/gateway.cjs");
const testRoot = path.resolve(process.argv[3] || `build/journal-v2-${Date.now()}`);
const { Gateway } = require(gatewayFile);
let passed = 0;

function check(name, condition) {
  if (!condition) throw new Error(`FAIL: ${name}`);
  passed += 1;
  console.log(`PASS: ${name}`);
}

function inspect(databaseFile) {
  const db = new DatabaseSync(databaseFile);
  const version = db.prepare("pragma user_version").get().user_version;
  const tables = new Set(db.prepare("select name from sqlite_master where type='table'").all().map((row) => row.name));
  const rows = db.prepare("select count(*) as count from operation").get().count;
  db.close();
  return { version, tables, rows };
}

const freshRoot = path.join(testRoot, "fresh");
new Gateway().init({ root: freshRoot, workspace: path.join(freshRoot, "workspace"), mode: "ask" });
const fresh = inspect(path.join(freshRoot, "gateway", "journal.sqlite"));
check("fresh journal schema version is 2", fresh.version === 2);
check("fresh journal has operation", fresh.tables.has("operation"));
check("fresh journal has network_request", fresh.tables.has("network_request"));
check("fresh journal has allow_rule", fresh.tables.has("allow_rule"));

const existingRoot = path.join(testRoot, "existing");
fs.mkdirSync(path.join(existingRoot, "gateway"), { recursive: true });
const existingFile = path.join(existingRoot, "gateway", "journal.sqlite");
const v1 = new DatabaseSync(existingFile);
v1.exec(`
  create table operation (
    id integer primary key autoincrement,
    ts text not null,
    session text, task text, tool text, args text,
    provider text, capability text, risk text, mode text,
    decision text, approval_source text, rule_hits text, hard_confirm integer,
    result text, files_modified text,
    before_hash text, after_hash text, backup_path text,
    reversible integer, detail text
  );
  insert into operation(ts, session, tool, risk, decision, detail)
    values('2026-09-28T00:00:00Z', 'existing-session', 'Read', 'READ', 'allow', 'preserve-me');
  pragma user_version = 1;
`);
v1.close();
new Gateway().init({ root: existingRoot, workspace: path.join(existingRoot, "workspace"), mode: "ask" });
const migrated = inspect(existingFile);
check("existing journal migrated to schema version 2", migrated.version === 2);
check("existing operation row preserved", migrated.rows === 1);
check("migration added network_request", migrated.tables.has("network_request"));
check("migration added allow_rule", migrated.tables.has("allow_rule"));

console.log(`RESULT: PASS=${passed} FAIL=0 root=${testRoot}`);
