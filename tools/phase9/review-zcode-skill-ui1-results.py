"""Offline receipt audit; reads sealed handoffs and local evidence, never executes payloads."""
from pathlib import Path
import hashlib
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / 'docs/handoff'
EXCHANGE = ROOT.parent / 'AGENT HANDOFF EXCHANGE'
PACKAGE = 'zcode-skill-ui1-review-20261017-r1'
INCOMING = DOCS / ('incoming-' + PACKAGE)
SEALED = DOCS / 'exchange-skill-ui1-20261017-r2'
PRIOR = DOCS / 'exchange-skill-bindings1-20261016-r2'
EVIDENCE = DOCS / 'evidence/skill-ui1'
checks = []


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def check(name, condition):
    checks.append(dict(name=name, passed=bool(condition)))
    assert condition, name


spec = importlib.util.spec_from_file_location('reviewed_exchange', ROOT / 'tools/handoff/file-exchange.py')
exchange = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exchange)
verified = exchange.verify(EXCHANGE / 'zcode-to-codex' / PACKAGE)
check('incoming immutable integrity and four payload files', verified['integrity'] == 'PASS' and verified['fileCount'] == 4)
meta = load(INCOMING / 'PACKAGE.json')
for dependency in meta['dependencies']:
    folder = EXCHANGE / 'codex-to-zcode' / dependency['packageId']
    identity = exchange.verify(folder)
    check('verified dependency ' + dependency['packageId'], identity['archiveSha256'] == dependency['archiveSha256'])
    import zipfile
    with zipfile.ZipFile(folder / 'bundle.zip') as bundle:
        check('required dependency paths ' + dependency['packageId'], all(p in bundle.namelist() for p in dependency['requiredPaths']))
facts = load(INCOMING / 'results/SOURCE-FACTS.json')
check('twelve exact rows and scoped caveat', [r['n'] for r in facts['rows']] == list(range(1, 13)) and
      all(r['verdict'] == ('PASS_WITH_CAVEAT' if r['n'] == 7 else 'PASS') for r in facts['rows']))
check('zero defects explicitly reported', facts['findings'].startswith('none (zero defects;'))
for item in load(SEALED / 'SOURCE_IDENTITY.json'):
    check('sealed ui1 source ' + item['path'], sha(SEALED / item['path']) == item['sha256'])
    current = ROOT / item['path']
    if item['path'].startswith(('app/', 'tools/')):
        check('current ui1 source ' + item['path'], sha(current) == item['sha256'])
prior = load(PRIOR / 'SOURCE_IDENTITY.json')
for item in prior:
    check('all prior binding pins unchanged ' + item['path'], sha(ROOT / item['path']) == item['sha256'])
coverage = []
for item in prior:
    if Path(item['path']).name in {'bootstrap.cjs', 'runtime-manifest.json', 'ZCodeHostService.kt', 'ZCodeRuntimeBundle.kt'}:
        check('earlier sealed source resolves coverage ' + item['path'], sha(PRIOR / item['path']) == item['sha256'])
        coverage.append(item)
check('exactly four coverage sources resolved locally', len(coverage) == 4)
postflight = load(EVIDENCE / 'postflight.json')
summary = load(EVIDENCE / 'acceptance-summary.json')
check('prior measured postflight scoped target and counts', postflight['verdict'] == 'PASS' and postflight['serial'] == 'DEVICE_ANDROID17' and postflight['packagedCount'] == 40 and postflight['immutableInstalledCount'] == 39)
check('frozen APK matches measured product', sha(EVIDENCE / 'skill-ui1-current.apk') == summary['apkSha256'] == postflight['apkSha256'])
check('model cache distinction and failures preserved', [r['freshReadContent'] for r in summary['modelTasks']] == [True, False, True] and summary['priorFailedInstrumentationRuns'] == 7 and summary['retiredSessionResume'] is True)
run = load(EVIDENCE / summary['uiRun'] / 'result.json')
check('real picker and three model turns measured', run['verdict'] == 'PASS' and run['actualSystemPicker'] and run['realModelTurns'] == 3)
check('live versions and retirement measured', run['liveOldV1NewV2'] and run['retiredThroughUi'] and run['oldVersionsRetained'])
check('unavailable python and root explicitly retained', run['missingDependencies'] == ['runtimes:python', 'permissions:root'])
receipts = [load(p) for p in (EXCHANGE / 'receipts/zcode').glob('codex-skill-ui1-20261017-r2-*.json')]
check('actual ZCode integrated receipt bound to outgoing r2', any(r.get('state') == 'INTEGRATED' and r.get('archiveSha256') == meta['dependencies'][0]['archiveSha256'] and r.get('recipient') == 'zcode' for r in receipts))
result = dict(verdict='PASS', disposition='ACCEPTED_SCOPED_OFFLINE_SKILL_UI_REVIEW',
              archiveSha256=verified['archiveSha256'], checkCount=len(checks), checks=checks,
              coverageResolvedAgainstEarlierSealedSource=coverage,
              productApkSha256=summary['apkSha256'],
              scope='Offline source/identity/evidence audit only; no new build, device or model execution. ZCode row7 evidence limit remains true of its shipped review scope.')
output = EVIDENCE / 'receiving-review-20261018.json'
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(verdict='PASS', checks=len(checks), output=str(output))))
