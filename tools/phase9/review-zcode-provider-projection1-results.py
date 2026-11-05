"""Offline review only. Never executes incoming wrapper/tests or accesses either device."""
from pathlib import Path
import ast
import hashlib
import importlib.util
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / 'docs/handoff'
BASE = DOC / 'incoming-zcode-provider-projection1-android15-20261023-r1'
SEALED = DOC / 'outgoing/codex-provider-projection1-20261023-r1'
OUT = DOC / 'evidence/provider-projection1-receiving'
OUT.mkdir(parents=True, exist_ok=True)
EXCHANGE = ROOT.parent / 'AGENT HANDOFF EXCHANGE'
checks = []
load = lambda path: json.loads(path.read_text(encoding='utf-8-sig'))
digest = lambda data: hashlib.sha256(data).hexdigest().upper()


def check(name, value):
    checks.append(dict(name=name, passed=bool(value)))
    assert value, name


spec = importlib.util.spec_from_file_location('reviewed_local_exchange', ROOT / 'tools/handoff/file-exchange.py')
exchange = importlib.util.module_from_spec(spec); spec.loader.exec_module(exchange)
verification = exchange.verify(EXCHANGE / 'zcode-to-codex' / BASE.name.removeprefix('incoming-'))
check('incoming eleven files complete and integrity', verification['integrity'] == 'PASS' and verification['completion'] == 'COMPLETE' and verification['fileCount'] == 11)
check('incoming exact archive identity', verification['archiveSha256'] == '929D776CE29C215273C71B2A0E3C148CFF5E037FB2FCE7CD49C11F2B1CD5F42C')
meta = load(BASE / 'PACKAGE.json')
with zipfile.ZipFile(EXCHANGE / 'zcode-to-codex' / meta['packageId'] / 'bundle.zip') as archive:
    for name in archive.namelist():
        check('local extracted sealed bytes '+name, (BASE/name).read_bytes() == archive.read(name))
dep = meta['dependencies'][0]
check('one exact dependency', len(meta['dependencies']) == 1 and dep['packageId'] == SEALED.name)
outgoing = exchange.verify(EXCHANGE / 'codex-to-zcode' / dep['packageId'])
check('sealed dependency archive', outgoing['archiveSha256'] == dep['archiveSha256'] == 'EF4E4C4BF7F0E09B60B321903425DA8E399C3D21329345A3C26AFFB023633149')
with zipfile.ZipFile(EXCHANGE / 'codex-to-zcode' / dep['packageId'] / 'bundle.zip') as archive:
    for name in dep['requiredPaths']:
        check('dependency required bytes '+name, archive.read(name) == (SEALED/name).read_bytes())
    pins = json.loads(archive.read('SOURCE_IDENTITY.json'))
    check('twenty-nine sealed source identities', len(pins) == 29)
    for name, expected in pins.items():
        check('sealed source '+name, digest(archive.read(name)) == expected == digest((SEALED/name).read_bytes()))
    reference = archive.read('ANDROID15-BASELINE-REFERENCE.md').decode()
reference = json.loads(re.search(r'```json\s+(.*?)\s+```', reference, re.S).group(1))
result = load(BASE / 'results/BASELINE-RESULT.json')
commands = load(BASE / 'results/commands-and-exits.json')
pre = load(BASE / 'results/baseline-pre.json'); post = load(BASE / 'results/baseline-post.json')
check('reported baseline exact raw documents', result['baseline']['pre'] == pre and result['baseline']['post'] == post and result['baseline']['allMatch'] is True)
check('all recorded commands assigned Android15 and successful', len(commands) == 46 and all(r['argv'][1:3] == ['-s','DEVICE_ANDROID15'] and r['exit'] == 0 for r in commands))
check('no APK install/restart/root command in recorded trace', not any(x in r['argv'] for r in commands for x in ['install','uninstall','su','force-stop','instrument']))
check('preflight Android/model from raw output', pre['android'] == reference['android'] == commands[1]['stdout'].strip() and pre['model'] == reference['model'] == commands[2]['stdout'].strip())
expected = {'base.apk':reference['apkSha256'], 'libnode.so':reference['libnodeSha256']}
expected.update({name:value['expected'] for name,value in reference['runtimePins'].items()})
for name, value in expected.items():
    rows = [r for r in commands if 'sha256sum' in ' '.join(r['argv']) and name in r['argv'][-1] and 'cache/provider-projection-' not in r['argv'][-1]]
    check('exact pre/post raw full hash '+name, len(rows) == 2 and all(r['stdout'].split()[0].upper() == value for r in rows))
    key = 'apkSha256' if name == 'base.apk' else 'libnode' if name == 'libnode.so' else 'pin:'+name
    check('exact pre/post baseline field '+name, pre[key] == post[key] == value)
check('APK-owned Node version', pre['node'] == reference['nodeVersion'] == commands[9]['stdout'].strip() == 'v24.18.0')
fixture = result['fixtureActualPath']
check('fixture path actually recorded realpath', commands[11]['stdout'].strip() == fixture and 'realpath '+fixture in commands[11]['argv'][-1] and fixture.startswith('/data/user/0/dev.zcode.nodepoc/cache/provider-projection-'))
copied = result['copiedByteExact']; check('nine copied sources', len(copied) == 9)
for destination, value in copied.items():
    source = ('app/src/main/assets/zcode-runtime/'+destination.removeprefix('runtime/')) if destination.startswith('runtime/') else 'tools/phase9/'+destination
    check('copied source sealed identity '+destination, pins[source] == value)
    rows = [r for r in commands if r['argv'][-2:] == ['sha256sum','cache/'+fixture.split('/cache/',1)[1]+'/'+destination]]
    check('copied device readback '+destination, len(rows) == 1 and rows[0]['stdout'].split()[0].upper() == value)
    pushes = [r for r in commands if r['argv'][3:4] == ['push'] and r['argv'][-2].replace('\\','/').endswith(source)]
    check('one byte-bound push '+destination, len(pushes) == 1)
    check('copy into own fixture '+destination, any(r['argv'][-3:] == ['cp',pushes[0]['argv'][-1],'cache/'+fixture.split('/cache/',1)[1]+'/'+destination] for r in commands))
test_runs = [r for r in commands if '--test --test-reporter=tap' in r['argv'][-1]]
check('one recorded Node test invocation', len(test_runs) == 1)
run = test_runs[0]; tap_bytes = (BASE/'results/tap.stdout').read_bytes()
check('raw stdout/stderr equal command trace', run['stdout'] == tap_bytes.decode() and run['stderr'] == (BASE/'results/tap.stderr').read_text() == '' and run['exit'] == 0)
tap = tap_bytes.decode().replace('\r\n','\n')
for name, value in dict(tests=36,pass_=36,fail=0,cancelled=0,skipped=0,todo=0).items():
    label = name.removesuffix('_')
    check('strict unique TAP '+label, re.findall(r'^# '+label+r' (\d+)$',tap,re.M) == [str(value)])
ok = re.findall(r'^ok (\d+) - (.+)$',tap,re.M)
check('all thirty-six individual test results', [int(i) for i,_ in ok] == list(range(1,37)) and not re.search(r'^(not ok |Bail out!)|^ok \d+ .*# (SKIP|TODO)(?:\s|$)',tap,re.M|re.I))
check('actual physical file links case ran', sum(name == 'metadata symlink and package script symlink refused' for _,name in ok) == 1)
expected_names = []
for file in ['provider-declaration-settlement-test.cjs','provider-projection-test.cjs','provider-session-bindings-test.cjs']:
    check('correct test entry only '+file, fixture+'/'+file in run['argv'][-1])
for text in ['TEST_RUNTIME='+fixture+'/runtime','TMPDIR='+fixture,'OPENSSL_CONF=/dev/null','LD_LIBRARY_PATH=/data/user/0/dev.zcode.nodepoc/files/runtime/lib']:
    check('test environment '+text.split('=')[0], text in run['argv'][-1])
check('helper not run as test entry', 'provider-projection-fixture.cjs' not in run['argv'][-1])
wrapper = (BASE/result['executedWrapper']['path']).read_bytes()
check('executed wrapper exact SOURCE identity', digest(wrapper) == result['executedWrapper']['sha256'] and result['executedWrapper']['type'].startswith('SOURCE'))
# Parse constants as data; never import/evaluate incoming Python.
constants={}
for node in ast.parse(wrapper.decode()).body:
    if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in {'PINS','APK','LIBNODE'}:
        constants[node.targets[0].id]=ast.literal_eval(node.value)
check('wrapper fixed constants equal sealed baseline', constants['PINS'] == {k:v['expected'] for k,v in reference['runtimePins'].items()} and constants['APK'] == reference['apkSha256'] and constants['LIBNODE'] == reference['libnodeSha256'])
check('clarification: baseline constants not JSON loaded', b'ANDROID15-BASELINE-REFERENCE.md' not in wrapper and all(k in constants for k in ['PINS','APK','LIBNODE']))
check('source verification count declaration', load(BASE/'results/source-verification.json') == dict(entries=29,allMatch=True))
receipts=[load(p) for p in (EXCHANGE/'receipts/zcode').glob(SEALED.name+'-*.json')]
check('real ZCode INTEGRATED receipt exact outgoing archive', any(r.get('state')=='INTEGRATED' and r.get('archiveSha256')==dep['archiveSha256'] for r in receipts))
review= (BASE/'results/SOURCE-REVIEW.md').read_text('utf-8')
check('four bounded source sections present', all('## Fact '+str(i) in review for i in range(1,5)))
summary=dict(disposition='ACCEPTED_SCOPED_ANDROID15_COMPATIBILITY',archiveSha256=verification['archiveSha256'],
    checkCount=len(checks),checks=checks,offlineOnly=True,deviceActions=0,incomingCodeExecution=0,productionEdits=0,
    actualAndroid15TestEvidence=dict(tests=36,passed=36,failed=0,cancelled=0,skipped=0,todo=0,recordedTestInvocations=1,commandRows=46),
    fixture=fixture,clarifications=[
        'Wrapper uses fixed baseline constants, independently equal to sealed reference; prose claim mechanically loaded from baseline JSON is unsupported by supplied wrapper.',
        'canonical rejects unpaired/lone surrogate code units, not valid surrogate pairs/emoji.',
        'Several source line citations shifted: carrier finish is line37; content match51; declaration54-58; canonical isWellFormed line10; route110-117.',
        'source-verification.json is a count/boolean summary; receiving side independently verified all29 exact sealed entries.',
        'Single recorded attempt and36 concrete results verified; no broader claim about unrecorded attempts or global security.'],
    limits=['No Android15 actual Core/HTTP worker/Dispatcher/provider execution or model proof; SQLite/projection fixtures only.',
        'Android17 prior scoped evidence is referenced, not replayed by ZCode or during receipt.',
        'No production admission UI/startup enrollment/full restart/in-flight revocation acceptance.',
        'Production APK/readiness not refreshed; no device access in receiving review.'])
(OUT/'offline-review.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(disposition=summary['disposition'],offlineChecks=len(checks),output=str(OUT/'offline-review.json'))))
