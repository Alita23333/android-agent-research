"""Exact candidate Gateway modules in NEW Android15 cache fixture, not a runtime transplant."""
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
PINS = {
    'zcode.cjs': 'B1DF2EF3E5BD76C4AF3ECB296BC003A10D3F13191A26610BD0BA940FEADAD529',
    'bootstrap.cjs': 'FB64415E39BDAFA0F9603832ECCA890AD7ACA10B8E6A11967FFF52B1CC449DB9',
    'gateway.cjs': 'CD9FE220F483F058FA9CBB1E7BA2DD24134AF79FC32F4DD0DF2392C3A4B0AA22',
    'carrier-authorization.cjs': '47C56F1E693E0DF2E31C0150374B5D821B0AF2A5FD05CCCC3A99884FBE1D6144',
}
EVIDENCE = Path(os.environ['TEST_EVIDENCE_DIR'])
EVIDENCE.mkdir(parents=True, exist_ok=False)
SCRIPT = Path(__file__).with_name('skill-control-path-regression.cjs')
# The sealed handoff layout is authoritative; never find modules in the other repository.
RUNTIME = Path(__file__).parent.parent / 'source/runtime'
assert (RUNTIME / 'gateway.cjs').is_file() and (RUNTIME / 'workspace-files.cjs').is_file()
commands = []


def adb(*args):
    p = subprocess.run([ADB, '-s', SERIAL, *args], capture_output=True,
                       text=True, encoding='utf-8', timeout=120)
    commands.append(dict(argv=[ADB, '-s', SERIAL, *args], exit=p.returncode,
                         stdout=p.stdout, stderr=p.stderr))
    (EVIDENCE / 'commands-and-exits.json').write_text(json.dumps(commands, indent=2) + '\n')
    return p


def success(*args):
    p = adb(*args)
    assert p.returncode == 0, 'assigned command failed; see raw evidence'
    return p.stdout


assert success('shell', 'getprop', 'ro.build.version.release').strip() == '15'
assert success('shell', 'getprop', 'ro.product.model').strip() == 'MODEL_ANDROID15'
apk = success('shell', 'pm', 'path', APP).strip().removeprefix('package:')
node = apk.rsplit('/', 1)[0] + '/lib/arm64/libnode.so'


def baseline():
    assert success('shell', 'run-as', APP, 'sha256sum', apk).split()[0].upper() == PRIMARY
    for name, expected in PINS.items():
        assert success('shell', 'run-as', APP, 'sha256sum', 'files/runtime/' + name).split()[0].upper() == expected
    assert success('shell', 'run-as', APP, 'sha256sum', node).split()[0].upper() == '1EE21EEBDA8BA05919050FE0D2B84B773A5CB2D2D1A42A27BDDFB5EAA1EE182E'


baseline()
nonce = str(time.time_ns())
cache = 'cache/skill-control-source-' + nonce
success('shell', 'run-as', APP, 'mkdir', cache)
hashes = {}
for file, name in [(SCRIPT, 'test.cjs'), (RUNTIME / 'gateway.cjs', 'gateway.cjs'), (RUNTIME / 'workspace-files.cjs', 'workspace-files.cjs')]:
    temporary = '/data/local/tmp/skill-control-' + nonce + '-' + name
    success('push', str(file), temporary)
    success('shell', 'run-as', APP, 'cp', temporary, cache + '/' + name)
    expected = hashlib.sha256(file.read_bytes()).hexdigest().upper()
    assert success('shell', 'run-as', APP, 'sha256sum', cache + '/' + name).split()[0].upper() == expected
    hashes[name] = expected
fixture = '/data/user/0/' + APP + '/' + cache
command = 'TEST_RUNTIME=' + shlex.quote(fixture) + ' TEST_FIXTURE_PARENT=' + shlex.quote(fixture) + ' OPENSSL_CONF=/dev/null LD_LIBRARY_PATH=/data/user/0/' + APP + '/files/runtime/lib ' + shlex.quote(node) + ' ' + shlex.quote(cache + '/test.cjs')
run = adb('shell', 'run-as', APP, 'sh', '-c', shlex.quote(command))
(EVIDENCE / 'regression.log').write_text(run.stdout + run.stderr, encoding='utf-8')
baseline()
assert run.returncode == 0 and 'RESULT 28 PASS' in run.stdout
(EVIDENCE / 'runtime-identity.json').write_text(json.dumps(dict(
    serial=SERIAL, android='15', primaryApkSha256=PRIMARY, runtimePins=PINS,
    copiedSourceHashes=hashes, cacheFixture=cache,
    scope='candidate Gateway source/SQLite in new cache only; installed production runtime unchanged'), indent=2) + '\n')
print('PASS candidate Gateway28 in isolated Android15 cache; primary/runtime pins preserved.')
