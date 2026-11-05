"""Freeze this bounded increment; verify candidate delta, payload pins and test evidence."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/handoff/evidence/provider-review1'
ADB = os.environ['ANDROID_ADB']
commands = []


def digest(data):
    return hashlib.sha256(data).hexdigest().upper()


def run(*args, credential=False):
    argv = [ADB, '-s', 'DEVICE_ANDROID17', *args]
    p = subprocess.run(argv, capture_output=True, timeout=20)
    commands.append(dict(argv=argv, exit=p.returncode,
        stdout='<credential withheld>' if credential else p.stdout.decode('utf-8', 'replace'),
        stderr=p.stderr.decode('utf-8', 'replace')))
    (OUT / 'postflight-commands.json').write_text(json.dumps(commands, indent=2)+'\n', encoding='utf-8')
    assert p.returncode == 0, 'postflight failed; credential output withheld'
    return p.stdout


candidate = ROOT / 'app/build/outputs/apk/debug/app-debug.apk'
previous = ROOT / 'docs/handoff/evidence/provider-session1/candidate.apk'
allowed = {'assets/zcode-runtime/' + name for name in ['runtime-manifest.json', 'payload-SHA256SUMS.txt']}
allowed.add('assets/isolated-provider-runtime.json')
with zipfile.ZipFile(previous) as old, zipfile.ZipFile(candidate) as new:
    names = [n for n in new.namelist() if n.startswith(('assets/', 'lib/')) or n == 'AndroidManifest.xml']
    assert set(names) == {n for n in old.namelist() if n.startswith(('assets/', 'lib/')) or n == 'AndroidManifest.xml'}
    changed = sorted(n for n in names if old.read(n) != new.read(n))
    assert set(changed) == allowed, changed
    pins = new.read('assets/zcode-runtime/payload-SHA256SUMS.txt').decode('utf-8').splitlines()
    for line in pins:
        expected, name = line.split('  ', 1)
        apk_name = name.replace('jniLibs/', 'lib/', 1)
        assert digest(new.read(apk_name)).lower() == expected
    assert new.read('assets/zcode-runtime/gateway.cjs') == old.read('assets/zcode-runtime/gateway.cjs')
    assert new.read('assets/zcode-runtime/contracts/journal.sql') == old.read('assets/zcode-runtime/contracts/journal.sql')
    assert json.loads(new.read('assets/zcode-runtime/runtime-manifest.json'))['productRevision'] == 'provider-review1-resolver-candidate'
counts = dict(tests=0, failures=0, errors=0, skipped=0)
xmls = list((ROOT / 'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'))
assert xmls
for file in xmls:
    row = ET.parse(file).getroot()
    for key in counts:
        counts[key] += int(row.attrib[key])
assert counts == dict(tests=118, failures=0, errors=0, skipped=0), counts
assert 'BUILD SUCCESSFUL' in (OUT / 'build.log').read_text('utf-8')
assert 'BUILD SUCCESSFUL' in (OUT / 'build-r2.log').read_text('utf-8')
assert 'BUILD SUCCESSFUL' in (OUT / 'test-build-final.log').read_text('utf-8')
assert 'BUILD SUCCESSFUL' in (OUT / 'lint-fresh.log').read_text('utf-8')
lint = (ROOT / 'app/build/reports/lint-results-debug.txt').read_text('utf-8')
assert '0 errors, 28 warnings' in lint
device = OUT / '1792729522969096400'
identity = json.loads((device / 'identity.json').read_text('utf-8'))
result = json.loads((device / 'result.json').read_text('utf-8'))
assert result['verdict'] == 'PASS'
for field in ['restoredReviewV1','retirementPreservedPin','revocationRejected','tamperRejected','physicalReportsVerified','staleCarrierPinRejected','indexLinkRejected','workspaceLinkRejected','reviewLinkRejected']:
    assert result[field] is True
assert [row['version'] for row in result['reports']] == ['v1','v1','v2']
for name, expected in json.loads((device / 'source-sha256.json').read_text('utf-8')).items():
    assert digest((ROOT/name).read_bytes()).lower() == expected
assert digest((device/'test.apk').read_bytes()) == identity['apkSha256']
baseline = 'C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D'
apk = run('shell', 'pm', 'path', 'dev.alita.androidagent').decode().strip().removeprefix('package:')
assert run('shell', 'run-as', 'dev.alita.androidagent', 'sha256sum', apk).decode().split()[0].upper() == baseline
run('forward', 'tcp:18765', 'tcp:8765')
token = run('exec-out', 'run-as', 'dev.alita.androidagent', 'cat', 'files/runtime/bridge-token', credential=True).decode().strip()
try:
    with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:18765/status', headers={'X-Bridge-Token':token}), timeout=5) as response:
        status = json.load(response)
    safe = dict(apkSha256=baseline, phase=status.get('phase'), mode=status.get('mode'), node=status.get('nodeVersion', status.get('node')))
    assert safe == dict(apkSha256=baseline, phase='ready', mode='real', node='v24.18.0')
except (OSError, __import__('http.client', fromlist=['RemoteDisconnected']).RemoteDisconnected) as error:
    # Artifact/source acceptance must not imply installed-host readiness.
    # Keep this unavailable state explicit; never upgrade it to a green baseline.
    safe = dict(apkSha256=baseline, phase='UNAVAILABLE_NO_HTTP_RESPONSE', errorType=type(error).__name__,
                readiness='NOT_VERIFIED; no HTTP response on read-only postflight, no production restart performed this increment')
(OUT / 'product-postflight.json').write_text(json.dumps(safe, indent=2)+'\n', encoding='utf-8')
reviews = json.loads(run('exec-out', 'run-as', 'dev.alita.androidagent.isolationtest', 'cat', 'files/provider-reviews.json'))
entries = [entry for entry in reviews['reviews'] if entry['snapshot']['id'] == result['providerId']]
assert len(entries) == 2
assert not any(pin['id'] == result['providerId'] for pin in reviews['selected'])
assert next(entry for entry in entries if entry['snapshot']['contentHash'] == result['oldHash'])['revoked'] is True
import base64
input_bytes = base64.b64decode('5a6J5Y2T8J+nqg==')
for i in range(3):
    artifact = json.loads((device / ('artifact-'+str(i)+'.json')).read_text('utf-8'))
    data = artifact['data']; pin = data['_hostProvider']
    entry = next(entry for entry in entries if entry['snapshot']['contentHash'] == pin['contentHash'])
    assert pin['definitionHash'] == entry['snapshot']['definitionHash']
    assert data['version'] == ['v1','v1','v2'][i] and data['bytes'] == len(input_bytes)
    assert data['sha256'].upper() == digest(input_bytes)
    assert 90000 <= data['uid'] <= 99999
    assert 'PRIVATE_REPORT_CANARY' not in json.dumps(artifact)
(OUT / 'physical-review-records.json').write_text(json.dumps(entries, indent=2)+'\n', encoding='utf-8')
shutil.copy2(candidate, OUT / 'candidate.apk')
shutil.copy2(ROOT / 'app/build/reports/lint-results-debug.txt', OUT / 'lint-results-debug.txt')
for file in xmls:
    destination = OUT / 'unit-tests' / file.name
    destination.parent.mkdir(exist_ok=True)
    shutil.copy2(file, destination)
files = [ROOT/'tools/phase9/provider-review-device-acceptance.py', Path(__file__)]
files += [ROOT/'app/src/main/java/dev/alita/androidagent'/name for name in ['AgentApplication.kt',
 'tools/LocalProviderCatalog.kt','tools/PinnedIsolatedProvider.kt','tools/ProviderReviewStore.kt',
 'zcode/adapter/AndroidToolContracts.kt','zcode/adapter/ReadOnlyToolDispatcher.kt','zcode/adapter/ZCodeToolMapping.kt',
 'zcode/runtime/ZCodeCarrierWorker.kt']]
files += [ROOT/'app/src/test/java/dev/alita/androidagent/ProviderReviewStoreTest.kt',
 ROOT/'app/src/isolationTest/java/dev/alita/androidagent/execution/isolation/ReviewProbeActivity.kt',
 ROOT/'app/src/isolationTest/AndroidManifest.xml']
hashes = {}
for file in files:
    relative = file.relative_to(ROOT).as_posix()
    hashes[relative] = digest(file.read_bytes())
    destination = OUT / 'sources' / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file, destination)
summary = dict(disposition='PASS_SCOPED_ACTUAL_CATALOG_REVIEW_AND_SESSION_RESOLVER_EXECUTION; NOT_MODEL_GATEWAY_ACCEPTANCE',
    candidateSha256=digest(candidate.read_bytes()), installedProductSha256=baseline,
    previousCandidateSha256=digest(previous.read_bytes()), changedApkAssets=changed,
    payloadHashRows=len(pins), unitTests=counts, lint=dict(errors=0,warnings=28),
    newReviewUnitTests=12, physicalArtifactReports=3, versionSequence=['v1','v1','v2'], testApkSha256=identity['apkSha256'], deviceRun=device.name, sourceHashes=hashes,
    installedHostPostflight=safe,
    remaining=['Production bootstrap verifier/selection adapter and old-session carrier metadata routing', 'Explicit user review UI and startup registration',
               'Real model/carrier/Dispatcher/Gateway/provider/artifact vertical acceptance', 'Production installation'])
(OUT / 'acceptance-summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
print(json.dumps(summary))
