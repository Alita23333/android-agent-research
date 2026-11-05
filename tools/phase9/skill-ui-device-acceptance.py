"""Pin/install reviewed UI candidate; run real SAF/Compose/model instrumentation on Android17."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
APP, SERIAL = 'dev.alita.androidagent', 'DEVICE_ANDROID17'
ADB = os.environ['ANDROID_ADB']
BASELINE = '422CF3E5DB29F81A88B306ECE04E62102CE688395A9C0F6A30B3EB212D11674B'
OUT = ROOT / 'docs/handoff/evidence/skill-ui1' / str(time.time_ns())
OUT.mkdir(exist_ok=False)
commands = []
RETRY = sys.argv[2] if len(sys.argv) == 3 and sys.argv[1] == '--retry-installed' else None
assert len(sys.argv) == 1 or RETRY

def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest().upper()

def adb(*args, check=True, timeout=180):
    p = subprocess.run([ADB, '-s', SERIAL, *args], capture_output=True, timeout=timeout)
    commands.append(dict(argv=[ADB, '-s', SERIAL, *args], exit=p.returncode,
        stdout=p.stdout.decode('utf-8', errors='replace'), stderr=p.stderr.decode('utf-8', errors='replace')))
    (OUT / 'commands-and-exits.json').write_text(json.dumps(commands, indent=2) + '\n')
    assert not check or p.returncode == 0, 'device command failed; see evidence'
    return p

def main():
    assert adb('shell', 'getprop', 'ro.build.version.release').stdout.decode().strip() == '17'
    assert adb('shell', 'getprop', 'ro.product.model').stdout.decode().strip() == 'MODEL_ANDROID17'
    current = adb('shell', 'pm', 'path', APP).stdout.decode().strip().removeprefix('package:')
    assert adb('shell', 'run-as', APP, 'sha256sum', current).stdout.decode().split()[0].upper() == (RETRY or BASELINE)
    apk = ROOT / 'app/build/outputs/apk/debug/app-debug.apk'
    test = ROOT / 'app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk'
    if RETRY:
        assert RETRY == sha(apk), 'retry must use exact already installed candidate'
    manifest = ROOT / 'app/build/intermediates/packaged_manifests/debugAndroidTest/processDebugAndroidTestManifest/AndroidManifest.xml'
    xml = ET.fromstring(manifest.read_text())
    runner = xml.find('instrumentation')
    assert xml.attrib['package'] == APP + '.test'
    assert runner.attrib['{http://schemas.android.com/apk/res/android}targetPackage'] == APP
    assert runner.attrib['{http://schemas.android.com/apk/res/android}name'] == 'androidx.test.runner.AndroidJUnitRunner'
    with zipfile.ZipFile(apk) as bundle:
        prior = ROOT / 'docs/handoff/evidence/skill-bindings1/skill-session-bindings1-candidate.apk'
        with zipfile.ZipFile(prior) as old:
            assert bundle.read('assets/zcode-runtime/payload-SHA256SUMS.txt') == old.read('assets/zcode-runtime/payload-SHA256SUMS.txt'), 'UI-only change must retain exact runtime payload'
    (OUT / 'candidate.apk').write_bytes(apk.read_bytes())
    (OUT / 'test.apk').write_bytes(test.read_bytes())
    (OUT / 'test-AndroidManifest.xml').write_bytes(manifest.read_bytes())
    identity = dict(serial=SERIAL, baseline=BASELINE, retryInstalled=RETRY, candidate=sha(apk), test=sha(test), runtimePayloadUnchanged=True)
    (OUT / 'identity.json').write_text(json.dumps(identity, indent=2) + '\n')
    adb('shell', 'am', 'force-stop', APP)
    if not RETRY:
        adb('install', '-r', str(apk))
    adb('install', '-r', str(test))
    run = adb('shell', 'am', 'instrument', '-w', '-e', 'class', APP + '.SkillManagerUiDeviceTest',
        APP + '.test/androidx.test.runner.AndroidJUnitRunner', check=False, timeout=660)
    (OUT / 'instrumentation.stdout').write_bytes(run.stdout)
    (OUT / 'instrumentation.stderr').write_bytes(run.stderr)
    result = adb('exec-out', 'run-as', APP, 'cat', 'cache/skill-ui1-result.json', check=False)
    (OUT / 'result.json').write_bytes(result.stdout)
    # Keep image/model evidence as exact bytes. Never put screenshot bytes in command logs.
    listing = adb('shell', 'run-as', APP, 'ls', 'cache').stdout.decode().splitlines()
    for name in listing:
        if name.startswith('skill-ui1-') and name.endswith(('.png', '-model.json')):
            if name == 'skill-ui1-failure.png' and b'OK (1 test)' in run.stdout:
                continue  # Previous failed run may have left this cache image; not PASS evidence.
            p = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'run-as', APP, 'cat', 'cache/' + name], capture_output=True, timeout=30)
            assert p.returncode == 0
            (OUT / name).write_bytes(p.stdout)
    assert run.returncode == 0 and b'OK (1 test)' in run.stdout and b'FAILURES' not in run.stdout
    report = json.loads(result.stdout)
    assert report['verdict'] == 'PASS' and report['actualSystemPicker'] and report['liveOldV1NewV2']
    assert report['realModelTurns'] == 3 and report['retiredThroughUi'] and report['oldVersionsRetained']
    print('PASS real SAF/UI/live model Skill flow; ' + str(OUT))

try:
    main()
except BaseException as error:
    (OUT / 'failure.json').write_text(json.dumps(dict(type=type(error).__name__, message=str(error)), indent=2) + '\n')
    print('FAIL retained evidence ' + str(OUT))
    raise
