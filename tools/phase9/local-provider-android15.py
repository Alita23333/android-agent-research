"""Directed Node/provider compatibility on ZCode's assigned device; no Core/model changes."""
from pathlib import Path
import hashlib
import json
import os
import shlex
import subprocess
import time

ADB = os.environ['ANDROID_ADB']
OUT = Path(os.environ['TEST_EVIDENCE_DIR']).resolve()
OUT.mkdir(parents=True, exist_ok=True)
HERE = Path(__file__).resolve().parent
serial, package = 'DEVICE_ANDROID15', 'dev.zcode.nodepoc'
records = []


def call(*args):
    argv = [ADB, '-s', serial, *args]
    p = subprocess.run(argv, capture_output=True, timeout=35)
    records.append({'argv': argv, 'exit': p.returncode, 'stdout': p.stdout.decode('utf-8', errors='replace'),
        'stderr': p.stderr.decode('utf-8', errors='replace')})
    (OUT / 'commands-and-exits.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert p.returncode == 0, 'Directed probe failed; raw outputs retained'
    return p.stdout


assert call('shell', 'getprop', 'ro.build.version.release').decode().strip() == '15'
assert call('shell', 'getprop', 'ro.product.model').decode().strip() == 'MODEL_ANDROID15'
apk = call('shell', 'pm', 'path', package).decode().strip().removeprefix('package:')
expected_apk = '809E54FC8FAE16B16BC141F070831C3C607CCE0FEAE090B02D6D87B5835528CF'
assert call('shell', 'run-as', package, 'sha256sum', apk).decode().split()[0].upper() == expected_apk
pins = {'zcode.cjs': 'B1DF2EF3E5BD76C4AF3ECB296BC003A10D3F13191A26610BD0BA940FEADAD529',
    'bootstrap.cjs': 'FB64415E39BDAFA0F9603832ECCA890AD7ACA10B8E6A11967FFF52B1CC449DB9',
    'gateway.cjs': 'CD9FE220F483F058FA9CBB1E7BA2DD24134AF79FC32F4DD0DF2392C3A4B0AA22',
    'carrier-authorization.cjs': '47C56F1E693E0DF2E31C0150374B5D821B0AF2A5FD05CCCC3A99884FBE1D6144'}
for name, sha in pins.items():
    assert call('shell', 'run-as', package, 'sha256sum', 'files/runtime/' + name).decode().split()[0].upper() == sha
provider = HERE.parent / 'source/providers/text-digest/provider.cjs'
probe = HERE / 'local-provider-stdio-probe.cjs'
call('push', str(provider), '/data/local/tmp/local-provider-pure.cjs')
call('push', str(probe), '/data/local/tmp/local-provider-stdio-probe.cjs')
relative = 'cache/local-provider-probe-' + str(time.time_ns())
node = apk.rsplit('/', 1)[0] + '/lib/arm64/libnode.so'
line = 'mkdir -p ' + relative + ' && cp /data/local/tmp/local-provider-pure.cjs ' + relative + '/provider.cjs && cp /data/local/tmp/local-provider-stdio-probe.cjs ' + relative + '/probe.cjs && OPENSSL_CONF=/dev/null LD_LIBRARY_PATH=/data/user/0/' + package + '/files/runtime/lib ' + shlex.quote(node) + ' ' + relative + '/probe.cjs /data/user/0/' + package + '/' + relative + '/provider.cjs'
raw = call('shell', 'run-as', package, 'sh', '-c', shlex.quote(line))
(OUT / 'stdio-results.json').write_bytes(raw)
data = json.loads(raw)
assert data['verdict'] == 'PASS' and len(data['checks']) == 8 and data['node'] == 'v24.18.0'
assert data['providerSha256'] == hashlib.sha256(provider.read_bytes()).hexdigest()
assert call('shell', 'run-as', package, 'sha256sum', apk).decode().split()[0].upper() == expected_apk
(OUT / 'runtime-identity.json').write_text(json.dumps({'serial': serial, 'android': '15', 'apkSha256': expected_apk,
    'providerSha256': data['providerSha256'], 'node': data['node'], 'runtimePins': pins,
    'fixture': relative, 'scope': 'independent local process protocol; no Gateway/dispatcher/model integration claim'}, indent=2) + '\n', encoding='utf-8')
print('PASS eight local-provider compatibility cases; primary Android15 APK unchanged')
