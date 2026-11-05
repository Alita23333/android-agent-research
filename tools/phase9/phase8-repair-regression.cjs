// Measured Phase 8 lifecycle/hash/rollback repair, against actual product sources.
const assert = require('node:assert/strict');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const runtime = path.resolve(__dirname, '../../app/src/main/assets/zcode-runtime');
const {Gateway} = require(path.join(runtime, 'gateway.cjs'));
const {handleWorkspaceTool} = require(path.join(runtime, 'workspace-files.cjs'));
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'p9-p8-repair-'));
const workspace = path.join(root, 'workspace'); fs.mkdirSync(workspace);
const gateway = new Gateway().init({root, workspace, mode:'full'});
try {
  const abs=path.join(workspace,'fixture.txt'); fs.writeFileSync(abs,'before');
  const input={path:'fixture.txt',resolved_path:abs};
  const intent=gateway.commitIntent({params:{toolName:'workspace_file_overwrite',sessionId:'fixture'},input,risk:'WRITE'});
  assert.ok(intent.ok);
  const result=handleWorkspaceTool('workspace_file_overwrite',{path:'fixture.txt',content:'after'},gateway);
  assert.ok(result.ok && result.verified);
  const terminal=gateway.writesView(10).find(t=>t.txn_id===intent.txnId);
  assert.equal(terminal.before_hash,result.beforeHash); assert.equal(terminal.before_size,6);
  assert.equal(terminal.observed_hash,result.afterHash); assert.equal(terminal.verify,'content_match');
  const op=gateway.journalView(10).find(o=>o.result==='ok'); assert.ok(op);
  const rollback=gateway.rollback(op.id); assert.ok(rollback.ok);
  const history=gateway.db.prepare('select * from write_txn where txn_id=? order by id').all(rollback.txnId);
  assert.deepEqual(history.map(t=>t.state),['intent','prepared','executed','verified','completed']);
  for (const state of ['executed','verified','completed']) {
    const row=history.find(t=>t.state===state);
    assert.equal(row.before_hash,result.afterHash); assert.equal(row.after_hash,result.beforeHash);
    if(state!=='executed') assert.equal(row.observed_hash,result.beforeHash);
  }
  const original=gateway.writesView(20).find(t=>t.txn_id===intent.txnId);
  assert.equal(original.state,'rolled_back'); assert.ok(original.backup_path && original.backup_sha256);
  assert.equal(fs.readFileSync(abs,'utf8'),'before');
  console.log('PASS: Phase 8 sparse terminal before-hash/size, observed verification, complete rollback lifecycle and retained original backup');
} finally {gateway.db.close(); fs.rmSync(root,{recursive:true,force:true});}
