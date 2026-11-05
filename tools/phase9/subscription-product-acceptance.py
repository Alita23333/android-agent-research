"""Actual Android17 product bridge subscription fix, preserving model/provider boundaries."""
from pathlib import Path
import argparse,base64,hashlib,json,os,re,shutil,subprocess,threading,time,urllib.request,xml.etree.ElementTree as ET,zipfile
ROOT=Path(__file__).resolve().parents[2];APP='dev.alita.androidagent';BASELINE='1FF91047068AF96339F2E451016C593DE28FDD360D3325B351D0A24B9966B8F9'
p=argparse.ArgumentParser();p.add_argument('stage',choices=['baseline','install','accept','cancel']);p.add_argument('--run');args=p.parse_args()
RUN=args.run or str(time.time_ns());assert RUN.isdigit() and (args.run or args.stage=='baseline')
BASE=ROOT/'docs/handoff/evidence/subscription1'/RUN;BASE.mkdir(exist_ok=True)
OUT=BASE/(args.stage+'-'+str(time.time_ns()));OUT.mkdir();shutil.copyfile(__file__,OUT/'driver.py')
statefile=BASE/'state.json';state=json.loads(statefile.read_text('utf-8')) if statefile.exists() else dict(run=RUN)
records=[];events=[];requests=[];token='';secrets=[];allowed=None;stream=None;thread=None;closed=threading.Event()
lock=BASE/'device.lock';locked=False
def clean(s):
 for secret in [token,*secrets]:
  if secret:s=s.replace(secret,'[redacted]')
 return s
def save(n,v):(OUT/n).write_text(clean(json.dumps(v,ensure_ascii=False,indent=2))+'\n',encoding='utf-8')
def checkpoint():statefile.write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
def adb(*a,private=False):
 r=subprocess.run([os.environ['ANDROID_ADB'],'-s','DEVICE_ANDROID17',*a],capture_output=True,timeout=90)
 if not private:records.append(dict(argv=list(a),exit=r.returncode,stdout=clean(r.stdout.decode('utf-8','replace')),stderr=clean(r.stderr.decode('utf-8','replace'))));save('commands.json',records)
 assert r.returncode==0,'See retained command failure'
 return r.stdout
def read(n,private=False):return adb('exec-out','run-as',APP,'cat',n,private=private)
def get(route,body=None,timeout=30):
 req=urllib.request.Request('http://127.0.0.1:18765'+route,data=None if body is None else json.dumps(body).encode(),headers={'X-Bridge-Token':token,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
def rpc(method,params):
 requests.append(dict(method=method,params=params));save('requests.json',requests)
 result=get('/rpc-wait',dict(method=method,params=params,timeoutMs=20000));assert not result.get('error'),str(result.get('error'));return result['result']
def snapshot(label):
 remote='/data/local/tmp/subscription-'+RUN+'.xml';adb('shell','uiautomator','dump',remote);raw=adb('exec-out','cat',remote);(OUT/(label+'.xml')).write_text(clean(raw.decode()),encoding='utf-8');return ET.fromstring(raw)
def tap(node):
 l,t,r,b=map(int,re.findall(r'\d+',node.attrib['bounds']));adb('shell','input','tap',str((l+r)//2),str((t+b)//2));time.sleep(.5)
def text(tree,value):return next(n for n in tree.iter('node') if n.get('text')==value)
def launch():
 global token
 adb('forward','tcp:18765','tcp:8765');adb('shell','am','start','-W','--activity-clear-top','-n',APP+'/.MainActivity')
 for i in range(5):
  time.sleep(.5);tree=snapshot('launch-'+str(i))
  if any(n.get('text')=='打开 Agent' for n in tree.iter('node')):break
  if any(n.get('text')=='任务' for n in tree.iter('node')):tap(text(tree,'任务'))
  else:adb('shell','am','start','-W','--activity-clear-top','-n',APP+'/.MainActivity')
 else:raise AssertionError('Product home not observed')
 tap(text(tree,'打开 Agent'));deadline=time.monotonic()+60
 while time.monotonic()<deadline:
  try:
   token=read('files/runtime/bridge-token',True).decode().strip();s=get('/status',timeout=2)
   if s['phase']=='ready':save('ready-'+str(len(records))+'.json',s);return s
  except (OSError,ValueError,KeyError):pass
  time.sleep(.5)
 raise AssertionError('Runtime ready deadline')
def begin_events():
 global stream,thread
 closed.clear();req=urllib.request.Request('http://127.0.0.1:18765/events',headers={'X-Bridge-Token':token});stream=urllib.request.urlopen(req,timeout=150)
 def consume():
  try:
   while not closed.is_set():
    line=stream.readline()
    if not line:break
    if not line.startswith(b'data:'):continue
    e=json.loads(line[5:]);events.append(e)
    if e.get('type')=='permission':
     grant=allowed is not None and not e.get('hardConfirm') and e.get('toolName')=='mcp__android-host__'+state['wire'] and e.get('input')==allowed
     answer=get('/respond',dict(requestId=e['requestId'],decision='allow' if grant else 'deny'));events.append(dict(type='test-permission-answer',requestId=e['requestId'],granted=grant,result=answer))
  except Exception as err:
   if not closed.is_set():events.append(dict(type='test-stream-error',message=clean(str(err))))
 thread=threading.Thread(target=consume,daemon=True);thread.start()
def end_events():
 closed.set()
 if stream:
  try:stream.fp.raw._sock.shutdown(2)
  except (OSError,AttributeError):pass
 if thread:thread.join(3)
 if stream:stream.close()
 save('events.json',events)
def messages(sid):return get('/session/read?id='+sid)['snapshot']['messages']
def create(user_only=False):
 options=dict(workspace=state['workspace'],mode='build',thoughtLevel='disabled',titleGenerationEnabled=False,dynamicWorkflowEnabled=False,offPeakToolEnabled=False)
 if user_only:options['importedHistory']=dict(source='claudeCode',title='Subscription fixture',messages=[dict(role='user',content='Protocol-only; do not request any model response.')])
 else:options['model']={**state['selection'],'options':dict(reasoningLevel='disabled')}
 return rpc('session/create',options)['session']['sessionId']
def subscription_results(sid,start=0):
 return [e['message']['result'] for e in events[start:] if isinstance(e.get('message',{}).get('result'),dict) and e['message']['result'].get('sessionId')==sid and isinstance(e['message']['result'].get('events'),list) and isinstance(e['message']['result'].get('eventSeq'),int)]
def model_turn(sid,label):
 global allowed
 raw=('subscription-model-'+RUN+'-'+label).encode();allowed=dict(base64=base64.b64encode(raw).decode());prior=messages(sid);start=len(events)
 rpc('session/send',dict(sessionId=sid,content='Use ONLY mcp__android-host__'+state['wire']+' once with exactly '+json.dumps(allowed)+'. Report the actual checksum and returned artifact. No other tools. End with SUBSCRIPTION_MODEL_OK after the result.'))
 deadline=time.monotonic()+120
 while time.monotonic()<deadline:
  all_messages=messages(sid);fresh=all_messages[len(prior):]
  if any(m.get('info',{}).get('role')=='assistant' and m.get('info',{}).get('finish')=='stop' for m in fresh):break
  time.sleep(.5)
 else:save(label+'-incomplete.json',all_messages);raise AssertionError('Model deadline')
 parts=[p for m in fresh for p in m.get('parts',[])];tools=[p for p in parts if p.get('type')=='tool']
 save(label+'-messages.json',all_messages)
 assert len(tools)==1 and tools[0]['tool']=='mcp__android-host__'+state['wire'] and tools[0]['state']['input']==allowed and tools[0]['state']['status']=='completed'
 result=json.loads(tools[0]['state']['output'].split('Structured content:\n',1)[1]);data=result['data']
 assert data['sha256']==hashlib.sha256(raw).hexdigest() and data['version']=='v2' and data['bytes']==len(raw)
 assert data['_hostProvider']['contentHash']==state['pin']['contentHash'] and data['_hostProvider']['definitionHash']==state['pin']['definitionHash']
 artifact=result['artifacts'][0];physical=read(artifact['uri']);report=json.loads(physical)
 assert report['data']==data and len(physical)==artifact['size'];(OUT/(label+'-artifact.json')).write_bytes(physical)
 ops=[r for r in get('/gateway/journal?limit=100')['operations'] if r['session']==sid and 'call_id='+report['callId']+' ' in (r.get('detail') or '')]
 assert len(ops)==1 and ops[0]['result']=='ok' and json.loads(ops[0]['args'])==allowed
 legacy=[e for e in events[start:] if e.get('message',{}).get('method')=='session/event' and e['message'].get('params',{}).get('sessionId')==sid]
 assert legacy,'Actual subscribed session/event notifications required'
 chunks=[e for e in events[start:] if e.get('message',{}).get('params',{}).get('kind')=='stream.chunk'];assert len(chunks)>1
 assert any(p.get('type')=='text' and 'SUBSCRIPTION_MODEL_OK' in p.get('text','') for p in parts)
 save(label+'-verified.json',dict(sessionId=sid,operation=ops[0],artifact=artifact,artifactSha256=hashlib.sha256(physical).hexdigest(),legacyEvents=len(legacy),legacyTypes=sorted({e['message']['params'].get('type','') for e in legacy}),streamChunks=len(chunks),data=data))
 return all_messages
def main():
 global locked,allowed
 fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd);locked=True
 assert adb('shell','getprop','ro.build.version.release').strip()==b'17'
 assert adb('shell','getprop','ro.product.model').strip()==b'MODEL_ANDROID17'
 apk=adb('shell','pm','path',APP).decode().strip().removeprefix('package:');installed=adb('shell','run-as',APP,'sha256sum',apk).decode().split()[0].upper()
 if args.stage=='install':
  assert installed==BASELINE
  candidate=ROOT/'app/build/outputs/apk/debug/app-debug.apk'
  shutil.copyfile(candidate,BASE/'candidate.apk');state['apkSha256']=hashlib.sha256(candidate.read_bytes()).hexdigest().upper();checkpoint()
  with zipfile.ZipFile(candidate) as z:
   for line in z.read('assets/zcode-runtime/payload-SHA256SUMS.txt').decode().splitlines():
    h,name=line.split(maxsplit=1);assert hashlib.sha256(z.read(name.replace('jniLibs/','lib/',1) if name.startswith('jniLibs/') else name)).hexdigest()==h
  adb('install','-r',str(BASE/'candidate.apk'));launch();state['installed']=True;checkpoint();save('result.json',dict(verdict='PASS_PINNED_INSTALL',apk=state['apkSha256']));return
 assert installed==(BASELINE if args.stage=='baseline' else state['apkSha256'])
 s=launch();state['workspace']=dict(workspacePath=s['workspace'],workspaceKey='default')
 config=json.loads(read('files/runtime/provider/personal_provider_config.json',True))
 for provider in config['config']['providerConfigRules']['providerRules']:secrets.append(provider['config']['access']['apiKey'])
 model=config['config']['modelConfigRules']['manualProviderModelRules'][0];state['selection']={k:model[k] for k in ['providerId','modelId']}
 pin=next(p for p in json.loads(read('files/provider-reviews.json'))['selected'] if p['id']=='aa_model_1792764185483531200')
 state['pin']=pin;state['wire']=pin['toolIds'][0].replace('.','_');checkpoint();begin_events()
 sid=create(user_only=True);state['protocolSession']=sid;checkpoint()
 for _ in range(3):messages(sid)
 time.sleep(.3)
 if args.stage=='baseline':
  errors=[e for e in events if 'deliveryKind' in str(e.get('message',{}).get('error',{}))]
  assert errors and not subscription_results(sid);save('result.json',dict(verdict='REPRODUCED_MISSING_DELIVERY_KIND',errors=len(errors),sessionId=sid,apk=installed));return
 assert subscription_results(sid),'Automatic production bridge subscription must succeed'
 if args.stage=='cancel':
  target=create();allowed=dict(base64=base64.b64encode(('WAIT:subscription-'+RUN).encode()).decode());start=len(events)
  rpc('session/send',dict(sessionId=target,content='Use ONLY mcp__android-host__'+state['wire']+' once with exactly '+json.dumps(allowed)+'. Wait for the actual result. No other tools.'))
  deadline=time.monotonic()+90;call=None
  while time.monotonic()<deadline:
   calls=[e for e in events[start:] if e.get('type')=='carrier-call' and e.get('toolId')==state['wire']]
   if calls:call=calls[0];break
   time.sleep(.1)
  assert call,'Need actual model carrier call before cancellation'
  physical=[]
  for _ in range(50):
   ps=adb('shell','ps','-A','-o','UID,PID,PPID,NAME,ARGS').decode();physical=[l.split() for l in ps.splitlines() if APP+':provider' in l]
   if physical:break
   time.sleep(.1)
  assert len(physical)==1;pid=physical[0][1];owner=adb('shell','run-as',APP,'id','-u').decode().strip();assert physical[0][0]!=owner
  save('live-isolated-process.json',physical[0]);started=time.monotonic();rpc('session/stop',dict(sessionId=target))
  deadline=time.monotonic()+10
  while time.monotonic()<deadline:
   ps=adb('shell','ps','-A','-o','UID,PID,PPID,NAME,ARGS').decode()
   if not any(len(l.split())>1 and l.split()[1]==pid for l in ps.splitlines()[1:]):break
   time.sleep(.1)
  else:raise AssertionError('Cancelled provider process still alive')
  elapsed=round((time.monotonic()-started)*1000);time.sleep(.5)
  ops=[r for r in get('/gateway/journal?limit=100')['operations'] if r['session']==target and r['tool']=='mcp__android-host__'+state['wire']]
  assert len(ops)==1 and ops[0]['result']=='CANCELLED' and json.loads(ops[0]['args'])==allowed
  assert 'call_id='+call['callId']+' ' in ops[0]['detail'] and 'provider_sha256='+pin['contentHash'] in ops[0]['detail'] and 'declaration_sha256='+pin['definitionHash'] in ops[0]['detail']
  saved=messages(target);save('cancel-messages.json',saved)
  assert any('cancel' in str(x.get('state',{}).get('error','')).lower() for m in saved for x in m.get('parts',[]) if x.get('type')=='tool')
  assert not any('deliveryKind' in str(e.get('message',{}).get('error',{})) for e in events)
  save('result.json',dict(verdict='PASS_SUBSCRIBED_MODEL_CANCELLATION',apk=state['apkSha256'],sessionId=target,call=call,operation=ops[0],isolatedPid=int(pid),pidGone=True,exitAfterStopMs=elapsed));return
 target=create();state['modelSession']=target;checkpoint();model_turn(target,'first')
 before=get('/status');old=messages(target);adb('shell','input','keyevent','HOME');after=launch();assert after['startedAt']==before['startedAt'] and messages(target)==old
 save('reconnect.json',dict(sameRuntime=True,fullMessagesEqual=True))
 end_events();adb('shell','am','force-stop',APP);launch();begin_events()
 rpc('session/resume',dict(sessionId=target,workspace=state['workspace'],dynamicWorkflowEnabled=False,offPeakToolEnabled=False));restored=messages(target)
 assert old==restored;save('before-restart.json',old);save('after-restart.json',restored)
 model_turn(target,'resumed')
 time.sleep(.3);errors=[e for e in events if 'deliveryKind' in str(e.get('message',{}).get('error',{}))];assert not errors
 assert subscription_results(target)
 legacy=[e for e in events if e.get('message',{}).get('method')=='session/event']
 save('result.json',dict(verdict='PASS_PRODUCT_SUBSCRIPTION_STREAM_RECONNECT_RESUME',apk=state['apkSha256'],protocolSession=sid,modelSession=target,
   automaticSubscribeReplies=sum(isinstance(e.get('message',{}).get('result'),dict) and 'eventSeq' in e['message']['result'] and 'events' in e['message']['result'] for e in events),
   legacyEvents=len(legacy),deliveryKindErrors=0,scope='Actual continuous Core owner bridge subscription; Activity uses SSE. No browser replay/cursor guarantee. Two real model/provider/artifact turns.'))
 state['accepted']=str(OUT.relative_to(ROOT));checkpoint()
try:main()
except BaseException as error:save('failure.json',dict(type=type(error).__name__,message=clean(str(error))));print('FAIL '+str(OUT));raise
finally:
 end_events()
 if locked:lock.unlink()
print(json.dumps(dict(evidence=str(OUT),run=RUN)))
