// Host-boundary unit tests only. Fake Core responses are explicitly NOT model/activation proof.
const {test}=require('node:test'), assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto');
const {SkillSessionBindings,hashTree,atomicWrite}=require(process.env.TEST_BINDING_MODULE||'../../app/src/main/assets/zcode-runtime/skill-session-bindings.cjs');
function fixture(t) {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'skill-binding-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const workspace=path.join(root,'workspaces','default');fs.mkdirSync(workspace,{recursive:true});
  const config=path.join(workspace,'.zcode','config.json');const inventory=path.join(root,'core-skill-inventory.json');
  let sequence=0;const calls=[],sessions=new Map(),fatals=[];
  function publish(version='1',enabled=true,available=true) {
    const home=path.join(root,'core-skill-packages','example');fs.mkdirSync(home,{recursive:true});
    const stage=path.join(root,'stage');fs.mkdirSync(stage);fs.writeFileSync(path.join(stage,'SKILL.md'),`---\nname: example\ndescription: Fixture\nversion: ${version}\n---\nFixture ${version}\n`);
    const hash=hashTree(stage),directory=path.join(home,'versions',hash);fs.mkdirSync(path.dirname(directory),{recursive:true});
    if(fs.existsSync(directory))fs.rmSync(stage,{recursive:true});else fs.renameSync(stage,directory);
    const previous=fs.existsSync(inventory)?JSON.parse(fs.readFileSync(inventory)).packages[0]:null;
    const versions=(previous?.versions||[]).filter(v=>v.hash!==hash).concat({hash,name:'example',version,source:'fixture:'+version,directory,available});
    atomicWrite(path.join(home,'package.json'),JSON.stringify({schemaVersion:1,id:'example',candidate:hash,enabled,removed:false,origins:Object.fromEntries(versions.map(v=>[v.hash,v.source]))}));
    atomicWrite(inventory,JSON.stringify({schemaVersion:1,packages:[{id:'example',candidate:hash,enabled,removed:false,versions}]}));
    return {hash,directory};
  }
  atomicWrite(inventory,JSON.stringify({schemaVersion:1,packages:[]}));
  const invoke=async(method,params)=>{
    calls.push({method,params});
    const cfg=fs.existsSync(config)?JSON.parse(fs.readFileSync(config)):{};
    if(method==='session/create'||method==='session/resume') {
      const sessionId=params.sessionId||'s'+(++sequence);sessions.set(sessionId,cfg.skills?.roots||[]);
      return {result:{session:{sessionId,mode:'build'}}};
    }
    if(method==='skills/referenceCatalog')return {result:{skills:(sessions.get(params.sessionId)||cfg.skills?.roots||[]).map(directory=>({name:'example',path:path.join(directory,'SKILL.md')}))}};
    return {result:{ok:true}};
  };
  const options={root,workspace,invoke,onFatal:code=>fatals.push(code)};
  const manager=new SkillSessionBindings(options);
  const create=()=>manager.dispatch('session/create',{workspace:{workspacePath:workspace}});
  return {root,workspace,config,inventory,publish,calls,sessions,fatals,options,manager,create};
}
test('update/new session and restarted resume retain distinct immutable versions',async t=>{
  const f=fixture(t),v1=f.publish();await f.create();const v2=f.publish('2');await f.create();
  assert.deepEqual(f.sessions.get('s1'),[v1.directory]);assert.deepEqual(f.sessions.get('s2'),[v2.directory]);
  const restart=new SkillSessionBindings(f.options);await restart.dispatch('session/resume',{sessionId:'s1'});
  assert.deepEqual(f.sessions.get('s1'),[v1.directory]);assert.equal(fs.existsSync(f.config),false);
  const rows=JSON.parse(fs.readFileSync(restart.index));assert.equal(rows[0].managedSkills[0].hash,v1.hash);assert.equal(rows[1].managedSkills[0].hash,v2.hash);
});
test('configuration bytes restored exactly on success and Core rejection',async t=>{
  const f=fixture(t);f.publish();const bytes=Buffer.from('{ "plugins": {"enabled":false}, "other":17 }\n');atomicWrite(f.config,bytes);
  await f.create();assert.deepEqual(fs.readFileSync(f.config),bytes);
  f.manager.invoke=async()=>({error:{code:-1,message:'fixture rejection'}});assert.ok((await f.create()).error);
  assert.deepEqual(fs.readFileSync(f.config),bytes);assert.equal(fs.existsSync(f.manager.txn),false);
});
test('legacy explicit roots survive empty managed selection',async t=>{
  const f=fixture(t),legacy=path.join(f.root,'legacy');atomicWrite(f.config,JSON.stringify({skills:{roots:[legacy]}}));
  await f.create();assert.deepEqual(f.sessions.get('s1'),[legacy]);
});
test('managed roots reject conflicting project overrides before any Core invocation',async t=>{
  const f=fixture(t);f.publish();atomicWrite(f.config,JSON.stringify({skills:{roots:['legacy']}}));
  await assert.rejects(f.create(),/SKILL_PROJECT_OVERRIDE/);assert.equal(f.calls.length,0);
});
test('retirement disables future selection but preserves old session resume',async t=>{
  const f=fixture(t),v=f.publish();await f.create();
  const inv=JSON.parse(fs.readFileSync(f.inventory)),pkg=inv.packages[0];pkg.removed=true;pkg.enabled=false;
  const index=path.join(f.root,'core-skill-packages/example/package.json'),meta=JSON.parse(fs.readFileSync(index));meta.removed=true;meta.enabled=false;
  atomicWrite(index,JSON.stringify(meta));atomicWrite(f.inventory,JSON.stringify(inv));
  await f.create();assert.deepEqual(f.sessions.get('s2'),[]);
  await f.manager.dispatch('session/resume',{sessionId:'s1'});assert.deepEqual(f.sessions.get('s1'),[v.directory]);
});
test('selected missing dependencies prevent Core calls',async t=>{
  const f=fixture(t);f.publish('1',true,false);await assert.rejects(f.create(),/SKILL_UNAVAILABLE/);assert.equal(f.calls.length,0);
});
test('post-import content changes prevent create and send',async t=>{
  const f=fixture(t),v=f.publish();await f.create();fs.appendFileSync(path.join(v.directory,'SKILL.md'),'tampered');
  await assert.rejects(f.create(),/SKILL_HASH_MISMATCH/);await assert.rejects(f.manager.dispatch('session/send',{sessionId:'s1'}),/SKILL_HASH_MISMATCH/);
  assert.equal(f.calls.filter(c=>c.method==='session/send').length,0);
});
test('stale inventory fails before Core invocation',async t=>{
  const f=fixture(t);f.publish();const inv=JSON.parse(fs.readFileSync(f.inventory));inv.packages[0].enabled=false;atomicWrite(f.inventory,JSON.stringify(inv));
  await assert.rejects(f.create(),/SKILL_INVENTORY_STALE/);assert.equal(f.calls.length,0);
});
test('catalog collision never writes a successful session binding',async t=>{
  const f=fixture(t);f.publish();const invoke=f.manager.invoke;f.manager.invoke=async(m,p)=>m==='skills/referenceCatalog'?{result:{skills:[]}}:invoke(m,p);
  await assert.rejects(f.create(),/SKILL_CATALOG_MISMATCH/);assert.equal(fs.existsSync(f.manager.index),false);assert.equal(fs.existsSync(f.config),false);
  await assert.rejects(f.manager.dispatch('session/send',{sessionId:'s1'}),/SKILL_SESSION_UNINDEXED/);
});
test('binding persistence failure poisons subsequent requests',async t=>{
  const f=fixture(t);f.publish();f.manager.writeRows=()=>{throw Error('fixture disk failure');};
  await assert.rejects(f.create(),/fixture disk failure/);assert.deepEqual(f.fatals,['SKILL_BINDING_WRITE_FAILED']);
  await assert.rejects(f.manager.dispatch('session/send',{sessionId:'s1'}),/SKILL_ROUTER_RESTART_REQUIRED/);assert.equal(fs.existsSync(f.config),false);
});
test('cancel bypasses lifecycle queue while concurrent creates serialize',async t=>{
  const f=fixture(t);f.publish();const invoke=f.manager.invoke;let release;
  f.manager.invoke=async(m,p)=>{if(m==='session/create')await new Promise(resolve=>{release=resolve;});return invoke(m,p);};
  const first=f.create();await new Promise(resolve=>setImmediate(resolve));const second=f.create();
  await f.manager.dispatch('session/stop',{sessionId:'s1'});assert.equal(f.calls[0].method,'session/stop');
  release();await first;await new Promise(resolve=>setImmediate(resolve));release();await second;assert.equal(f.sessions.size,2);
});
test('uncertain Core timeout restores configuration and requires restart',async t=>{
  const f=fixture(t);f.publish();f.manager.timeoutMs=10;f.manager.invoke=()=>new Promise(()=>{});
  await assert.rejects(f.create(),/SKILL_RPC_UNCERTAIN/);assert.equal(fs.existsSync(f.config),false);assert.deepEqual(f.fatals,['SKILL_RPC_UNCERTAIN']);
  await assert.rejects(f.create(),/SKILL_ROUTER_RESTART_REQUIRED/);
});
test('startup recovery restores interrupted overlay using durable original bytes',t=>{
  const f=fixture(t),base=Buffer.from('{"preserved":true}\n');atomicWrite(f.config,'{"skills":{"roots":["temporary"]}}');
  atomicWrite(f.manager.txn,JSON.stringify({schemaVersion:1,workspace:f.workspace,existed:true,base64:base.toString('base64'),sha256:crypto.createHash('sha256').update(base).digest('hex')}));
  new SkillSessionBindings(f.options);assert.deepEqual(fs.readFileSync(f.config),base);assert.equal(fs.existsSync(f.manager.txn),false);
});
test('corrupt recovery hash stops startup without replacing configuration',t=>{
  const f=fixture(t);atomicWrite(f.config,'{}');atomicWrite(f.manager.txn,JSON.stringify({schemaVersion:1,workspace:f.workspace,existed:true,base64:'e30=',sha256:'wrong'}));
  assert.throws(()=>new SkillSessionBindings(f.options),/SKILL_RECOVERY_HASH/);assert.equal(fs.readFileSync(f.config,'utf8'),'{}');
});
test('session sending and resume require durable host index',async t=>{
  const f=fixture(t);for(const method of ['session/send','session/resume'])await assert.rejects(f.manager.dispatch(method,{sessionId:'unknown'}),/SKILL_SESSION_UNINDEXED/);
  assert.equal(f.calls.length,0);
});
test('managed child execution remains unavailable until binding contract exists',async t=>{
  const f=fixture(t);f.publish();await assert.rejects(f.manager.dispatch('session/fork',{}),/SKILL_UNBOUND_CHILD_DEFERRED/);
  await assert.rejects(f.manager.dispatch('workspace/generateText',{}),/SKILL_UNBOUND_CHILD_DEFERRED/);assert.equal(f.calls.length,0);
});
