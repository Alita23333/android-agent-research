"""Freeze scoped admission/UI/restart evidence, without devices or incoming execution."""
from pathlib import Path
import hashlib,json,shutil,xml.etree.ElementTree as ET,zipfile

ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'docs/handoff/evidence/provider-admission1'
device=OUT/'1792760006423232400';ui=OUT/'ui-1792760188831031400'
sha=lambda data:hashlib.sha256(data).hexdigest().upper()
candidate=ROOT/'app/build/outputs/apk/debug/app-debug.apk'
previous=ROOT/'docs/handoff/evidence/provider-projection1/candidate.apk'
with zipfile.ZipFile(previous) as old,zipfile.ZipFile(candidate) as new,zipfile.ZipFile(device/'test.apk') as test:
    names={n for n in new.namelist() if n.startswith(('assets/','lib/')) or n=='AndroidManifest.xml'}
    assert names=={n for n in old.namelist() if n.startswith(('assets/','lib/')) or n=='AndroidManifest.xml'}
    assert all(new.read(n)==old.read(n) for n in names),'Unexpected runtime/native/main manifest delta'
    assert all(new.read(n)==test.read(n) for n in names if n!='AndroidManifest.xml')
    pins=new.read('assets/zcode-runtime/payload-SHA256SUMS.txt').decode().splitlines()
    for line in pins:
        expected,name=line.split('  ',1);assert sha(new.read(name.replace('jniLibs/','lib/',1))).lower()==expected
identity=json.loads((device/'identity.json').read_text());result=json.loads((device/'result.json').read_text())
assert sha((device/'test.apk').read_bytes())==identity['testApk']
assert result['verdict']=='PASS_SCOPED_ADMISSION_CORE_RESTART_TRANSPORT'
assert all(result['checks'][k] is True for k in ['inertImport','previewInert','approveDeferred','activeMutationsRejected',
    'firstStopQuiescent','registryRemovedOnStop','secondStopQuiescent','oldPinRetainedAcrossRestart'])
for name,value in json.loads((device/'source-sha256.json').read_text()).items():
    if name.startswith('app/') or name=='tools/phase9/provider-admission-device-acceptance.py':
        assert sha((ROOT/name).read_bytes()).lower()==value,name
counts=dict(tests=0,failures=0,errors=0,skipped=0)
for file in (ROOT/'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
    row=ET.parse(file).getroot()
    for k in counts:counts[k]+=int(row.attrib[k])
    target=OUT/'unit-tests'/file.name;target.parent.mkdir(exist_ok=True);shutil.copy2(file,target)
assert counts==dict(tests=134,failures=0,errors=0,skipped=0)
assert 'BUILD SUCCESSFUL' in (OUT/'build-repaired-final.log').read_text('utf-8')
assert 'BUILD SUCCESSFUL' in (OUT/'build-probe-reader-repair.log').read_text('utf-8')
lint=(ROOT/'app/build/reports/lint-results-debug.txt').read_text('utf-8');assert '0 errors, 28 warnings' in lint
uiresult=json.loads((ui/'result.json').read_text());assert uiresult['verdict']=='PASS_UI_PREVIEW_CANCEL_ONLY'
assert uiresult['reviewSha256Before']==uiresult['reviewSha256After']
assert uiresult['driverSha256'].upper()==sha((ROOT/'tools/phase9/provider-admission-ui-smoke.py').read_bytes())
shutil.copy2(ROOT/'tools/phase9/provider-admission-ui-smoke.py',ui/'driver-frozen-after-run.py')
reports=[]
for i,version in enumerate(['v1','v1','v2']):
    report=(device/f'artifact-{i}.json').read_bytes();physical=json.loads(report);data=physical['data']
    row=result['reports'][i];pin=result['newPin'] if i==2 else result['oldPin']
    assert data['version']==version and data['bytes']==5 and data['sha256']==hashlib.sha256(b'hello').hexdigest()
    assert 90000<=data['uid']<=99999
    assert data['_hostProvider']['contentHash']==pin['contentHash'] and data['_hostProvider']['definitionHash']==pin['definitionHash']
    ops=[r for r in row['operations'] if 'call_id='+physical['callId']+' ' in r['detail']]
    assert len(ops)==1 and ops[0]['decision']=='allow' and ops[0]['result']=='ok'
    assert 'declaration_sha256='+pin['definitionHash'] in ops[0]['detail']
    reports.append(dict(version=version,callId=physical['callId'],sessionId=row['sessionId'],operationId=ops[0]['id'],
        uid=data['uid'],pid=data['pid'],artifactSha256=sha(report)))
assert len(result['shutdowns'])==2
for stopped in result['shutdowns']:
    assert all(stopped[k] is True for k in ['workerStopReturned','workerQuiescent','childStopped','bootstrapStopped','quiescent','leaseReleased'])
baseline='C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D'
assert identity['productionBefore']==identity['productionAfter']==baseline
summary=dict(disposition='PASS_SCOPED_EXPLICIT_ADMISSION_AND_CONTROLLED_CORE_RESTART_TRANSPORT',
    candidateSha256=sha(candidate.read_bytes()),previousCandidateSha256=sha(previous.read_bytes()),
    installedProductSha256=baseline,testApkSha256=identity['testApk'],deviceRun=device.name,uiRun=ui.name,
    payloadHashRows=len(pins),importantApkAssetNativeManifestDelta=[],runtimeVersion='0.16.9-runtime5',
    unitTests=counts,newAdmissionTests=12,newWorkerLifecycleTests=4,lint=dict(errors=0,warnings=28),
    deviceChecks=result['checks'],physicalReports=reports,shutdowns=result['shutdowns'],ui=uiresult,
    failedDeviceAttempts=['1792759464379526800','1792759831813604200'],
    failureExplanation='Both probe processes died from uncaught diagnostic-reader InterruptedIOException during teardown (owner logcat retained). Recorded stale RUNNING is not a hung-worker diagnosis. Independent synchronous-interrupt blocker fix verified by dedicated JVM test.',
    remaining=['Real production HostService stop/start with old Core/MCP descendant exit measurement (probe explicitly signals its owned Core child)',
        'Actual UI confirmation approval/retire/revoke taps (UI smoke covers preview/back/cancel only)',
        'Real model-issued imported-provider call and final answer, cancellation and force-stop/resume',
        'Production APK installation and final product acceptance'])
shutil.copy2(candidate,OUT/'candidate.apk');shutil.copy2(ROOT/'app/build/reports/lint-results-debug.txt',OUT/'lint-results-debug.txt')
(OUT/'acceptance-summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,indent=2))
