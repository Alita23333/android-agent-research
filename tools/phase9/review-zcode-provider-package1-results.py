"""Offline received evidence checks; never executes incoming code or operates a device."""
from pathlib import Path
import hashlib
import importlib.util
import json
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/handoff/incoming-zcode-provider-package1-android15-20261018-r1'
SEALED = ROOT / 'docs/handoff/exchange-provider-package1-20261018-r1'
EXCHANGE = ROOT.parent / 'AGENT HANDOFF EXCHANGE'
checks = []


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def check(name, value):
    checks.append(dict(name=name, passed=bool(value)))
    assert value, name


spec = importlib.util.spec_from_file_location('local_exchange', ROOT / 'tools/handoff/file-exchange.py')
exchange = importlib.util.module_from_spec(spec); spec.loader.exec_module(exchange)
verified = exchange.verify(EXCHANGE / 'zcode-to-codex' / BASE.name.removeprefix('incoming-'))
meta = load(BASE / 'PACKAGE.json')
check('eleven payload files complete/integrity', verified['fileCount'] == 11 and verified['completion'] == 'COMPLETE' and verified['integrity'] == 'PASS')
for dep in meta['dependencies']:
    check('sealed dependency ' + dep['packageId'], exchange.verify(EXCHANGE / 'codex-to-zcode' / dep['packageId'])['archiveSha256'] == dep['archiveSha256'])
pins = load(SEALED / 'SOURCE_IDENTITY.json')
check('twenty-nine source identities', len(pins) == 29)
for pin in pins:
    check('sealed source ' + pin['path'], sha(SEALED / pin['path']) == pin['sha256'])
copied = load(BASE / 'results/copy-log.json')
for operation in copied['operations']:
    hits = [p for p in pins if p['path'].endswith('/' + operation['path'])]
    check('exact copied new source ' + operation['path'], len(hits) == 1 and hits[0]['sha256'] == operation['newSha'])
domain = next(p for p in pins if p['path'].endswith('/core/Domain.kt'))
check('kept Domain identity', copied['kept']['dev/alita/androidagent/core/Domain.kt'] == domain['sha256'])
identity = load(BASE / 'results/runtime-identity.json')
commands = load(BASE / 'results/commands-and-exits.json')
check('twenty-four raw commands all assigned device', len(commands) == 24 and all(r['argv'][1:3] == ['-s', 'DEVICE_ANDROID15'] for r in commands))
check('only expected host-stopped probe fails', [(i,r['exit']) for i,r in enumerate(commands) if r['exit']] == [(19,1)] and 'ECONNREFUSED' in commands[19]['stdout'])
expected = {'base.apk': identity['pre']['apkSha256'], 'libnode.so': identity['pre']['libnodeSha256']}
expected.update({k:v['expected'] for k,v in identity['pre']['runtimePins'].items()})
for filename, value in expected.items():
    hits = [r for r in commands if 'sha256sum' in ' '.join(r['argv']) and filename in r['argv'][-1]]
    check('full pre/post raw hash ' + filename, len(hits) == 2 and all(r['stdout'].split()[0].upper() == value for r in hits))
    if filename in identity['post']['runtimePins']:
        check('identity post ' + filename, identity['post']['runtimePins'][filename]['actual'] == value)
check('main APK known baseline', expected['base.apk'] == '809E54FC8FAE16B16BC141F070831C3C607CCE0FEAE090B02D6D87B5835528CF' == identity['post']['apkSha256'])
check('Node binary known baseline', expected['libnode.so'] == '1EE21EEBDA8BA05919050FE0D2B84B773A5CB2D2D1A42A27BDDFB5EAA1EE182E' == identity['post']['libnodeSha256'])
check('authorization byte identity from product source', expected['carrier-authorization.cjs'] == sha(ROOT / 'app/src/main/assets/zcode-runtime/carrier-authorization.cjs'))
check('Node version raw', commands[5]['stdout'].strip() == 'v24.18.0')
run = commands[11]
check('only assigned native class invoked', run['argv'][3:] == ['shell','am','instrument','-w','-e','class','dev.alita.androidagent.LocalProviderPackageDeviceTest','dev.zcode.nodepoc.test/androidx.test.runner.AndroidJUnitRunner'])
check('literal four tests four dots empty stderr', run['exit'] == 0 and run['stderr'] == '' and
      'LocalProviderPackageDeviceTest:....' in run['stdout'] and 'OK (4 tests)' in run['stdout'] and
      'Time: 0.312' in run['stdout'] and not re.search(r'FAIL|ignored|skipped', run['stdout'], re.I))
check('only test APK installed', [r for r in commands if 'install' in r['argv']] == [commands[10]] and 'androidTest' in commands[10]['argv'][-1])
manifest = (BASE / 'results/manifest-raw.txt').read_text()
check('actual manifest package and target and runner', 'package="dev.zcode.nodepoc.test"' in manifest and 'android:targetPackage(0x01010021)="dev.zcode.nodepoc"' in manifest and 'androidx.test.runner.AndroidJUnitRunner' in manifest)
build = load(BASE / 'results/test-build-identity.json')
check('native count and build exit', build['build']['exit'] == 0 and build['instrumentation']['exit'] == 0 and 'BUILD SUCCESSFUL' in (BASE / 'results/build.log').read_text())
check('host recovery raw and four private fixtures', commands[21]['exit'] == 0 and commands[21]['stdout'].strip() == identity['post']['hostAfterInstrumentation'] and commands[22]['stdout'].strip() == '4')
receipts = [load(p) for p in (EXCHANGE / 'receipts/zcode').glob('codex-provider-package1-20261018-r1-*.json')]
check('actual ZCode integrated receipt matches original', any(r.get('state') == 'INTEGRATED' and r.get('archiveSha256') == meta['dependencies'][0]['archiveSha256'] for r in receipts))
hash_labels = identity['executedRecorderScripts']
check('recording gap: manifest digest is output digest', hash_labels['manifest-raw.txt'] == sha(BASE / 'results/manifest-raw.txt'))
old_copy = copied['operations'][1]['oldSha']
old_build = re.search(r'([A-F0-9]{64}) ->', build['sourceArrangement']['replaced'][1]).group(1)
check('recording gap: contradictory previous protocol hashes', old_copy != old_build)
result = dict(verdict='NATIVE4_COMPATIBILITY_SUPPORTED_WITH_RECORDING_GAPS', checkCount=len(checks), checks=checks,
    archiveSha256=verified['archiveSha256'], receiptDisposition='NEEDS_REVISION_PROVENANCE_ONLY',
    supported=['Exact newly copied executable source hashes', 'Literal native4 first test invocation PASS', 'Pre/post main APK/runtime pins', 'Existing launcher recovery'],
    findings=[dict(id='F1',issue='executedRecorderScripts includes output hash; actual recorder source bytes/identities not independently established',manifestOutputSha256=hash_labels['manifest-raw.txt']),
              dict(id='F2',issue='Previous LocalToolProtocol hash conflicts between two result documents',copyLog=old_copy,testBuild=old_build),
              dict(id='F3',issue='First erroneous-constant failure described but original failed recorder source/output absent from payload/raw command history')],
    note='No device/build/model/incoming source execution. Request recording supplement only, no rerun; product C51DB531 baseline unchanged. User prose quotes a 65-character archive string; authoritative READY/actual ZIP SHA is the 64-character archiveSha256 above.')
out = ROOT / 'docs/handoff/evidence/provider-package1/android15-receiving-review-20261018.json'
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(checks=len(checks), disposition=result['receiptDisposition'], output=str(out))))
