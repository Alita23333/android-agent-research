"""Real provider multi-step task; fixed synthetic Android17 workspace only."""
from pathlib import Path
import hashlib, json, os, subprocess

root=Path(__file__).resolve().parents[2]
evidence=root/'docs/handoff/evidence/command-analysis1'
identity=json.loads((evidence/'device-identity.json').read_text(encoding='utf-8'))
folder=identity['fixtureRelative']
fixture=json.loads((root/'docs/project/fixtures/organizing-input.json').read_text(encoding='utf-8'))
paths=[folder+'/'+file['path'] for file in fixture['files']]
prompt=('This is an authorized synthetic workspace task. Only modify files below '+folder+
 '. Use only mcp__android-host__workspace_analyze and mcp__android-host__workspace_file_create. '
 'No Bash, UI, network, deletion or overwrite. First inventory these exact workspace-relative files '
 'using workspace_analyze operation inventory: '+json.dumps(paths,ensure_ascii=False)+
 '. Then call workspace_analyze operation parse_json on '+folder+'/inbox/broken.json. '
 'It is intentionally malformed: preserve it and report the real INVALID_JSON/exitCode3, do not fix '
 'it or pretend success. Continue after that recoverable failure. Using returned base64 content '
 'and encoding base64, create classified copies with create_parents true and expect_hash absent: '
 'report.txt -> organized/documents/report-imported.txt (existing organized/documents/report.txt '
 'must remain unchanged), notes.md and 空格 notes.txt -> organized/documents/; measurements.csv -> '
 'organized/data/; opaque.bin -> organized/other/. Preserve ALL source files. Create '+folder+
 '/RESULTS.md with a concise change list, collision preservation, invalid JSON failure and byte/hash '
 'verification findings. Finally inventory all five new copies and the original organized/documents/report.txt '
 'via workspace_analyze to verify exact sizes and SHA256. End with COMMAND_TASK_ACCEPTANCE_OK only '
 'after actual tool success and verification. Do not claim files were moved: these are classified copies.')
apk=subprocess.check_output([os.environ['ANDROID_ADB'],'-s','DEVICE_ANDROID17','shell','pm','path','dev.alita.androidagent'],encoding='utf-8').strip().removeprefix('package:')
actual=subprocess.check_output([os.environ['ANDROID_ADB'],'-s','DEVICE_ANDROID17','shell','run-as','dev.alita.androidagent','sha256sum',apk],encoding='utf-8').split()[0]
assert actual==identity['apkSha256'], 'fixture identity belongs to another APK; prepare a fresh fixture first'
assert folder.startswith('command-analysis-') and folder.removeprefix('command-analysis-').isdigit()
subprocess.run([os.environ['ANDROID_ADB'],'-s','DEVICE_ANDROID17','shell','run-as','dev.alita.androidagent','test','!', '-e',
 'files/workspaces/default/'+folder+'/RESULTS.md'],check=True,capture_output=True)
env=dict(os.environ,ANDROID_SERIAL='DEVICE_ANDROID17')
result=subprocess.run([os.environ['ACCEPTANCE_NODE'],str(root/'tools/zcode/bridge-acceptance.cjs'),
 'ui-lab',prompt],env=env,capture_output=True,timeout=180)
(evidence/'real-organizing-task.json').write_bytes(result.stdout)
(evidence/'real-organizing-task.err').write_bytes(result.stderr)
if result.returncode:raise RuntimeError('real model harness failed; inspect saved stderr')
data=json.loads(result.stdout)
parts=[p for m in data['messages'] for p in m.get('parts',[]) if p.get('type')=='tool']
assert parts and all(p['tool'] in ['mcp__android-host__workspace_analyze','mcp__android-host__workspace_file_create'] for p in parts)
assert all(p.get('state',{}).get('status')=='completed' for p in parts)
assert any('COMMAND_TASK_ACCEPTANCE_OK' in p.get('text','') for m in data['messages'] for p in m.get('parts',[]) if p.get('type')=='text')
rows=[x for x in data['gatewayJournalRows'] if x.get('tool')=='mcp__android-host__workspace_analyze']
assert len(rows)==3 and sorted(x['result'] for x in rows)==['INVALID_JSON','ok','ok']
assert all(x['decision']=='allow' and x['session']==data['sessionId'] for x in rows)
def read(rel):
 return subprocess.check_output([os.environ['ANDROID_ADB'],'-s','DEVICE_ANDROID17','exec-out','run-as',
  'dev.alita.androidagent','cat','files/workspaces/default/'+folder+'/'+rel])
files=[]
for f in fixture['files']:
 assert hashlib.sha256(read(f['path'])).hexdigest().upper()==f['sha256']
 files.append({'path':f['path'],'preserved':True,'sha256':f['sha256']})
for src,dst in [('inbox/report.txt','organized/documents/report-imported.txt'),('inbox/notes.md','organized/documents/notes.md'),
 ('inbox/空格 notes.txt','organized/documents/空格 notes.txt'),('inbox/measurements.csv','organized/data/measurements.csv'),('inbox/opaque.bin','organized/other/opaque.bin')]:
 raw=read(dst);assert hashlib.sha256(raw).hexdigest().upper()==next(f['sha256'] for f in fixture['files'] if f['path']==src)
 files.append({'path':dst,'copyVerified':True,'bytes':len(raw)})
report=read('RESULTS.md').decode('utf-8');assert 'INVALID_JSON' in report
(evidence/'RESULTS.md').write_text(report,encoding='utf-8')
summary={'sessionId':data['sessionId'],'apkSha256':identity['apkSha256'],'scriptCalls':3,'createCalls':6,
 'originalFilesPreserved':7,'classifiedCopiesVerified':5,'journalScriptResults':[x['result'] for x in rows],
 'files':files,'artifactPath':folder+'/RESULTS.md','scope':'real Android17 model task; copies, no move/delete'}
(evidence/'task-verification.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('PASS actual model script/create/verify cycle and independent byte/hash verification',flush=True)
