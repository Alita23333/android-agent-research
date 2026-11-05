"""Directed Android15 catalog compatibility only; never operates Android17."""
from pathlib import Path
import hashlib
import json
import os
import shlex
import subprocess

adb = os.environ['ANDROID_ADB']
output = Path(os.environ['TEST_EVIDENCE_DIR']).resolve()
output.mkdir(parents=True, exist_ok=True)
serial, package = 'DEVICE_ANDROID15', 'dev.zcode.nodepoc'
commands = []


def call(*args):
    argv = [adb, '-s', serial, *args]
    result = subprocess.run(argv, capture_output=True, timeout=50)
    commands.append({'argv': argv, 'exit': result.returncode,
        'stdout': result.stdout.decode('utf-8', errors='replace'),
        'stderr': result.stderr.decode('utf-8', errors='replace')})
    (output / 'commands-and-exits.json').write_text(json.dumps(commands, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert result.returncode == 0, 'Directed command failed; retained raw output'
    return result.stdout


assert call('shell', 'getprop', 'ro.build.version.release').decode().strip() == '15'
assert call('shell', 'getprop', 'ro.product.model').decode().strip() == 'MODEL_ANDROID15'
apk = call('shell', 'pm', 'path', package).decode().strip().removeprefix('package:')
apk_hash = call('shell', 'run-as', package, 'sha256sum', apk).decode().split()[0].upper()
assert apk_hash == '809E54FC8FAE16B16BC141F070831C3C607CCE0FEAE090B02D6D87B5835528CF', 'Test baseline changed: stop, report identity'
pins = {
    'zcode.cjs': 'B1DF2EF3E5BD76C4AF3ECB296BC003A10D3F13191A26610BD0BA940FEADAD529',
    'bootstrap.cjs': 'FB64415E39BDAFA0F9603832ECCA890AD7ACA10B8E6A11967FFF52B1CC449DB9',
    'gateway.cjs': 'CD9FE220F483F058FA9CBB1E7BA2DD24134AF79FC32F4DD0DF2392C3A4B0AA22',
    'carrier-authorization.cjs': '47C56F1E693E0DF2E31C0150374B5D821B0AF2A5FD05CCCC3A99884FBE1D6144',
}
for name, expected in pins.items():
    actual = call('shell', 'run-as', package, 'sha256sum', 'files/runtime/' + name).decode().split()[0].upper()
    assert actual == expected, name + ' changed: stop, report identity'
script = Path(__file__).with_name('core-skill-catalog-device.cjs')
remote = '/data/local/tmp/core-skill-catalog-device.cjs'
call('push', str(script), remote)
node = apk.rsplit('/', 1)[0] + '/lib/arm64/libnode.so'
line = 'OPENSSL_CONF=/dev/null LD_LIBRARY_PATH=/data/user/0/' + package + '/files/runtime/lib ' + shlex.quote(node) + ' ' + remote + ' ' + package
raw = call('shell', 'run-as', package, 'sh', '-c', shlex.quote(line))
(output / 'catalog-results.json').write_bytes(raw)
data = json.loads(raw)
assert data['verdict'] == 'PASS' and data['app'] == package and data['node'] == 'v24.18.0'
assert len(data['checks']) == 7 and all(data['checks'].values())
identity = {'serial': serial, 'android': '15', 'apkSha256': apk_hash, 'runtimePins': pins,
    'driverSha256': hashlib.sha256(script.read_bytes()).hexdigest().upper(),
    'workspaceFixture': data['workspace'], 'scope': 'catalog only; no model or new production capability'}
(output / 'runtime-identity.json').write_text(json.dumps(identity, indent=2) + '\n', encoding='utf-8')
print('PASS seven native Core catalog conditions on assigned Android15; dependency behavior is a documented gap')
