"""Offline audit/freeze of product-code backend in distinct isolationTest application ID."""
from pathlib import Path
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/handoff/evidence/provider-service1'
RUN = OUT / '1792299540959343800'
ACCEPTED = 'C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D'


def load(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest().upper()


identity, result = load(RUN / 'identity.json'), load(RUN / 'result.json')
assert identity['productionBefore'] == identity['productionAfter'] == ACCEPTED
assert sha(RUN / 'test.apk') == identity['apkSha256']
assert result['verdict'] == 'PASS' and result['runId'] == RUN.name
assert result['processes'] == 4 and len(result['identities']) == 4
assert all(row['isolated'] and not row['graphInitialized'] and row['uid'] != result['ownerUid'] for row in result['identities'])
assert len({row['uid'] for row in result['identities']}) == 4
for field in ['ownerGraphInitialized', 'nonExecutingDiscovery', 'ownerNetworkPositiveControl',
              'resourceReadback', 'instanceExclusion', 'cancelAndRecovery', 'wallLimitDeath', 'wrongScriptPinRejected']:
    assert result[field] is True
assert result['naturalExit'] == 0
for name in ['firstResult', 'secondResult']:
    data = result[name]
    assert data['node'] == 'v24.18.0' and data['unicode'] == '安卓🧪'
    assert data['privateRead'] == data['privateWrite'] == dict(allowed=False, code='ENOENT')
    assert data['network'] == dict(allowed=False, code='EACCES')
    assert data['sha256'] == hashlib.sha256(b'product-service-fixture').hexdigest()
    assert data['fdLimits'] == ['512', '512'] and data['coreLimits'] == ['0', '0']
    assert data['envKeys'] == ['HOME', 'OPENSSL_CONF', 'PATH'] and data['heapLimit'] == 92274688
    assert data['_localProvider']['replyValidated'] and data['_localProvider']['protocolVersion'] == '1.0'
assert result['firstResult']['_localProvider']['processInstanceId'] != result['secondResult']['_localProvider']['processInstanceId']
sources = load(RUN / 'source-sha256.json')
for name, digest in sources.items():
    assert sha(ROOT / name).lower() == sha(RUN / 'source' / name).lower() == digest
assert sha(RUN / 'source/tools/phase9/provider-service-device-acceptance.py') == identity['driverSha256']
for command in load(RUN / 'commands-and-exits.json'):
    assert command['argv'][1:3] == ['-s', 'DEVICE_ANDROID17']
    if 'install' in command['argv']: assert command['argv'][-1].endswith('app-isolationTest.apk')
    if 'force-stop' in command['argv']: assert command['argv'][-1] == 'dev.alita.androidagent.isolationtest'
candidate = ROOT / 'app/build/outputs/apk/debug/app-debug.apk'
shutil.copyfile(candidate, OUT / 'candidate.apk')
with zipfile.ZipFile(candidate) as now, zipfile.ZipFile(ROOT / 'docs/handoff/evidence/provider-package1/candidate.apk') as old:
    for name in old.namelist():
        if name.startswith(('assets/', 'lib/')) and not name.endswith('/'):
            assert now.read(name) == old.read(name), 'existing runtime bytes changed: ' + name
    assert 'assets/provider-service-fixture.cjs' not in now.namelist()
    manifest = json.loads(now.read('assets/isolated-provider-runtime.json'))
    assert manifest == identity['runtime']
    for library in manifest['libraries']:
        assert hashlib.sha256(now.read('lib/arm64-v8a/'+library['packagedName'])).hexdigest() == library['sha256']
    assert hashlib.sha256(now.read('lib/arm64-v8a/libisolatednode.so')).hexdigest() == manifest['shimSha256']
    assert hashlib.sha256(now.read('assets/zcode-runtime/payload-SHA256SUMS.txt')).hexdigest() == manifest['payloadManifestSha256']
android = '{http://schemas.android.com/apk/res/android}'
debug_manifest = ROOT / 'app/build/intermediates/merged_manifests/debug/processDebugManifest/AndroidManifest.xml'
product = ET.parse(debug_manifest).getroot()
assert product.attrib['package'] == 'dev.alita.androidagent'
assert not any('ServiceProbeActivity' in item.attrib[android+'name'] for item in product.findall('application/activity'))
service = next(item for item in product.findall('application/service') if item.attrib[android+'name'].endswith('IsolatedNodeService'))
assert service.attrib[android+'exported'] == 'false' and service.attrib[android+'isolatedProcess'] == 'true'
shutil.copyfile(debug_manifest, OUT / 'product-manifest.xml')
loads = [int(line.split()[-1], 16) for line in (RUN / 'shim-elf.txt').read_text().splitlines() if line.strip().startswith('LOAD')]
assert loads and all(alignment >= 16384 for alignment in loads)
counts = {name: 0 for name in ['tests', 'failures', 'errors', 'skipped']}
for path in (ROOT / 'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
    suite = ET.parse(path).getroot()
    for name in counts: counts[name] += int(suite.get(name, 0))
    (OUT / 'unit-results').mkdir(exist_ok=True); shutil.copyfile(path, OUT / 'unit-results' / path.name)
assert counts == dict(tests=96, failures=0, errors=0, skipped=0)
for name in ['final-checks.log', 'lint-fresh.log']:
    assert 'BUILD SUCCESSFUL' in (OUT / name).read_text(encoding='utf-8')
lint = ROOT / 'app/build/reports/lint-results-debug.txt'
assert '0 errors, 28 warnings' in lint.read_text(encoding='utf-8'); shutil.copyfile(lint, OUT / 'lint-results.txt')
postflight = load(OUT / 'product-postflight.json')
assert postflight == dict(apkSha256=ACCEPTED, phase='ready', mode='real', node='v24.18.0')
extra_sources = [Path(__file__), ROOT / 'tools/phase9/provider-service-postflight.py',
    ROOT / 'app/src/test/java/dev/alita/androidagent/execution/isolation/IsolatedNodeEndpointTest.java']
for path in extra_sources:
    target = OUT / 'extra-source' / path.relative_to(ROOT); target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, target)
failures = ['1792299203409274200', '1792299279992218100', '1792299374367559300']
assert all(load(OUT / run / 'result.json')['verdict'] == 'FAIL' for run in failures)
assert load(OUT / '1792299429577716000/result.json')['verdict'] == 'PASS'
summary = dict(disposition='PASS_SCOPED_PRODUCT_ISOLATED_BACKEND; NOT_MODEL_ADMISSION_OR_PRODUCTION_INSTALL',
    installedProductSha256=ACCEPTED, uninstalledCandidateSha256=sha(candidate), testApkSha256=identity['apkSha256'],
    run=RUN.name, unitTests=counts, lint=dict(errors=0, warnings=28), graphIsolation='actual product Application+Service classes in distinct application ID',
    processes=4, nativeLoadAlignments=loads, resourceReadback=dict(fdSoftHard=[512,512], coreSoftHard=[0,0], v8HeapBytes=92274688),
    originalRuntimeAssetsAndNative='all pre-existing C51 asset/native bytes unchanged; additional isolated manifest/dependencies/shim',
    attemptHistory=dict(failedRuns=failures, rootCause='FD128 below full Android startup baseline; A/B512 succeeds, then resource readback passes',
        earlierPass='1792299429577716000', firstLintFailure='two API33 InputStream calls with min31; replaced by bounded compatible read'),
    residuals=['No model-issued imported-provider, Gateway/journal/artifact/version-pinning vertical slice accepted',
        'Product candidate not installed; actual backend acceptance uses separate isolationTest ID with exact product classes',
        'Resource limits bound FDs/core/V8 old+semi heap/CPU/wall; not total Android/native RSS or complete descendant containment',
        'Before START dispatch: close gate/unbind means no code dispatched, not proof idle Android process death; after START wait for Binder death',
        'Host process-death linkage present but not independently injected in this run',
        'Nonblocking host binding required; no arbitrary third-party Binder/native code allowed in host',
        'Node Start ABI pinned24.18.0; generated build requires resolved Python/Clang, no runtime download',
        'Wall death exit70 means unreported termination, not kernel exit status or a new public error contract',
        'Android15, root, Shizuku untouched; existing ZCode recording-only task unchanged'])
(OUT / 'acceptance-summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
print(json.dumps({name: summary[name] for name in ['disposition','uninstalledCandidateSha256','testApkSha256','unitTests']}))
