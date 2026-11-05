"""Directed Android15 native Core root selection protocol fixture only.
No model turn, runtime/primary APK installation or production configuration change.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time

ADB = os.environ['ANDROID_ADB']
APP = 'dev.zcode.nodepoc'
SERIAL = 'DEVICE_ANDROID15'
PRIMARY = '809E54FC8FAE16B16BC141F070831C3C607CCE0FEAE090B02D6D87B5835528CF'
PINS = {
    'zcode.cjs': 'B1DF2EF3E5BD76C4AF3ECB296BC003A10D3F13191A26610BD0BA940FEADAD529',
    'bootstrap.cjs': 'FB64415E39BDAFA0F9603832ECCA890AD7ACA10B8E6A11967FFF52B1CC449DB9',
    'gateway.cjs': 'CD9FE220F483F058FA9CBB1E7BA2DD24134AF79FC32F4DD0DF2392C3A4B0AA22',
    'carrier-authorization.cjs': '47C56F1E693E0DF2E31C0150374B5D821B0AF2A5FD05CCCC3A99884FBE1D6144',
}
EVIDENCE = Path(os.environ['TEST_EVIDENCE_DIR'])
EVIDENCE.mkdir(parents=True, exist_ok=False)
SOURCE = Path(__file__).with_name('core-skill-session-seam.cjs')
commands = []


def adb(*args):
    p = subprocess.run([ADB, '-s', SERIAL, *args], capture_output=True,
                       text=True, encoding='utf-8', timeout=180)
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
shared = '/data/local/tmp/skill-session-seam-' + nonce + '.cjs'
success('push', str(SOURCE), shared)
cache = 'cache/skill-seam-driver-' + nonce
script = cache + '/probe.cjs'
setup = 'mkdir ' + shlex.quote(cache) + ' && cp ' + shlex.quote(shared) + ' ' + shlex.quote(script)
success('shell', 'run-as', APP, 'sh', '-c', shlex.quote(setup))
source_sha = hashlib.sha256(SOURCE.read_bytes()).hexdigest().upper()
assert success('shell', 'run-as', APP, 'sha256sum', script).split()[0].upper() == source_sha
command = 'OPENSSL_CONF=/dev/null LD_LIBRARY_PATH=/data/user/0/' + APP + '/files/runtime/lib ' + shlex.quote(node) + ' ' + shlex.quote(script) + ' ' + APP
run = adb('shell', 'run-as', APP, 'sh', '-c', shlex.quote(command))
(EVIDENCE / 'probe.json').write_text(run.stdout, encoding='utf-8')
(EVIDENCE / 'probe.err').write_text(run.stderr, encoding='utf-8')
# Always attempt baseline readback even when the protocol fixture fails.
baseline()
assert run.returncode == 0, 'protocol fixture failed; preserve raw failure, no pin/expectation changes'
data = json.loads(run.stdout)
assert data['verdict'] == 'PASS_SOURCE_SEAM_WITH_RESUME_GAP'
assert len(data['checks']) == 9 and all(v is True for v in data['checks'].values())
assert data['node'] == 'v24.18.0' and data['coreSha256'].upper() == PINS['zcode.cjs']
(EVIDENCE / 'runtime-identity.json').write_text(json.dumps(dict(
    serial=SERIAL, android='15', primaryApkSha256=PRIMARY, runtimePins=PINS,
    sourceSha256=source_sha, wrapperSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest().upper(),
    scope='native catalog/create/import-fixture/close/resume only; no model or Skill activation'), indent=2) + '\n')
print('PASS native Core root selection fixture; nine checks include measured resume gap, not production pinning.')
