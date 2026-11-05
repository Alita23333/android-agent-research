// Runs actual receiving-product sources. The mock proves protocol/boundaries, never VLM accuracy.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const v = require('../../app/src/main/assets/zcode-runtime/vision-pipeline.cjs');
const {classify, decide} = require('../../app/src/main/assets/zcode-runtime/gateway.cjs');
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'p9-vision-'));
const dir = path.join(root,'runtime','vision'); fs.mkdirSync(dir,{recursive:true});
const cfg = {enabled:true,providerId:'lab',modelId:'lab-vlm',apiKey:'fixture-only',apiType:'openai-chat-completions',baseUrl:'http://127.0.0.1:18086/v1'};
const id = 'shot_' + 'a'.repeat(32);
const frame = {generation:7,screenW:1080,screenH:2400,rotation:0,observationEpoch:'fixture-epoch',render:{nodes:[]}};
const meta = {treeId:'g7',screenW:1080,screenH:2400,rotation:0,observationEpoch:'fixture-epoch',format:'jpeg'};
let requests=0, bodyMode='normal'; const rows=[]; const cache=new Map();
const server = http.createServer((req,res) => {
  requests++; let body=''; req.on('data',x=>body+=x); req.on('end',()=>{
    if (bodyMode === 'normal') assert.match(body,/data:image\/jpeg;base64,/);
    if (bodyMode === 'delay') return setTimeout(()=>res.end('{}'),5000);
    if (bodyMode === 'oversize') return res.end('x'.repeat(140000));
    const content = {text:'屏幕'.repeat(5000),elements:Array.from({length:40},()=>({label:'a'.repeat(80),bbox:[10,20,90,100]}))};
    res.end(JSON.stringify({choices:[{message:{content:JSON.stringify(content)}}]}));
  });
});
const helpers = () => ({spikeRoot:root,lab:true,sessionKey:'session-fixture',sessionCount:()=>0,
  renderFrame:async()=>frame,internalCall:async()=>({ok:true,shotId:id}),readShot:()=>Buffer.from('fixture-image'),shotMeta:()=>meta,
  journal:row=>rows.push(row),cacheGet:key=>cache.get(key),cachePut:(key,value)=>cache.set(key,value)});
async function main() {
  await new Promise(resolve=>server.listen(18086,'127.0.0.1',resolve));
  assert.deepEqual(v.normalizeBbox([1,20,30,40]).bbox,[1,20,30,40]);
  assert.deepEqual(v.normalizeBbox([0.1,0.2,0.3,0.4]).bbox,[100,200,300,400]);
  assert.equal(v.normalizeBbox(['10garbage',20,30,40]).ok,false);
  for (const tool of ['ui_tap','ui_click']) {
    const c=classify('mcp__android-host__'+tool,{confirm:'benign',label:'Factory Reset'},root,root);
    assert.equal(c.risk,'CRITICAL'); assert.equal(decide('full',c.risk),'hard_confirm');
  }
  let r=await v.executeSee({arguments:{question:'Locate'}},helpers());
  assert.equal(r.structuredContent.error.code,'vision_unconfigured'); assert.equal(requests,0);
  fs.writeFileSync(path.join(dir,'vision_config.json'),JSON.stringify(cfg));
  r=await v.executeSee({arguments:{question:'Locate',shotId:'../../escape'}},helpers());
  assert.equal(r.structuredContent.error.code,'ui_invalid_input'); assert.equal(requests,0);
  r=await v.executeSee({arguments:{question:'Locate',shotId:id}},{...helpers(),shotMeta:()=>({...meta,treeId:'g6'})});
  assert.equal(r.structuredContent.error.code,'vision_stale_shot'); assert.equal(requests,0);
  for (const changed of [{observationEpoch:'reconnected-service'},{rotation:2}]) {
    r=await v.executeSee({arguments:{question:'Locate',shotId:id}},{...helpers(),shotMeta:()=>({...meta,...changed})});
    assert.equal(r.structuredContent.error.code,'vision_stale_shot'); assert.equal(requests,0);
  }
  r=await v.executeSee({arguments:{question:'Locate',shotId:id}},helpers());
  assert.equal(r.ok,true); assert.ok(Buffer.byteLength(JSON.stringify(r))<=8192);
  assert.equal(rows[0].result_code,'started'); assert.equal(requests,1);
  assert.match(r.structuredContent.elements[0].action_hint,/shotId/);
  const same=await v.executeSee({arguments:{question:'Locate',shotId:id}},helpers());
  assert.equal(same.ok,true); assert.equal(requests,1,'repeat interpretation must reuse the cache');
  const atCap=await v.executeSee({arguments:{question:'Locate',shotId:id}},{...helpers(),sessionCount:()=>20});
  assert.equal(atCap.ok,true); assert.equal(requests,1,'cached result remains available without egress at the cap');
  const freshAtCap=await v.executeSee({arguments:{question:'Another question',shotId:id}},{...helpers(),sessionCount:()=>20});
  assert.equal(freshAtCap.structuredContent.error.code,'vision_session_cap'); assert.equal(requests,1);
  await assert.rejects(v.httpJson('http://127.0.0.1:18086/v1/chat/completions',{}, {},1000),/egress_refused/);
  await assert.rejects(v.httpJson('https://127.0.0.1:18086/v1/chat/completions',{}, {},1000),/egress_refused/);
  await assert.rejects(v.httpJson('https://localhost:18086/v1/chat/completions',{}, {},1000),/egress_refused/);
  for (const host of ['[::1]','[::ffff:127.0.0.1]','[::ffff:10.0.0.1]','[fe80::1]','[fd00::1]'])
    await assert.rejects(v.httpJson('https://'+host+'/v1/chat/completions',{}, {},1000),/egress_refused/);
  await assert.rejects(v.httpJson(cfg.baseUrl+'/chat/completions',{}, {},1000,{lab:true,beforeEgress:()=>{throw Error('journal failed')}}),/journal failed/);
  assert.equal(requests,1,'audit intent failure must cause zero requests');
  bodyMode='oversize';
  await assert.rejects(v.httpJson(cfg.baseUrl+'/chat/completions',{messages:[]},{},1000,{lab:true}),/too_large/);
  bodyMode='delay'; const controller = new AbortController();
  const pending = v.httpJson(cfg.baseUrl+'/chat/completions',{messages:[]},{},10000,{lab:true,signal:controller.signal});
  setTimeout(()=>controller.abort(),100);
  await assert.rejects(pending,/cancelled/);
  console.log('PASS: actual source bbox, hard safety, config, traversal, stale frame, bounded output, cache, private/HTTP egress, audit failure, response size, cancellation');
}
main().catch(e=>{console.error(e);process.exitCode=1}).finally(()=>{server.closeAllConnections();server.close();fs.rmSync(root,{recursive:true,force:true})});
