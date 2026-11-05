"""Standalone Android17 isolation probe. Never installs or force-stops the product package."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import time
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get('PROBE_EVIDENCE_DIR', ROOT / 'docs/handoff/evidence/provider-isolation1')) / str(time.time_ns())
OUT.mkdir(parents=True, exist_ok=False)
ADB = os.environ['ANDROID_ADB']
PRODUCT, PROBE, SERIAL = 'dev.alita.androidagent', 'dev.alita.providerprobe', 'DEVICE_ANDROID17'
EXPECTED = 'C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D'
PROJECT = ROOT / 'experiments/provider-isolation'
rows = []


def adb(*args, check=True, timeout=60):
    argv = [ADB, '-s', SERIAL, *args]
    try:
        p = subprocess.run(argv, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        rows.append(dict(argv=argv, exit=None, timeout=True,
                         stdout=(error.stdout or b'').decode('utf-8','replace'), stderr=(error.stderr or b'').decode('utf-8','replace')))
        save_rows()
        raise
    rows.append(dict(argv=argv, exit=p.returncode, stdout=p.stdout.decode('utf-8','replace'), stderr=p.stderr.decode('utf-8','replace')))
    save_rows()
    assert not check or p.returncode == 0, 'device command failed; see raw evidence'
    return p


def save_rows():
    (OUT / 'commands-and-exits.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')


def product_identity():
    path = adb('shell','pm','path',PRODUCT).stdout.decode().strip().removeprefix('package:')
    digest = adb('shell','run-as',PRODUCT,'sha256sum',path).stdout.decode().split()[0].upper()
    assert digest == EXPECTED
    return dict(apkSha256=digest)


try:
    assert adb('shell','getprop','ro.build.version.release').stdout.decode().strip() == '17'
    assert adb('shell','getprop','ro.product.model').stdout.decode().strip() == 'MODEL_ANDROID17'
    before = product_identity()
    apk = PROJECT / 'build/outputs/apk/debug/provider-isolation-debug.apk'
    if not apk.exists():
        outputs = list((PROJECT / 'build/outputs/apk/debug').glob('*.apk'))
        assert len(outputs) == 1
        apk = outputs[0]
    source_paths = [
        ROOT / 'app/src/main/java/dev/alita/androidagent/execution/IsolatedProviderProcess.java',
        *sorted((PROJECT / 'src/main').rglob('*.java')),
        *sorted((PROJECT / 'src/main/native').glob('*.c')),
        PROJECT / 'src/main/AndroidManifest.xml', PROJECT / 'build.gradle.kts',
        PROJECT / 'src/main/assets/probe-provider.cjs', Path(__file__),
        ROOT / 'tools/phase9/prepare-provider-isolation-probe.py',
    ]
    copied = PROJECT / 'build/product-source/dev/alita/androidagent/execution/IsolatedProviderProcess.java'
    assert copied.read_bytes() == source_paths[0].read_bytes(), 're-prepare and rebuild after product facade changes'
    source_hashes = {}
    for source in source_paths:
        relative = source.relative_to(ROOT)
        target = OUT / 'source' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        source_hashes[relative.as_posix()] = hashlib.sha256(source.read_bytes()).hexdigest()
    (OUT / 'source-sha256.json').write_text(json.dumps(source_hashes,indent=2)+'\n', encoding='utf-8')
    with zipfile.ZipFile(apk) as bundle:
        payload = json.loads(bundle.read('assets/payload-identity.json'))
        for row in payload['libraries']:
            assert hashlib.sha256(bundle.read('lib/arm64-v8a/' + row['packagedName'])).hexdigest() == row['sha256']
    manifest = PROJECT / 'build/intermediates/merged_manifests/debug/processDebugManifest/AndroidManifest.xml'
    tree = ET.fromstring(manifest.read_text())
    android = '{http://schemas.android.com/apk/res/android}'
    assert tree.attrib['package'] == PROBE
    service = tree.find('application/service')
    assert service.attrib[android+'isolatedProcess'] == 'true' and service.attrib[android+'exported'] == 'false'
    (OUT / 'manifest.xml').write_bytes(manifest.read_bytes())
    (OUT / 'probe.apk').write_bytes(apk.read_bytes())
    identity = dict(apkSha256=hashlib.sha256(apk.read_bytes()).hexdigest().upper(),
                    driverSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest().upper(),
                    productionBefore=before, payload=payload, serial=SERIAL)
    (OUT / 'identity.json').write_text(json.dumps(identity, indent=2)+'\n', encoding='utf-8')
    adb('install','-r',str(apk))
    adb('shell','am','force-stop',PROBE)
    startup_cancel = os.environ.get('PROBE_STARTUP_CANCEL') == '1'
    adb('shell','am','start','-n',PROBE+'/.ProbeActivity','--es','runId',OUT.name,
        '--ez','startupCancel',str(startup_cancel).lower())
    result = None
    for _ in range(70):
        p = adb('exec-out','run-as',PROBE,'cat','files/result.json',check=False)
        if p.returncode == 0:
            try:
                observed = json.loads(p.stdout)
                if observed.get('runId') != OUT.name:
                    (OUT / 'stale-result-ignored.json').write_bytes(p.stdout)
                    time.sleep(1)
                    continue
                result = observed
                (OUT / 'result.json').write_bytes(p.stdout)
                if result.get('verdict') in {'PASS','FAIL'}:
                    break
            except ValueError:
                pass
        time.sleep(1)
    identity['productionAfter'] = product_identity()
    (OUT / 'identity.json').write_text(json.dumps(identity,indent=2)+'\n',encoding='utf-8')
    if result and result.get('isolatedPid'):
        log = adb('logcat','-d','--pid='+str(result['isolatedPid']),check=False)
        (OUT / 'isolated-process.log').write_bytes(log.stdout)
    assert result and result.get('verdict') == 'PASS', 'Isolation route not proven; failure/result retained'
    assert result['isolatedUid'] != result['ownerUid']
    if startup_cancel:
        assert result['startupCancelled'] and result['isIsolated']
        assert result['readyCount'] == 0 and result['startupDelayMs'] == 3000
        assert 0 <= result['serviceAgeAtDeathMs'] < result['startupDelayMs']
        assert result['cancelDeathMs'] < 2500
        assert result['stage'] == 'cancel_during_real_isolated_service_startup'
        print('PASS cancellation during actual isolated service startup; evidence ' + str(OUT))
    else:
        assert result.get('facadeWaitFor') is True and result.get('facadeExit') == 137
        assert result.get('facadeClass') == 'dev.alita.androidagent.execution.IsolatedProviderProcess'
        assert result['toolResult']['data']['uid'] == result['isolatedUid']
        print('PASS isolated Node/local protocol/private-file+network rejection/cancel; evidence ' + str(OUT))
finally:
    # Only this experiment is stopped. Never kill/restart the accepted product or other device.
    adb('shell','am','force-stop',PROBE,check=False)
