"""Run admission faults in an isolated directory with the installed APK's Node.

Does not open or modify the live Gateway database; target is explicitly owned.
"""
from pathlib import Path
import hashlib, json, os, shlex, subprocess, time

root = Path(__file__).resolve().parents[2]
adb = os.environ['ANDROID_ADB']
serial, package = 'DEVICE_ANDROID17', 'dev.alita.androidagent'
evidence = root / 'docs/handoff/evidence/mainline-safety'

def command(*args):
    return subprocess.check_output([adb, '-s', serial, *args], encoding='utf-8').strip()

runtime = '/data/user/0/' + package + '/files/runtime'
apk = command('shell', 'pm', 'path', package).splitlines()[0].removeprefix('package:')
node = apk.rsplit('/', 1)[0] + '/lib/arm64/libnode.so'
relative = 'files/safety-regression-' + str(time.time_ns())
command('push', str(root / 'tools/phase9/carrier-authorization-regression.cjs'),
        '/data/local/tmp/agent-safety-regression.cjs')
script = ('mkdir -p ' + relative + '/tmp && cp /data/local/tmp/agent-safety-regression.cjs ' + relative +
          '/test.cjs && cd ' + relative + ' && TMPDIR="$PWD/tmp" TEST_RUNTIME=' + shlex.quote(runtime) +
          ' OPENSSL_CONF=/dev/null LD_LIBRARY_PATH=' + shlex.quote(runtime + '/lib') + ' ' +
          shlex.quote(node) + ' test.cjs')
result = command('shell', 'run-as', package, 'sh', '-c', shlex.quote(script))
(evidence / 'final-native-admission.log').write_text(result + '\n', encoding='utf-8')
assert 'RESULT 15 PASS' in result

source_root = root / 'app/src/main'
rows = []
for line in (source_root / 'assets/zcode-runtime/payload-SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
    expected, name = line.split(maxsplit=1)
    assert hashlib.sha256((source_root / name).read_bytes()).hexdigest() == expected
    if name.startswith('assets/zcode-runtime/') and name != 'assets/zcode-runtime/provider/personal_provider_config.json':
        destination = runtime + '/' + name.removeprefix('assets/zcode-runtime/')
    elif name.startswith('jniLibs/arm64-v8a/'):
        destination = apk.rsplit('/', 1)[0] + '/lib/arm64/' + name.rsplit('/', 1)[1]
    else:
        continue  # Host-owned mutable provider configuration is separately validated at boot.
    actual = command('shell', 'run-as', package, 'sha256sum', destination).split()[0]
    assert actual == expected, name
    rows.append({'path': name, 'sha256': actual})
assert len(rows) == 34, len(rows)
(evidence / 'final-installed-hashes.json').write_text(json.dumps({
    'serial': serial, 'packagedEntries': 35, 'installedImmutableEntries': len(rows),
    'excluded': 'provider/personal_provider_config.json (host-owned mutable config)', 'rows': rows,
}, indent=2), encoding='utf-8')
print('PASS APK-owned Node admission15; packaged35 and installed immutable34 hashes')
