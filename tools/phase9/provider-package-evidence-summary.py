"""Offline checks of the exact candidate, measured product evidence and unchanged host boundaries."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/handoff/evidence/provider-package1'


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


identity = read('build-identity.json')
assert sha(OUT / 'candidate.apk') == identity['apkSha256']
assert sha(OUT / 'test.apk') == identity['testApkSha256']
assert sha(ROOT / 'tools/phase9/provider-package-device-acceptance.py') == identity['driverSha256']
units = read('unit-summary.json')
assert [units[k] for k in ['tests', 'failures', 'errors', 'skipped']] == [62, 0, 0, 0]
native = read('native-summary.json')
assert native['verdict'] == 'PASS' and native['packageTests'] == 4 and native['stdioTests'] == 5
commands = read('commands-and-exits.json')
assert all(r['argv'][1:3] == ['-s', 'DEVICE_ANDROID17'] and r['exit'] == 0 for r in commands)
model = read('verification.json')
assert model['apkSha256'] == identity['apkSha256'] and model['verdict'] == 'PASS'
assert model['independentProviderCalls'] == 2 and model['hostRejectedCalls'] == 1 and len(model['verifiedArtifacts']) == 2
device = read('identity-model.json')
tools = [p for m in device['messages'] for p in m.get('parts', []) if p.get('type') == 'tool']
assert len(tools) == 1 and tools[0]['tool'] == 'mcp__android-host__device_info_identity' and tools[0]['state']['status'] == 'completed'
body = json.loads(tools[0]['state']['output'].split('Structured content:\n', 1)[1])
assert body['data']['model'] == 'MODEL_ANDROID17' and body['data']['abi'] == 'arm64-v8a' and body['data']['api'] == '37'
assert body['data']['_localProvider']['replyValidated'] is True
assert len(device['carrierCalls']) == 1 and any(r['tool'] == tools[0]['tool'] and r['decision'] == 'allow' and r['session'] == device['sessionId'] for r in device['gatewayJournalRows'])
assert any('PROVIDER_PACKAGE_IDENTITY_OK' in p.get('text', '') for m in device['messages'] for p in m.get('parts', []))
restart = read('force-resume.json')
assert all(restart[k] is True for k in ['unreachableAfterStop', 'relaunchedReady', 'newRuntime', 'resumed']) and restart['persistedMessageCount'] == 6
postflight = read('postflight.json')
assert postflight['apkSha256'] == identity['apkSha256'] and postflight['verdict'] == 'PASS'
assert postflight['packagedCount'] == 40 and postflight['immutableInstalledCount'] == 39 and postflight['priorProviderToolParts'] == 3
assert postflight['retainedFixtureVersions'] == 2 and postflight['configTransactionAbsent']
assert 'BUILD SUCCESSFUL' in (OUT / 'lint-fresh.log').read_text(encoding='utf-8')
lint = ROOT / 'app/build/reports/lint-results-debug.txt'
assert lint.stat().st_mtime > (OUT / 'unit-first.log').stat().st_mtime
assert '0 errors, 28 warnings' in lint.read_text(encoding='utf-8')
shutil.copyfile(lint, OUT / 'lint-results-debug.txt')
for name in ['model-task.err', 'identity-model.err', 'force-resume.err', 'prior-provider-resume.err']:
    assert (OUT / name).read_bytes() == b''
unchanged = []
for item in json.loads((ROOT / 'docs/handoff/exchange-skill-ui1-20261017-r2/SOURCE_IDENTITY.json').read_text()):
    if item['path'].startswith('app/'):
        assert sha(ROOT / item['path']) == item['sha256'], item['path']
        unchanged.append(item)
for item in json.loads((ROOT / 'docs/handoff/exchange-skill-bindings1-20261016-r2/SOURCE_IDENTITY.json').read_text()):
    assert sha(ROOT / item['path']) == item['sha256'], item['path']
    if item not in unchanged:
        unchanged.append(item)
result = dict(verdict='PASS', disposition='ACCEPTED_SCOPED_PROVIDER_PACKAGE_STORAGE', identity=identity,
              unitTests=62, nativePackageTests=4, nativeStdioTests=5, nativeStdioSeconds=107.996,
              digestSession=model['sessionId'], identitySession=device['sessionId'], restart=restart,
              packagedCount=40, immutableInstalledCount=39, sourcePinsUnchanged=unchanged,
              firstFailure='Windows physical symlink privilege; retained first-unit log/XML, native case passed',
              residuals=['Imported provider admission remains unavailable', 'No new whole-suite cancellation wall-time claim',
                         'No repeat full UI/Skill/search/vision matrix', 'Lint SDK and ! path warnings retained'],
              scope='Storage increment and existing fixed provider model/restart regression only')
(OUT / 'acceptance-summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('PASS scoped provider storage evidence, exact real model/Gateway/artifacts/restart and unchanged source pins')
