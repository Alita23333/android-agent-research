"""Freeze/audit the cancellable startup increment; never operates a device."""
from pathlib import Path
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/handoff/evidence/provider-startup1'
RUN = OUT / '1792298608451768900'


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


identity, result = load(RUN / 'identity.json'), load(RUN / 'result.json')
accepted = 'C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D'
assert identity['productionBefore'] == identity['productionAfter'] == {'apkSha256': accepted}
assert result['verdict'] == 'PASS' and result['runId'] == RUN.name
assert sha(RUN / 'probe.apk') == identity['apkSha256']
sources = load(RUN / 'source-sha256.json')
for relative, digest in sources.items():
    assert sha(ROOT / relative).lower() == sha(RUN / 'source' / relative).lower() == digest
assert sha(RUN / 'source/tools/phase9/provider-isolation-device-probe.py') == identity['driverSha256']
data = result['toolResult']['data']
assert data['uid'] == result['isolatedUid'] != result['ownerUid']
assert data['node'] == 'v24.18.0' and result['stderr'] == ''
assert data['privateRead'] == data['privateWrite'] == {'allowed': False, 'code': 'ENOENT'}
assert data['network'] == {'allowed': False, 'code': 'EACCES'}
assert result['ownerNetworkPositiveControl'] and result['privateSentinelUnchanged']
assert data['sha256'] == hashlib.sha256(b'isolation-fixture').hexdigest()
assert result['facadeWaitFor'] and result['facadeExit'] == 137
assert result['facadeClass'] == 'dev.alita.androidagent.execution.IsolatedProviderProcess'
assert result['cancelDeathMs'] < 2500 and result['protocolReplies'] == 2
assert result['initializeResult']['protocolVersion'] == '1.0'
for command in load(RUN / 'commands-and-exits.json'):
    assert command['argv'][1:3] == ['-s', 'DEVICE_ANDROID17']
    if 'install' in command['argv']:
        assert command['argv'][-1].endswith('ProviderIsolationProbe-debug.apk')
    if 'force-stop' in command['argv']:
        assert command['argv'][-1] == 'dev.alita.providerprobe'
with zipfile.ZipFile(RUN / 'probe.apk') as apk:
    for library in identity['payload']['libraries']:
        assert hashlib.sha256(apk.read('lib/arm64-v8a/' + library['packagedName'])).hexdigest() == library['sha256']
        assert sha(ROOT / 'app/src/main' / library['source']).lower() == library['sha256']
tests = []
for path in sorted((ROOT / 'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml')):
    node = ET.parse(path).getroot()
    tests.append(dict(name=node.attrib['name'], **{key: int(node.get(key, 0)) for key in ['tests', 'failures', 'errors', 'skipped']}))
    (OUT / 'unit-results').mkdir(exist_ok=True)
    shutil.copyfile(path, OUT / 'unit-results' / path.name)
counts = {key: sum(row[key] for row in tests) for key in ['tests', 'failures', 'errors', 'skipped']}
assert counts == dict(tests=86, failures=0, errors=0, skipped=0)
for name in ['product-checks.log', 'lint-fresh.log', 'probe-final-build.log']:
    assert 'BUILD SUCCESSFUL' in (OUT / name).read_text(encoding='utf-8')
lint = ROOT / 'app/build/reports/lint-results-debug.txt'
assert '0 errors, 28 warnings' in lint.read_text(encoding='utf-8')
shutil.copyfile(lint, OUT / 'lint-results.txt')
candidate = ROOT / 'app/build/outputs/apk/debug/app-debug.apk'
shutil.copyfile(candidate, OUT / 'candidate.apk')
with zipfile.ZipFile(candidate) as now, zipfile.ZipFile(ROOT / 'docs/handoff/evidence/provider-package1/candidate.apk') as old:
    for name in old.namelist():
        if name.startswith(('assets/', 'lib/')) and not name.endswith('/'):
            assert now.read(name) == old.read(name), 'runtime/asset changed: ' + name
    assert now.read('AndroidManifest.xml') == old.read('AndroidManifest.xml')
for relative in ['app/src/main/java/dev/alita/androidagent/execution/IsolatedProviderProcess.java',
                 'app/src/main/java/dev/alita/androidagent/tools/JsonRpcStdioProvider.kt',
                 'app/src/test/java/dev/alita/androidagent/IsolatedProviderProcessTest.java',
                 'app/src/test/java/dev/alita/androidagent/LocalProviderBoundaryTest.kt',
                 'tools/phase9/provider-startup-evidence-summary.py',
                 'app/src/main/java/dev/alita/androidagent/AgentApplication.kt',
                 'app/src/test/java/dev/alita/androidagent/IsolatedApplicationTest.java']:
    target = OUT / 'product-source' / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / relative, target)
postflight = load(OUT / 'product-postflight.json')
assert postflight == dict(apkSha256=accepted, phase='ready', mode='real', node='v24.18.0')
startup_run = OUT / '1792298603781943800'
startup_identity, startup = load(startup_run / 'identity.json'), load(startup_run / 'result.json')
assert startup['verdict'] == 'PASS' and startup['runId'] == startup_run.name
assert startup['stage'] == 'cancel_during_real_isolated_service_startup'
assert startup['startupCancelled'] and startup['isIsolated'] and startup['readyCount'] == 0
assert startup['ownerUid'] != startup['isolatedUid'] and startup['startupDelayMs'] == 3000
assert startup['cancelDeathMs'] < 2500
assert 0 <= startup['serviceAgeAtDeathMs'] < startup['startupDelayMs']
assert startup_identity['apkSha256'] == identity['apkSha256'] == sha(startup_run / 'probe.apk')
assert startup_identity['productionBefore'] == startup_identity['productionAfter'] == {'apkSha256': accepted}
for relative, digest in load(startup_run / 'source-sha256.json').items():
    assert sha(ROOT / relative).lower() == sha(startup_run / 'source' / relative).lower() == digest
for command in load(startup_run / 'commands-and-exits.json'):
    assert command['argv'][1:3] == ['-s', 'DEVICE_ANDROID17']
    if 'install' in command['argv']: assert command['argv'][-1].endswith('ProviderIsolationProbe-debug.apk')
    if 'force-stop' in command['argv']: assert command['argv'][-1] == 'dev.alita.providerprobe'
summary = dict(disposition='PASS_SCOPED_CANCELLABLE_STARTUP; NOT_PRODUCTION_ADMISSION',
    startupRun=startup_run.name, startupCancelDeathMs=startup['cancelDeathMs'], serviceAgeAtDeathMs=startup['serviceAgeAtDeathMs'],
    isolatedApplicationGuard='Robolectric isolated Process shadow; real target service reports isIsolated true; product service not enabled',
    installedProductSha256=accepted, uninstalledCandidateSha256=sha(candidate),
    probeApkSha256=identity['apkSha256'], run=RUN.name, counts=counts, suites=tests,
    lint=dict(errors=0, warnings=28), cancelDeathMs=result['cancelDeathMs'],
    ownerUid=result['ownerUid'], isolatedUid=result['isolatedUid'],
    facadeExit=137, exitMeaning='host-mapped cancellation after Binder death, not kernel waitpid status',
    productionAssetsAndNativeLibrariesAndManifest='byte-identical to C51',
    attemptHistory='unit-first PASS84; final PASS86. Initial target pair PASS. Added cross-process elapsed clock proof; rebuilt and final pair PASS; all4 runs retained',
    residuals=['Binder endpoint and delayed-start fixture remain experiment-only; no product service/admission enabled',
        'Application graph guard is source/Robolectric proof, not actual product-isolated-service acceptance',
        'Cancellable factory must be host-owned and cooperate with signal; arbitrary blocking legacy factory not made cancellable',
        'Node scripts are not started in delayed-start test (death before 3s delay; readyCount0); no generic plugin sandbox guarantee',
        'Partial pipe construction failure, null binding, late bind and all cleanup races still require hardened product endpoint tests',
        'CPU/memory/descendant constraints and concurrent instances not proven',
        'No real model/Gateway/artifact/imported-provider vertical slice accepted',
        'No Android15 action or new ZCode task; recording-only supplement unchanged'])
(OUT / 'acceptance-summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: summary[k] for k in ['disposition', 'uninstalledCandidateSha256', 'probeApkSha256', 'counts']}))
