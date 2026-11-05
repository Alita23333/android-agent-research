"""Offline receiving checks only. Does not execute incoming source or touch a device."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
HANDOFF = ROOT / 'docs/handoff'
seam = HANDOFF / 'incoming-zcode-skill-session-seam1-android15-20261017-r1'
binding = HANDOFF / 'incoming-zcode-skill-bindings1-android15-20261017-r1'
sealed = HANDOFF / 'exchange-skill-bindings1-20261016-r2'
checks = []

def check(name, condition):
    checks.append(dict(name=name, passed=bool(condition)))
    assert condition, name

def load(base, name):
    return json.loads((base / 'results' / name).read_text(encoding='utf-8-sig'))

def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest().upper()

PRIMARY = '809E54FC8FAE16B16BC141F070831C3C607CCE0FEAE090B02D6D87B5835528CF'
PINS = dict(zcode='B1DF2EF3E5BD76C4AF3ECB296BC003A10D3F13191A26610BD0BA940FEADAD529',
    node='1EE21EEBDA8BA05919050FE0D2B84B773A5CB2D2D1A42A27BDDFB5EAA1EE182E',
    bootstrap='FB64415E39BDAFA0F9603832ECCA890AD7ACA10B8E6A11967FFF52B1CC449DB9',
    gateway='CD9FE220F483F058FA9CBB1E7BA2DD24134AF79FC32F4DD0DF2392C3A4B0AA22',
    auth='47C56F1E693E0DF2E31C0150374B5D821B0AF2A5FD05CCCC3A99884FBE1D6144')

def commands(base, file, expected_count, prefix):
    rows = load(base, file)
    check(prefix + ' raw command count', len(rows) == expected_count)
    check(prefix + ' all argv target assigned device', all(r['argv'][1:3] == ['-s', 'DEVICE_ANDROID15'] for r in rows))
    check(prefix + ' all exits zero', all(r['exit'] == 0 for r in rows))
    check(prefix + ' no install/root/Android17 invocation', all('DEVICE_ANDROID17' not in ' '.join(r['argv']) and
        not any(a in {'install', 'su', 'instrument'} for a in r['argv']) for r in rows))
    hashes = [r for r in rows if 'sha256sum' in r['argv']]
    suffixes = {'/base.apk': PRIMARY, '/libnode.so': PINS['node'], 'zcode.cjs': PINS['zcode'],
        'bootstrap.cjs': PINS['bootstrap'], 'gateway.cjs': PINS['gateway'], 'carrier-authorization.cjs': PINS['auth']}
    for suffix, expected in suffixes.items():
        hits = [r for r in hashes if r['argv'][-1].endswith(suffix) and
            ('/files/runtime/' in r['argv'][-1] or r['argv'][-1].startswith('files/runtime/') or suffix in {'/base.apk', '/libnode.so'})]
        check(prefix + ' full pre/post pin ' + suffix, len(hits) == 2 and all(r['stdout'].split()[0].upper() == expected for r in hits))
    return rows

a = commands(seam, 'part-a-commands-and-exits.json', 19, 'seamA')
b = commands(seam, 'part-b-commands-and-exits.json', 26, 'seamB')
c = commands(binding, 'commands-and-exits.json', 30, 'binding')
probe = load(seam, 'part-a-probe.json')
expected_checks = {'workspaceV1', 'oldInitiallyV1', 'workspaceV2', 'liveOldRemainsV1', 'newUsesV2',
    'resumeRebuildsCurrentV2', 'restoringConfigRebuildsV1', 'immutableInputsUnchanged', 'globalSafetyConfigUnchanged'}
check('nine exact named Core seam checks all true', set(probe['checks']) == expected_checks and all(v is True for v in probe['checks'].values()))
check('Core seam explicitly reports resume GAP', probe['verdict'] == 'PASS_SOURCE_SEAM_WITH_RESUME_GAP')
check('Core seam source stderr empty', (seam / 'results/part-a-probe.err').read_bytes() == b'')
aid = load(seam, 'part-a-runtime-identity.json')
check('seam driver exact assigned bytes', aid['sourceSha256'] == sha(ROOT / 'tools/phase9/core-skill-session-seam.cjs'))
check('seam wrapper full hash', aid['wrapperSha256'] == sha(ROOT / 'tools/phase9/core-skill-session-seam-android15.py'))
arun = [r for r in a if 'sh' in r['argv'] and 'OPENSSL_CONF=' in r['argv'][-1] and 'probe.cjs' in r['argv'][-1]]
check('seam full raw stdout/JSON match', len(arun) == 1 and json.loads(arun[0]['stdout']) == probe and arun[0]['stderr'] == '')
bid = load(seam, 'part-b-runtime-identity.json')
for target, source in {'test.cjs': 'tools/phase9/skill-control-path-regression.cjs',
    'gateway.cjs': 'app/src/main/assets/zcode-runtime/gateway.cjs',
    'workspace-files.cjs': 'app/src/main/assets/zcode-runtime/workspace-files.cjs'}.items():
    check('seamB exact copied ' + target, bid['copiedSourceHashes'][target] == sha(ROOT / source))
blog = (seam / 'results/part-b-regression.log').read_text()
check('28 literal independent PASS rows and final result', len(re.findall(r'^PASS ', blog, re.M)) == 28 and blog.rstrip().endswith('RESULT 28 PASS'))
brun = [r for r in b if 'sh' in r['argv'] and 'TEST_RUNTIME=' in r['argv'][-1]]
check('Gateway full raw stdout match', len(brun) == 1 and brun[0]['stdout'] == blog and brun[0]['stderr'] == '')
check('Gateway regression isolated fixture environment', 'TEST_FIXTURE_PARENT=' in brun[0]['argv'][-1] and bid['cacheFixture'] in brun[0]['argv'][-1])
identity = load(binding, 'identity.json')
check('binding exact two runs, no optional Host path', identity['runs'] == [dict(name='skill-session-bindings-test.cjs', exit=0), dict(name='skill-session-bindings-core-test.cjs', exit=0)])
for name, source in {'skill-session-bindings.cjs': 'app/src/main/assets/zcode-runtime/skill-session-bindings.cjs',
    'bootstrap.cjs': 'app/src/main/assets/zcode-runtime/bootstrap.cjs',
    'skill-session-bindings-test.cjs': 'tools/phase9/skill-session-bindings-test.cjs',
    'skill-session-bindings-core-test.cjs': 'tools/phase9/skill-session-bindings-core-test.cjs'}.items():
    check('binding copied source pinned r2 ' + name, identity['copiedSourceHashes'][name] == sha(sealed / source))
    hits = [r for r in c if 'sha256sum' in r['argv'] and r['argv'][-1] == identity['fixture'] + '/' + name]
    check('binding device-side SHA ' + name, len(hits) == 1 and hits[0]['stdout'].split()[0].upper() == identity['copiedSourceHashes'][name])
tap = (binding / 'results/skill-session-bindings-test.cjs.stdout').read_text()
expected_names = re.findall(r"^test\('([^']+)'", (sealed / 'tools/phase9/skill-session-bindings-test.cjs').read_text(), re.M)
actual_names = re.findall(r'^ok \d+ - (.+)$', tap, re.M)
check('all16 exact case names/order match sealed source', len(expected_names) == 16 and actual_names == expected_names)
for value in ['tests 16', 'pass 16', 'fail 0', 'cancelled 0', 'skipped 0', 'todo 0']:
    check('TAP exact ' + value, '# ' + value + '\n' in tap)
core = load(binding, 'skill-session-bindings-core-test.cjs.stdout')
check('actual Core result exact route/count/version', core['verdict'] == 'PASS' and core['route'] == 'direct-module-core' and core['checks'] == 6 and core['node'] == 'v24.18.0' and core['retainedHostFixture'] is None)
for name in ['skill-session-bindings-test.cjs', 'skill-session-bindings-core-test.cjs']:
    err = (binding / ('results/' + name + '.stderr')).read_bytes()
    check('raw stderr empty ' + name, err == b'')
    runs = [r for r in c if 'sh' in r['argv'] and r['argv'][-1].endswith(name + "'")]
    text = (binding / ('results/' + name + '.stdout')).read_text()
    check('full captured stdout matches ' + name, len(runs) == 1 and runs[0]['stdout'] == text and runs[0]['stderr'] == '')
check('no optional Host execution flag', all('TEST_BINDING_BOOTSTRAP=' not in ' '.join(r['argv']) for r in c))
result = dict(verdict='PASS', disposition='ACCEPTED_SCOPED_ANDROID15_COMPATIBILITY', checkCount=len(checks),
    checks=checks, commandsReviewed=75, receivedPackages=2,
    evidenceNote='Bindings wrapper SHA not separately reported in identity.json; exact copied executable hashes and full raw device argv/results verified. Not an independent wrapper byte-identity claim.',
    scope='Core seam9 with expected resume gap; candidate Gateway28; binding unit16 and directCore6. No Android15 model/GUI/Host bootstrap/product transplant acceptance.')
out = HANDOFF / 'evidence/skill-bindings1/android15-receiving-review-20261017.json'
out.write_text(json.dumps(result, indent=2) + '\n')
print('PASS ' + str(len(checks)) + ' offline receiving checks; 75 raw commands; no incoming code executed')
