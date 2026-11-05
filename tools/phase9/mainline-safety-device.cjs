// Fixture-only Android17 acceptance. No production journal fault injection.
const http=require('node:http'), fs=require('node:fs'), path=require('node:path'), assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const adb=process.env.ANDROID_ADB, serial='DEVICE_ANDROID17', pkg='dev.alita.androidagent';
const token=execFileSync(adb,['-s',serial,'exec-out','run-as',pkg,'cat','files/runtime/bridge-token'],{encoding:'utf8'}).trim();
const sid=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../docs/handoff/evidence/phase9-f1/real-turn.json'))).sessionId;
const delay=ms=>new Promise(r=>setTimeout(r,ms));
let mode='deny', eventsRequest;const checks=[];
function request(method,url,body,signal){return new Promise((resolve,reject)=>{
 const bytes=body?Buffer.from(JSON.stringify(body)):null;
 const req=http.request({host:'127.0.0.1',port:18765,path:url,method,signal,headers:{'X-Bridge-Token':token,
 ...(bytes?{'Content-Type':'application/json','Content-Length':bytes.length}:{})}},res=>{
 let text='';res.on('data',b=>text+=b);res.on('end',()=>{try{resolve({status:res.statusCode,body:JSON.parse(text)});}catch(e){reject(e);}});
 });req.setTimeout(45000,()=>req.destroy(Error('fixture timeout')));req.on('error',reject);req.end(bytes);
});}
const get=async url=>(await request('GET',url)).body;
function events(){eventsRequest=http.get({host:'127.0.0.1',port:18765,path:'/events',headers:{'X-Bridge-Token':token}},res=>{
 let data='';res.on('data',b=>{data+=b;let i;while((i=data.indexOf('\n\n'))>=0){const block=data.slice(0,i);data=data.slice(i+2);
 const line=block.split('\n').find(l=>l.startsWith('data: '));if(!line)continue;const e=JSON.parse(line.slice(6));
 if(e.type==='permission' && mode!=='hold')request('POST','/respond',{requestId:e.requestId,
 decision:mode==='allow' && !e.hardConfirm && e.toolName==='mcp__android-host__ui_scroll'?'allow':'deny'}).catch(()=>{});
 }});});eventsRequest.on('error',()=>{});}
const call=async(toolId,args={},meta={sessionId:sid},signal)=>(await request('POST','/carrier/call',{toolId,arguments:args,meta},signal)).body;
const dump=async()=>{const r=await call('ui_dump');assert.ok(r.ok,JSON.stringify(r));return r.structuredContent;};
const items=d=>(d.snapshot?.nodes||[]).map(n=>n.text).filter(t=>t?.startsWith('longlist-item-')).sort();
const check=(name,ok,evidence)=>{assert.ok(ok,name);checks.push({name,pass:true,evidence});console.log('PASS '+name);};
(async()=>{
 assert.equal((await get('/status')).phase,'ready');await get('/session/resume?id='+encodeURIComponent(sid));events();await delay(400);
 execFileSync(adb,['-s',serial,'shell','su','-c','am start --activity-clear-top -n '+pkg+'/.zcode.runtime.LongListActivity']);await delay(1500);
 const prior=(await get('/gateway/ui?limit=500')).ui_actions;const max=prior[0]?.id||0;
 const before=await dump();assert.ok(items(before).length>=3);
 const denied=await call('ui_scroll',{direction:'forward'});const afterDeny=await dump();
 check('direct scroll denial has no UI mutation',!denied.ok && JSON.stringify(items(before))===JSON.stringify(items(afterDeny)),{error:denied.error});
 const networkBefore=(await get('/gateway/network?limit=500')).network_requests.map(r=>r.id);
 const searchDenied=await call('web_search',{query:'fixture denial must never reach search provider'});
 const networkAfter=(await get('/gateway/network?limit=500')).network_requests.map(r=>r.id);
 check('direct search denial sends no provider request',!searchDenied.ok && searchDenied.error?.code==='GATEWAY_DENIED' && JSON.stringify(networkBefore)===JSON.stringify(networkAfter),{error:searchDenied.error});
 mode='allow';const forward=await call('ui_scroll',{direction:'forward'});await delay(600);const after=await dump();
 const added=items(after).filter(x=>!items(before).includes(x)),gone=items(before).filter(x=>!items(after).includes(x));
 check('forward scroll verified by fresh observation',forward.ok && added.length>0 && gone.length>0,{added:added.length,gone:gone.length});
 const backward=await call('ui_scroll',{direction:'backward'});await delay(600);const back=await dump();
 check('backward scroll verified by fresh observation',backward.ok && items(back)[0]<items(after)[0],{beforeFirst:items(after)[0],afterFirst:items(back)[0]});
 let end, count=0;for(;count<40;count++){end=await call('ui_scroll',{direction:'forward'});if(end.structuredContent?.at_end)break;}
 check('at_end separate from positive scroll',!!end?.structuredContent?.at_end,{scrolls:count+1,error:end?.structuredContent?.error});
 const wrong=await call('ui_scroll',{direction:'forward'},{sessionId:'wrong-session'});
 check('session substitution rejected',wrong.error?.code==='SESSION_MISMATCH',{error:wrong.error});
 const unknown=await call('ui_not_registered');check('unknown tool rejected',unknown.error?.code==='UNKNOWN_TOOL',{error:unknown.error});
 check('legacy selftest disabled',(await request('POST','/ui/selftest',{})).status===403);
 mode='hold';const oldAnswered=(await get('/status')).carrierCounters?.workerCallsAnswered||0;
 const c=new AbortController();const waiting=call('ui_scroll',{direction:'backward'},{sessionId:sid},c.signal).catch(()=>null);
 let pending=false;for(let i=0;i<20;i++){if((await get('/gateway/pending')).pending?.length){pending=true;break;}await delay(100);}
 assert.ok(pending);c.abort();await waiting;await delay(500);
 const cancelled=(await get('/status')).carrierCounters?.workerCallsAnswered||0;
 check('cancelled approval never reaches worker',cancelled===oldAnswered,{before:oldAnswered,after:cancelled});
 const rows=(await get('/gateway/ui?limit=500')).ui_actions.filter(r=>r.id>max);
 const operations=(await get('/gateway/journal?limit=500')).operations;
 check('all completed UI calls have exact committed Gateway operation',rows.length>0 && rows.every(r=>r.op_id && operations.some(o=>o.id===r.op_id && o.decision==='allow' && o.tool===r.tool && o.session===sid)),{uiRows:rows.length});
 fs.writeFileSync(path.resolve(__dirname,'../../docs/handoff/evidence/mainline-safety/device-checks.json'),JSON.stringify({serial,checks},null,2));
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>eventsRequest?.destroy());
