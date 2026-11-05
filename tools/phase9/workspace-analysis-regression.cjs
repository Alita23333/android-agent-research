const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict');
const runtime=process.env.TEST_RUNTIME || path.resolve(__dirname,'../../app/src/main/assets/zcode-runtime');
const {Gateway}=require(path.join(runtime,'gateway.cjs'));
const {CarrierAuthorization}=require(path.join(runtime,'carrier-authorization.cjs'));
const {executeAnalysis,runProcess}=require(path.join(runtime,'workspace-analysis.cjs'));
const root=fs.mkdtempSync(path.join(os.tmpdir(),'workspace-analysis-'));
const ws=path.join(root,'workspace');fs.mkdirSync(ws);
fs.writeFileSync(path.join(ws,'data.json'),'{"value":42}');fs.writeFileSync(path.join(ws,'broken.json'),'{broken');
const gateway=new Gateway().init({root,workspace:ws,mode:'ask'}),admission=new CarrierAuthorization(gateway);
gateway.onAsk=key=>gateway.resolveAnswer(key,{decision:'deny'});
let count=0;async function check(name,fn){await fn();console.log('PASS '+name);count++;}
async function call(args,signal) {
  const sessionId='script-fixture';
  const id=await admission.authorize('workspace_analyze',args,sessionId,signal);
  return executeAnalysis({arguments:args,meta:{sessionId},approvalOpId:id,cancelSignal:signal},gateway,admission);
}
(async()=>{
  await check('real Gateway read approval precedes fixed Node script and exact row finishes',async()=>{
    const r=await call({operation:'inventory',files:['data.json']});assert.ok(r.ok);assert.equal(r.structuredContent.execution.exitCode,0);
    assert.equal(Buffer.from(r.structuredContent.files[0].content,'base64').toString(),'{"value":42}');
    assert.equal(gateway.journalView(1)[0].result,'ok');
  });
  await check('invalid JSON yields script exit3 and structured failure',async()=>{
    const r=await call({operation:'parse_json',files:['broken.json']});assert.equal(r.ok,false);assert.equal(r.error.code,'INVALID_JSON');
    assert.equal(r.structuredContent.execution.exitCode,3);assert.equal(fs.readFileSync(path.join(ws,'broken.json'),'utf8'),'{broken');
  });
  for(const [name,args] of [['traversal',{operation:'inventory',files:['../outside']}],['unknown command',{operation:'inventory',files:['data.json'],command:'anything'}],['missing file',{operation:'inventory',files:['missing']}]] )
    await check(name+' rejected without script',async()=>{const r=await call(args);assert.equal(r.ok,false);assert.equal(r.structuredContent,undefined);});
  await check('forged operation cannot execute',async()=>{
    const r=await executeAnalysis({approvalOpId:123456,arguments:{operation:'inventory',files:['data.json']},meta:{sessionId:'script-fixture'}},gateway,admission);
    assert.equal(r.error.code,'GATEWAY_INTENT_UNBOUND');
  });
  await check('journal failure yields no execution',async()=>{
    const journal=gateway.journal;gateway.journal=()=>{throw Error('journal fault');};
    await assert.rejects(call({operation:'inventory',files:['data.json']}),/journal fault/);gateway.journal=journal;
  });
  await check('pre-cancel denies invocation',async()=>{const c=new AbortController();c.abort();await assert.rejects(call({operation:'inventory',files:['data.json']},c.signal),/CANCELLED/);});
  await check('large input rejected before script',async()=>{
    fs.writeFileSync(path.join(ws,'large.txt'),'x'.repeat(32769));
    const r=await call({operation:'inventory',files:['large.txt']});assert.equal(r.error.code,'INPUT_TOO_LARGE');assert.equal(r.structuredContent,undefined);
  });
  if(process.platform!=='win32') await check('outside symlink cannot enter script snapshot',async()=>{
    const outside=path.join(root,'private.txt');fs.writeFileSync(outside,'not workspace input');fs.symlinkSync(outside,path.join(ws,'link.txt'));
    const r=await call({operation:'inventory',files:['link.txt']});assert.equal(r.ok,false);assert.equal(r.structuredContent,undefined);
  });
  await check('bounded process drains and rejects excessive output',async()=>{
    const r=await runProcess({executable:process.execPath,args:['-e',"process.stdout.write('x'.repeat(100000))"],cwd:ws,env:process.env,input:'',maxOutput:1024});
    assert.equal(r.code,'OUTPUT_LIMIT');assert.ok(r.truncated);assert.ok(Buffer.byteLength(r.stdout)<=1024);
  });
  await check('actual timeout is not a successful process',async()=>{
    const r=await runProcess({executable:process.execPath,args:['-e','setInterval(()=>{},1000)'],cwd:ws,env:process.env,input:'',timeoutMs:120});assert.equal(r.code,'TIMEOUT');
  });
  await check('actual cancellation is not a successful process',async()=>{
    const c=new AbortController();setTimeout(()=>c.abort(),120);
    const r=await runProcess({executable:process.execPath,args:['-e','setInterval(()=>{},1000)'],cwd:ws,env:process.env,input:'',signal:c.signal});assert.equal(r.code,'CANCELLED');
  });
  if(process.platform!=='win32') await check('cancel stops ignoring descendant even if leader exits',async()=>{
    const file=path.join(ws,'leaf.pid'),c=new AbortController();
    const code=`const {spawn}=require('node:child_process');const fs=require('node:fs');const leaf=spawn(process.execPath,['-e',"process.on('SIGTERM',()=>{});setInterval(()=>{},1000)"],{stdio:'ignore'});fs.writeFileSync(${JSON.stringify(file)},String(leaf.pid));setInterval(()=>{},1000);`;
    const pending=runProcess({executable:process.execPath,args:['-e',code],cwd:ws,env:process.env,input:'',signal:c.signal});
    while(!fs.existsSync(file))await new Promise(r=>setTimeout(r,20));await new Promise(r=>setTimeout(r,120));c.abort();
    const r=await pending;assert.equal(r.code,'CANCELLED');const pid=Number(fs.readFileSync(file,'utf8'));
    for(let i=0;i<20;i++){try{const s=fs.readFileSync('/proc/'+pid+'/stat','utf8');if(s.slice(s.lastIndexOf(')')+2).startsWith('Z'))return;}catch(e){if(e.code==='ENOENT')return;}await new Promise(r=>setTimeout(r,20));}
    throw Error('descendant still running');
  });
  console.log(JSON.stringify({checks:count,platform:process.platform,root}));
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>{gateway.db.close();fs.rmSync(root,{recursive:true,force:true});});
