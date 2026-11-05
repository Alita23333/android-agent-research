// Research fixture, never a production host adapter. No model turn or runtime patch.
// Writes exclusively new assigned-app cache/workspace fixture paths; uses existing Core RPC.
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const crypto = require('node:crypto');
const APP = process.argv[2];
if (!['dev.alita.androidagent', 'dev.zcode.nodepoc'].includes(APP)) throw Error('explicit assigned app required');
const root = '/data/user/0/' + APP;
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const coreSha = sha(fs.readFileSync(root + '/files/runtime/zcode.cjs'));
if (coreSha !== 'b1df2ef3e5bd76c4af3ecb296bc003a10d3f13191a26610bd0ba940feadad529') throw Error('Core pin mismatch');
if (process.version !== 'v24.18.0') throw Error('APK-owned Node24.18.0 required');
const token = fs.readFileSync(root + '/files/runtime/bridge-token', 'utf8').trim();
const records = [];
function request(route, body) {
  return new Promise((resolve, reject) => {
    const bytes = body === undefined ? null : Buffer.from(JSON.stringify(body));
    const req = http.request({host:'127.0.0.1',port:8765,path:route,method:bytes?'POST':'GET',headers:{
      'X-Bridge-Token':token,...(bytes?{'Content-Type':'application/json','Content-Length':bytes.length}:{})
    }}, res => {
      const chunks=[];let total=0;
      res.on('data', b => {total+=b.length;if(total>1024*1024)req.destroy(Error('response limit'));else chunks.push(b);});
      res.on('error',reject);
      res.on('end',()=>{try {if(res.statusCode!==200)throw Error('HTTP '+res.statusCode);resolve(JSON.parse(Buffer.concat(chunks)));}catch(e){reject(e);}});
    });
    req.setTimeout(35000,()=>req.destroy(Error('request timeout')));req.on('error',reject);req.end(bytes);
  });
}
async function rpc(method,params) {
  const answer=await request('/rpc-wait',{method,params,timeoutMs:30000});
  records.push({method,params,ok:!answer.error,error:answer.error?{code:answer.error.code,message:answer.error.message}:null});
  if(answer.error)throw Error(method+' error '+answer.error.code+': '+answer.error.message);
  return answer.result;
}
async function main() {
  const status=await request('/status');if(status.phase!=='ready')throw Error('runtime not ready');
  const base=fs.realpathSync(status.workspace);
  if(!base.startsWith(root+'/files/workspaces/'))throw Error('unexpected workspace');
  const globalCfg=root+'/files/.zcode/cli/config.json';const before=fs.readFileSync(globalCfg);
  const cfg=JSON.parse(before);
  if(cfg.plugins?.enabled!==false || cfg.features?.memory!==false || cfg.memory?.extractionEnabled!==false)throw Error('disable pack mismatch');
  const run=Date.now().toString();const workspace=path.join(base,'skill-session-seam-'+run);
  const store=root+'/cache/skill-session-seam-'+run;fs.mkdirSync(workspace);fs.mkdirSync(store);
  fs.mkdirSync(workspace+'/.git');fs.mkdirSync(workspace+'/.zcode');
  const name='immutable-seam-'+run;
  const versions={};const inputs=[];
  for(const revision of ['v1','v2']) {
    const dir=path.join(store,revision);fs.mkdirSync(dir);fs.mkdirSync(dir+'/references');
    const text=`---\nname: ${name}\ndescription: Immutable ${revision} native root fixture only; do not execute.\nversion: ${revision}\n---\nRead references/rule.txt; fixture revision ${revision}.\n`;
    fs.writeFileSync(dir+'/SKILL.md',text,{flag:'wx'});fs.writeFileSync(dir+'/references/rule.txt',revision,{flag:'wx'});
    versions[revision]=dir;
    inputs.push({path:dir+'/SKILL.md',sha256:sha(Buffer.from(text))},{path:dir+'/references/rule.txt',sha256:sha(Buffer.from(revision))});
  }
  function select(revision) {
    const selected={features:{memory:false},memory:{extractionEnabled:false},plugins:{enabled:false},hooks:{enabled:false,events:{}},skills:{enabled:true,roots:[versions[revision]]}};
    const file=workspace+'/.zcode/config.json';const bytes=JSON.stringify(selected,null,2);
    fs.writeFileSync(file+'.tmp',bytes);fs.renameSync(file+'.tmp',file);if(fs.readFileSync(file,'utf8')!==bytes)throw Error('fixture config verification');
  }
  const identity={workspacePath:workspace,workspaceKey:path.basename(workspace)};
  const filtered = c => ({authority:c.authority,skills:c.skills.filter(s=>s.name===name),otherCount:c.skills.filter(s=>s.name!==name).length});
  const catalog=async sessionId=>filtered(await rpc('skills/referenceCatalog',{workspace:identity,...(sessionId?{sessionId}:{})}));
  const create=async()=>{
    // Empty sessions have no durable Core row. Import a clearly synthetic user-only fixture
    // through the supported history schema solely to exercise resume, never to fake a model turn.
    const r=await rpc('session/create',{workspace:identity,mode:'build',titleGenerationEnabled:false,dynamicWorkflowEnabled:false,offPeakToolEnabled:false,toolAllowlist:['Skill','Read'],
      importedHistory:{source:'claudeCode',title:'Protocol-only synthetic root selection fixture',messages:[{role:'user',content:'Synthetic persisted protocol fixture only; no model response or tool execution.'}]}});
    if(!r.session?.sessionId)throw Error('missing session ID');return r.session.sessionId;
  };
  const seen={};const sessions={};
  try {
    select('v1');seen.workspaceV1=await catalog();sessions.old=await create();seen.oldBeforeUpdate=await catalog(sessions.old);
    select('v2');seen.workspaceV2=await catalog();seen.oldAfterUpdate=await catalog(sessions.old);
    sessions.new=await create();seen.newAfterUpdate=await catalog(sessions.new);
    await rpc('session/close',{sessionId:sessions.old});
    await rpc('session/resume',{sessionId:sessions.old,workspace:identity,dynamicWorkflowEnabled:false,offPeakToolEnabled:false,toolAllowlist:['Skill','Read']});
    seen.oldResumedWithCurrentV2=await catalog(sessions.old);
    await rpc('session/close',{sessionId:sessions.old});
    select('v1');
    await rpc('session/resume',{sessionId:sessions.old,workspace:identity,dynamicWorkflowEnabled:false,offPeakToolEnabled:false,toolAllowlist:['Skill','Read']});
    seen.oldResumedWithRestoredV1=await catalog(sessions.old);
  } finally {
    for(const id of Object.values(sessions))try{await rpc('session/close',{sessionId:id});}catch{}
    if(!fs.readFileSync(globalCfg).equals(before))throw Error('global production config changed');
  }
  const isVersion=(c,v)=>c.skills.length===1&&c.skills[0].path===versions[v]+'/SKILL.md';
  const checks={workspaceV1:isVersion(seen.workspaceV1,'v1'),oldInitiallyV1:isVersion(seen.oldBeforeUpdate,'v1'),
    workspaceV2:isVersion(seen.workspaceV2,'v2'),liveOldRemainsV1:isVersion(seen.oldAfterUpdate,'v1'),newUsesV2:isVersion(seen.newAfterUpdate,'v2'),
    resumeRebuildsCurrentV2:isVersion(seen.oldResumedWithCurrentV2,'v2'),restoringConfigRebuildsV1:isVersion(seen.oldResumedWithRestoredV1,'v1'),
    immutableInputsUnchanged:inputs.every(i=>sha(fs.readFileSync(i.path))===i.sha256),globalSafetyConfigUnchanged:fs.readFileSync(globalCfg).equals(before)};
  const pass=Object.values(checks).every(Boolean);
  console.log(JSON.stringify({verdict:pass?'PASS_SOURCE_SEAM_WITH_RESUME_GAP':'UNEXPECTED',scope:'catalog/create/import-fixture/close/resume only; synthetic history is NOT model proof; no Skill activation or production pinning',coreSha256:coreSha,node:process.version,
    workspace,store,versions,skillName:name,sessions,inputs,seen,checks,records},null,2));
  process.exitCode=pass?0:1;
}
main().catch(e=>{console.log(JSON.stringify({verdict:'FAIL',error:e.message,records},null,2));process.exitCode=1;});
