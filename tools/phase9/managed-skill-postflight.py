"""Read-only installed payload/config/provider-history checks; never emits credentials."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
APP, SERIAL = 'dev.alita.androidagent', 'DEVICE_ANDROID17'
ADB = os.environ['ANDROID_ADB']
OUT = Path(os.environ.get('PRODUCT_POSTFLIGHT_OUT', str(ROOT / 'docs/handoff/evidence/skill-bindings1/product-postflight-20261017.json')))
EXPECTED = os.environ.get('EXPECTED_PRODUCT_APK_SHA256', '422CF3E5DB29F81A88B306ECE04E62102CE688395A9C0F6A30B3EB212D11674B')
FIXTURE = os.environ.get('SKILL_FIXTURE_ID', 'bound-proof-1792243836049717400')

def adb(*args):
    return subprocess.check_output([ADB, '-s', SERIAL, *args], timeout=30)

apk_path = adb('shell', 'pm', 'path', APP).decode().strip().removeprefix('package:')
assert adb('shell', 'run-as', APP, 'sha256sum', apk_path).decode().split()[0].upper() == EXPECTED
node_path = apk_path.rsplit('/', 1)[0] + '/lib/arm64'
apk = Path(os.environ.get('PRODUCT_APK_PATH', str(ROOT / 'docs/handoff/evidence/skill-bindings1/skill-session-bindings1-candidate.apk')))
assert hashlib.sha256(apk.read_bytes()).hexdigest().upper() == EXPECTED
rows = []
with zipfile.ZipFile(apk) as bundle:
    manifest = bundle.read('assets/zcode-runtime/payload-SHA256SUMS.txt').decode()
    for line in manifest.splitlines():
        expected, name = line.split('  ', 1)
        zip_name = name.replace('jniLibs/', 'lib/')
        assert hashlib.sha256(bundle.read(zip_name)).hexdigest() == expected
        if name == 'assets/zcode-runtime/provider/personal_provider_config.json':
            continue  # Existing mutable secure-settings projection, not immutable payload.
        if name.startswith('assets/zcode-runtime/'):
            target = 'files/runtime/' + name.removeprefix('assets/zcode-runtime/')
        elif name.startswith('jniLibs/arm64-v8a/'):
            target = node_path + '/' + name.rsplit('/', 1)[1]
        elif name.startswith('assets/providers/text-digest/'):
            version = adb('exec-out', 'run-as', APP, 'cat', 'files/tool-providers/text_digest/active').decode().strip()
            target = 'files/tool-providers/text_digest/versions/' + version + '/' + name.rsplit('/', 1)[1]
        else:
            raise AssertionError('unmapped payload path')
        actual = adb('shell', 'run-as', APP, 'sha256sum', target).decode().split()[0]
        assert actual == expected, name
        rows.append(dict(path=name, sha256=actual))
cfg = json.loads(adb('exec-out', 'run-as', APP, 'cat', 'files/.zcode/cli/config.json'))
controls = dict(pluginsEnabled=cfg['plugins']['enabled'], memoryFeature=cfg['features']['memory'],
    memoryExtraction=cfg['memory']['extractionEnabled'], androidHostMcpType=cfg['mcp']['servers']['android-host']['type'])
assert controls == dict(pluginsEnabled=False, memoryFeature=False, memoryExtraction=False, androidHostMcpType='stdio')
inventory = json.loads(adb('exec-out', 'run-as', APP, 'cat', 'files/core-skill-inventory.json'))
fixture = next(p for p in inventory['packages'] if p['id'] == FIXTURE)
assert fixture['removed'] and not fixture['enabled'] and len(fixture['versions']) == 2
token = adb('exec-out', 'run-as', APP, 'cat', 'files/runtime/bridge-token').decode().strip()
req = urllib.request.Request('http://127.0.0.1:18765/session/read?id=sess_a5b744f0-762e-443e-9de1-74b83a573ff8', headers={'X-Bridge-Token': token})
with urllib.request.urlopen(req, timeout=30) as response:
    messages = json.load(response)['snapshot']['messages']
parts = [p for m in messages for p in m.get('parts', []) if p.get('type') == 'tool' and 'text_digest' in p.get('tool', '')]
assert len(parts) == 3 and all(p['state']['status'] == 'completed' for p in parts)
marker = subprocess.run([ADB, '-s', SERIAL, 'shell', 'run-as', APP, 'stat', 'files/skill-config-transaction.json'], capture_output=True, timeout=30)
assert marker.returncode != 0 and b'No such file or directory' in marker.stderr, 'unfinished config transaction'
OUT.write_text(json.dumps(dict(verdict='PASS', serial=SERIAL, apkSha256=EXPECTED, packagedCount=len(manifest.splitlines()),
    immutableInstalledCount=len(rows), payload=rows, controls=controls, retiredFixture=fixture['id'],
    retainedFixtureVersions=2, configTransactionAbsent=True, priorProviderMessages=len(messages), priorProviderToolParts=len(parts),
    scope='exact immutable installed hashes/config and preserved provider tool history; not full UI/search/vision/provider re-execution acceptance'), indent=2) + '\n')
print('PASS immutable installed payload/config/retirement/prior-provider history checks')
