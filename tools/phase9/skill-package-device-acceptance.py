"""Assigned Android17 host package storage proof; installs only instrumentation APK.
No Core activation, provider/model request, root or production APK installation.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'docs/handoff/evidence/skill-package1'
SERIAL = 'DEVICE_ANDROID17'
APP = 'dev.alita.androidagent'
PRIMARY = 'B87638B935F77D225FD2EAD46D1C163B992D8398A5B7359362A9185D65A4650B'
ADB = os.environ['ANDROID_ADB']
EVIDENCE.mkdir(parents=True, exist_ok=True)
commands = []


def adb(*args):
    result = subprocess.run([ADB, '-s', SERIAL, *args], capture_output=True,
                            text=True, encoding='utf-8', timeout=120)
    commands.append(dict(argv=['adb', '-s', SERIAL, *args], exit=result.returncode,
                         stdout=result.stdout, stderr=result.stderr))
    (EVIDENCE / 'device-commands.json').write_text(json.dumps(commands, indent=2) + '\n')
    assert result.returncode == 0, result.stderr
    return result.stdout


def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest().upper()


def runtime_pins():
    pins = {}
    for name in ['zcode.cjs', 'bootstrap.cjs', 'gateway.cjs', 'carrier-authorization.cjs']:
        actual = adb('shell', 'run-as', APP, 'sha256sum', 'files/runtime/' + name).split()[0].upper()
        assert actual == sha(ROOT / 'app/src/main/assets/zcode-runtime' / name), name
        pins[name] = actual
    return pins


assert adb('shell', 'getprop', 'ro.build.version.release').strip() == '17'
apk_path = adb('shell', 'pm', 'path', APP).strip().removeprefix('package:')
assert adb('shell', 'run-as', APP, 'sha256sum', apk_path).split()[0].upper() == PRIMARY
before = runtime_pins()
candidate = ROOT / 'app/build/outputs/apk/debug/app-debug.apk'
test_apk = ROOT / 'app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk'
manifest = ROOT / 'app/build/intermediates/packaged_manifests/debugAndroidTest/processDebugAndroidTestManifest/AndroidManifest.xml'
tree = ET.fromstring(manifest.read_text())
runner = tree.find('instrumentation')
ns = '{http://schemas.android.com/apk/res/android}'
assert tree.attrib['package'] == APP + '.test'
assert runner.attrib[ns + 'targetPackage'] == APP
assert runner.attrib[ns + 'name'] == 'androidx.test.runner.AndroidJUnitRunner'
(EVIDENCE / 'test-AndroidManifest.xml').write_bytes(manifest.read_bytes())
for file, name in [(candidate, 'skill-package1-candidate.apk'), (test_apk, 'skill-package1-test.apk')]:
    (EVIDENCE / name).write_bytes(file.read_bytes())
adb('install', '-r', str(test_apk))
output = adb('shell', 'am', 'instrument', '-w', '-e', 'class',
             'dev.alita.androidagent.CoreSkillPackageDeviceTest',
             APP + '.test/androidx.test.runner.AndroidJUnitRunner')
(EVIDENCE / 'device-tests.log').write_text(output, encoding='utf-8')
assert 'OK (3 tests)' in output and 'CoreSkillPackageDeviceTest:...' in output
assert 'FAILURES!!!' not in output
assert adb('shell', 'run-as', APP, 'sha256sum', apk_path).split()[0].upper() == PRIMARY
assert runtime_pins() == before
suites = [ET.parse(p).getroot() for p in (ROOT / 'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml')]
summary = dict(scope='host package storage/readiness only; no Core Skill activation or model proof',
               installedPrimaryApkSha256=PRIMARY, candidateApkSha256=sha(candidate), candidateInstalled=False,
               testApkSha256=sha(test_apk), serial=SERIAL, nativeTests=3,
               jvmTests=sum(int(s.attrib['tests']) for s in suites),
               jvmFailures=sum(int(s.attrib['failures']) + int(s.attrib['errors']) for s in suites),
               jvmSkipped=sum(int(s.attrib['skipped']) for s in suites),
               manifestTarget=runner.attrib[ns + 'targetPackage'], runtimePins=before)
assert summary['jvmTests'] == 48 and summary['jvmFailures'] == summary['jvmSkipped'] == 0
(EVIDENCE / 'validation-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
