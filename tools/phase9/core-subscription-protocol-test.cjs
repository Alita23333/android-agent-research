// Actual immutable Core schema/lifecycle only. No model/tool requests or production config.
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'core-sub-')),workspace=path.join(root,'workspace');
fs.mkdirSync(workspace);fs.mkdirSync(path.join(workspace,'.git'));fs.mkdirSync(path.join(root,'.zcode/cli'),{recursive:true});
fs.writeFileSync(path.join(root,'.zcode/cli/config.json'),JSON.stringify({features:{memory:false},memory:{extractionEnabled:false},plugins:{enabled:false},hooks:{enabled:false,events:{}}}));
assert.ok(process.env.TEST_CORE);
const core=spawn(process.execPath,[process.env.TEST_CORE,'app-server'],{cwd:workspace,env:{...process.env,HOME:root,USERPROFILE:root,ZCODE_HOME:path.join(root,'.zcode'),ZCODE_STORAGE_DIR:root,ZCODE_LOG_DIR:path.join(root,'logs')}});
let buffer='',sequence=0,stderr='',exited=false;const pending=new Map(),timers=new Set();
const exit=new Promise((resolve,reject)=>{core.once('error',reject);core.once('exit',(code,signal)=>{exited=true;resolve({code,signal});});});
core.stderr.on('data',b=>{stderr=(stderr+b).slice(-2000);});core.stdin.on('error',()=>{});
core.stdout.on('data',b=>{buffer+=b;let i;while((i=buffer.indexOf('\n'))>=0){
 let m;try{m=JSON.parse(buffer.slice(0,i));}catch{}buffer=buffer.slice(i+1);if(!m)continue;
 if(m.method&&m.id!==undefined){let result={};if(m.method==='interaction/requestPermission')result={decision:'deny'};
  if(m.method==='session/requestRuntimePreferences')result={nativeSearchEnhancementsEnabled:false,memoryEnabled:false,askUserQuestionAutoResolutionEnabled:true};
  core.stdin.write(JSON.stringify({id:m.id,result})+'\n');
 }else if(pending.has(m.id)){pending.get(m.id)(m);pending.delete(m.id);}
}});
function deadline(p,ms){let timer;return Promise.race([p,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('protocol deadline')),ms);timers.add(timer);})]).finally(()=>{clearTimeout(timer);timers.delete(timer);});}
function rpc(method,params){const id='sub_'+(++sequence);return deadline(new Promise(resolve=>{pending.set(id,resolve);core.stdin.write(JSON.stringify({id,method,params})+'\n');}),15000);}
(async()=>{
 try{
  const created=await rpc('session/create',{workspace:{workspacePath:workspace,workspaceKey:'default'},mode:'build',titleGenerationEnabled:false,dynamicWorkflowEnabled:false,offPeakToolEnabled:false,
   importedHistory:{source:'claudeCode',title:'Subscription-only protocol fixture',messages:[{role:'user',content:'Protocol fixture only, do not call any model or tools.'}]}});
  assert.equal(created.error,undefined);const sessionId=created.result.session.sessionId;
  const missing=await rpc('session/subscribe',{sessionId});
  assert.equal(missing.error?.code,-32602);assert.match(JSON.stringify(missing.error),/deliveryKind/);
  const invalid=await rpc('session/subscribe',{sessionId,deliveryKind:'web'});
  assert.equal(invalid.error?.code,-32602);assert.match(JSON.stringify(invalid.error),/deliveryKind/);
  const positive=[];
  for(let i=0;i<2;i++){
   const subscribed=await rpc('session/subscribe',{sessionId,deliveryKind:'desktop-continuous'});
   assert.equal(subscribed.error,undefined);assert.equal(subscribed.result.sessionId,sessionId);
   assert.ok(Number.isSafeInteger(subscribed.result.eventSeq)&&subscribed.result.eventSeq>=0);assert.ok(Array.isArray(subscribed.result.events));
   positive.push(subscribed.result);
  }
  const read=await rpc('session/read',{sessionId});assert.equal(read.error,undefined);assert.ok(Array.isArray(read.result.messages));
  core.stdin.end();const termination=await deadline(exit,5000);assert.deepEqual(termination,{code:0,signal:null});
  return {verdict:'PASS_ACTUAL_CORE_SUBSCRIPTION_PROTOCOL',node:process.version,sessionId,checks:5,
   missingDeliveryKind:missing.error.code,invalidDeliveryKind:invalid.error.code,positive,readMessageCount:read.result.messages.length,naturalExit:termination,
   scope:'Actual immutable Core schema and repeat subscribe/read only; no model, provider, Service or product bridge acceptance'};
 }finally{
  for(const t of timers)clearTimeout(t);
  if(!exited){core.kill('SIGKILL');await exit;}
  fs.rmSync(root,{recursive:true,force:true});
 }
})().then(r=>console.log(JSON.stringify(r))).catch(e=>{console.error(e.stack);console.error(stderr);process.exitCode=1;});
