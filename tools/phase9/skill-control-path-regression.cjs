// Actual Gateway/SQLite regressions. No production config writes or model calls.
const assert = require('node:assert/strict');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const runtime = process.env.TEST_RUNTIME || path.resolve(__dirname,'../../app/src/main/assets/zcode-runtime');
const {Gateway,resolveWorkspaceTarget,containWorkspaceAbsolute} = require(path.join(runtime,'gateway.cjs'));
const {handleWorkspaceTool} = require(path.join(runtime,'workspace-files.cjs'));
const root=fs.mkdtempSync(path.join(process.env.TEST_FIXTURE_PARENT || os.tmpdir(),'skill-control-'));
const workspace=path.join(root,'workspace');fs.mkdirSync(workspace);
const gateway=new Gateway().init({root,workspace,mode:'full'});
let count=0;
function check(name,fn) {fn();console.log('PASS '+name);count++;}
async function main() {
  const reserved=['.zcode/config.json','zcode.json','.agents/skills/example/SKILL.md','nested/.zcode/config.json',
    'nested/.agents/skills/example/references/rule.txt','notes/../.zcode/config.json'];
  for(const rel of reserved) check('both resolvers reserve '+rel,()=>{
    assert.equal(resolveWorkspaceTarget(workspace,rel,{createParents:true}).code,'path_reserved');
    assert.equal(containWorkspaceAbsolute(workspace,path.resolve(workspace,rel),{createParents:true}).code,'path_reserved');
  });
  let asks=0;gateway.onAsk=()=>{asks++;};
  for(const mode of ['ask','supervised','full']) {
    gateway.mode=mode;
    for(const tool of ['workspace_file_create','workspace_file_overwrite','workspace_file_append','workspace_file_delete']) {
      const before=gateway.db.prepare('select count(*) as n from write_txn').get().n;
      for(const rel of reserved) {
        const result=await gateway.handlePermission({sessionId:'control-fixture',toolName:'mcp__android-host__'+tool,input:{path:rel,content:'fixture',create_parents:true}});
        assert.equal(result.decision,'deny');assert.match(result.reason,/path_reserved/);
      }
      check(mode+' '+tool+' reserves all control paths before intent/ask',()=>{
        assert.equal(gateway.db.prepare('select count(*) as n from write_txn').get().n,before);assert.equal(asks,0);
      });
    }
  }
  gateway.mode='full';
  for(const tool of ['Write','Edit']) {
    const result=await gateway.handlePermission({sessionId:'control-fixture',toolName:tool,input:{path:'.zcode/config.json',content:'fixture'}});
    check('upstream '+tool+' relative control path denied',()=>assert.equal(result.decision,'deny'));
  }
  check('direct intent cannot bypass control reserve',()=>{
    const result=gateway.commitIntent({params:{toolName:'workspace_file_create',sessionId:'control-fixture'},input:{path:'.zcode/config.json',resolved_path:path.join(workspace,'.zcode/config.json'),create_parents:true},risk:'WRITE'});
    assert.equal(result.ok,false);assert.equal(result.code,'path_outside_workspace');
  });
  for(const tool of ['workspace_file_create','workspace_file_overwrite','workspace_file_append','workspace_file_delete']) {
    check('execution leg rejects control target '+tool,()=>{
      const result=handleWorkspaceTool(tool,{path:'.zcode/config.json',content:'fixture',create_parents:true},gateway);
      assert.equal(result.ok,false);assert.equal(fs.existsSync(path.join(workspace,'.zcode/config.json')),false);
    });
  }
  check('ordinary names close to reserved names remain valid',()=>{
    for(const rel of ['notes/.zcode-guide.txt','.agents-guide/SKILL.md','zcode.json.txt','SKILL.md'])
      assert.equal(resolveWorkspaceTarget(workspace,rel,{createParents:true}).ok,true);
  });
  const rel='notes/result.txt',input={path:rel,content:'normal',create_parents:true};
  const approved=await gateway.handlePermission({sessionId:'control-fixture',toolName:'mcp__android-host__workspace_file_create',input});
  assert.equal(approved.decision,'allow');
  const result=handleWorkspaceTool('workspace_file_create',input,gateway);
  check('ordinary journalled create remains functional',()=>{assert.equal(result.ok,true);assert.equal(result.verified,true);});
  const row=gateway.journalView(10).find(x=>x.result==='ok');
  const rolled=gateway.rollback(row.id);
  check('ordinary rollback remains a verified Gateway operation',()=>{
    assert.equal(rolled.ok,true);assert.equal(fs.existsSync(path.join(workspace,rel)),false);
  });
  console.log('RESULT '+count+' PASS');
}
main().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>{
  gateway.db.close();fs.rmSync(root,{recursive:true,force:true});
});
