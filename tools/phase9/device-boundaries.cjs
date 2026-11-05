// Fixture-only tests on the receiving-product phone. Never approve a hard confirmation.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const {execFileSync}=require('node:child_process');
const adb=process.env.ANDROID_ADB || 'C:\\Android\\Sdk\\platform-tools\\adb.exe';
const serial='DEVICE_ANDROID17', pkg='dev.alita.androidagent';
const token=execFileSync(adb,['-s',serial,'exec-out','run-as',pkg,'cat','files/runtime/bridge-token'],{encoding:'utf8'}).trim();
const permissions=[], checks=[]; let sse;
const delay=ms=>new Promise(r=>setTimeout(r,ms));
function request(method,url,body){return new Promise((resolve,reject)=>{
  const data=body ? JSON.stringify(body) : null;
  const req=http.request({host:'127.0.0.1',port:18765,path:url,method,headers:{'X-Bridge-Token':token,
    ...(data?{'Content-Type':'application/json','Content-Length':Buffer.byteLength(data)}:{})}},res=>{
    let text='';res.on('data',b=>text+=b);res.on('end',()=>{try{resolve(JSON.parse(text))}catch(e){reject(e)}});
  });req.setTimeout(45000,()=>req.destroy(Error('fixture timeout')));req.on('error',reject);req.end(data);
})}
function openEvents(){
  sse=http.request({host:'127.0.0.1',port:18765,path:'/events',headers:{'X-Bridge-Token':token}},res=>{
    let text='';res.on('data',b=>{text+=b;let i;while((i=text.indexOf('\n\n'))>=0){const block=text.slice(0,i);text=text.slice(i+2);
      const data=block.split('\n').find(x=>x.startsWith('data: '));if(!data)continue;
      const event=JSON.parse(data.slice(6));if(event.type==='permission'){
        permissions.push({tool:event.toolName,risk:event.risk,hardConfirm:!!event.hardConfirm});
        const allowed=!event.hardConfirm && String(event.toolName).startsWith('mcp__android-host__ui_');
        request('POST','/respond',{requestId:event.requestId,decision:allowed?'allow':'deny'}).catch(e=>console.error(e.message));
      }
    }});
  });sse.on('error',e=>console.error('SSE:',e.message));sse.end();
}
function launch(extra=[]){execFileSync(adb,['-s',serial,'shell','am','start','--activity-clear-top','-n',pkg+'/.zcode.runtime.UiLabActivity',...extra]);}
let sessionId;
const call=async(toolId,args={})=>request('POST','/carrier/call',{toolId,arguments:args,meta:{sessionId}});
const content=r=>r.structuredContent || r;
const check=(name,condition,evidence)=>{assert.ok(condition,name+' '+JSON.stringify(evidence));checks.push({name,pass:true,evidence});};
const node=(dump,text)=>dump.snapshot.nodes.find(n=>(n.text || '').toLowerCase().includes(text.toLowerCase()));
async function main(){
  let ready=false;
  for (let i=0;i<50;i++){try{ready=(await request('GET','/status')).phase==='ready'}catch{}
    if(ready)break;await delay(400);}
  assert.ok(ready,'runtime ready');
  openEvents(); await delay(300);
  const priorUi=await request('GET','/gateway/ui?limit=500');
  const priorIds=new Set(priorUi.ui_actions.map(x=>x.id));
  const prior=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../docs/handoff/evidence/phase9/real-turn.json')));
  sessionId=prior.sessionId;
  const resumed=await request('GET','/session/resume?id='+encodeURIComponent(sessionId));
  assert.ok(!resumed.error,'real session resume');
  const status=await request('GET','/vision/status');check('explicit real provider configured',status.configured,status);
  launch(); await delay(1200);
  const dump=content(await call('ui_dump'));
  assert.equal(dump.ok,true,JSON.stringify(dump));
  const button=node(dump,'INCREMENT');assert.ok(button);
  const [l,t,r,b]=button.bounds,x=Math.floor((l+r)/2),y=Math.floor((t+b)/2);
  const first=content(await call('ui_screenshot'));
  check('physical screenshot metadata and compressed budget',first.ok && first.bytes<=153600 && /^shot_[a-f0-9]{32}$/.test(first.shotId),
    {shotId:first.shotId,bytes:first.bytes,width:first.width,height:first.height,screenW:first.screenW,screenH:first.screenH});
  const roi=[Math.floor(l/first.screenW*1000),Math.floor(t/first.screenH*1000),Math.ceil(r/first.screenW*1000),Math.ceil(b/first.screenH*1000)];
  const gate=content(await call('ui_see',{question:'Locate Increment',region:roi,shotId:first.shotId}));
  check('a11y-first refuses an addressable region',gate.error?.code==='ui_vision_not_needed',gate.error);
  const tapped=content(await call('ui_tap',{x,y,shotId:first.shotId,label:'Increment'}));
  check('coordinate gesture produces verified count=1',tapped.ok && tapped.verified && node(tapped,'count=1'),{verified:tapped.verified});
  const stale=content(await call('ui_tap',{x,y,shotId:first.shotId,label:'Increment'}));
  check('changed generation rejects old frame without a second increment',stale.error?.code==='ui_stale_shot',stale.error);
  check('physical counter remains one',!!node(content(await call('ui_dump')),'count=1'));
  const outside=content(await call('ui_tap',{x:999999,y,label:'fixture'}));
  check('display containment rejects coordinates',outside.error?.code==='ui_coordinate_out_of_bounds',outside.error);
  await delay(400); const second=content(await call('ui_screenshot'));
  await delay(400); const third=content(await call('ui_screenshot'));
  const rows=JSON.parse(execFileSync(adb,['-s',serial,'exec-out','run-as',pkg,'cat','files/runtime/vision/shots/index.json'],{encoding:'utf8'}));
  check('live store retains only two unique frames',rows.length===2 && rows.every(x=>x.shotId!==first.shotId) && second.shotId!==third.shotId,rows.map(x=>x.shotId));
  const visionArgs={question:'Read the visible counter value and the main button label.',shotId:third.shotId,force:true};
  const seen=content(await call('ui_see',visionArgs));
  check('real image provider sees current physical fixture',seen.ok && /count\s*=\s*1/i.test(seen.text) && /increment/i.test(seen.text),{model:seen.model,text:seen.text});
  const netBefore=await request('GET','/gateway/network?limit=500');
  const cached=content(await call('ui_see',visionArgs));
  const netAfter=await request('GET','/gateway/network?limit=500');
  check('repeated live interpretation uses cache without more network',cached.ok && netAfter.network_requests.length===netBefore.network_requests.length);
  const network=netAfter.network_requests.filter(row=>row.source==='ui.vision');
  check('vision has committed started and completed network audit',network.some(x=>x.result_code==='started') && network.some(x=>x.result_code==='ok'),
    network.slice(-2).map(x=>({id:x.id,host:x.host,result_code:x.result_code,status:x.status})));
  const longPress=content(await call('ui_tap',{x,y,shotId:third.shotId,label:'Increment',longPress:true}));
  check('long-press verified against physical state',longPress.ok && !!node(longPress,'long_press=1'));
  launch(['--ez','secure','true']);await delay(1200);
  const secure=content(await call('ui_screenshot'));
  check('FLAG_SECURE capture refused',secure.error?.code==='ui_screenshot_secure_window',secure.error);
  launch(['--ez','black','true']);await delay(1200);
  const black=content(await call('ui_screenshot'));
  check('all-black frame refused before storage/egress',black.error?.code==='ui_screenshot_secure_window',black.error);
  launch(['--ez','criticalFixture','true']);await delay(1200);
  const criticalDump=content(await call('ui_dump')), critical=node(criticalDump,'Factory Reset');assert.ok(critical);
  const bounds=critical.bounds;
  const denied=content(await call('ui_tap',{x:Math.floor((bounds[0]+bounds[2])/2),y:Math.floor((bounds[1]+bounds[3])/2),label:'benign'}));
  check('actual target label escalates despite benign model label',denied.error?.code==='GATEWAY_DENIED' && permissions.some(p=>p.hardConfirm),denied.error);
  check('denied critical fixture has no mutation',!node(content(await call('ui_dump')),'critical_clicked=1'));
  const journal=await request('GET','/gateway/ui?limit=100');
  const actions=journal.ui_actions.filter(row=>!priorIds.has(row.id) && (row.action==='tap' || row.action==='screenshot'));
  check('new physical actions have bound Gateway operation ids',actions.length>0 && actions.every(row=>row.op_id!=null),actions.map(row=>({call_id:row.call_id,op_id:row.op_id,action:row.action,result:row.result})));
  launch(); await delay(1200);
  const noChange=content(await call('ui_tap',{x:1100,y:1800,label:'blank fixture area',timeoutMs:400}));
  check('unobservable gesture is unverified and never retried',noChange.ok===false && noChange.performed===true && noChange.verified===false && noChange.retries===0 && noChange.error?.code==='ui_not_verified',noChange.error);
  const found=content(await call('ui_find',{text:'Increment'}));
  check('legacy ui_find resolves current fixture',found.ok && found.matches?.length>0);
  const clicked=content(await call('ui_click',{text:'Increment'}));
  check('legacy ui_click normalized/raw mapping changes physical counter',clicked.ok && clicked.verified && node(clicked,'count=1'));
  const typed=content(await call('ui_type',{role:'Edit',text:'phase9-fixture'}));
  check('legacy ui_type reads back fixture text',typed.ok && typed.verified && typed.observed==='phase9-fixture',typed);
  const waited=content(await call('ui_wait',{wait_for:'text_appear',text:'echo:phase9-fixture',timeoutMs:1000}));
  check('legacy ui_wait observes fixture echo',waited.ok && waited.matched);
  const longClicked=content(await call('ui_long_press',{text:'Increment'}));
  check('legacy ui_long_press observes physical long-click',longClicked.ok && longClicked.verified && node(longClicked,'long_press=1'));
  const scrolled=content(await call('ui_scroll',{direction:'forward'}));
  check('legacy ui_scroll honestly reports non-scrollable fixture end',scrolled.ok && scrolled.at_end===true);
  const back=content(await call('ui_back'));
  check('legacy ui_back dispatched once',back.performed===true);
  launch(); await delay(1200);
  const editDump=content(await call('ui_dump'));
  const edit=editDump.snapshot.nodes.find(n=>n.editable); assert.ok(edit);
  await call('ui_click',{treeId:editDump.treeId,nodeId:'#'+edit.id}); await delay(1200);
  const imeShot=content(await call('ui_screenshot'));
  check('visible keyboard refuses window-only screenshot',imeShot.error?.code==='ui_screenshot_ime_visible',imeShot.error);
  const imeTap=content(await call('ui_tap',{x:600,y:265,label:'Increment'}));
  check('visible keyboard refuses ambiguous coordinate action',imeTap.error?.code==='ui_ime_visible',imeTap.error);
  await call('ui_back'); await delay(1200);
  const live=content(await call('ui_screenshot')); assert.ok(live.ok,JSON.stringify(live));
  await request('POST','/rpc',{id:19991,method:'session/stop',params:{sessionId}}); await delay(300);
  const listing=execFileSync(adb,['-s',serial,'exec-out','run-as',pkg,'ls','files/runtime/vision/shots'],{encoding:'utf8'});
  check('session stop purges all live screen files',listing.trim()==='');
  await request('GET','/session/resume?id='+encodeURIComponent(sessionId));
  const oldFrame=content(await call('ui_tap',{x:600,y:265,shotId:live.shotId,label:'Increment'}));
  check('stopped-session frame cannot be replayed',oldFrame.error?.code==='ui_stale_shot',oldFrame.error);
  console.log(JSON.stringify({serial,sessionId,checks,permissions},null,2));
}
main().catch(e=>{console.error(e.stack);console.log(JSON.stringify({serial,checks,permissions},null,2));process.exitCode=1}).finally(()=>sse?.destroy());
