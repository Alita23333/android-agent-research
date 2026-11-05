"""Exact Android17 candidate install + private-cache storage/stdio regression. No other device."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/handoff/evidence/provider-package1'
ADB = os.environ['ANDROID_ADB']
APP, SERIAL = 'dev.alita.androidagent', 'DEVICE_ANDROID17'
BASELINE = 'D944F72FF15E77AAF3E486990581541EEEFE338C0E888AAE10C6BB91E9CFFCAC'
records = []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def adb(*args, timeout=60):
    p = subprocess.run([ADB, '-s', SERIAL, *args], capture_output=True, timeout=timeout)
    records.append(dict(argv=[ADB, '-s', SERIAL, *args], exit=p.returncode,
                        stdout=p.stdout.decode('utf-8', 'replace'), stderr=p.stderr.decode('utf-8', 'replace')))
    (OUT / 'commands-and-exits.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
    assert p.returncode == 0, 'device command failed; see raw evidence'
    return p.stdout


assert adb('shell', 'getprop', 'ro.build.version.release').decode().strip() == '17'
assert adb('shell', 'getprop', 'ro.product.model').decode().strip() == 'MODEL_ANDROID17'
current = adb('shell', 'pm', 'path', APP).decode().strip().removeprefix('package:')
assert adb('shell', 'run-as', APP, 'sha256sum', current).decode().split()[0].upper() == BASELINE
apk = ROOT / 'app/build/outputs/apk/debug/app-debug.apk'
test = ROOT / 'app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk'
manifest = ROOT / 'app/build/intermediates/packaged_manifests/debugAndroidTest/processDebugAndroidTestManifest/AndroidManifest.xml'
xml = ET.fromstring(manifest.read_text(encoding='utf-8'))
assert xml.attrib['package'] == APP + '.test'
assert xml.find('instrumentation').attrib['{http://schemas.android.com/apk/res/android}targetPackage'] == APP
assert xml.find('instrumentation').attrib['{http://schemas.android.com/apk/res/android}name'] == 'androidx.test.runner.AndroidJUnitRunner'
with zipfile.ZipFile(apk) as candidate, zipfile.ZipFile(OUT.parent / 'skill-ui1/skill-ui1-current.apk') as prior:
    payload = candidate.read('assets/zcode-runtime/payload-SHA256SUMS.txt')
    assert payload == prior.read('assets/zcode-runtime/payload-SHA256SUMS.txt')
    for line in payload.decode().splitlines():
        expected, name = line.split('  ', 1)
        entry = name.replace('jniLibs/', 'lib/')
        assert candidate.read(entry) == prior.read(entry)
        assert hashlib.sha256(candidate.read(entry)).hexdigest() == expected
(OUT / 'candidate.apk').write_bytes(apk.read_bytes())
(OUT / 'test.apk').write_bytes(test.read_bytes())
(OUT / 'test-AndroidManifest.xml').write_bytes(manifest.read_bytes())
identity = dict(serial=SERIAL, baselineApk=BASELINE, apkSha256=sha(apk), testApkSha256=sha(test),
                driverSha256=sha(Path(__file__)), runtimePayloadUnchanged=True)
(OUT / 'build-identity.json').write_text(json.dumps(identity, indent=2) + '\n', encoding='utf-8')
adb('shell', 'am', 'force-stop', APP)
adb('install', '-r', str(apk))
adb('install', '-r', str(test))
for name, count in [('LocalProviderPackageDeviceTest', 4), ('LocalProviderDeviceTest', 5)]:
    raw = adb('shell', 'am', 'instrument', '-w', '-e', 'class', APP + '.' + name,
              APP + '.test/androidx.test.runner.AndroidJUnitRunner', timeout=120)
    (OUT / (name + '.stdout')).write_bytes(raw)
    (OUT / (name + '.stderr')).write_text(records[-1]['stderr'], encoding='utf-8')
    assert ('OK (' + str(count) + ' tests)').encode() in raw and b'FAILURES' not in raw
    assert records[-1]['stderr'] == ''
adb('shell', 'su', '-c', 'am start -n dev.alita.androidagent/.zcode.runtime.ZCodeActivity')
adb('forward', 'tcp:18765', 'tcp:8765')
token = adb('exec-out', 'run-as', APP, 'cat', 'files/runtime/bridge-token').decode().strip()
for attempt in range(60):
    try:
        req = urllib.request.Request('http://127.0.0.1:18765/status', headers={'X-Bridge-Token': token})
        with urllib.request.urlopen(req, timeout=3) as response:
            status = json.load(response)
        if status.get('phase') == 'ready':
            break
    except Exception:
        pass
    time.sleep(1)
else:
    raise AssertionError('Host did not return ready after native tests')
current = adb('shell', 'pm', 'path', APP).decode().strip().removeprefix('package:')
assert adb('shell', 'run-as', APP, 'sha256sum', current).decode().split()[0].upper() == identity['apkSha256']
(OUT / 'native-summary.json').write_text(json.dumps(dict(verdict='PASS', packageTests=4, stdioTests=5,
    hostReady=True, identity=identity, scope='private cache storage and existing fixed stdio boundary; no imported provider admission/model claim'), indent=2) + '\n', encoding='utf-8')
print('PASS four native storage and five stdio tests; product host ready')
