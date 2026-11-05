// Actual immutable Core lifecycle compatibility. No model/provider tool execution or credentials.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const coreFile=process.env.TEST_CORE;assert.ok(coreFile&&fs.statSync(coreFile).isFile());
async function cycle(){
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'core-eof-')),workspace=path.join(root,'workspace');
 fs.mkdirSync(path.join(root,'.zcode/cli'),{recursive:true});fs.mkdirSync(workspace);fs.mkdirSync(path.join(workspace,'.git'));
 fs.writeFileSync(path.join(root,'.zcode/cli/config.json'),JSON.stringify({features:{memory:false},memory:{extractionEnabled:false},plugins:{enabled:false},hooks:{enabled:false,events:{}}}));
 const child=spawn(process.execPath,[coreFile,'app-server'],{cwd:workspace,env:{...process.env,HOME:root,USERPROFILE:root,ZCODE_HOME:path.join(root,'.zcode'),ZCODE_STORAGE_DIR:root,ZCODE_LOG_DIR:path.join(root,'logs')}});
 let buffer='',stderr='',seq=0,closed=false,exited=false;const pending=new Map();
 const exit=new Promise((resolve,reject)=>{child.once('error',reject);child.once('exit',(code,signal)=>{exited=true;resolve({code,signal});});});
 child.stderr.on('data',b=>{stderr=(stderr+b).slice(-2000);});
 child.stdout.on('data',b=>{buffer+=b;let i;while((i=buffer.indexOf('\n'))>=0){
  let message;try{message=JSON.parse(buffer.slice(0,i));}catch{}buffer=buffer.slice(i+1);if(!message)continue;
  if(message.method&&message.id!==undefined&&!closed){let result={};
   if(message.method==='interaction/requestPermission')result={decision:'deny'};
   if(message.method==='session/requestRuntimePreferences')result={nativeSearchEnhancementsEnabled:false,memoryEnabled:false,askUserQuestionAutoResolutionEnabled:true};
   child.stdin.write(JSON.stringify({id:message.id,result})+'\n');
  }else if(pending.has(message.id)){pending.get(message.id)(message);pending.delete(message.id);}
 }});
 child.stdin.on('error',()=>{});
 const invoke=(method,params)=>new Promise(resolve=>{const id='eof_'+(++seq);pending.set(id,resolve);child.stdin.write(JSON.stringify({id,method,params})+'\n');});
 let timer;
 try{
  const create=await Promise.race([invoke('session/create',{workspace:{workspacePath:workspace,workspaceKey:'default'},mode:'build',titleGenerationEnabled:false,dynamicWorkflowEnabled:false,offPeakToolEnabled:false,
    importedHistory:{source:'claudeCode',title:'EOF protocol fixture',messages:[{role:'user',content:'Protocol fixture only. Do not request a model response.'}]}}),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('create deadline')),15000);})]);
  clearTimeout(timer);assert.equal(create.error,undefined);assert.ok(create.result?.session?.sessionId);
  const start=Date.now();closed=true;child.stdin.end();
  const termination=await Promise.race([exit,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('EOF exit deadline')),5000);})]);
  clearTimeout(timer);assert.equal(termination.signal,null);assert.equal(termination.code,0);
  return {pid:child.pid,sessionId:create.result.session.sessionId,naturalExit:true,...termination,exitAfterEofMs:Date.now()-start};
 }finally{
  clearTimeout(timer);
  // Failure cleanup only; never count a signalled process as a natural EOF PASS.
  if(!exited){child.kill('SIGKILL');await exit;}
  fs.rmSync(root,{recursive:true,force:true});
 }
}
(async()=>{const cycles=[];for(let i=0;i<2;i++)cycles.push(await cycle());console.log(JSON.stringify({verdict:'PASS_ACTUAL_CORE_STDIN_EOF',node:process.version,cycles,scope:'Actual Core user-only session then stdin EOF; no model/active MCP/Android HostService proof'}));})().catch(e=>{console.error(e.stack);process.exitCode=1;});
