"""Android17 test APK only: actual Core -> HTTP carrier -> Gateway -> isolated provider. No model."""
from pathlib import Path
import hashlib
import json
import os
import shlex
import subprocess
import time
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/handoff/evidence/provider-projection1' / str(time.time_ns())
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
    else:
        commands.append(dict(argv=argv, exit=p.returncode, stdout=p.stdout.decode('utf-8', 'replace'), stderr=p.stderr.decode('utf-8', 'replace')))
    finally:
        (OUT / 'commands-and-exits.json').write_text(json.dumps(commands, indent=2)+'\n', encoding='utf-8')
    assert not check or p.returncode == 0, 'device command failed; raw evidence retained'
    return p


def production_hash():
    apk = adb('shell', 'pm', 'path', PRODUCT).stdout.decode().strip().removeprefix('package:')
    value = adb('shell', 'run-as', PRODUCT, 'sha256sum', apk).stdout.decode().split()[0].upper()
    assert value == BASELINE
    return value


def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


try:
    assert adb('shell', 'getprop', 'ro.build.version.release').stdout.decode().strip() == '17'
    assert adb('shell', 'getprop', 'ro.product.model').stdout.decode().strip() == 'MODEL_ANDROID17'
    before = production_hash()
    apk = ROOT / 'app/build/outputs/apk/isolationTest/app-isolationTest.apk'
    manifest = ROOT / 'app/build/intermediates/merged_manifests/isolationTest/processIsolationTestManifest/AndroidManifest.xml'
    xml = ET.fromstring(manifest.read_text()); android = '{http://schemas.android.com/apk/res/android}'
    assert xml.attrib['package'] == TEST
    assert any(e.attrib[android+'name'].endswith('.ProjectionProbeActivity') for e in xml.findall('application/activity'))
    service = next(e for e in xml.findall('application/service') if e.attrib[android+'name'].endswith('.execution.isolation.IsolatedNodeService'))
    assert service.attrib[android+'isolatedProcess'] == 'true' and service.attrib[android+'exported'] == 'false'
    (OUT / 'manifest.xml').write_bytes(manifest.read_bytes())
    with zipfile.ZipFile(apk) as bundle:
        runtime = json.loads(bundle.read('assets/isolated-provider-runtime.json'))
        for library in runtime['libraries']:
            assert hashlib.sha256(bundle.read('lib/arm64-v8a/'+library['packagedName'])).hexdigest() == library['sha256']
        assert hashlib.sha256(bundle.read('lib/arm64-v8a/libisolatednode.so')).hexdigest() == runtime['shimSha256']
        assert hashlib.sha256(bundle.read('assets/zcode-runtime/payload-SHA256SUMS.txt')).hexdigest() == runtime['payloadManifestSha256']
    (OUT / 'test.apk').write_bytes(apk.read_bytes())
    files = [ROOT / 'app/build.gradle.kts', ROOT / 'app/src/main/AndroidManifest.xml',
             ROOT / 'app/src/main/java/dev/alita/androidagent/AgentApplication.kt',
             *sorted((ROOT / 'app/src/main/java/dev/alita/androidagent/tools').glob('*.kt')),
             *sorted((ROOT / 'app/src/main/java/dev/alita/androidagent/zcode/adapter').glob('*.kt')),
             ROOT / 'app/src/main/java/dev/alita/androidagent/zcode/runtime/ZCodeCarrierWorker.kt',
             ROOT / 'app/src/main/java/dev/alita/androidagent/zcode/runtime/ZCodeRuntimeBundle.kt',
             *sorted((ROOT / 'app/src/isolationTest').rglob('*')),
             *sorted((ROOT / 'app/src/main/assets/zcode-runtime').glob('*.cjs')),
             ROOT / 'app/src/main/assets/zcode-runtime/runtime-manifest.json',
             ROOT / 'app/src/main/assets/zcode-runtime/payload-SHA256SUMS.txt',
             *sorted((ROOT / 'tools/phase9').glob('provider-projection*')),
             ROOT / 'tools/phase9/provider-session-bindings-test.cjs',
             ROOT / 'tools/phase9/provider-declaration-settlement-test.cjs']
    sources = {}
    for file in files:
        if not file.is_file(): continue
        relative = file.relative_to(ROOT); copy = OUT / 'source' / relative
        copy.parent.mkdir(parents=True, exist_ok=True); copy.write_bytes(file.read_bytes()); sources[relative.as_posix()] = sha(file)
    (OUT / 'source-sha256.json').write_text(json.dumps(sources, indent=2)+'\n', encoding='utf-8')
    identity = dict(productionBefore=before, testApk=sha(apk).upper(), driverSha256=sha(Path(__file__)), runtime=runtime)
    (OUT / 'identity.json').write_text(json.dumps(identity, indent=2)+'\n', encoding='utf-8')
    adb('install', '-r', str(apk))
    adb('shell', 'am', 'force-stop', TEST)
    adb('shell', 'am', 'start', '-n', TEST+'/dev.alita.androidagent.execution.isolation.ProjectionProbeActivity', '--es', 'runId', OUT.name)
    result = None
    for _ in range(130):
        observed = adb('exec-out', 'run-as', TEST, 'cat', 'files/projection-probe-result.json', check=False)
        if observed.returncode == 0:
            try:
                value = json.loads(observed.stdout)
                if value.get('runId') == OUT.name:
                    result = value; (OUT / 'result.json').write_bytes(observed.stdout)
                    if result.get('verdict') != 'RUNNING': break
            except ValueError: pass
        time.sleep(1)
    identity['productionAfter'] = production_hash()
    (OUT / 'identity.json').write_text(json.dumps(identity, indent=2)+'\n', encoding='utf-8')
    assert result and result.get('verdict') == 'PASS_SCOPED_CORE_GATEWAY_PROVIDER_TRANSPORT', 'see retained stage/failure'
    assert result['oldPin']['contentHash'] != result['newPin']['contentHash']
    assert result['oldSession'] != result['newSession']
    assert [r['expectedVersion'] for r in result['reports']] == ['v1', 'v1', 'v2']
    # Pull physical host-created reports, match session/call IDs, actual bytes and SHA-256.
    for i, row in enumerate(result['reports']):
        response = row['response']; data = response['structuredContent']['data']
        pin = result['newPin'] if i == 2 else result['oldPin']
        assert data['_hostProvider']['contentHash'] == pin['contentHash']
        assert data['_hostProvider']['definitionHash'] == pin['definitionHash']
        assert data['sha256'] == hashlib.sha256(b'hello').hexdigest() and data['bytes'] == 5
        artifacts = response['artifacts']; assert len(artifacts) == 1
        artifact = artifacts[0]
        assert artifact['uri'].startswith('/data/user/0/'+TEST+'/files/artifacts/'+row['sessionId']+'/')
        report = adb('exec-out', 'run-as', TEST, 'cat', artifact['uri']).stdout
        assert len(report) == artifact['size']; physical = json.loads(report)
        assert physical['data'] == data
        call_id = physical['callId']
        joined = [op for op in row['operations'] if 'call_id='+call_id+' ' in op['detail']]
        assert len(joined) == 1 and joined[0]['decision'] == 'allow' and joined[0]['result'] == 'ok'
        (OUT / ('artifact-'+str(i)+'.json')).write_bytes(report)
    # Actual Android Node tests: Windows-only skip must disappear on the phone.
    installed = adb('shell', 'pm', 'path', TEST).stdout.decode().strip().removeprefix('package:')
    assert adb('shell', 'run-as', TEST, 'sha256sum', installed).stdout.decode().split()[0].upper() == identity['testApk']
    node = installed.rsplit('/', 1)[0]+'/lib/arm64/libnode.so'
    cache = 'cache/provider-projection-'+OUT.name
    home = '/data/user/0/'+TEST+'/'+cache
    adb('shell', 'run-as', TEST, 'mkdir', '-p', cache)
    for name in ['provider-projection-test.cjs', 'provider-projection-fixture.cjs', 'provider-session-bindings-test.cjs', 'provider-declaration-settlement-test.cjs']:
        file = ROOT / 'tools/phase9' / name; temporary = '/data/local/tmp/projection-'+OUT.name+'-'+name
        adb('push', str(file), temporary); adb('shell', 'run-as', TEST, 'cp', temporary, cache+'/'+name)
        assert adb('shell', 'run-as', TEST, 'sha256sum', cache+'/'+name).stdout.decode().split()[0] == sha(file)
    environment = dict(TEST_RUNTIME='/data/user/0/'+TEST+'/files/runtime',
        LD_LIBRARY_PATH='/data/user/0/'+TEST+'/files/runtime/lib', TMPDIR=home, OPENSSL_CONF='/dev/null')
    prefix = ' '.join(k+'='+shlex.quote(v) for k,v in environment.items())
    test_command = prefix+' '+shlex.quote(node)+' --test --test-reporter=tap '+ ' '.join(shlex.quote(home+'/'+n) for n in [
        'provider-projection-test.cjs', 'provider-session-bindings-test.cjs', 'provider-declaration-settlement-test.cjs'])
    output = adb('shell', 'run-as', TEST, 'sh', '-c', shlex.quote(test_command)).stdout.decode()
    (OUT / 'android-boundary-tests.log').write_text(output, encoding='utf-8')
    assert '# pass 36' in output and '# fail 0' in output and '# skipped 0' in output
    production_hash()
    print('PASS scoped Core/Gateway/carrier/isolated-provider transport + Android36; no model, no production admission; '+str(OUT))
finally:
    adb('shell', 'am', 'force-stop', TEST, check=False)
