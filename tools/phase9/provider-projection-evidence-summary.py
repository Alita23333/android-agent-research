"""Verify final scoped acceptance and freeze the uninstalled candidate. No device actions."""
from pathlib import Path
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/handoff/evidence/provider-projection1'
device = OUT / __import__('sys').argv[1]
assert device.parent == OUT and device.is_dir()
sha = lambda b: hashlib.sha256(b).hexdigest().upper()
candidate = ROOT / 'app/build/outputs/apk/debug/app-debug.apk'
previous = ROOT / 'docs/handoff/evidence/provider-review1/candidate.apk'
new_module = 'assets/zcode-runtime/provider-review-bindings.cjs'
allowed = {'assets/zcode-runtime/'+name for name in ['bootstrap.cjs','skill-session-bindings.cjs',
    'carrier-authorization.cjs','runtime-manifest.json','payload-SHA256SUMS.txt']}
allowed.add('assets/isolated-provider-runtime.json')
with zipfile.ZipFile(previous) as old, zipfile.ZipFile(candidate) as new:
    important = lambda names: {n for n in names if n.startswith(('assets/','lib/')) or n == 'AndroidManifest.xml'}
    old_names,new_names = important(old.namelist()),important(new.namelist())
    assert new_names-old_names == {new_module} and old_names-new_names == set()
    changed = sorted(n for n in old_names if old.read(n) != new.read(n))
    assert set(changed) == allowed, changed
    pins = new.read('assets/zcode-runtime/payload-SHA256SUMS.txt').decode().splitlines()
    for line in pins:
        expected,name = line.split('  ',1)
        assert sha(new.read(name.replace('jniLibs/','lib/',1))).lower() == expected
    assert json.loads(new.read('assets/zcode-runtime/runtime-manifest.json'))['productRevision'] == 'provider-projection1-session-routing-candidate'
    # The tested separate APK must contain exactly the same runtime/native/production manifest assets.
    with zipfile.ZipFile(device/'test.apk') as test:
        assert all(new.read(name) == test.read(name) for name in new_names if name != 'AndroidManifest.xml')
identity = json.loads((device/'identity.json').read_text())
result = json.loads((device/'result.json').read_text())
assert result['verdict'] == 'PASS_SCOPED_CORE_GATEWAY_PROVIDER_TRANSPORT'
assert sha((device/'test.apk').read_bytes()) == identity['testApk']
for name,expected in json.loads((device/'source-sha256.json').read_text()).items():
    assert sha((ROOT/name).read_bytes()).lower() == expected, name
counts = dict(tests=0,failures=0,errors=0,skipped=0)
for file in (ROOT/'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
    row = ET.parse(file).getroot()
    for name in counts: counts[name] += int(row.attrib[name])
    dest = OUT/'unit-tests'/file.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(file,dest)
assert counts == dict(tests=118,failures=0,errors=0,skipped=0)
for name in ['build-final.log','lint.log']:
    assert 'BUILD SUCCESSFUL' in (OUT/name).read_text('utf-8')
lint = (ROOT/'app/build/reports/lint-results-debug.txt').read_text('utf-8')
assert '0 errors, 28 warnings' in lint
host = (OUT/'boundary-tests.log').read_text('utf-8')
android = (device/'android-boundary-tests.log').read_text('utf-8')
assert all(x in host for x in ['# tests 36','# pass 35','# fail 0','# skipped 1'])
assert all(x in android for x in ['# tests 36','# pass 36','# fail 0','# skipped 0'])
assert 'RESULT 22 PASS' in (OUT/'settlement-regression.log').read_text('utf-8')
baseline = 'C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D'
assert identity['productionBefore'] == identity['productionAfter'] == baseline
reports=[]
for i,expected in enumerate(['v1','v1','v2']):
    artifact = json.loads((device/f'artifact-{i}.json').read_text('utf-8'));data=artifact['data']
    row=result['reports'][i];pin=result['newPin'] if i==2 else result['oldPin']
    assert data['version']==expected and data['bytes']==5 and data['sha256']==hashlib.sha256(b'hello').hexdigest()
    assert 90000<=data['uid']<=99999
    assert data['_hostProvider']['contentHash']==pin['contentHash'] and data['_hostProvider']['definitionHash']==pin['definitionHash']
    assert row['approval']['risk']=='PRIVILEGED' and row['approval']['hardConfirm'] is False
    matches=[op for op in row['operations'] if 'call_id='+artifact['callId']+' ' in op['detail']]
    assert len(matches)==1 and matches[0]['decision']=='allow' and matches[0]['result']=='ok'
    assert 'provider_sha256='+pin['contentHash'] in matches[0]['detail'] and 'declaration_sha256='+pin['definitionHash'] in matches[0]['detail']
    reports.append(dict(callId=artifact['callId'],sessionId=row['sessionId'],operationId=matches[0]['id'],version=expected,
        uid=data['uid'],pid=data['pid'],artifactSha256=sha((device/f'artifact-{i}.json').read_bytes())))
summary=dict(disposition='PASS_SCOPED_CORE_GATEWAY_PROVIDER_TRANSPORT',deviceRun=device.name,
    installedProductSha256=baseline,hostReadiness='NOT_VERIFIED; no production restart/install or readiness request',
    candidateSha256=sha(candidate.read_bytes()),previousCandidateSha256=sha(previous.read_bytes()),testApkSha256=identity['testApk'],
    changedApkAssets=changed,addedApkAssets=[new_module],payloadHashRows=len(pins),
    payloadManifestSha256=sha((ROOT/'app/src/main/assets/zcode-runtime/payload-SHA256SUMS.txt').read_bytes()),
    runtimeManifestSha256=sha((ROOT/'app/src/main/assets/zcode-runtime/runtime-manifest.json').read_bytes()),
    unitTests=counts,hostBoundary=dict(tests=36,passed=35,failed=0,skipped=1,skipReason='Windows file symlink privilege unavailable'),
    androidBoundary=dict(tests=36,passed=36,failed=0,skipped=0),settlementRegressionChecks=22,lint=dict(errors=0,warnings=28),
    physicalReports=reports,remaining=['Explicit user provider review/admission UI and startup enrollment',
        'Real model-issued imported provider tool call/final answer', 'Full host/force-stop restart and imported-provider cancellation acceptance',
        'Production APK installation and final acceptance'])
shutil.copy2(candidate,OUT/'candidate.apk');shutil.copy2(ROOT/'app/build/reports/lint-results-debug.txt',OUT/'lint-results-debug.txt')
(OUT/'acceptance-summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,indent=2))
