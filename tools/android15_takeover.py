"""Explicit product takeover and acceptance. Android15 main; Android17 is read-only credential source."""
from pathlib import Path
import argparse,base64,hashlib,json,os,re,shutil,subprocess,threading,time,urllib.request,xml.etree.ElementTree as ET,zipfile
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('stage');parser.add_argument('--run');parser.add_argument('--target',default='android15-main');parser.add_argument('--revision',default='v1');args=parser.parse_args()
# Shared target is loaded once available; refuse unknown targets even for initial bootstrap.
from device_target import get_target
TARGET=get_target(args.target);APP=TARGET.package;SERIAL=TARGET.serial
RUN=args.run or str(time.time_ns());assert RUN.isdigit() and (args.run or args.stage=='preflight')
BASE=ROOT/'docs/handoff/evidence/android15-takeover'/RUN;BASE.mkdir(parents=True,exist_ok=True)
OUT=BASE/(args.stage+'-'+str(time.time_ns()));OUT.mkdir();shutil.copyfile(__file__,OUT/'driver.py')
statefile=BASE/'state.json';state=json.loads(statefile.read_text('utf-8')) if statefile.exists() else dict(run=RUN,target=args.target,providerId='aa_model_'+RUN,skillId='bound-proof-'+RUN)
assert state['target']==args.target
rows=[];requests=[];events=[];token='';secrets=[];allowed=None;stream=None;thread=None;closed=threading.Event();locked=False
ADB=os.environ['ANDROID_ADB'];EXPECTED='E36A5B071FA052104C00618E788E66A1A4AA4C009D21C828462D407A8700F8F2'
def clean(s):
 for x in [token,*secrets]:
  if x:s=s.replace(x,'[redacted]')
 return s
def save(n,v):(OUT/n).write_text(clean(json.dumps(v,ensure_ascii=False,indent=2))+'\n',encoding='utf-8')
def checkpoint():statefile.write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
def adb(*a,check=True,private=False):
 p=subprocess.run([ADB,'-s',SERIAL,*a],capture_output=True,timeout=150)
 if not private:rows.append(dict(argv=[ADB,'-s',SERIAL,*a],exit=p.returncode,stdout=clean(p.stdout.decode('utf-8','replace')),stderr=clean(p.stderr.decode('utf-8','replace'))));save('commands.json',rows)
 assert not check or p.returncode==0,'See retained command failure'
 return p.stdout
def read(n,private=False,check=True):return adb('exec-out','run-as',APP,'cat',n,private=private,check=check)
def get(route,body=None,timeout=30):
 req=urllib.request.Request('http://127.0.0.1:18765'+route,data=None if body is None else json.dumps(body).encode(),headers={'X-Bridge-Token':token,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
def rpc(method,params):
 requests.append(dict(method=method,params=params));save('requests.json',requests)
 result=get('/rpc-wait',dict(method=method,params=params,timeoutMs=25000));assert not result.get('error'),str(result.get('error'));return result['result']
def snapshot(label):
 remote='/data/local/tmp/takeover-'+RUN+'.xml';adb('shell','uiautomator','dump',remote);raw=adb('exec-out','cat',remote);(OUT/(label+'.xml')).write_text(clean(raw.decode('utf-8')),encoding='utf-8');return ET.fromstring(raw)
def text(tree,s):return next(n for n in tree.iter('node') if n.get('text')==s)
def tap(n):
 assert n.get('enabled')=='true','Disabled UI control'
 l,t,r,b=map(int,re.findall(r'\d+',n.get('bounds')));adb('shell','input','tap',str((l+r)//2),str((t+b)//2));time.sleep(.5)
def home():
 adb('shell','am','start','-W','--activity-clear-top','-n',APP+'/.MainActivity')
 for i in range(6):
  tree=snapshot('home-'+str(i))
  if any(n.get('text')=='任务' for n in tree.iter('node')):return tree
  time.sleep(.5)
 raise AssertionError('Product main UI not observed')
def launch():
 global token
 adb('forward','tcp:18765','tcp:8765');tree=home();tap(text(tree,'任务'));tree=snapshot('task-home');tap(text(tree,'打开 Agent'))
 deadline=time.monotonic()+60
 while time.monotonic()<deadline:
  try:
   token=read('files/runtime/bridge-token',True).decode().strip();s=get('/status',timeout=2)
   if s['phase']=='ready':
    cfg=json.loads(read('files/runtime/provider/personal_provider_config.json',True))
    for p in cfg['config']['providerConfigRules']['providerRules']:secrets.append(p['config']['access']['apiKey'])
    m=cfg['config']['modelConfigRules']['manualProviderModelRules'][0];state['selection']={k:m[k] for k in ['providerId','modelId']};state['workspace']=dict(workspacePath=s['workspace'],workspaceKey='default');checkpoint();save('ready.json',s);return s
  except (OSError,ValueError,IndexError,KeyError):time.sleep(.5)
 raise AssertionError('Runtime ready/config deadline')
def installed_hash():
 path=adb('shell','pm','path',APP).decode().strip().removeprefix('package:');return adb('shell','run-as',APP,'sha256sum',path).decode().split()[0].upper(),path
def old_identity():
 old='dev.zcode.nodepoc';path=adb('shell','pm','path',old).decode().strip().removeprefix('package:')
 hashes=dict(apk=adb('shell','run-as',old,'sha256sum',path).decode().split()[0].upper())
 for n in ['zcode.cjs','bootstrap.cjs','gateway.cjs','carrier-authorization.cjs']:hashes[n]=adb('shell','run-as',old,'sha256sum','files/runtime/'+n).decode().split()[0].upper()
 return hashes,path
def begin_events():
 global stream,thread
 closed.clear();stream=urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:18765/events',headers={'X-Bridge-Token':token}),timeout=150)
 def consume():
  try:
   while not closed.is_set():
    line=stream.readline()
    if not line:break
    if not line.startswith(b'data:'):continue
    e=json.loads(line[5:]);events.append(e)
    if e.get('type')=='permission':
     grant=allowed is not None and not e.get('hardConfirm') and (e.get('toolName'),e.get('input')) in allowed
     answer=get('/respond',dict(requestId=e['requestId'],decision='allow' if grant else 'deny'));events.append(dict(type='test-permission-response',granted=grant,result=answer))
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
def create():return rpc('session/create',dict(workspace=state['workspace'],mode='build',thoughtLevel='disabled',model={**state['selection'],'options':dict(reasoningLevel='disabled')},titleGenerationEnabled=False,dynamicWorkflowEnabled=False,offPeakToolEnabled=False))['session']['sessionId']
def turn(sid,prompt,label,timeout=150):
 prior=messages(sid);rpc('session/send',dict(sessionId=sid,content=prompt));deadline=time.monotonic()+timeout
 while time.monotonic()<deadline:
  value=messages(sid);fresh=value[len(prior):]
  if any(m.get('info',{}).get('role')=='assistant' and m.get('info',{}).get('finish')=='stop' for m in fresh):break
  time.sleep(.5)
 else:save(label+'-incomplete.json',value);raise AssertionError('Real model completion deadline')
 save(label+'-messages.json',value);return value,[p for m in fresh for p in m.get('parts',[])]
def stop_ui():
 tree=home();tap(text(tree,'工具'));tree=snapshot('tools-before-stop')
 buttons=[n for n in tree.iter('node') if n.get('text')=='停止 Agent 以管理工具']
 if buttons:
  tap(buttons[0]);time.sleep(1);tree=snapshot('tools-stopped');tap(text(tree,'刷新'));tree=snapshot('tools-refreshed')
 assert any(n.get('text','').startswith('Agent 已停止，可修改准入') for n in tree.iter('node'))
def fixture(kind,revision):
 cls='ManagedProviderModelFixtureTest' if kind=='provider' else 'ManagedSkillBindingFixtureTest'
 identifier=state['providerId'] if kind=='provider' else state['skillId']
 out=adb('shell','am','instrument','-w','-e','class',APP+'.'+cls,'-e','fixtureId',identifier,'-e','revision',revision,*TARGET.instrumentation_args(),APP+'.test/androidx.test.runner.AndroidJUnitRunner').decode()
 assert 'OK (1 test)' in out and 'FAILURES' not in out and 'INSTRUMENTATION_FAILED' not in out
 name='cache/'+identifier+'-'+revision+('.json' if kind=='provider' else '-receipt.json')
 receipt=json.loads(read(name));save(kind+'-import.json',receipt);state[kind+'-'+revision]=receipt;checkpoint();return receipt
def approve_provider(receipt):
 tree=home();tap(text(tree,'工具'));tree=snapshot('provider-list');title=text(tree,state['providerId']+' · '+receipt['version']);parents={c:p for p in tree.iter() for c in p};card=title
 while not any(n.get('text')=='填写声明并评审' for n in card.iter('node')):card=parents[card]
 tap(text(card,'填写声明并评审'));tree=snapshot('provider-editor');fields=[n for n in tree.iter('node') if n.get('class')=='android.widget.EditText'];tap(fields[0]);adb('shell','input','text','compute');adb('shell','input','keyevent','4')
 tree=snapshot('provider-name');fields=[n for n in tree.iter('node') if n.get('class')=='android.widget.EditText'];tap(fields[2]);adb('shell','input','text',receipt['description'].replace(' ','%s'));adb('shell','input','keyevent','4')
 tree=snapshot('provider-description');tap(text(tree,'检查'));tree=snapshot('provider-confirm');assert any(receipt['contentHash'] in n.get('text','') for n in tree.iter('node'));tap(text(tree,'确认准入'))
 pin=next(p for p in json.loads(read('files/provider-reviews.json'))['selected'] if p['id']==state['providerId']);assert pin['contentHash']==receipt['contentHash'];state['pin-'+receipt['version']]=pin;checkpoint();save('approved-pin.json',pin)
def provider_turn(sid,version,label):
 global allowed
 raw=('Android15-provider-'+RUN+'-'+label).encode();input=dict(base64=base64.b64encode(raw).decode());wire=state['providerId']+'_compute';allowed=[('mcp__android-host__'+wire,input)]
 all_messages,parts=turn(sid,'Use ONLY mcp__android-host__'+wire+' once with exactly '+json.dumps(input)+'. Report the real version, checksum, isolated UID and returned artifact path. No other tools. End with TAKEOVER_PROVIDER_OK after the actual result.',label)
 tools=[p for p in parts if p.get('type')=='tool'];assert len(tools)==1 and tools[0]['tool']=='mcp__android-host__'+wire and tools[0]['state']['input']==input and tools[0]['state']['status']=='completed'
 payload=json.loads(tools[0]['state']['output'].split('Structured content:\n',1)[1]);data=payload['data'];pin=state['pin-'+version]
 assert data['version']==version and data['sha256']==hashlib.sha256(raw).hexdigest() and data['bytes']==len(raw)
 assert data['_hostProvider']['contentHash']==pin['contentHash'] and data['_hostProvider']['definitionHash']==pin['definitionHash'] and data['_hostProvider']['backend']=='android-isolated-node'
 assert data['_localProvider']['rpcVersion']=='2.0' and data['_localProvider']['replyValidated'] is True
 owner=adb('shell','run-as',APP,'id','-u').decode().strip();assert str(data['uid'])!=owner and data['pid']>0
 artifact=payload['artifacts'][0];assert artifact['uri'].startswith('/data/user/0/'+APP+'/files/artifacts/'+sid+'/')
 physical=read(artifact['uri']);report=json.loads(physical);assert report['data']==data and len(physical)==artifact['size'];(OUT/(label+'-artifact.json')).write_bytes(physical)
 ops=[r for r in get('/gateway/journal?limit=200')['operations'] if r['session']==sid and 'call_id='+report['callId']+' ' in (r.get('detail') or '')]
 assert len(ops)==1 and ops[0]['result']=='ok' and json.loads(ops[0]['args'])==input and 'provider_sha256='+pin['contentHash'] in ops[0]['detail'] and 'declaration_sha256='+pin['definitionHash'] in ops[0]['detail']
 assert any(e.get('type')=='carrier-call' and e.get('callId')==report['callId'] for e in events)
 assert any('TAKEOVER_PROVIDER_OK' in p.get('text','') for p in parts if p.get('type')=='text')
 save(label+'-verified.json',dict(sessionId=sid,data=data,operation=ops[0],artifact=artifact,artifactSha256=hashlib.sha256(physical).hexdigest(),modelIssued=True));return all_messages
def skill_turn(sid,revision,label):
 global allowed
 receipt=state['skill-'+revision];path=receipt['directory']+'/references/rule.txt';identifier=state['skillId'];allowed=[('Skill',dict(skill=identifier)),('Read',dict(file_path=path))]
 value,parts=turn(sid,'Use the Skill tool to load the installed skill named '+identifier+'. Follow its instructions and read references/rule.txt using Read. Return its exact resource line and version. Only Skill and Read are allowed; no other tools.',label)
 tools=[p for p in parts if p.get('type')=='tool'];assert tools and all(p['tool'] in ['Skill','Read'] and p['state']['status']=='completed' for p in tools)
 assert any(p['tool']=='Skill' and p['state']['input'].get('skill')==identifier for p in tools)
 reads=[p for p in tools if p['tool']=='Read' and p['state']['input'].get('file_path')==path];assert reads
 proof=receipt['proof'];assert read(path).decode()==proof+'\n'
 # Exact physical path/history lineage permits Core's unchanged-file cache response.
 historic=[p for m in value for p in m.get('parts',[]) if p.get('type')=='tool' and p.get('tool')=='Read' and p.get('state',{}).get('input',{}).get('file_path')==path and proof in p['state'].get('output','')]
 assert historic and any(proof in p.get('text','') for p in parts if p.get('type')=='text')
 index=json.loads(read('files/sessions-index.json'));row=next(r for r in index if r['sessionId']==sid);assert any(p['hash']==receipt['hash'] and p['id']==identifier for p in row['managedSkills'])
 save(label+'-verified.json',dict(sessionId=sid,hash=receipt['hash'],directory=receipt['directory'],physicalProof=proof,sessionPin=row['managedSkills'],modelActivated=True))
def active_wait_call(sid,label):
 global allowed
 input=dict(base64=base64.b64encode(('WAIT:'+label+'-'+RUN).encode()).decode());wire=state['providerId']+'_compute';allowed=[('mcp__android-host__'+wire,input)];start=len(events)
 rpc('session/send',dict(sessionId=sid,content='Use ONLY mcp__android-host__'+wire+' once with exactly '+json.dumps(input)+'. Wait for the actual result. No other tools.'))
 deadline=time.monotonic()+90;call=None
 while time.monotonic()<deadline:
  calls=[e for e in events[start:] if e.get('type')=='carrier-call' and e.get('toolId')==wire]
  if calls:call=calls[0];break
  time.sleep(.1)
 assert call,'No actual model carrier invocation before cancellation'
 physical=[]
 for _ in range(50):
  ps=adb('shell','ps','-A','-o','UID,PID,PPID,NAME,ARGS').decode();physical=[l.split() for l in ps.splitlines() if APP+':provider' in l]
  if physical:break
  time.sleep(.1)
 assert len(physical)==1;owner=adb('shell','run-as',APP,'id','-u').decode().strip();assert physical[0][0]!=owner
 save(label+'-active-process.json',physical[0]);return call,int(physical[0][1]),ps
def wait_dead(pids,label):
 start=time.monotonic();deadline=start+15
 while time.monotonic()<deadline:
  ps=adb('shell','ps','-A','-o','UID,PID,PPID,NAME,ARGS').decode();live={int(x[1]) for l in ps.splitlines()[1:] if len(x:=l.split())>=4}
  if not pids&live:break
  time.sleep(.1)
 else:raise AssertionError('Owned processes survived stop')
 save(label+'-processes-gone.json',dict(pids=sorted(pids),survivors=[],observedMs=round((time.monotonic()-start)*1000)))
def cancelled_operation(sid,call,label):
 ops=[r for r in get('/gateway/journal?limit=200')['operations'] if r['session']==sid and 'call_id='+call['callId']+' ' in (r.get('detail') or '')];pin=state['pin-v2']
 assert len(ops)==1 and ops[0]['result']=='CANCELLED' and 'provider_sha256='+pin['contentHash'] in ops[0]['detail'] and 'declaration_sha256='+pin['definitionHash'] in ops[0]['detail']
 save(label+'-operation.json',ops[0]);return ops[0]
def main():
 global locked,allowed
 fd=os.open(BASE/'device.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd);locked=True
 properties={n:adb('shell','getprop',n).decode().strip() for n in ['ro.build.version.sdk','ro.build.version.release','ro.product.model','ro.product.cpu.abilist']}
 TARGET.validate_properties(properties)
 save('device-target.json',dict(profile=TARGET.name,serial=TARGET.serial,properties=properties,apkSha256=EXPECTED))
 if args.stage=='preflight':
  present=adb('shell','pm','list','packages',APP).decode();assert 'package:'+APP not in present,'Product already exists; review before fresh installation'
  identity,path=old_identity();state['oldIdentity']=identity;checkpoint();adb('pull',path,str(BASE/'old-zcode.apk'))
  assert hashlib.sha256((BASE/'old-zcode.apk').read_bytes()).hexdigest().upper()==identity['apk']
  adb('shell','am','force-stop','dev.zcode.nodepoc');save('old-owner-after-stop.json',dict(pid=adb('shell','pidof','dev.zcode.nodepoc',check=False).decode().strip()))
  save('preflight.json',dict(identity=identity,productInitiallyAbsent=True,sourceApk=EXPECTED,serial=SERIAL));return
 if args.stage=='install':
  apk=ROOT/'docs/handoff/evidence/subscription1/1792939546631881700/candidate.apk';assert hashlib.sha256(apk.read_bytes()).hexdigest().upper()==EXPECTED
  shutil.copyfile(apk,BASE/'product-e36.apk');adb('install','-r',str(BASE/'product-e36.apk'));actual,path=installed_hash();assert actual==EXPECTED
  state['apk']=actual;checkpoint();save('installed.json',dict(apkSha256=actual,path=path));return
 assert installed_hash()[0]==EXPECTED
 if args.stage=='configure':
  adb('shell','pm','grant',APP,'android.permission.POST_NOTIFICATIONS')
  # Only explicitly authorized model settings are recreated; no prefs, token, journal or session clone.
  source=subprocess.run([ADB,'-s','DEVICE_ANDROID17','exec-out','run-as',APP,'cat','files/runtime/provider/personal_provider_config.json'],capture_output=True,check=True)
  cfg=json.loads(source.stdout);p=cfg['config']['providerConfigRules']['providerRules'][0];settings=[p['config']['api']['baseUrl'],p['config']['personalModelIds'][0],p['config']['access']['apiKey']];secrets.append(settings[2])
  tree=home();tap(text(tree,'设置'));tree=snapshot('settings-empty');fields=[n for n in tree.iter('node') if n.get('class')=='android.widget.EditText'];assert len(fields)>=3
  for i,value in enumerate(settings):
   tree=snapshot('settings-field-'+str(i));fields=[n for n in tree.iter('node') if n.get('class')=='android.widget.EditText'];tap(fields[i]);adb('shell','input','keyevent','KEYCODE_MOVE_END')
   assert len(fields[i].get('text',''))<512
   adb('shell','input','keyevent',*(['67']*(len(fields[i].get('text',''))+2)))
   adb('shell','input','text',value.replace(' ','%s'));adb('shell','input','keyevent','4')
  tree=snapshot('settings-filled');tap(text(tree,'保存'));launch();target=json.loads(read('files/runtime/provider/personal_provider_config.json',True));actual=target['config']['providerConfigRules']['providerRules'][0]
  assert actual['config']['access']['apiKey']==settings[2] and actual['config']['api']['baseUrl']==settings[0] and actual['config']['personalModelIds'][0]==settings[1]
  save('configured.json',dict(model=settings[1],sameAuthorizedConfiguration=True,throughProductSettingsUi=True,targetEncryptionRecreated=True));return
 if args.stage=='test-install':
  apk=ROOT/'app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk';adb('install','-r',str(apk));save('test-apk.json',dict(sha256=hashlib.sha256(apk.read_bytes()).hexdigest()));return
 if args.stage=='provider-import':
  stop_ui();receipt=fixture('provider',args.revision);approve_provider(receipt);launch();return
 if args.stage=='provider-model':
  launch();begin_events()
  if args.revision=='v1':sid=create();state['providerOldSession']=sid;checkpoint();provider_turn(sid,'v1','provider-v1')
  else:
   sid=state['providerOldSession'];rpc('session/resume',dict(sessionId=sid,workspace=state['workspace'],dynamicWorkflowEnabled=False,offPeakToolEnabled=False));provider_turn(sid,'v1','provider-old-after-update')
   sid=create();state['providerNewSession']=sid;checkpoint();provider_turn(sid,'v2','provider-new-v2')
  save('result.json',dict(verdict='PASS_REAL_MODEL_ISOLATED_PROVIDER',revision=args.revision));return
 if args.stage=='skill-import':
  stop_ui();fixture('skill',args.revision);launch();return
 if args.stage=='skill-model':
  launch();begin_events()
  if args.revision=='1':sid=create();state['skillOldSession']=sid;checkpoint();skill_turn(sid,'1','skill-v1')
  else:
   sid=state['skillOldSession'];rpc('session/resume',dict(sessionId=sid,workspace=state['workspace'],dynamicWorkflowEnabled=False,offPeakToolEnabled=False));skill_turn(sid,'1','skill-old-v1')
   sid=create();state['skillNewSession']=sid;checkpoint();skill_turn(sid,'2','skill-new-v2')
  save('result.json',dict(verdict='PASS_REAL_MODEL_SKILL_PIN',revision=args.revision));return
 if args.stage=='reliability':
  before=launch();begin_events();old=state['providerOldSession'];rpc('session/resume',dict(sessionId=old,workspace=state['workspace'],dynamicWorkflowEnabled=False,offPeakToolEnabled=False));initial=messages(old)
  adb('shell','input','keyevent','HOME');after=launch();assert before['startedAt']==after['startedAt'] and messages(old)==initial;save('reconnect.json',dict(sameRuntime=True,fullMessagesEqual=True))
  end_events();adb('shell','am','force-stop',APP);after=launch();assert after['startedAt']!=before['startedAt'];begin_events()
  rpc('session/resume',dict(sessionId=old,workspace=state['workspace'],dynamicWorkflowEnabled=False,offPeakToolEnabled=False));restored=messages(old);assert restored==initial
  save('before-restart.json',initial);save('after-restart.json',restored);provider_turn(old,'v1','old-provider-after-restart')
  skill=state['skillOldSession'];rpc('session/resume',dict(sessionId=skill,workspace=state['workspace'],dynamicWorkflowEnabled=False,offPeakToolEnabled=False));skill_turn(skill,'1','old-skill-after-restart')
  sid=create();call,pid,_=active_wait_call(sid,'cancel');rpc('session/stop',dict(sessionId=sid));wait_dead({pid},'cancel');cancelled_operation(sid,call,'cancel')
  sid=create();call,pid,ps=active_wait_call(sid,'service-stop');status=get('/status');core=status['childPid'];processes={int(x[1]):x for l in ps.splitlines()[1:] if len(x:=l.split())>=4};bootstrap=int(processes[core][2]);assert 'bootstrap.cjs' in ' '.join(processes[bootstrap]);owned={bootstrap,core}
  for _ in processes:
   extra={p for p,x in processes.items() if int(x[2]) in owned}
   if extra<=owned:break
   owned|=extra
  assert any('android-carr' in ' '.join(processes[p]) for p in owned);owned.add(pid);save('service-owned-before.json',[processes[p] for p in sorted(owned)])
  stop_ui();wait_dead(owned,'service-stop');end_events();launch();cancelled_operation(sid,call,'service-stop');begin_events();provider_turn(create(),'v2','provider-after-service-stop')
  assert not any('deliveryKind' in str(e.get('message',{}).get('error',{})) for e in events)
  save('result.json',dict(verdict='PASS_ANDROID15_RELIABILITY',providerOld=old,skillOld=skill,ownedServicePids=sorted(owned),cancelledProviderPid=pid));return
 if args.stage=='accessibility':
  save('settings-before.json',dict(enabled=adb('shell','settings','get','secure','enabled_accessibility_services').decode().strip()))
  adb('shell','am','start','-W','-a','android.settings.ACCESSIBILITY_SETTINGS');snapshot('accessibility-settings');return
 if args.stage=='accessibility-ui':
  tree=snapshot('before');node=text(tree,args.revision);tap(node);snapshot('after');return
 if args.stage=='accessibility-checkbox':
  tree=snapshot('before');nodes=[n for n in tree.iter('node') if n.get('resource-id')=='com.miui.securitycenter:id/check_box' and n.get('checked')=='false'];assert len(nodes)==1;tap(nodes[0]);snapshot('after');return
 if args.stage=='device-readonly':
  stop_ui();launch();begin_events();sid=create()
  inputs=[('mcp__android-host__ui_dump',dict(detail='compact',maxNodes=80)),('mcp__android-host__ui_screenshot',dict(maxLongEdge=1080))];allowed=inputs
  adb('shell','am','start','-W','--activity-clear-top','-n',APP+'/.zcode.runtime.UiLabActivity');snapshot('lab-visible')
  value,parts=turn(sid,'Read-only controlled device test. Use ONLY mcp__android-host__ui_dump once with exactly '+json.dumps(inputs[0][1])+' and then mcp__android-host__ui_screenshot once with exactly '+json.dumps(inputs[1][1])+'. Do not click/type/scroll or use other tools. Describe the observed UiLab fixture and screenshot metadata. End with ANDROID15_OBSERVATION_OK only after both results.','device-observation')
  tools=[p for p in parts if p.get('type')=='tool'];assert len(tools)==2 and {p['tool'] for p in tools}=={t for t,_ in inputs} and all(p['state']['status']=='completed' for p in tools)
  screenshot=None
  for p in tools:
   assert p['state']['input']==dict(inputs)[p['tool']]
   payload=json.loads(p['state']['output'].split('Structured content:\n',1)[1]);assert payload['ok'] is True
   if p['tool'].endswith('ui_dump'):
    labels={n.get('text') for n in payload['nodes']};assert {'UiLab fixture','count=0','INCREMENT'}<=labels;save('ui-dump.json',payload)
   else:screenshot=payload
  assert screenshot['performed'] is False and screenshot['verified'] is False and screenshot['verify']=='skipped'
  assert re.fullmatch('shot_[a-f0-9]{32}',screenshot['shotId']) and screenshot['captureScope']=='active_window' and screenshot['bytes']<=153600
  physical=read('files/runtime/vision/shots/'+screenshot['shotId']+'.jpeg');assert len(physical)==screenshot['bytes'] and hashlib.sha256(physical).hexdigest()==screenshot['sha256']
  (OUT/'fixture-screenshot.jpeg').write_bytes(physical);save('screenshot-metadata.json',screenshot)
  index=json.loads(read('files/runtime/vision/shots/index.json'));assert any(r['shotId']==screenshot['shotId'] and r['sessionId']==sid for r in index)
  ops=[r for r in get('/gateway/journal?limit=100')['operations'] if r['session']==sid and r['tool'] in dict(inputs)];assert len(ops)==2 and all(r['decision']=='allow' for r in ops)
  save('device-operations.json',ops);assert any('ANDROID15_OBSERVATION_OK' in p.get('text','') for p in parts if p.get('type')=='text');save('result.json',dict(verdict='PASS_ANDROID15_ACCESSIBILITY_AND_SCREENSHOT',sessionId=sid,screenshotSha256=screenshot['sha256'],onlyReadOnlyTools=True));return
 raise ValueError('Unknown stage '+args.stage)
try:main()
except BaseException as err:save('failure.json',dict(type=type(err).__name__,message=clean(str(err))));print('FAIL retained '+str(OUT));raise
finally:
 end_events()
 if locked:(BASE/'device.lock').unlink()
print(json.dumps(dict(evidence=str(OUT),run=RUN)))
