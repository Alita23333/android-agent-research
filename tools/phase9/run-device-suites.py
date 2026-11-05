"""Previous suites on APK-owned Node, isolated from the production journal/workspace."""
from pathlib import Path
import json, subprocess, shlex
root = Path(__file__).resolve().parents[2]
adb = r'C:\Android\Sdk\platform-tools\adb.exe'
serial, package = 'DEVICE_ANDROID17', 'dev.alita.androidagent'
evidence = root / 'docs/handoff/evidence/phase9/final'
evidence.mkdir(parents=True, exist_ok=True)
def command(*args, data=None):
    return subprocess.run([adb, '-s', serial, *args], input=data, capture_output=True, check=True).stdout
def app_shell(script):
    return command('shell', 'run-as ' + package + ' sh -c ' + shlex.quote(script))
apk = command('shell', 'pm', 'path', package).decode().strip().split('package:')[1]
native = apk.rsplit('/', 1)[0] + '/lib/arm64/libnode.so'
app_shell(
        'mkdir -p files/phase9-regression/runtime; cp files/runtime/gateway.cjs files/runtime/workspace-files.cjs files/runtime/web-search.cjs files/runtime/zcode.cjs files/phase9-regression/runtime/')
checks = []
for filename, expected in [('wws-unittest.cjs', 44), ('gateway-unittest.cjs', 22), ('web-search-unittest.cjs', 57)]:
    source = root / 'tools/phase8' / filename
    command('push', str(source), '/data/local/tmp/p9-' + filename)
    app_shell(
            'cat /data/local/tmp/p9-' + filename + ' > files/phase9-regression/' + filename)
    script = ('cd files/phase9-regression; export SPIKE_ROOT="$PWD" HOME="$PWD" OPENSSL_CONF=/dev/null '
              'LD_LIBRARY_PATH=/data/user/0/dev.alita.androidagent/files/runtime/lib; '
              + shlex.quote(native) + ' ' + shlex.quote(filename))
    result = subprocess.run([adb, '-s', serial, 'shell', 'run-as ' + package + ' sh -c ' + shlex.quote(script)], capture_output=True, timeout=90)
    (evidence / (filename + '.log')).write_bytes(result.stdout + result.stderr)
    text = result.stdout.decode('utf-8', 'replace')
    marker = 'RESULT: PASS=' + str(expected) + ' FAIL=0'
    if result.returncode or marker not in text:
        raise AssertionError(filename + ': failed; inspect saved log')
    checks.append({'suite': filename, 'pass': expected, 'fail': 0, 'node': 'APK-owned 24.18.0'})
    print('PASS ' + filename + ': ' + str(expected) + '/0', flush=True)
(evidence / 'device-suites.json').write_text(json.dumps({'serial': serial, 'isolated': True, 'suites': checks}, indent=2), encoding='utf-8')
