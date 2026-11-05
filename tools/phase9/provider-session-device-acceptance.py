"""Android17 session-index boundary: fake Core, explicit fixture verifier, real Node. No install/model."""
from pathlib import Path
import hashlib
import json
import os
import shlex
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/handoff/evidence/provider-session1' / str(time.time_ns())
OUT.mkdir(parents=True, exist_ok=False)
ADB = os.environ['ANDROID_ADB']
SERIAL = 'DEVICE_ANDROID17'
TEST = 'dev.alita.androidagent.isolationtest'
PRODUCT = 'dev.alita.androidagent'
BASELINE = 'C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D'
TEST_APK = '735864E4FC064903208FDFCC8F10E3A49FD94FD459CE4A64B988312707EC719B'
NODE = '1EE21EEBDA8BA05919050FE0D2B84B773A5CB2D2D1A42A27BDDFB5EAA1EE182E'
commands = []


def run(*args, timeout=90):
    argv = [ADB, '-s', SERIAL, *args]
    p = subprocess.run(argv, capture_output=True, timeout=timeout)
    commands.append(dict(argv=argv, exit=p.returncode, stdout=p.stdout.decode('utf-8', 'replace'), stderr=p.stderr.decode('utf-8', 'replace')))
    (OUT / 'commands-and-exits.json').write_text(json.dumps(commands, indent=2)+'\n', encoding='utf-8')
    assert p.returncode == 0, 'command failed; raw evidence retained'
    return p.stdout.decode('utf-8')


def package_path(package, expected):
    apk = run('shell', 'pm', 'path', package).strip().removeprefix('package:')
    assert run('shell', 'run-as', package, 'sha256sum', apk).split()[0].upper() == expected
    return apk


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest().upper()


assert run('shell', 'getprop', 'ro.build.version.release').strip() == '17'
assert run('shell', 'getprop', 'ro.product.model').strip() == 'MODEL_ANDROID17'
package_path(PRODUCT, BASELINE)
apk = package_path(TEST, TEST_APK)
node = apk.rsplit('/', 1)[0] + '/lib/arm64/libnode.so'
assert run('shell', 'run-as', TEST, 'sha256sum', node).split()[0].upper() == NODE
cache = 'cache/provider-session-' + OUT.name
home = '/data/user/0/' + TEST + '/' + cache
run('shell', 'run-as', TEST, 'mkdir', '-p', cache + '/runtime/lib', cache + '/runtime/provider')
runtime = ROOT / 'app/src/main/assets/zcode-runtime'
files = [(runtime / name, 'runtime/' + name) for name in ['skill-session-bindings.cjs', 'bootstrap.cjs', 'zcode.cjs']]
files += [(runtime / 'provider/zcode-builtin.json', 'runtime/provider/zcode-builtin.json')]
files += [(file, 'runtime/lib/' + file.name) for file in sorted((runtime / 'lib').iterdir()) if file.is_file()]
files += [(Path(__file__).with_name('provider-session-bindings-test.cjs'), 'test.cjs')]
files += [(Path(__file__).with_name('provider-session-core-test.cjs'), 'core-test.cjs')]
hashes = {}
for file, relative in files:
    temporary = '/data/local/tmp/provider-session-' + OUT.name + '-' + file.name
    run('push', str(file), temporary)
    run('shell', 'run-as', TEST, 'cp', temporary, cache + '/' + relative)
    expected = digest(file)
    assert run('shell', 'run-as', TEST, 'sha256sum', cache + '/' + relative).split()[0].upper() == expected
    hashes[relative] = expected
prefix = dict(OPENSSL_CONF='/dev/null', LD_LIBRARY_PATH=home + '/runtime/lib', TMPDIR=home,
              TEST_RUNTIME=home + '/runtime', TEST_BINDING_RUNTIME=home + '/runtime',
              TEST_BINDING_MODULE=home + '/runtime/skill-session-bindings.cjs')
environment = ' '.join(k + '=' + shlex.quote(v) for k, v in prefix.items())
try:
    version = run('shell', 'run-as', TEST, 'sh', '-c', shlex.quote(environment + ' ' + shlex.quote(node) + ' --version')).strip()
    assert version == 'v24.18.0'
    output = run('shell', 'run-as', TEST, 'sh', '-c', shlex.quote(environment + ' ' + shlex.quote(node) + ' --test --test-reporter=tap ' + shlex.quote(home + '/test.cjs')))
    (OUT / 'settlement.stdout').write_text(output, encoding='utf-8')
    assert '# pass 15' in output and '# fail 0' in output and '# skipped 0' in output
    # Core creates a Unix socket in TMPDIR. Its 108-byte path limit is exceeded
    # by this long application ID + timestamp fixture + UUID socket basename.
    # Keep it inside this same test app UID's private cache, using the shorter base.
    core_environment = environment + ' TMPDIR=' + shlex.quote('/data/user/0/' + TEST + '/cache')
    core_output = run('shell', 'run-as', TEST, 'sh', '-c', shlex.quote(core_environment + ' ' + shlex.quote(node) + ' ' + shlex.quote(home + '/core-test.cjs')))
    (OUT / 'core-protocol.stdout').write_text(core_output, encoding='utf-8')
    core_result = json.loads(core_output)
    assert core_result['verdict'] == 'PASS' and core_result['checks'] == 10 and core_result['node'] == 'v24.18.0'
    result = dict(verdict='PASS_SCOPED_ANDROID17_SESSION_INDEX_BOUNDARY', serial=SERIAL, node=version, checks=15,
                  actualCoreProtocolChecks=10,
                  productApk=BASELINE, testApk=TEST_APK, sourceHashes=hashes, fixture=cache,
                  scope='Host session-index metadata unit15 plus actual Core lifecycle10; explicit inert-file verifier, no actual package catalog/resolver, HTTP/model or production admission')
    (OUT / 'identity.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result))
finally:
    package_path(PRODUCT, BASELINE)
    package_path(TEST, TEST_APK)
