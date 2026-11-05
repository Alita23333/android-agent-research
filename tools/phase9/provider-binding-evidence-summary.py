"""Offline audit of immutable host-reviewed provider/Dispatcher boundary. No model claim."""
from pathlib import Path
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/handoff/evidence/provider-binding1'
RUN = OUT / '1792301127522516900'
BASE = 'C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D'


def load(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest().upper()


identity, result = load(RUN / 'identity.json'), load(RUN / 'result.json')
assert identity['productionBefore'] == identity['productionAfter'] == BASE
assert identity['apkSha256'] == sha(RUN / 'test.apk')
assert result['verdict'] == 'PASS' and result['runId'] == RUN.name
assert result['oldHash'] != result['newHash']
for field in ['retainedHandleV1', 'tamperRejected', 'physicalReportsVerified', 'staleCarrierPinRejected']:
    assert result[field] is True
assert [row['version'] for row in result['reports']] == ['v1', 'v1', 'v2']
for index, row in enumerate(result['reports']):
    raw = (RUN / f'artifact-{index}.json').read_bytes()
    assert len(raw) == row['artifact']['size'] and b'PRIVATE_REPORT_CANARY' not in raw
    value = json.loads(raw); data = value['data']; host = data['_hostProvider']
    assert data['version'] == row['version'] and host['contentHash'] == row['contentHash']
    assert row['contentHash'] == result['newHash' if index == 2 else 'oldHash']
    assert host['backend'] == 'android-isolated-node' and host['runtimeVersion'] == 'node24.18.0'
    assert len(host['scriptSha256']) == 64 and host['toolVersion'] == '1'
    assert data['_localProvider']['replyValidated'] and data['_localProvider']['protocolVersion'] == '1.0'
    assert data['uri'].endswith('/files/private-report-canary')
    assert row['artifact']['uri'].startswith('/data/user/0/dev.alita.androidagent.isolationtest/files/artifacts/binding-probe/')
for name, digest in load(RUN / 'source-sha256.json').items():
    assert sha(ROOT / name).lower() == sha(RUN / 'source' / name).lower() == digest
assert sha(RUN / 'source/tools/phase9/provider-binding-device-acceptance.py') == identity['driverSha256']
for command in load(RUN / 'commands-and-exits.json'):
    assert command['argv'][1:3] == ['-s', 'DEVICE_ANDROID17']
    if 'install' in command['argv']: assert command['argv'][-1].endswith('app-isolationTest.apk')
    if 'force-stop' in command['argv']: assert command['argv'][-1] == 'dev.alita.androidagent.isolationtest'
candidate = ROOT / 'app/build/outputs/apk/debug/app-debug.apk'
shutil.copyfile(candidate, OUT / 'candidate.apk')
with zipfile.ZipFile(candidate) as now, zipfile.ZipFile(ROOT / 'docs/handoff/evidence/provider-service1/candidate.apk') as old:
    for name in old.namelist():
        if name.startswith(('assets/', 'lib/')) and not name.endswith('/'):
            assert now.read(name) == old.read(name), 'runtime asset/native changed: ' + name
    assert now.read('AndroidManifest.xml') == old.read('AndroidManifest.xml')
counts = {name: 0 for name in ['tests', 'failures', 'errors', 'skipped']}
for path in (ROOT / 'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
    suite = ET.parse(path).getroot()
    for name in counts: counts[name] += int(suite.get(name, 0))
    (OUT / 'unit-results').mkdir(exist_ok=True); shutil.copyfile(path, OUT / 'unit-results' / path.name)
assert counts == dict(tests=106, failures=0, errors=0, skipped=0)
for name in ['snapshot-checks.log', 'lint-final-fresh.log', 'native-fixture-build.log']:
    assert 'BUILD SUCCESSFUL' in (OUT / name).read_text(encoding='utf-8')
lint = ROOT / 'app/build/reports/lint-results-debug.txt'
assert '0 errors, 28 warnings' in lint.read_text(encoding='utf-8'); shutil.copyfile(lint, OUT / 'lint-results.txt')
assert load(OUT / 'product-postflight.json') == dict(apkSha256=BASE, phase='ready', mode='real', node='v24.18.0')
for path in [Path(__file__), ROOT / 'tools/phase9/provider-binding-postflight.py',
    ROOT / 'app/src/test/java/dev/alita/androidagent/PinnedIsolatedProviderTest.kt']:
    target = OUT / 'extra-source' / path.relative_to(ROOT); target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, target)
summary = dict(disposition='PASS_SCOPED_PINNED_PROVIDER_DISPATCH_AND_HOST_ARTIFACT; NOT_GATEWAY_MODEL_ACCEPTANCE',
    installedProductSha256=BASE, uninstalledCandidateSha256=sha(candidate), testApkSha256=identity['apkSha256'],
    run=RUN.name, unitTests=counts, lint=dict(errors=0, warnings=28), physicalReports=3,
    versions=['v1','v1','v2'], retainedV1Handle=True, stalePinAndTamperRejected=True,
    runtimeAssetNativeManifest='unchanged from product-service1 candidate; Core/Gateway/journal unchanged',
    attemptHistory='unit105 then106 PASS; first target1792300776522434400 PASS. Single-object metadata/pin snapshot fix; repeated106 and final target1792301127522516900 PASS; both retained',
    residuals=['Host review API exists; no user-facing review/grant UI or persisted admission enabled',
        'No imported provider auto-registered in AgentApplication/ZCodeHostService; test-only registration',
        'Base64<=16KiB/single pinned Node entry/data-transform only; not arbitrary shell/runtime support',
        'Pinned handles and carrier snapshot fencing proven; no persisted session-to-provider pin binding accepted',
        'Existing Gateway unknown-tool PRIVILEGED ceiling unchanged; no new READ classification',
        'bootstrap exact native-provider journal result completion remains text_digest-only; must extend/test before model exposure',
        'Real Core model/Gateway journal/force-stop/session-resume vertical slice still pending',
        'A report proves delivered bytes/provenance, not correctness of an arbitrary transformation',
        'Worker wire-ID duplicate guard added; no live Core registration collision run in this increment',
        'Android15/root/Shizuku untouched; ZCode recording-only task unchanged'])
(OUT / 'acceptance-summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
print(json.dumps({name: summary[name] for name in ['disposition','uninstalledCandidateSha256','testApkSha256','unitTests']}))
