const assert = require('node:assert/strict'), fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const runtime=process.env.TEST_RUNTIME || path.resolve(__dirname,'../../app/src/main/assets/zcode-runtime');
const {Gateway} = require(path.join(runtime,'gateway.cjs'));
const {CarrierAuthorization} = require(path.join(runtime,'carrier-authorization.cjs'));
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'carrier-admission-'));
fs.mkdirSync(path.join(root,'workspace'));
const gateway = new Gateway().init({root, workspace:path.join(root,'workspace'), mode:'ask'});
let decision='allow', asks=0, effects=0, now=Date.now();
gateway.onAsk = key => {asks++; gateway.resolveAnswer(key,{decision});};
const admission = new CarrierAuthorization(gateway, () => now);
const params = {requestId:'broker',sessionId:'fixture',toolName:'mcp__android-host__ui_scroll',input:{direction:'forward'}};
const execute = async (args={direction:'forward'}, session='fixture', signal) => {
  const id = await admission.authorize('ui_scroll',args,session,signal); effects++; return id;
};
let checks=0;
async function test(name, fn) {await fn();checks++;console.log('PASS '+name);}
(async()=>{
  await test('direct UI call commits real Gateway intent before execution', async()=>{
    const id=await execute();assert.equal(gateway.journalView(1)[0].id,id);assert.equal(effects,1);
  });
  await test('normal broker approval reused once without a second prompt', async()=>{
    const p=await gateway.handlePermission(params);admission.recordBroker(params,p);const before=asks;
    assert.equal(await execute(),p.operationId);assert.equal(asks,before);
    decision='deny';await assert.rejects(execute(),/GATEWAY_DENIED/);assert.equal(asks,before+1);decision='allow';
  });
  for (const kind of ['arguments','session','tool']) await test('no approval widening: '+kind, async()=>{
    const p=await gateway.handlePermission(params);admission.recordBroker(params,p);decision='deny';const before=effects;
    if(kind==='arguments')await assert.rejects(execute({direction:'backward'}),/GATEWAY_DENIED/);
    if(kind==='session')await assert.rejects(execute({direction:'forward'},'other'),/GATEWAY_DENIED/);
    if(kind==='tool')await assert.rejects(admission.authorize('ui_click',{direction:'forward'},'fixture'),/GATEWAY_DENIED/);
    assert.equal(effects,before);decision='allow';admission.clear();
  });
  await test('journal failure means zero executions',async()=>{
    const journal=gateway.journal;const before=effects;gateway.journal=()=>{throw Error('injected journal failure');};
    await assert.rejects(execute(),/injected journal failure/);assert.equal(effects,before);gateway.journal=journal;
  });
  await test('approved response without matching committed row rejected',async()=>{
    const handle=gateway.handlePermission;gateway.handlePermission=async()=>({decision:'allow',operationId:999999});
    await assert.rejects(execute(),/GATEWAY_INTENT_UNBOUND/);gateway.handlePermission=handle;
  });
  await test('committed row exact tool/arguments/session required',async()=>{
    const p=await gateway.handlePermission(params);
    assert.ok(admission.matches(p.operationId,'ui_scroll',{direction:'forward'},'fixture'));
    assert.ok(!admission.matches(p.operationId,'ui_click',{direction:'forward'},'fixture'));
    assert.ok(!admission.matches(p.operationId,'ui_scroll',{direction:'backward'},'fixture'));
    assert.ok(!admission.matches(p.operationId,'ui_scroll',{direction:'forward'},'other'));
  });
  await test('cancelled before admission means zero execution',async()=>{
    const c=new AbortController();c.abort();const before=effects;await assert.rejects(execute(undefined,undefined,c.signal),/CANCELLED/);assert.equal(effects,before);
  });
  await test('cancel during pending confirmation means zero execution',async()=>{
    const c=new AbortController();let key;const before=effects;gateway.onAsk=k=>{key=k;};
    const wait=execute(undefined,undefined,c.signal);c.abort();gateway.resolveAnswer(key,{decision:'allow'});
    await assert.rejects(wait,/CANCELLED/);assert.equal(effects,before);
    gateway.onAsk=k=>{asks++;gateway.resolveAnswer(k,{decision});};
  });
  await test('expired grant cannot authorize another call',async()=>{
    const p=await gateway.handlePermission(params);admission.recordBroker(params,p);now+=121000;decision='deny';
    await assert.rejects(execute(),/GATEWAY_DENIED/);now=Date.now();decision='allow';admission.clear();
  });
  await test('ambiguous grants fail closed',async()=>{
    for(let i=0;i<2;i++){const p=await gateway.handlePermission(params);admission.recordBroker(params,p);}
    await assert.rejects(execute(),/GATEWAY_APPROVAL_AMBIGUOUS/);admission.clear();
  });
  await test('session cancellation clears reusable grants',async()=>{
    const p=await gateway.handlePermission(params);admission.recordBroker(params,p);admission.clear();decision='deny';
    await assert.rejects(execute(),/GATEWAY_DENIED/);decision='allow';
  });
  await test('completed operation cannot be executed again',async()=>{
    const p=await gateway.handlePermission(params);gateway.db.prepare('update operation set result=? where id=?').run('ok',p.operationId);
    assert.ok(!admission.matches(p.operationId,'ui_scroll',{direction:'forward'},'fixture'));
  });
  await test('real closed SQLite journal means zero execution',async()=>{
    admission.clear();const before=effects;gateway.db.close();await assert.rejects(execute(),/not open|closed/i);assert.equal(effects,before);
  });
  console.log('RESULT '+checks+' PASS; zero execution on denied/unbound/cancelled scopes');
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>{try {gateway.db.close();} catch {} fs.rmSync(root,{recursive:true,force:true});});
