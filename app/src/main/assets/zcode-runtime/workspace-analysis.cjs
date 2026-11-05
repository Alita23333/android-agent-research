// Host script boundary: fixed code + contained input snapshots, never arbitrary
// Shell. Mutations remain exclusively in the existing workspace transactions.
const fs = require('node:fs'), path = require('node:path');
const {spawn} = require('node:child_process');
const {resolveWorkspaceTarget} = require('./gateway.cjs');
const TOOL = {toolId:'workspace_analyze', readOnly:true, supportsCancellation:true,
  description:'Run an APK-owned Node analysis script on explicit workspace-relative files. operation=inventory returns bytes, SHA256 and base64 content; parse_json validates JSON and reports INVALID_JSON with exitCode=3. Read-only snapshot; cannot run arbitrary code or change files. Use workspace_file_* for approved changes. Timeout <=60s; combined output <=64KiB.',
  inputSchema:{type:'object', additionalProperties:false, required:['files','operation'], properties:{
    files:{type:'array', minItems:1,maxItems:16,items:{type:'string'}},
    operation:{type:'string',enum:['inventory','parse_json']},
    timeoutMs:{type:'integer',minimum:100,maximum:60000,default:10000}}}};
function snapshot(args, gateway) {
  if (!args || Array.isArray(args) || Object.keys(args).some(k=>!['files','operation','timeoutMs'].includes(k)) ||
      !['inventory','parse_json'].includes(args.operation) || !Array.isArray(args.files) ||
      args.files.length < 1 || args.files.length > 16 || new Set(args.files).size !== args.files.length ||
      (args.timeoutMs !== undefined && (!Number.isInteger(args.timeoutMs) || args.timeoutMs < 100 || args.timeoutMs > 60000)))
    throw Error('INVALID_ARGUMENTS');
  let bytes=0;
  return {operation:args.operation, files:args.files.map(rel=>{
    if (typeof rel !== 'string' || rel.split('/').includes('..')) throw Error('PATH_REJECTED');
    const target=resolveWorkspaceTarget(gateway.rootReal,rel,{reservedRoots:[gateway.storeRoot]});
    if (!target.ok || !target.exists) throw Error(target.code || 'FILE_NOT_FOUND');
    const fd=fs.openSync(target.abs,fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
    try {
      const st=fs.fstatSync(fd), lst=fs.lstatSync(target.abs);
      if (!st.isFile() || st.dev!==lst.dev || st.ino!==lst.ino || fs.realpathSync(target.abs)!==target.abs)
        throw Error('PATH_CHANGED');
      if (['android','linux'].includes(process.platform) && fs.readlinkSync('/proc/self/fd/'+fd)!==target.abs)
        throw Error('PATH_CHANGED');
      if (st.size>32768 || (bytes+=st.size)>32768) throw Error('INPUT_TOO_LARGE');
      const data=Buffer.alloc(st.size);let read=0;
      while(read<data.length) {const n=fs.readSync(fd,data,read,data.length-read,null);if(!n)throw Error('INPUT_CHANGED');read+=n;}
      const after=fs.fstatSync(fd);
      if (after.size!==st.size || after.mtimeMs!==st.mtimeMs || after.ctimeMs!==st.ctimeMs) throw Error('INPUT_CHANGED');
      return {path:target.rel,content:data.toString('base64')};
    } finally {fs.closeSync(fd);}
  })};
}
// Reusable bounded process mechanism; executable/argv/env are host-owned only.
function runProcess({executable,args,cwd,env,input,signal,timeoutMs=10000,maxOutput=65536}) {
  return new Promise(resolve=>{
    if (signal?.aborted) return resolve({code:'CANCELLED',exitCode:null,stdout:'',stderr:''});
    const child=spawn(executable,args,{cwd,env,detached:process.platform!=='win32',stdio:['pipe','pipe','pipe']});
    let output=[],errors=[],captured=0,received=0,reason=null,killTimer,timer;
    function terminate(code) {
      reason=reason || code;
      function send(sig) {
        try {
          if(process.platform==='win32') child.kill(sig);
          else if(child.pid>1) process.kill(-child.pid,sig);
        } catch(e) {if(e.code!=='ESRCH') child.kill(sig);}
      }
      send('SIGTERM');if(!killTimer)killTimer=setTimeout(()=>send('SIGKILL'),200);
    }
    const abort=()=>terminate('CANCELLED');
    signal?.addEventListener('abort',abort,{once:true});
    child.stdin.on('error',()=>{});
    function capture(list,chunk) {
      received+=chunk.length;const remaining=maxOutput-captured;
      if(remaining>0){const b=chunk.subarray(0,remaining);list.push(b);captured+=b.length;}
      if(received>maxOutput)terminate('OUTPUT_LIMIT');
    }
    child.stdout.on('data',chunk=>capture(output,chunk));child.stderr.on('data',chunk=>capture(errors,chunk));
    child.once('error',()=>{reason='PROCESS_START_FAILED';});
    child.once('close',(exitCode,exitSignal)=>{
      // A leader may exit while descendants close inherited pipes or ignore
      // TERM. Complete termination of our spawned group before dropping the
      // escalation timer. Caller code can never choose the group identifier.
      if(reason && process.platform!=='win32' && child.pid>1) {
        try {process.kill(-child.pid,'SIGKILL');} catch(e) {if(e.code!=='ESRCH')reason='PROCESS_CLEANUP_FAILED';}
      }
      clearTimeout(timer);clearTimeout(killTimer);signal?.removeEventListener('abort',abort);
      resolve({code:reason,exitCode,exitSignal,stdout:Buffer.concat(output).toString('utf8'),
        stderr:Buffer.concat(errors).toString('utf8'),receivedBytes:received,truncated:received>maxOutput});
    });
    timer=setTimeout(()=>terminate('TIMEOUT'),timeoutMs);
    if(signal?.aborted)abort();else child.stdin.end(input);
  });
}
async function executeAnalysis(call, gateway, admission) {
  const args=call.arguments || {},session=call.meta?.sessionId;
  if (!admission.matches(call.approvalOpId,TOOL.toolId,args,session))
    return {ok:false,error:{code:'GATEWAY_INTENT_UNBOUND'}};
  let result;
  try {
    if(call.cancelSignal?.aborted)throw Error('CANCELLED');
    const input=snapshot(args,gateway);
    const env={PATH:'/system/bin',OPENSSL_CONF:'/dev/null',LD_LIBRARY_PATH:process.env.LD_LIBRARY_PATH || ''};
    const processResult=await runProcess({executable:process.execPath,
      args:[path.join(__dirname,'analysis-worker.cjs')],cwd:gateway.rootReal,env,
      input:JSON.stringify(input),signal:call.cancelSignal,timeoutMs:args.timeoutMs || 10000});
    let data=null;
    if(!processResult.code) {try{data=JSON.parse(processResult.stdout);}catch{processResult.code='SCRIPT_RESULT_INVALID';}}
    const ok=!processResult.code && processResult.exitCode===0 && data?.ok===true;
    result={ok,structuredContent:{...data,execution:{runtime:process.version,script:'analysis-worker-v1',
      cwd:gateway.rootReal,exitCode:processResult.exitCode,exitSignal:processResult.exitSignal,
      stderr:processResult.stderr,receivedBytes:processResult.receivedBytes,truncated:processResult.truncated}},
      ...(ok?{}:{error:{code:processResult.code || (processResult.exitCode===3?'INVALID_JSON':'SCRIPT_FAILED')}})};
  } catch(e) {result={ok:false,error:{code:e.message}};}
  // Finish only the exact precommitted operation; never invent another schema.
  gateway.db.prepare("update operation set result=?, detail=coalesce(detail || ' ', '') || ? where id=? and result is null")
    .run(result.ok?'ok':result.error?.code || 'error','workspace_analyze execution finished',call.approvalOpId);
  return {...result,text:JSON.stringify(result.structuredContent || result)};
}
module.exports={TOOL,snapshot,runProcess,executeAnalysis};
