// Execute the actual host functions in an isolated VM; never touch a running product.
const assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.resolve(__dirname,'../../app/src/main/assets/zcode-runtime/bootstrap.cjs'),'utf8');
const functions=source.slice(source.indexOf('function boundInternalApproval('),source.indexOf('function forwardToChild('));
const cleanup=source.slice(source.indexOf('let liveUiRaw = null;'),source.indexOf('const { TOOLS: WS_TOOLS'));
const root=fs.mkdtempSync(path.join(os.tmpdir(),'p9-internal-'));
async function main(){
  for(const mismatch of ['missing','session','args','deny','journal_failure']) {
    const state={};
    const row={id:35,decision:'allow',tool:'mcp__android-host__ui_dump',session:'fixture',args:'{}'};
    if(mismatch==='session') row.session='other';
    if(mismatch==='args') row.args='{"raw":true}';
    if(mismatch==='deny') row.decision='deny';
    const context=vm.createContext({state,require,signal:new AbortController().signal,
      gateway:{handlePermission:async()=>{if(mismatch==='journal_failure')throw Error('journal failed');return {decision:'allow',operationId:35}},
        journalView:()=>mismatch==='missing'?[]:[row]}});
    vm.runInContext(functions,context);
    await assert.rejects(vm.runInContext('tapPreflight({x:50,y:50},"fixture",signal)',context),/GATEWAY_INTENT_UNBOUND|journal failed/);
    assert.equal(state.carrierQueue,undefined,'no observation/action may queue without exact committed approval');
  }
  const state={}; const raw={generation:4,observationEpoch:'fixture-epoch',nodes:[{b:[0,0,100,100],t:'Factory Reset',children:[]}]};
  const context=vm.createContext({state,require,setTimeout,clearTimeout,liveUiRaw:raw,signal:new AbortController().signal,
    gateway:{handlePermission:async()=>({decision:'allow',operationId:35}),journalView:()=>[{id:35,decision:'allow',tool:'mcp__android-host__ui_dump',session:'fixture',args:'{}'}]}});
  vm.runInContext(functions,context);
  const task=vm.runInContext('tapPreflight({x:50,y:50,label:"benign"},"fixture",signal)',context);
  await new Promise(r=>setImmediate(r));
  assert.equal(state.carrierQueue.length,1);
  const pending=state.carrierPending.get(state.carrierQueue[0].callId);
  assert.equal(pending.approvalOpId,35);
  pending.resolve({body:{structuredContent:{ok:true,treeId:'g4'}}});
  const target=await task; assert.match(target.label,/Factory Reset/); assert.equal(target.epoch,'fixture-epoch');
  assert.equal(state.carrierQueue.length,0); assert.equal(state.carrierPending.size,0);
  fs.writeFileSync(path.join(root,'fixture.jpeg'),'fixture');
  const controller=new AbortController(); const results=[];
  const canceled={carrierQueue:[{}],carrierPending:new Map([['id',{timer:setTimeout(()=>{},3000),resolve:r=>results.push(r)}]]),
    visionControllers:new Set([controller]),visionCache:new Map([['fixture',{}]])};
  vm.runInNewContext(cleanup+'\ncancelCarrierPending("CANCELLED");', {fs,path,SHOTS:root,state:canceled,clearTimeout});
  assert.equal(controller.signal.aborted,true); assert.equal(canceled.carrierPending.size,0);
  assert.equal(canceled.carrierQueue.length,0); assert.equal(canceled.visionCache.size,0);
  assert.equal(results[0].body.error.code,'CANCELLED'); assert.equal(fs.readdirSync(root).length,0);
  console.log('PASS: exact internal approval binding, no-journal/no-queue, actual critical labels, pending cleanup and frame/cache purge');
}
main().catch(e=>{console.error(e);process.exitCode=1}).finally(()=>fs.rmSync(root,{recursive:true,force:true}));
