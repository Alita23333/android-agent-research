"""Verify retained model/artifact/journal evidence and current Android17 package without replay."""
from pathlib import Path
import hashlib,json,os,subprocess,time,urllib.request,xml.etree.ElementTree as ET,zipfile

ROOT=Path(__file__).resolve().parents[2]
EV=ROOT/'docs/handoff/evidence/provider-model1'
BASE=EV/'1792764185483531200'
OUT=EV/('acceptance-20261025-'+str(time.time_ns()));OUT.mkdir(exist_ok=False)
APP='dev.alita.androidagent'
state=json.loads((BASE/'state.json').read_text('utf-8'))
checks=[];commands=[]
def check(name,condition):
    checks.append(dict(name=name,passed=bool(condition)));assert condition,name
def load(p):return json.loads(p.read_text('utf-8'))
def sha(raw):return hashlib.sha256(raw).hexdigest()
def save(name,data):(OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def adb(*argv,private=False):
    p=subprocess.run([os.environ['ANDROID_ADB'],'-s','DEVICE_ANDROID17',*argv],capture_output=True,timeout=40)
    if not private:
        commands.append(dict(argv=list(argv),exit=p.returncode,stdout=p.stdout.decode('utf-8','replace'),stderr=p.stderr.decode('utf-8','replace')));save('postflight-commands.json',commands)
    assert p.returncode==0,'postflight command failed'
    return p.stdout
check('Android17 assigned device',adb('shell','getprop','ro.build.version.release').strip()==b'17' and adb('shell','getprop','ro.product.model').strip()==b'MODEL_ANDROID17')
apk=adb('shell','pm','path',APP).decode().strip().removeprefix('package:')
actual=adb('shell','run-as',APP,'sha256sum',apk).decode().split()[0].upper()
check('final installed package exact frozen APK',actual==state['serviceRepairedApk']==sha((BASE/'service-repaired-candidate.apk').read_bytes()).upper())
with zipfile.ZipFile(BASE/'service-repaired-candidate.apk') as z:
    sums=z.read('assets/zcode-runtime/payload-SHA256SUMS.txt');pins={n:h for h,n in (l.split(maxsplit=1) for l in sums.decode().splitlines())}
    for name,h in pins.items():check('packaged exact payload '+name,sha(z.read(name.replace('jniLibs/','lib/',1) if name.startswith('jniLibs/') else name))==h)
with zipfile.ZipFile(BASE/'candidate.apk') as z:
    old={n:h for h,n in (l.split(maxsplit=1) for l in z.read('assets/zcode-runtime/payload-SHA256SUMS.txt').decode().splitlines())}
    changes=[n for n in pins if pins[n]!=old[n]]
    check('payload changes only bootstrap and manifest description',sorted(changes)==['assets/zcode-runtime/bootstrap.cjs','assets/zcode-runtime/runtime-manifest.json'])
    for name in ['bootstrap.cjs','runtime-manifest.json']:(OUT/('before-'+name)).write_bytes(z.read('assets/zcode-runtime/'+name))
installed=[]
active=adb('exec-out','run-as',APP,'cat','files/tool-providers/text_digest/active').decode().strip()
for name,h in pins.items():
    if name.endswith('/personal_provider_config.json'):continue
    if name.startswith('assets/zcode-runtime/'):dest='files/runtime/'+name.removeprefix('assets/zcode-runtime/')
    elif name.startswith('assets/providers/text-digest/'):dest='files/tool-providers/text_digest/versions/'+active+'/'+name.rsplit('/',1)[1]
    else:dest=apk.rsplit('/',1)[0]+'/lib/arm64/'+name.rsplit('/',1)[1]
    got=adb('shell','run-as',APP,'sha256sum',dest).decode().split()[0]
    check('installed payload '+name,got==h);installed.append(dict(path=name,sha256=got))
save('installed-payload.json',installed)
cfg=json.loads(adb('exec-out','run-as',APP,'cat','files/.zcode/cli/config.json',private=True))
flags=dict(memory=cfg.get('features',{}).get('memory'),memoryExtraction=cfg.get('memory',{}).get('extractionEnabled'),plugins=cfg.get('plugins',{}).get('enabled'))
check('production memory/plugins kill switches retained',flags==dict(memory=False,memoryExtraction=False,plugins=False))
token=adb('exec-out','run-as',APP,'cat','files/runtime/bridge-token',private=True).decode().strip()
def get(route):
    req=urllib.request.Request('http://127.0.0.1:18765'+route,headers={'X-Bridge-Token':token})
    with urllib.request.urlopen(req,timeout=10) as r:return json.load(r)
ready=get('/status');check('fresh real runtime ready',ready['phase']=='ready' and ready['mode']=='real' and ready['nodeVersion']=='v24.18.0')
save('ready.json',ready)
index=json.loads(adb('exec-out','run-as',APP,'cat','files/sessions-index.json'))
own={r['sessionId']:r for r in index if r['sessionId'] in {state['oldSession'],state['newSession']}}
check('durable old/new session provider version bindings',own[state['oldSession']]['managedProviders']==[state['v1']['pin']] and own[state['newSession']]['managedProviders']==[state['v2']['pin']])
save('session-pins.json',own)
models=[]
for p in sorted(BASE.glob('*/*-verified.json')):
    row=load(p)
    if row.get('modelIssued') is not True:continue
    label=p.name.removesuffix('-verified.json');messages=load(p.with_name(label+'-messages.json'))
    artifact=p.with_name(label+'-artifact.json').read_bytes();physical=json.loads(artifact)
    check('artifact exact bytes '+p.parent.name+label,sha(artifact)==row['artifactSha256'] and len(artifact)==row['artifact']['size'] and physical['data']==row['data'])
    trace=row['data']['_localProvider']
    check('JSON-RPC2 actual provider trace '+p.parent.name+label,trace['rpcVersion']=='2.0' and trace['protocolVersion']=='1.0' and trace['providerId']==state['id'] and trace['method']=='tools/call' and trace['requestId']==2 and trace['replyValidated'] is True)
    op=row['operation'];call=physical['callId'];host=row['data']['_hostProvider'];pin=state[row['version']]['pin']
    check('exact successful operation provenance '+str(op['id']),op['decision']=='allow' and op['result']=='ok' and op['session']==row['sessionId'] and 'call_id='+call+' ' in op['detail'] and 'provider_sha256='+pin['contentHash'] in op['detail'] and 'declaration_sha256='+pin['definitionHash'] in op['detail'] and host['contentHash']==pin['contentHash'] and host['definitionHash']==pin['definitionHash'])
    args=json.loads(op['args']);raw=__import__('base64').b64decode(args['base64'])
    check('independent input checksum '+str(op['id']),sha(raw)==row['data']['sha256'] and len(raw)==row['data']['bytes'] and row['isolatedUidDistinctFromHost'] is True)
    tools=[part for m in messages for part in m.get('parts',[]) if part.get('type')=='tool' and part.get('state',{}).get('input')==args and call in part.get('state',{}).get('output','')]
    check('actual model tool part '+str(op['id']),len(tools)==1 and tools[0]['tool']=='mcp__android-host__'+state['id']+'_compute' and tools[0]['state']['status']=='completed')
    models.append(dict(evidence=str(p.parent.relative_to(EV)),operation=op['id'],version=row['version'],sessionId=row['sessionId'],artifactSha256=sha(artifact)))
check('eight retained real-model successful physical reports',len(models)==8)
final_service=load(sorted(BASE.glob('service-stop-*/service-stop-verified.json'))[-1])
process=load(sorted(BASE.glob('service-stop-*/service-stop-process-outcome.json'))[-1])
check('final actual UI Service stop fully observed',final_service['journalSettled'] and final_service['operation']['result']=='CANCELLED' and final_service['survivors']==[] and final_service['admissionUnlockedInActualUi'] and final_service['relaunched'] and len(process['ownedPids'])>=4 and process['survivingPids']==[])
final_cancel=load(sorted(BASE.glob('cancel-*/cancel-verified.json'))[-1])
check('final ordinary cancel settled and dead process',final_cancel['journalSettled'] and final_cancel['operation']['result']=='CANCELLED' and final_cancel['processGone'] and final_cancel['noCallArtifact'])
restart=sorted(BASE.glob('restart-*/persisted-before.json'))[-1]
check('final force-stop preserves exact full messages',load(restart)==load(restart.with_name('persisted-after.json')))
reconnect=load(sorted(BASE.glob('reconnect-*/reconnect-verified.json'))[-1])
check('Activity reconnect same runtime and messages',reconnect['sameRuntime'] and reconnect['exactMessagesRetained'])
events=load(sorted(BASE.glob('restart-*/events.json'))[-1])
chunks=[e['message']['params'] for e in events if e.get('type')=='rpc' and e.get('message',{}).get('method')=='v4/telemetry/event' and e['message'].get('params',{}).get('kind')=='stream.chunk']
check('real streamed response multiple chunks observed',len(chunks)>1 and any(c.get('channel')=='text' and c.get('chunkLength',0)>0 for c in chunks))
delivery_errors=[e for e in events if 'deliveryKind' in str(e.get('message',{}).get('error',{}))]
counts={k:0 for k in ['tests','failures','errors','skipped']}
for p in (ROOT/'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
    suite=ET.parse(p).getroot()
    for k in counts:counts[k]+=int(suite.attrib[k])
check('fresh JVM134 zero failure error skip',counts==dict(tests=134,failures=0,errors=0,skipped=0))
lint=ET.parse(ROOT/'app/build/reports/lint-results-debug.xml').getroot();lc={s:sum(x.get('severity')==s for x in lint.findall('issue')) for s in ['Error','Warning']}
check('lint0 errors28warnings',lc==dict(Error=0,Warning=28))
shutil=__import__('shutil');(OUT/'unit-tests').mkdir()
for p in (ROOT/'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):shutil.copyfile(p,OUT/'unit-tests'/p.name)
shutil.copyfile(ROOT/'app/build/reports/lint-results-debug.txt',OUT/'lint-results-debug.txt')
summary=dict(verdict='PASS_SCOPED_PRODUCT_MODEL_PROVIDER_AND_CANCELLATION',apkSha256=actual,runtime='0.16.9-runtime5',payloadSha256=sha(sums),packagedPayloads=len(pins),installedPayloads=len(installed),changedPayloads=changes,
    killSwitches=flags,models=models,finalServiceStop=final_service,finalServiceProcessObservation=process,finalCancel=final_cancel,reconnect=reconnect,
    streamChunks=len(chunks),jvm=counts,lint=lc,offlineChecks=len(checks),checks=checks,
    residuals=['Pre-repair operation655 and658 remain historically incomplete, not retrospectively rewritten.',
      'Native fixture imports package through real product store; ZIP picker import not exercised in this round.',
      'Per-call Gateway approval uses exact-tool/exact-input test responder; actual product admission/Service stop use real UI taps.',
      'SSE contains existing web consumer deliveryKind Invalid params errors: '+str(len(delivery_errors))+'. Model streaming is observed; complete web event-subscription compatibility is not claimed.',
      'No whole-app crash while a side-effecting operation is active, universal process deadline or Android15 model acceptance claim.'])
save('acceptance-summary.json',summary)
sources={}
for p in [*sorted((ROOT/'app/src/main/java/dev/alita/androidagent/tools').glob('*.kt')),*sorted((ROOT/'app/src/main/java/dev/alita/androidagent/zcode/adapter').glob('*.kt')),
 ROOT/'app/src/main/java/dev/alita/androidagent/zcode/runtime/ZCodeHostService.kt',ROOT/'app/src/main/java/dev/alita/androidagent/zcode/runtime/ZCodeGatewayClient.kt',ROOT/'app/src/main/java/dev/alita/androidagent/zcode/runtime/ZCodeCarrierWorker.kt',
 ROOT/'app/src/main/assets/zcode-runtime/bootstrap.cjs',ROOT/'app/src/main/assets/zcode-runtime/gateway.cjs',ROOT/'app/src/main/assets/zcode-runtime/carrier-authorization.cjs',ROOT/'app/src/main/assets/zcode-runtime/runtime-manifest.json',ROOT/'app/src/main/assets/zcode-runtime/payload-SHA256SUMS.txt',
 ROOT/'app/src/androidTest/java/dev/alita/androidagent/ManagedProviderModelFixtureTest.kt',ROOT/'tools/phase9/provider-model-product-acceptance.py',Path(__file__),ROOT/'tools/phase9/provider-abandoned-carrier-test.cjs']:
    rel=p.relative_to(ROOT);dest=OUT/'source'/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes());sources[rel.as_posix()]=sha(p.read_bytes())
save('source-sha256.json',sources)
print(json.dumps(dict(evidence=str(OUT),**{k:summary[k] for k in ['verdict','apkSha256','installedPayloads','streamChunks','offlineChecks']})))
