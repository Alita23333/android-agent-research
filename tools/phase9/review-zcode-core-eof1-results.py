"""Review sealed Android15 evidence as data; never execute incoming code or adb."""
from pathlib import Path
import ast
import hashlib
import importlib.util
import json
import re
import shlex
import zipfile

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / 'docs/handoff'
EXCHANGE = ROOT.parent / 'AGENT HANDOFF EXCHANGE'
ID = 'zcode-provider-core-eof1-android15-20261023-r1'
BASE = DOC / ('incoming-' + ID)
OUT = DOC / 'evidence/provider-core-eof1-receiving'
OUT.mkdir(parents=True, exist_ok=True)
checks = []
load = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda b: hashlib.sha256(b).hexdigest().upper()


def check(name, condition):
    checks.append(dict(name=name, passed=bool(condition)))
    assert condition, name


spec = importlib.util.spec_from_file_location('reviewed_exchange', ROOT / 'tools/handoff/file-exchange.py')
exchange = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exchange)
verified = exchange.verify(EXCHANGE / 'zcode-to-codex' / ID)
check('COMPLETE integrity and sixteen payload files', verified['integrity'] == 'PASS' and verified['completion'] == 'COMPLETE' and verified['fileCount'] == 16)
check('exact archive', verified['archiveSha256'] == '77A61CEE16629DF1CF6919C746147E4B4E60B321990620FABFFE9D8B704722AF')
with zipfile.ZipFile(EXCHANGE / 'zcode-to-codex' / ID / 'bundle.zip') as z:
    for name in z.namelist():
        check('extracted sealed bytes ' + name, z.read(name) == (BASE / name).read_bytes())
meta = load(BASE / 'PACKAGE.json')
check('one dependency', len(meta['dependencies']) == 1)
dep = meta['dependencies'][0]
dv = exchange.verify(EXCHANGE / 'codex-to-zcode' / dep['packageId'])
check('exact assigned outgoing dependency', dep['packageId'] == 'codex-provider-host-lifecycle1-20261023-r1' and dv['archiveSha256'] == dep['archiveSha256'] == 'D62235FDA3FB17F9159A97BC9028A1A5DA4E8C687783CB4993A88E3E0E4086C8')
with zipfile.ZipFile(EXCHANGE / 'codex-to-zcode' / dep['packageId'] / 'bundle.zip') as z:
    for name in dep['requiredPaths']:
        check('required dependency bytes ' + name, z.read(name) == (DOC / 'outgoing' / dep['packageId'] / name).read_bytes())
    pins = json.loads(z.read('SOURCE_IDENTITY.json'))
    rows = load(BASE / 'results/source-verification.json')
    check('seven unique complete identity rows', len(rows) == len(pins) == 7 and len({r['path'] for r in rows}) == 7 and {r['path'] for r in rows} == set(pins))
    for row in rows:
        name = row['path']
        check('per-entry identity ' + name, row['match'] is True and row['expected'] == row['actual'] == pins[name] == sha(z.read(name)) == sha((ROOT / name).read_bytes()))
    ref = json.loads(re.search(r'```json\s*(.*?)\s*```', z.read('ANDROID15-BASELINE-REFERENCE.md').decode(), re.S).group(1))
    test_sha = pins['tools/phase9/core-stdin-eof-test.cjs']

expected = {k: ref[k] for k in ['android', 'model', 'apkSha256']}
expected.update({'pin:' + k: v['expected'] for k, v in ref['runtimePins'].items()})
expected.update(libnode=ref['libnodeSha256'], node=ref['nodeVersion'])
cycle_results = []
fixtures = []
for label, sub, expected_ms in [('attempt-1', 'results/first-failure-attempt1', [85, 82]), ('attempt-2', 'results', [64, 46])]:
    p = BASE / sub
    pre, post = load(p / 'baseline-pre.json'), load(p / 'baseline-post.json')
    records = load(p / 'commands-and-exits.json')
    check(label + ' pre baseline matches sealed reference', pre == expected)
    check(label + ' post hash fields complete and unchanged', post == {k: v for k, v in expected.items() if k not in ['android', 'model', 'node']})
    check(label + ' exactly22 commands all exit0', len(records) == 22 and all(r['exit'] == 0 for r in records))
    check(label + ' only assigned Android15 serial', all(r['argv'][1:3] == ['-s', 'DEVICE_ANDROID15'] for r in records))
    # push progress belongs on stderr; the actual test stderr must be empty.
    check(label + ' stderr empty except push progress', all(not r['stderr'] for i, r in enumerate(records) if i != 12) and '1 file pushed, 0 skipped' in records[12]['stderr'])
    check(label + ' raw identity properties', records[1]['stdout'].strip() == pre['android'] and records[2]['stdout'].strip() == pre['model'] and records[9]['stdout'].strip() == pre['node'])
    hash_keys = ['apkSha256', *['pin:' + k for k in ref['runtimePins']], 'libnode']
    for i, k in enumerate(hash_keys):
        check(label + ' raw pre and post ' + k, records[3 + i]['stdout'].split()[0].upper() == records[16 + i]['stdout'].split()[0].upper() == expected[k])
    fixture = records[11]['stdout'].strip()
    fixtures.append(fixture)
    check(label + ' observed realpath consistent with mkdir', fixture == '/data/user/0/dev.zcode.nodepoc/' + records[10]['argv'][-1] and shlex.split(shlex.split(records[11]['argv'][-1])[0]) == ['realpath', fixture])
    check(label + ' copy hash matches immutable assigned source', records[14]['stdout'].split()[0].upper() == test_sha and records[14]['argv'][-1] == records[10]['argv'][-1] + '/core-stdin-eof-test.cjs')
    argv = shlex.split(shlex.split(records[15]['argv'][-1])[0])
    apk = records[0]['stdout'].strip().removeprefix('package:')
    node = apk.rsplit('/', 1)[0] + '/lib/arm64/libnode.so'
    check(label + ' installed Core Node and short TMPDIR exact command', argv == ['TEST_CORE=/data/user/0/dev.zcode.nodepoc/files/runtime/zcode.cjs', 'OPENSSL_CONF=/dev/null', 'LD_LIBRARY_PATH=/data/user/0/dev.zcode.nodepoc/files/runtime/lib', 'TMPDIR=/data/user/0/dev.zcode.nodepoc/cache', node, fixture + '/core-stdin-eof-test.cjs'])
    check(label + ' test output byte matches command record', records[15]['stdout'].encode() == (p / 'eof.stdout').read_bytes() and records[15]['stderr'].encode() == (p / 'eof.stderr').read_bytes() == b'')
    result = load(p / 'eof.stdout')
    check(label + ' exact verdict and Node version', result['verdict'] == 'PASS_ACTUAL_CORE_STDIN_EOF' and result['node'] == 'v24.18.0')
    cycles = result['cycles']
    check(label + ' exactly2 distinct pid and full session IDs', len(cycles) == 2 and len({c['pid'] for c in cycles}) == 2 and len({c['sessionId'] for c in cycles}) == 2 and all(isinstance(c['pid'], int) and c['pid'] > 0 and re.fullmatch(r'sess_[0-9a-f-]{36}', c['sessionId']) for c in cycles))
    for i, c in enumerate(cycles):
        check(label + ' natural termination ' + str(i), c['naturalExit'] is True and c['code'] == 0 and c['signal'] is None and type(c['exitAfterEofMs']) is int and 0 <= c['exitAfterEofMs'] < 5000 and c['exitAfterEofMs'] == expected_ms[i])
    cycle_results.append(result)
check('distinct physical fixtures across attempts', fixtures[0] != fixtures[1])

summary = load(BASE / 'results/BASELINE-RESULT.json')
check('final summary exact identity and fixture', summary['copiedByteExact'] == {'core-stdin-eof-test.cjs': test_sha} and summary['fixtureActualPath'] == fixtures[1])
check('final wrapper identity', summary['executedWrapper']['sha256'] == sha((BASE / summary['executedWrapper']['path']).read_bytes()))
check('final summary baseline matches retained files', summary['baseline']['pre'] == load(BASE / 'results/baseline-pre.json') and summary['baseline']['post'] == load(BASE / 'results/baseline-post.json') and summary['baseline']['allMatch'] is True)
final = summary['result']
check('summary result exact counts and booleans', final['exit'] == 0 and final['verdict'] == cycle_results[1]['verdict'] and final['node'] == cycle_results[1]['node'] and final['cyclesLen'] == 2 and all(final[k] is True for k in ['distinctPids', 'distinctSessions', 'allNatural', 'allFast']))
for i, c in enumerate(cycle_results[1]['cycles']):
    check('summary cycle fields ' + str(i), final['each'][i] == {**c, 'sessionId': c['sessionId'][:12]})
# Parse source for provenance only. Never import or execute received wrappers.
old = (BASE / 'results/first-failure-attempt1/wrapper-source.py').read_text('utf-8')
new = (BASE / 'source/wrapper.txt').read_text('utf-8')
ast.parse(old)
ast.parse(new)
normalized = new.replace("% (2, time.time_ns())", "% (1, time.time_ns())").replace("test_sha = IDENT['tools/phase9/core-stdin-eof-test.cjs']\nwant = test_sha", "want = IDENT['tools/phase9/core-stdin-eof-test.cjs']").replace("'copied': {'core-stdin-eof-test.cjs': test_sha}", "'copied': {'core-stdin-eof-test.cjs': want}")
check('wrapper delta only attempt number and dedicated hash binding', normalized == old)
check('old leak after copy assertion before summary', old.index('assert got == want') < old.index('for name, want in PINS.items():', old.index('post =')) < old.index("'copied': {'core-stdin-eof-test.cjs': want}"))
residual = (BASE / 'residuals/RESIDUALS.md').read_text('utf-8')
check('overwritten summary explicitly not reconstructed', 'overwritten' in residual and 'rather than reconstructed' in residual)
receipts = [load(p) for p in (EXCHANGE / 'receipts/zcode').glob(dep['packageId'] + '-*.json')]
check('actual upstream INTEGRATED receipt', any(r.get('state') == 'INTEGRATED' and r.get('archiveSha256') == dep['archiveSha256'] for r in receipts))
report = dict(disposition='ACCEPTED_SCOPED_ACTUAL_CORE_STDIN_EOF_COMPATIBILITY', archiveSha256=verified['archiveSha256'], offlineCheckCount=len(checks), checks=checks,
              sourceEntries=7, cycleEvidence=cycle_results, fixtures=fixtures,
              incomingExecution=0, deviceActions=0, productionEdits=0,
              retentionLimit='Attempt-1 erroneous summary original NOT_RETAINED; source, command records, raw test output and baselines retained. Do not reconstruct missing original.',
              scope='USER-only Core stdin EOF; no model/tool/active MCP/Service/Gateway/production final acceptance.',
              next='Codex Android17 active model/provider/artifact/cancellation and product-package restart acceptance; ZCode holds baseline pending next pinned substantive task.')
(OUT / 'offline-review.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(disposition=report['disposition'], offlineChecks=len(checks))))
