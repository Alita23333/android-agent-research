// Read-only acceptance snapshot. Never replays or changes a Gateway operation.
const { DatabaseSync } = require('node:sqlite');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = process.env.SPIKE_ROOT || process.cwd();
const db = new DatabaseSync(path.join(root, 'gateway/journal.sqlite'), { readOnly: true });
const txns = db.prepare('select * from v_write_txn_latest order by id').all();
const report = {
  tables: db.prepare("select name from sqlite_master where type='table' order by name").all(),
  operationCount: db.prepare('select count(*) as count, min(id) as firstId, max(id) as lastId from operation').get(),
  transactions: txns.map(t => ({ ...t,
    lifecycle: db.prepare('select id,state,before_hash,after_hash,observed_hash,verify,error_code from write_txn where txn_id=? order by id').all(t.txn_id),
    backupActualHash: t.backup_path && fs.existsSync(t.backup_path)
      ? crypto.createHash('sha256').update(fs.readFileSync(t.backup_path)).digest('hex') : null,
  })),
  uiActions: db.prepare('select * from ui_action order by id').all(),
  workspaces: fs.readdirSync(path.join(root, 'workspaces')),
};
db.close();
console.log(JSON.stringify(report, null, 2));
