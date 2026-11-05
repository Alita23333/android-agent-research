"""Independent offline consistency checks; all device actions are in frozen acceptance records."""
from pathlib import Path
import hashlib,json,re,shutil
ROOT=Path(__file__).resolve().parents[2];EV=ROOT/'docs/handoff/evidence/subscription1';BASE=EV/'1792939546631881700';OUT=EV/'summary-20261025';OUT.mkdir(exist_ok=False)
load=lambda p:json.loads(p.read_text('utf-8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
def check(n,v):checks.append(dict(name=n,passed=bool(v)));assert v,n
state=load(BASE/'state.json');post=load(EV/'postflight-20261025/identity.json')
baseline=load(next(BASE.glob('baseline-*/result.json')));accepted=load(next(BASE.glob('accept-*/result.json')));cancel=load(next(BASE.glob('cancel-*/result.json')))
check('baseline old package reproduces4 errors',baseline['verdict']=='REPRODUCED_MISSING_DELIVERY_KIND' and baseline['errors']==4 and baseline['apk']=='1FF91047068AF96339F2E451016C593DE28FDD360D3325B351D0A24B9966B8F9')
check('installed exact frozen new APK',post['apkSha256']==state['apkSha256']==accepted['apk']==cancel['apk']==sha(BASE/'candidate.apk').upper())
check('only bootstrap changes in pinned runtime payload',post['changedPayloads']==['assets/zcode-runtime/bootstrap.cjs'] and len(post['installed'])==40 and len(post['codeAndNativeUnchanged'])==36)
check('final kill switches and real readiness',all(v is False for v in post['killSwitches'].values()) and post['status']['phase']=='ready' and post['status']['mode']=='real')
before=(EV/'postflight-20261025/before-bootstrap.cjs').read_text('utf-8');after=(EV/'postflight-20261025/bootstrap.cjs').read_text('utf-8')
expected=before.replace('// Phase 7: session/event notifications (incl. network_request_status)\n        // only flow to SUBSCRIBED clients — measured: zero events without this\n        rpc("session/subscribe", { sessionId: m.result.session.sessionId }, 8000)',
 '// Core0.16.9 requires deliveryKind. The persistent bridge owns the Core\n        // connection; Activity/SSE reconnects do not turn it into a replay client.\n        rpc("session/subscribe", { sessionId: m.result.session.sessionId, deliveryKind: "desktop-continuous" }, 8000)')
check('exact production diff field and explanatory comment only',expected==after and before!=after)
protocol=load(EV/'protocol-1792939480181341100/protocol.stdout')
check('actual immutable Core negative and positive schema cases',protocol['verdict']=='PASS_ACTUAL_CORE_SUBSCRIPTION_PROTOCOL' and protocol['node']=='v24.18.0' and protocol['checks']==5 and protocol['missingDeliveryKind']==protocol['invalidDeliveryKind']==-32602 and len(protocol['positive'])==2 and all(r['sessionId']==protocol['sessionId'] and isinstance(r['eventSeq'],int) and r['events']==[] for r in protocol['positive']) and protocol['readMessageCount']==1 and protocol['naturalExit']==dict(code=0,signal=None))
check('protocol stderr empty',(EV/'protocol-1792939480181341100/protocol.stderr').read_bytes()==b'')
folder=next(BASE.glob('accept-*'));events=load(folder/'events.json')
errors=[e for e in events if 'deliveryKind' in str(e.get('message',{}).get('error',{}))]
subs=[e['message']['result'] for e in events if isinstance(e.get('message',{}).get('result'),dict) and 'eventSeq' in e['message']['result'] and 'events' in e['message']['result']]
legacy=[e['message']['params'] for e in events if e.get('message',{}).get('method')=='session/event']
check('28 actual automatic subscribe replies with zero delivery errors',len(subs)==accepted['automaticSubscribeReplies']==28 and not errors and accepted['deliveryKindErrors']==0)
check('53 typed session events in continuous delivery',len(legacy)==accepted['legacyEvents']==53 and all(e['deliveryKind']=='desktop-continuous' and e['sessionId']==accepted['modelSession'] and isinstance(e['seq'],int) for e in legacy))
types=sorted({e.get('type','') for e in legacy});check('typed started and completed events',any('started' in t.lower() for t in types) and any('completed' in t.lower() for t in types))
reports=[]
for label in ['first','resumed']:
 r=load(folder/(label+'-verified.json'));physical=(folder/(label+'-artifact.json')).read_bytes();artifact=json.loads(physical);op=r['operation'];args=json.loads(op['args']);raw=__import__('base64').b64decode(args['base64']);data=r['data']
 check(label+' exact physical checksum and input',hashlib.sha256(raw).hexdigest()==data['sha256'] and len(raw)==data['bytes'] and artifact['data']==data and hashlib.sha256(physical).hexdigest()==r['artifactSha256'] and len(physical)==r['artifact']['size'])
 check(label+' local protocol and pin metadata',data['_localProvider']['rpcVersion']=='2.0' and data['_localProvider']['protocolVersion']=='1.0' and data['_localProvider']['replyValidated'] is True and data['_hostProvider']['contentHash']==state['pin']['contentHash'] and data['_hostProvider']['definitionHash']==state['pin']['definitionHash'])
 check(label+' exact successful operation and call',op['result']=='ok' and op['decision']=='allow' and op['session']==r['sessionId']==accepted['modelSession'] and 'call_id='+artifact['callId']+' ' in op['detail'] and 'provider_sha256='+state['pin']['contentHash'] in op['detail'] and 'declaration_sha256='+state['pin']['definitionHash'] in op['detail'])
 messages=load(folder/(label+'-messages.json'));matching=[p for m in messages for p in m.get('parts',[]) if p.get('type')=='tool' and p.get('state',{}).get('input')==args and artifact['callId'] in p['state'].get('output','')]
 check(label+' actual model tool state and streamed evidence',len(matching)==1 and matching[0]['state']['status']=='completed' and r['streamChunks']>1 and r['legacyEvents']>0)
 reports.append(dict(label=label,operationId=op['id'],streamChunks=r['streamChunks'],artifactSha256=r['artifactSha256']))
check('reconnect same runtime and exact messages',load(folder/'reconnect.json')==dict(sameRuntime=True,fullMessagesEqual=True))
check('force-stop resume exact persisted messages',load(folder/'before-restart.json')==load(folder/'after-restart.json'))
check('active cancellation settled and process terminated',cancel['verdict']=='PASS_SUBSCRIBED_MODEL_CANCELLATION' and cancel['pidGone'] is True and cancel['operation']['result']=='CANCELLED' and 'call_id='+cancel['call']['callId']+' ' in cancel['operation']['detail'])
check('Node14 exact pass no skip',all(re.search(r'(?m)^[ℹ#\s]*'+k+r'\s+'+str(n)+r'\s*$',(EV/'node14.log').read_text('utf-8')) for k,n in dict(tests=14,fail=0,cancelled=0,skipped=0,todo=0).items()) and re.search(r'(?m)^[ℹ#\s]*pass\s+14\s*$',(EV/'node14.log').read_text('utf-8')) is not None)
sql=(EV/'settlement22.log').read_text('utf-8');check('SQLite22 exact PASS lines',len([l for l in sql.splitlines() if l.startswith('PASS ')])==22 and sql.splitlines()[-1]=='RESULT 22 PASS')
check('successful build','BUILD SUCCESSFUL' in (EV/'build.log').read_text('utf-8',errors='replace'))
result=dict(verdict='PASS_SCOPED_CONTINUOUS_BRIDGE_SUBSCRIPTION',apkSha256=post['apkSha256'],payloadSha256=post['payloadSha256'],protocolChecks=5,automaticSubscribeReplies=len(subs),legacyEvents=len(legacy),legacyEventTypes=types,deliveryKindErrors=0,modelReports=reports,cancellation=cancel,offlineCheckCount=len(checks),checks=checks,
 retainedLimits=['Persistent bridge-to-Core continuous subscription, not browser replay/cursor/afterSeq recovery.',
 'Prior blanket Web consumer diagnosis corrected to missing bridge automatic subscribe parameter.',
 'Existing downstream legacy folds still use older payload.type assumptions; full upstream write/network event-shape compatibility is not established by this field-only fix.',
 'Accepted driver originally labelled payload.type values as legacyTypes; raw outer params.type is authoritative and independently enumerated here. Future driver summary corrected without rewriting original proof.',
 'No new JVM/lint run: previous134 and0/28 remain dated proof; all36DEX/native/manifest entries unchanged. Related Node14+SQLite22 and actual Core5 were run this round.'])
(OUT/'acceptance-summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
source_paths=['app/src/main/assets/zcode-runtime/bootstrap.cjs','app/src/main/assets/zcode-runtime/payload-SHA256SUMS.txt','tools/phase9/subscription-product-acceptance.py','tools/phase9/core-subscription-protocol-test.cjs','tools/phase9/subscription-evidence-summary.py']
ids={}
for n in source_paths:
 p=ROOT/n;dest=OUT/'source'/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);ids[n]=sha(p)
(OUT/'source-sha256.json').write_text(json.dumps(ids,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(verdict=result['verdict'],offlineChecks=len(checks),eventTypes=types,reports=reports)))
