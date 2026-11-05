// Actual Core lifecycle + provider session metadata; explicit inert fixture verifier. No provider/model execution.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const http=require('node:http');
const {SkillSessionBindings,hashTree,atomicWrite}=require(process.env.TEST_BINDING_MODULE||'../../app/src/main/assets/zcode-runtime/skill-session-bindings.cjs');
const runtime=process.env.TEST_BINDING_RUNTIME||path.resolve(__dirname,'../../app/src/main/assets/zcode-runtime');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'skill-binding-core-')),workspace=path.join(root,'workspaces','default');
fs.mkdirSync(workspace,{recursive:true});fs.mkdirSync(path.join(workspace,'.git'));
const config={features:{memory:false},memory:{extractionEnabled:false},plugins:{enabled:false},hooks:{enabled:false,events:{}}};
atomicWrite(path.join(root,'.zcode/cli/config.json'),JSON.stringify(config));
const throughHost=process.env.TEST_BINDING_BOOTSTRAP;assert.ok(!throughHost,'This provider-metadata fixture supports direct Core protocol only');
if(throughHost){
  const target=path.join(root,'runtime');fs.mkdirSync(target);
  // Copy code/contracts only. Never copy installed credentials, token, journal, or personal config.
  for(const name of fs.readdirSync(runtime).filter(n=>n.endsWith('.cjs')))fs.copyFileSync(path.join(runtime,name),path.join(target,name));
  fs.cpSync(path.join(runtime,'contracts'),path.join(target,'contracts'),{recursive:true});
  fs.mkdirSync(path.join(target,'provider'));fs.copyFileSync(path.join(runtime,'provider/zcode-builtin.json'),path.join(target,'provider/zcode-builtin.json'));
  fs.copyFileSync(throughHost,path.join(target,'bootstrap.cjs'));
  fs.copyFileSync(process.env.TEST_BINDING_MODULE||path.join(runtime,'skill-session-bindings.cjs'),path.join(target,'skill-session-bindings.cjs'));
}
const core=spawn(process.execPath,throughHost?[path.join(root,'runtime/bootstrap.cjs')]:[path.join(runtime,'zcode.cjs'),'app-server'],{cwd:workspace,env:{...process.env,HOME:root,USERPROFILE:root,ZCODE_HOME:path.join(root,'.zcode'),SPIKE_ROOT:root,SPIKE_MODE:'real',SPIKE_HTTP_PORT:'18765',BRIDGE_TOKEN:'isolated-protocol-fixture-token'}});
let sequence=0,buffer='',stderr='',exitInfo=null,hostChildPid=null;const pending=new Map();
core.stderr.on('data',b=>{stderr=(stderr+b).slice(-8000);});
core.on('exit',(code,signal)=>{exitInfo={code,signal};for(const p of pending.values())p.reject(Error('Core exited '+JSON.stringify(exitInfo)));pending.clear();});
core.stdout.on('data',b=>{
  buffer+=b;let end;while((end=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,end);buffer=buffer.slice(end+1);let m;try{m=JSON.parse(line);}catch{continue;}
    if(m.method&&m.id!==undefined){const result=m.method==='interaction/requestPermission'?{decision:'deny'}:m.method==='session/requestRuntimePreferences'?{nativeSearchEnhancementsEnabled:false,memoryEnabled:false,askUserQuestionAutoResolutionEnabled:true}:{};core.stdin.write(JSON.stringify({id:m.id,result})+'\n');}
    else if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);p.resolve(m);}
  }
});
const invoke=(method,params)=>new Promise((resolve,reject)=>{const id='android-host-'+(++sequence);pending.set(id,{resolve,reject});core.stdin.write(JSON.stringify({id,method,params})+'\n');});
function request(route,body){return new Promise((resolve,reject)=>{
  const bytes=body&&Buffer.from(JSON.stringify(body));const req=http.request({host:'127.0.0.1',port:18765,path:route,method:bytes?'POST':'GET',headers:{'X-Bridge-Token':'isolated-protocol-fixture-token',...(bytes?{'Content-Type':'application/json','Content-Length':bytes.length}:{})}},res=>{
    const chunks=[];res.on('data',b=>chunks.push(b));res.on('end',()=>{try{assert.equal(res.statusCode,200);resolve(JSON.parse(Buffer.concat(chunks)));}catch(e){reject(e);}});res.on('error',reject);
  });req.setTimeout(20000,()=>req.destroy(Error('fixture HTTP timeout')));req.on('error',reject);req.end(bytes);
});}
const inventory=path.join(root,'core-skill-inventory.json');
function publish(version){
  const home=path.join(root,'core-skill-packages','binding-fixture'),stage=path.join(root,'stage');fs.mkdirSync(stage);
  fs.writeFileSync(path.join(stage,'SKILL.md'),`---\nname: binding-fixture\ndescription: Protocol-only immutable fixture\nversion: ${version}\n---\nRevision ${version}; no execution.\n`);
  const hash=hashTree(stage),directory=path.join(home,'versions',hash);fs.mkdirSync(path.dirname(directory),{recursive:true});fs.renameSync(stage,directory);
  const previous=fs.existsSync(inventory)?JSON.parse(fs.readFileSync(inventory)).packages[0]?.versions||[]:[];
  const versions=previous.concat({hash,name:'binding-fixture',version,source:'protocol-fixture:'+version,directory,available:true});
  atomicWrite(path.join(home,'package.json'),JSON.stringify({schemaVersion:1,id:'binding-fixture',candidate:hash,enabled:true,removed:false,origins:Object.fromEntries(versions.map(v=>[v.hash,v.source]))}));
  atomicWrite(inventory,JSON.stringify({schemaVersion:1,packages:[{id:'binding-fixture',candidate:hash,enabled:true,removed:false,versions}]}));return directory;
}
async function main(){
  const crypto=require('node:crypto'),sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
  let current=[];const retained=new Map();
  const providerBindings={selected:()=>current,verify:p=>{
    const e=retained.get(p.contentHash);return !!e&&sha(fs.readFileSync(e.file))===p.contentHash&&JSON.stringify(e.pin)===JSON.stringify(p);
  }};
  function publishProvider(version){
    const bytes=Buffer.from('Inert reviewed fixture '+version),contentHash=sha(bytes),file=path.join(root,'fixture-bytes',contentHash);atomicWrite(file,bytes);
    const pin={id:'sample',version,contentHash,definitionHash:sha('host declaration '+version),toolIds:['sample.inspect']};
    retained.set(contentHash,{file,pin:structuredClone(pin)});current=[pin];return pin;
  }
  const options={root,workspace,invoke,timeoutMs:15000,providerBindings};let manager=new SkillSessionBindings(options);
  if(throughHost){
    atomicWrite(inventory,JSON.stringify({schemaVersion:1,packages:[]}));
    let ready=false;for(let i=0;i<100;i++){if(exitInfo)throw Error('Host exited '+JSON.stringify(exitInfo));try{const state=await request('/status');hostChildPid=state.childPid;if(state.phase==='ready'){ready=true;break;}}catch{}await new Promise(resolve=>setTimeout(resolve,100));}assert.ok(ready,'host ready deadline');
  }
  const identity={workspacePath:workspace,workspaceKey:'default'};
  const rpc=async(method,params)=>{const r=throughHost?await request('/rpc-wait',{method,params,timeoutMs:15000}):await manager.dispatch(method,params);assert.equal(r.error,undefined,JSON.stringify(r.error));return r.result;};
  const create=async()=> (await rpc('session/create',{workspace:identity,mode:'build',titleGenerationEnabled:false,dynamicWorkflowEnabled:false,offPeakToolEnabled:false,
    importedHistory:{source:'claudeCode',title:'Synthetic user-only protocol fixture',messages:[{role:'user',content:'Protocol lifecycle fixture only. No model response or tool execution.'}]}})).session.sessionId;
  const catalog=async id=>(await rpc('skills/referenceCatalog',{workspace:identity,sessionId:id})).skills.filter(s=>s.name==='binding-fixture');
  const providerV1=publishProvider('1');const v1=publish('1'),old=await create();assert.deepEqual(manager.providerPin(old,'sample.inspect'),providerV1);assert.equal((await catalog(old))[0].path,path.join(v1,'SKILL.md'));
  const providerV2=publishProvider('2');const v2=publish('2'),newer=await create();assert.deepEqual(manager.providerPin(newer,'sample.inspect'),providerV2);assert.equal((await catalog(newer))[0].path,path.join(v2,'SKILL.md'));assert.equal((await catalog(old))[0].path,path.join(v1,'SKILL.md'));
  await rpc('session/close',{sessionId:old});manager=new SkillSessionBindings(options);await rpc('session/resume',{sessionId:old,workspace:identity,dynamicWorkflowEnabled:false,offPeakToolEnabled:false});
  assert.equal((await catalog(old))[0].path,path.join(v1,'SKILL.md'));
  assert.deepEqual(manager.providerPin(old,'sample.inspect'),providerV1);assert.deepEqual(manager.providerPin(newer,'sample.inspect'),providerV2);
  assert.equal(fs.existsSync(manager.config),false);assert.equal(fs.existsSync(manager.txn),false);
  return {verdict:'PASS',route:throughHost?'actual-bootstrap-http':'direct-module-core',retainedHostFixture:throughHost?root:null,scope:'Actual Core lifecycle and durable host Skill/provider metadata; reconstructed host binding retains v1/v2; explicit inert-file host verifier; no actual provider/catalog/admission/model execution',node:process.version,checks:10};
}
main().finally(async()=>{
  if(hostChildPid)try{process.kill(hostChildPid);}catch(e){if(e.code!=='ESRCH')throw e;}
  core.kill();await new Promise(resolve=>{if(exitInfo)return resolve();core.once('exit',resolve);});
  http.globalAgent.destroy();
  // Keep full isolated Host fixture for inspection (also avoids Windows directory watcher locks).
  if(!throughHost)fs.rmSync(root,{recursive:true,force:true,maxRetries:10,retryDelay:100});
}).then(result=>console.log(JSON.stringify(result))).catch(error=>{console.error(error.stack);console.error(stderr);process.exitCode=1;});
