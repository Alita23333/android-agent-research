"""Android17-only pinned provider binding acceptance in separate application ID. No product reinstall."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import time
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/handoff/evidence/provider-review1' / str(time.time_ns())
OUT.mkdir(parents=True, exist_ok=False)
ADB = os.environ['ANDROID_ADB']
SERIAL, PRODUCT, TEST = 'DEVICE_ANDROID17', 'dev.alita.androidagent', 'dev.alita.androidagent.isolationtest'
BASELINE = 'C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D'
commands = []


def adb(*args, check=True, timeout=60):
    argv = [ADB, '-s', SERIAL, *args]
    try:
        p = subprocess.run(argv, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        commands.append(dict(argv=argv, exit=None, timeout=True,
            stdout=(error.stdout or b'').decode('utf-8', 'replace'), stderr=(error.stderr or b'').decode('utf-8', 'replace')))
        raise
    finally:
        (OUT / 'commands-and-exits.json').write_text(json.dumps(commands, indent=2)+'\n', encoding='utf-8')
    commands.append(dict(argv=argv, exit=p.returncode, stdout=p.stdout.decode('utf-8', 'replace'), stderr=p.stderr.decode('utf-8', 'replace')))
    (OUT / 'commands-and-exits.json').write_text(json.dumps(commands, indent=2)+'\n', encoding='utf-8')
    assert not check or p.returncode == 0, 'device command failed; raw evidence retained'
    return p


def production_hash():
    path = adb('shell', 'pm', 'path', PRODUCT).stdout.decode().strip().removeprefix('package:')
    digest = adb('shell', 'run-as', PRODUCT, 'sha256sum', path).stdout.decode().split()[0].upper()
    assert digest == BASELINE
    return digest


try:
    assert adb('shell', 'getprop', 'ro.build.version.release').stdout.decode().strip() == '17'
    assert adb('shell', 'getprop', 'ro.product.model').stdout.decode().strip() == 'MODEL_ANDROID17'
    before = production_hash()
    apk = ROOT / 'app/build/outputs/apk/isolationTest/app-isolationTest.apk'
    manifest = ROOT / 'app/build/intermediates/merged_manifests/isolationTest/processIsolationTestManifest/AndroidManifest.xml'
    xml = ET.fromstring(manifest.read_text()); android = '{http://schemas.android.com/apk/res/android}'
    assert xml.attrib['package'] == TEST
    service = next(e for e in xml.findall('application/service') if e.attrib[android+'name'].endswith('.execution.isolation.IsolatedNodeService'))
    assert service.attrib[android+'isolatedProcess'] == 'true' and service.attrib[android+'exported'] == 'false'
    assert xml.find('application').attrib[android+'name'] == 'dev.alita.androidagent.AgentApplication'
    (OUT / 'manifest.xml').write_bytes(manifest.read_bytes())
    with zipfile.ZipFile(apk) as bundle:
        runtime = json.loads(bundle.read('assets/isolated-provider-runtime.json'))
        for library in runtime['libraries']:
            assert hashlib.sha256(bundle.read('lib/arm64-v8a/'+library['packagedName'])).hexdigest() == library['sha256']
        assert hashlib.sha256(bundle.read('lib/arm64-v8a/libisolatednode.so')).hexdigest() == runtime['shimSha256']
        assert hashlib.sha256(bundle.read('assets/zcode-runtime/payload-SHA256SUMS.txt')).hexdigest() == runtime['payloadManifestSha256']
    (OUT / 'test.apk').write_bytes(apk.read_bytes())
    for name in ['native-build.json', 'shim-elf.txt']:
        (OUT / name).write_bytes((ROOT / 'app/build/isolated-runtime' / name).read_bytes())
    files = [ROOT / 'app/build.gradle.kts', ROOT / 'app/src/main/AndroidManifest.xml',
        ROOT / 'app/src/main/java/dev/alita/androidagent/AgentApplication.kt',
        ROOT / 'app/src/main/java/dev/alita/androidagent/execution/IsolatedProviderProcess.java',
        ROOT / 'app/src/main/java/dev/alita/androidagent/tools/JsonRpcStdioProvider.kt',
        *sorted((ROOT / 'app/src/main/java/dev/alita/androidagent/execution/isolation').glob('*.java')),
        ROOT / 'app/src/main/java/dev/alita/androidagent/tools/LocalProviderCatalog.kt',
        ROOT / 'app/src/main/java/dev/alita/androidagent/tools/ProviderReviewStore.kt',
        ROOT / 'app/src/test/java/dev/alita/androidagent/ProviderReviewStoreTest.kt',
        ROOT / 'app/src/main/java/dev/alita/androidagent/tools/PinnedIsolatedProvider.kt',
        ROOT / 'app/src/main/java/dev/alita/androidagent/zcode/adapter/AndroidToolContracts.kt',
        ROOT / 'app/src/main/java/dev/alita/androidagent/zcode/adapter/ReadOnlyToolDispatcher.kt',
        ROOT / 'app/src/main/java/dev/alita/androidagent/zcode/adapter/ZCodeToolMapping.kt',
        ROOT / 'app/src/main/java/dev/alita/androidagent/zcode/runtime/ZCodeCarrierWorker.kt',
        *sorted((ROOT / 'app/src/isolationTest').rglob('*')), ROOT / 'app/src/main/native/isolated_node.c',
        ROOT / 'tools/phase9/prepare-product-isolation.py', Path(__file__)]
    sources = {}
    for path in files:
        if not path.is_file(): continue
        relative = path.relative_to(ROOT)
        copy = OUT / 'source' / relative; copy.parent.mkdir(parents=True, exist_ok=True); copy.write_bytes(path.read_bytes())
        sources[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    (OUT / 'source-sha256.json').write_text(json.dumps(sources, indent=2)+'\n', encoding='utf-8')
    identity = dict(productionBefore=before, apkSha256=hashlib.sha256(apk.read_bytes()).hexdigest().upper(),
        driverSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest().upper(), runtime=runtime)
    (OUT / 'identity.json').write_text(json.dumps(identity, indent=2)+'\n', encoding='utf-8')
    adb('install', '-r', str(apk))
    adb('shell', 'am', 'force-stop', TEST)
    adb('shell', 'am', 'start', '-n', TEST+'/dev.alita.androidagent.execution.isolation.ReviewProbeActivity', '--es', 'runId', OUT.name)
    result = None
    for _ in range(65):
        observed = adb('exec-out', 'run-as', TEST, 'cat', 'files/review-probe-result.json', check=False)
        if observed.returncode == 0:
            try:
                value = json.loads(observed.stdout)
                if value.get('runId') == OUT.name:
                    result = value; (OUT / 'result.json').write_bytes(observed.stdout)
                    if result.get('verdict') in {'PASS', 'FAIL'}: break
            except ValueError: pass
        time.sleep(1)
    identity['productionAfter'] = production_hash()
    (OUT / 'identity.json').write_text(json.dumps(identity, indent=2)+'\n', encoding='utf-8')
    owner_pid = adb('shell', 'pidof', TEST, check=False).stdout.decode().strip()
    pids = [int(pid) for pid in owner_pid.split() if pid.isdigit()]
    pids += [row['pid'] for row in (result or {}).get('reports', [])]
    for pid in sorted(set(pids)):
        (OUT / f'process-{pid}.log').write_bytes(adb('logcat', '-d', '--pid='+str(pid), check=False).stdout)
    assert result and result.get('verdict') == 'PASS', 'product backend not proven; see retained failure'
    for field in ['restoredReviewV1', 'retirementPreservedPin', 'revocationRejected', 'tamperRejected', 'physicalReportsVerified', 'staleCarrierPinRejected', 'indexLinkRejected', 'workspaceLinkRejected', 'reviewLinkRejected']:
        assert result[field] is True
    assert result['oldHash'] != result['newHash']
    assert [row['version'] for row in result['reports']] == ['v1','v1','v2']
    for i, row in enumerate(result['reports']):
        assert row['uid'] != 0
        expected = result['newHash'] if i == 2 else result['oldHash']
        assert row['contentHash'] == expected
        artifact = row['artifact']
        assert artifact['uri'].startswith('/data/user/0/'+TEST+'/files/artifacts/'+('new-probe' if i == 2 else 'binding-probe')+'/')
        report = adb('exec-out','run-as',TEST,'cat',artifact['uri']).stdout
        assert len(report) == artifact['size'] and b'PRIVATE_REPORT_CANARY' not in report
        value=json.loads(report)
        assert value['data']['version'] == row['version'] and value['data']['_hostProvider']['contentHash'] == expected
        (OUT / ('artifact-'+str(i)+'.json')).write_bytes(report)
    print('PASS actual imported catalog/review persistence+reconstruction/session resolver/v1-v1-v2 isolated execution/artifacts/revoke+tamper refusal; evidence '+str(OUT))
finally:
    adb('shell', 'am', 'force-stop', TEST, check=False)
