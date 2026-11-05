"""Candidate source in private cache; real APK-owned Core/Node. No APK/runtime transplant."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time

ADB = os.environ['ANDROID_ADB']
SERIAL, APP = 'DEVICE_ANDROID15', 'dev.zcode.nodepoc'
PRIMARY = '809E54FC8FAE16B16BC141F070831C3C607CCE0FEAE090B02D6D87B5835528CF'
CORE = 'B1DF2EF3E5BD76C4AF3ECB296BC003A10D3F13191A26610BD0BA940FEADAD529'
NODE = '1EE21EEBDA8BA05919050FE0D2B84B773A5CB2D2D1A42A27BDDFB5EAA1EE182E'
PINS = {'bootstrap.cjs': 'FB64415E39BDAFA0F9603832ECCA890AD7ACA10B8E6A11967FFF52B1CC449DB9',
        'gateway.cjs': 'CD9FE220F483F058FA9CBB1E7BA2DD24134AF79FC32F4DD0DF2392C3A4B0AA22',
        'carrier-authorization.cjs': '47C56F1E693E0DF2E31C0150374B5D821B0AF2A5FD05CCCC3A99884FBE1D6144'}
EVIDENCE = Path(os.environ['TEST_EVIDENCE_DIR'])
EVIDENCE.mkdir(parents=True, exist_ok=False)
repo = Path(__file__).resolve().parents[2]
commands = []

def adb(*args):
    p = subprocess.run([ADB, '-s', SERIAL, *args], capture_output=True, text=True, encoding='utf-8', timeout=180)
    commands.append(dict(argv=[ADB, '-s', SERIAL, *args], exit=p.returncode, stdout=p.stdout, stderr=p.stderr))
    (EVIDENCE / 'commands-and-exits.json').write_text(json.dumps(commands, indent=2) + '\n')
    return p

def success(*args):
    p = adb(*args)
    assert p.returncode == 0, 'command failed; preserve raw evidence'
    return p.stdout

assert success('shell', 'getprop', 'ro.build.version.release').strip() == '15'
assert success('shell', 'getprop', 'ro.product.model').strip() == 'MODEL_ANDROID15'
apk = success('shell', 'pm', 'path', APP).strip().removeprefix('package:')
node = apk.rsplit('/', 1)[0] + '/lib/arm64/libnode.so'
runtime = '/data/user/0/' + APP + '/files/runtime'

def baseline():
    assert success('shell', 'run-as', APP, 'sha256sum', apk).split()[0].upper() == PRIMARY
    assert success('shell', 'run-as', APP, 'sha256sum', runtime + '/zcode.cjs').split()[0].upper() == CORE
    assert success('shell', 'run-as', APP, 'sha256sum', node).split()[0].upper() == NODE
    for name, expected in PINS.items():
        assert success('shell', 'run-as', APP, 'sha256sum', runtime + '/' + name).split()[0].upper() == expected

baseline()
cache = 'cache/skill-binding-source-' + str(time.time_ns())
success('shell', 'run-as', APP, 'mkdir', cache)
fixture = '/data/user/0/' + APP + '/' + cache
files = [repo / 'app/src/main/assets/zcode-runtime/skill-session-bindings.cjs',
         repo / 'app/src/main/assets/zcode-runtime/bootstrap.cjs',
         Path(__file__).with_name('skill-session-bindings-test.cjs'),
         Path(__file__).with_name('skill-session-bindings-core-test.cjs')]
hashes = {}
for file in files:
    temporary = '/data/local/tmp/' + Path(cache).name + '-' + file.name
    success('push', str(file), temporary)
    success('shell', 'run-as', APP, 'cp', temporary, cache + '/' + file.name)
    expected = hashlib.sha256(file.read_bytes()).hexdigest().upper()
    assert success('shell', 'run-as', APP, 'sha256sum', cache + '/' + file.name).split()[0].upper() == expected
    hashes[file.name] = expected
prefix = dict(OPENSSL_CONF='/dev/null', LD_LIBRARY_PATH=runtime + '/lib', TMPDIR='/data/user/0/' + APP + '/cache',
              TEST_BINDING_MODULE=fixture + '/skill-session-bindings.cjs', TEST_BINDING_RUNTIME=runtime)
environment = ' '.join(k + '=' + shlex.quote(v) for k, v in prefix.items())
runs = []
try:
    for name in ['skill-session-bindings-test.cjs', 'skill-session-bindings-core-test.cjs']:
        host = name == 'bootstrap-core-test.cjs'
        script = 'skill-session-bindings-core-test.cjs' if host else name
        extra = (' TEST_BINDING_BOOTSTRAP=' + shlex.quote(fixture + '/bootstrap.cjs')) if host else ''
        command = environment + extra + ' ' + shlex.quote(node) + (' --test --test-reporter=tap ' if name == 'skill-session-bindings-test.cjs' else ' ') + shlex.quote(fixture + '/' + script)
        run = adb('shell', 'run-as', APP, 'sh', '-c', shlex.quote(command))
        (EVIDENCE / (name + '.stdout')).write_text(run.stdout, encoding='utf-8')
        (EVIDENCE / (name + '.stderr')).write_text(run.stderr, encoding='utf-8')
        runs.append(dict(name=name, exit=run.returncode))
        assert run.returncode == 0, 'test failure; see retained raw evidence'
        if name != 'skill-session-bindings-test.cjs':
            result = json.loads(run.stdout)
            assert result['verdict'] == 'PASS' and result['checks'] == 6 and result['node'] == 'v24.18.0'
            assert result['route'] == ('actual-bootstrap-http' if host else 'direct-module-core')
        else:
            assert '# pass 16' in run.stdout and '# fail 0' in run.stdout and '# skipped 0' in run.stdout
finally:
    baseline()
    (EVIDENCE / 'identity.json').write_text(json.dumps(dict(serial=SERIAL, primaryApkSha256=PRIMARY, coreSha256=CORE,
        nodeSha256=NODE, runtimePins=PINS, copiedSourceHashes=hashes, fixture=cache, runs=runs,
        scope='candidate host boundary and actual Core protocol only; no model/Skill activation, no installed runtime change'), indent=2) + '\n')
print('PASS Android15 candidate boundary16 + actual Core protocol6; installed baseline preserved.')
