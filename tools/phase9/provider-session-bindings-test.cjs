// Host session-index boundary only: fake Core, explicit host verifier, inert fixture packages.
// This does not prove imported-provider admission, catalog integration or model execution.
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto'),vm=require('node:vm');
const runtime=process.env.TEST_RUNTIME||path.resolve(__dirname,'../../app/src/main/assets/zcode-runtime');
const {SkillSessionBindings,atomicWrite}=require(path.join(runtime,'skill-session-bindings.cjs'));
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
function fixture(t) {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'provider-session-')),workspace=path.join(root,'workspaces/default');
  fs.mkdirSync(workspace,{recursive:true});atomicWrite(path.join(root,'core-skill-inventory.json'),JSON.stringify({schemaVersion:1,packages:[]}));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  let selected=[],sequence=0;const entries=new Map(),calls=[],fatals=[];
  function publish(version='1') {
    const bytes=Buffer.from('Inert provider fixture version '+version),contentHash=sha(bytes);
    const file=path.join(root,'test-packages',contentHash,'fixture.txt');atomicWrite(file,bytes);
    const declaration={toolId:'sample.inspect',version,profile:'bounded-data-transform'};
    const pin={id:'sample',version,contentHash,definitionHash:sha(JSON.stringify(declaration)),toolIds:['sample.inspect']};
    entries.set(contentHash,{file,pin:structuredClone(pin)});selected=[pin];return pin;
  }
  const providerBindings={selected:()=>selected,verify:pin=>{
    const e=entries.get(pin.contentHash);
    return !!e&&fs.existsSync(e.file)&&sha(fs.readFileSync(e.file))===pin.contentHash&&JSON.stringify(pin)===JSON.stringify(e.pin);
  }};
  const options={root,workspace,providerBindings,onFatal:c=>fatals.push(c),invoke:async(method,params)=>{
    calls.push({method,params});
    return {result:method==='session/create'||method==='session/resume'?{session:{sessionId:params.sessionId||'s'+(++sequence)}}:{ok:true}};
  }};
  const manager=new SkillSessionBindings(options);
  const create=(extra={})=>manager.dispatch('session/create',{workspace:{workspacePath:workspace},...extra});
  return {root,workspace,options,manager,create,publish,calls,entries,fatals,setSelected:p=>{selected=p;},providerBindings};
}
test('v1/v2 create, send and restarted resume keep original durable pins',async t=>{
  const f=fixture(t),v1=f.publish();await f.create();const v2=f.publish('2');await f.create();
  const restart=new SkillSessionBindings(f.options);
  await restart.dispatch('session/resume',{sessionId:'s1'});await restart.dispatch('session/send',{sessionId:'s1'});
  assert.deepEqual(restart.providerPin('s1','sample.inspect'),v1);assert.deepEqual(restart.providerPin('s2','sample.inspect'),v2);
  const rows=JSON.parse(fs.readFileSync(restart.index));assert.equal(rows.length,2);
  assert.deepEqual(rows[0].managedProviders,[v1]);assert.deepEqual(rows[1].managedProviders,[v2]);
});
test('model/RPC supplied snapshot fields cannot select or widen providers',async t=>{
  const f=fixture(t),pin=f.publish();await f.create({managedProviders:[{id:'root'}],providerBindings:{toolIds:['workspace.delete']}});
  await f.manager.dispatch('session/resume',{sessionId:'s1',managedProviders:[]});
  assert.deepEqual(f.manager.providerPin('s1','sample.inspect'),pin);
  assert.throws(()=>f.manager.providerPin('s1','sample.delete'),/PROVIDER_SESSION_TOOL_UNBOUND/);
});
test('retirement stops new selection while retained old reviewed version resumes',async t=>{
  const f=fixture(t),pin=f.publish();await f.create();f.setSelected([]);await f.create();
  const restart=new SkillSessionBindings(f.options);await restart.dispatch('session/resume',{sessionId:'s1'});
  assert.deepEqual(restart.providerPin('s1','sample.inspect'),pin);
  assert.throws(()=>restart.providerPin('s2','sample.inspect'),/TOOL_UNBOUND/);
});
test('missing or tampered original fixture prevents resume, send and tool resolution',async t=>{
  const f=fixture(t),pin=f.publish();await f.create();f.publish('2');
  fs.writeFileSync(f.entries.get(pin.contentHash).file,'tampered');const before=f.calls.length;
  for(const method of ['session/resume','session/send'])await assert.rejects(f.manager.dispatch(method,{sessionId:'s1'}),/PIN_UNAVAILABLE/);
  assert.throws(()=>f.manager.providerPin('s1','sample.inspect'),/PIN_UNAVAILABLE/);assert.equal(f.calls.length,before);
});
test('restart without host verifier fails closed for pinned sessions',async t=>{
  const f=fixture(t);f.publish();await f.create();const restart=new SkillSessionBindings({...f.options,providerBindings:null});
  await assert.rejects(restart.dispatch('session/resume',{sessionId:'s1'}),/PIN_UNAVAILABLE/);
});
test('legacy and empty sessions do not inherit providers selected later',async t=>{
  const f=fixture(t);await f.create();f.publish();
  await f.manager.dispatch('session/resume',{sessionId:'s1'});assert.throws(()=>f.manager.providerPin('s1','sample.inspect'),/TOOL_UNBOUND/);
  const rows=JSON.parse(fs.readFileSync(f.manager.index));delete rows[0].managedProviders;delete rows[0].managedProviderBindingVersion;
  atomicWrite(f.manager.index,JSON.stringify(rows));await f.manager.dispatch('session/resume',{sessionId:'s1'});
  assert.deepEqual(JSON.parse(fs.readFileSync(f.manager.index))[0].managedProviders,[]);
});
test('selection, verifier argument and resolved pin cannot mutate persisted snapshot',async t=>{
  const f=fixture(t),pin=f.publish();await f.create();pin.toolIds.push('sample.other');
  const resolved=f.manager.providerPin('s1','sample.inspect');resolved.toolIds.push('sample.hijack');
  assert.deepEqual(f.manager.providerPin('s1','sample.inspect').toolIds,['sample.inspect']);
  f.providerBindings.verify=p=>{p.toolIds.push('sample.verifier');return true;};
  assert.deepEqual(f.manager.providerPin('s1','sample.inspect').toolIds,['sample.inspect']);
});
test('changed or revoked reviewed declaration is rejected even if content hash survives',async t=>{
  const f=fixture(t),pin=f.publish();await f.create();f.entries.get(pin.contentHash).pin.definitionHash='b'.repeat(64);
  await assert.rejects(f.manager.dispatch('session/send',{sessionId:'s1'}),/PIN_UNAVAILABLE/);
});
test('snapshot malformed, duplicate, reserved, wire collision and promise verifier refused before Core',async t=>{
  const f=fixture(t),pin=f.publish();
  for(const value of [[{...pin,extra:true}],[{...pin,contentHash:'../bad'}],[{...pin,id:'ui'}],[pin,pin],
    [{...pin,id:'foo_bar',toolIds:['foo_bar.inspect']},{...pin,id:'foo',toolIds:['foo.bar_inspect']}],
    [{...pin,toolIds:['sample.inspect','sample.inspect']}],[{...pin,version:'\n'}]]) {
    f.setSelected(value);await assert.rejects(f.create(),/PROVIDER_SESSION_/);
  }
  f.setSelected([pin]);f.providerBindings.verify=async()=>true;await assert.rejects(f.create(),/PIN_UNAVAILABLE/);
  assert.equal(f.calls.length,0);
});
test('workspace mismatch prevents Core and direct tool resolution',async t=>{
  const f=fixture(t);f.publish();await f.create();const other=path.join(f.root,'workspaces/other');fs.mkdirSync(other);
  await assert.rejects(f.create({workspace:{workspacePath:other}}),/WORKSPACE_MISMATCH/);
  const restart=new SkillSessionBindings({...f.options,workspace:other});await assert.rejects(restart.dispatch('session/resume',{sessionId:'s1'}),/WORKSPACE_MISMATCH/);
  assert.throws(()=>restart.providerPin('s1','sample.inspect'),/WORKSPACE_MISMATCH/);
});
test('post-Core recheck refuses revoked pin without persisting successful binding',async t=>{
  const f=fixture(t),pin=f.publish(),invoke=f.manager.invoke;
  f.manager.invoke=async(m,p)=>{const result=await invoke(m,p);f.entries.delete(pin.contentHash);return result;};
  await assert.rejects(f.create(),/PIN_UNAVAILABLE/);assert.equal(fs.existsSync(f.manager.index),false);
});
test('binding write failure poisons subsequent operations including tool resolution',async t=>{
  const f=fixture(t);f.publish();f.manager.writeRows=()=>{throw Error('injected index failure');};
  await assert.rejects(f.create(),/injected index failure/);
  await assert.rejects(f.create(),/RESTART_REQUIRED/);assert.throws(()=>f.manager.providerPin('s1','sample.inspect'),/RESTART_REQUIRED/);
  assert.deepEqual(f.fatals,['SKILL_BINDING_WRITE_FAILED']);
});
test('managed child execution deferred and cancellation bypasses lifecycle queue',async t=>{
  const f=fixture(t);f.publish();
  for(const m of ['session/fork','workspace/generateText'])await assert.rejects(f.manager.dispatch(m),/PROVIDER_UNBOUND_CHILD_DEFERRED/);
  const invoke=f.manager.invoke;let release;f.manager.invoke=async(m,p)=>{if(m==='session/create')await new Promise(r=>{release=r;});return invoke(m,p);};
  const create=f.create();await new Promise(r=>setImmediate(r));await f.manager.dispatch('session/stop',{sessionId:'s1'});
  assert.equal(f.calls[0].method,'session/stop');release();await create;
});
test('resume cannot bind snapshot to a different Core session ID',async t=>{
  const f=fixture(t);f.publish();await f.create();f.manager.invoke=async()=>({result:{session:{sessionId:'other'}}});
  await assert.rejects(f.manager.dispatch('session/resume',{sessionId:'s1'}),/PROVIDER_SESSION_ID_MISMATCH/);
  assert.equal(JSON.parse(fs.readFileSync(f.manager.index)).length,1);
});
test('real bootstrap delegates host session pin to projection, never selects latest worker hash',t=>{
  const source=fs.readFileSync(path.join(runtime,'bootstrap.cjs'),'utf8'),start=source.indexOf('if (nativeDispatcher && providerContentHash !== null)');
  const end=source.indexOf('const controller = new AbortController();',start);assert.ok(start>0&&end>start);
  const block=source.slice(start,end),calls=[];
  for(const mode of ['match','new-worker','unbound','fixed']) {
    const pin={contentHash:'a'.repeat(64),definitionHash:'b'.repeat(64)};
    const ctx={nativeDispatcher:true,providerContentHash:mode==='fixed'?null:'c'.repeat(64),providerDefinitionHash:null,providerSessionPin:null,
      sessionId:'s1',nativeDefinition:{metadata:{canonicalToolId:'sample.inspect'}},call:{meta:{}},
      skillBindings:{providerPin:(session,tool)=>{calls.push([session,tool]);if(mode==='unbound')throw Error('PROVIDER_SESSION_TOOL_UNBOUND');return pin;}},
      providerBindings:{route:(value,definition,call)=>{assert.equal(value,pin);call.meta.providerContentHash=value.contentHash;return value;}}};
    if(mode==='unbound')assert.throws(()=>vm.runInNewContext(block,ctx),/PROVIDER_SESSION_/);
    else {vm.runInNewContext(block,ctx);if(mode!=='fixed'){assert.equal(ctx.providerContentHash,pin.contentHash);assert.equal(ctx.providerDefinitionHash,pin.definitionHash);}}
  }
  assert.deepEqual(calls,[['s1','sample.inspect'],['s1','sample.inspect'],['s1','sample.inspect']]);
});
