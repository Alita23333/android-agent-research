"""Prove a valid imported-provider layout stays inert in the actual product APK."""
from pathlib import Path
import hashlib
import json
import os
import shlex
import struct
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/handoff/evidence/local-provider1'
ADB = os.environ['ANDROID_ADB']
SERIAL, PACKAGE = 'DEVICE_ANDROID17', 'dev.alita.androidagent'
run = str(time.time_ns())
provider = 'unapproved_' + run
marker = '/data/user/0/' + PACKAGE + '/cache/inert-proof-' + run
manifest = json.dumps({'id': provider, 'version': '1.0.0', 'command': ['/system/bin/sh', '${DIR}/provider.sh']})
script = '#!/system/bin/sh\nprintf executed > ' + marker + '\nwhile IFS= read -r line; do\n' + \
    'id="$(printf \'%s\' "$line" | sed -n \'s/.*"id"[ ]*:[ ]*\\([0-9][0-9]*\\).*/\\1/p\')"\n' + \
    'printf \'%s\\n\' "{\\"jsonrpc\\":\\"2.0\\",\\"id\\":$id,\\"result\\":{\\"protocolVersion\\":\\"1.0\\",\\"tools\\":[]}}"\ndone\n'
files = {'provider.json': manifest.encode(), 'provider.sh': script.encode()}
digest = hashlib.sha256(b'AndroidLocalProvider-content-v2\n')
for name in sorted(files):
    digest.update(struct.pack('>I', len(name.encode()))); digest.update(name.encode())
    digest.update(struct.pack('>Q', len(files[name]))); digest.update(files[name])
version = digest.hexdigest()
directory = 'files/tool-providers/' + provider + '/versions/' + version


def command(*args):
    return subprocess.check_output([ADB, '-s', SERIAL, *args])


apk = command('shell', 'pm', 'path', PACKAGE).decode().strip().removeprefix('package:')
expected = json.loads((OUT / 'build-identity.json').read_text(encoding='utf-8'))['apkSha256']
assert command('shell', 'run-as', PACKAGE, 'sha256sum', apk).decode().split()[0].upper() == expected
data = {'directory': '/data/user/0/' + PACKAGE + '/' + directory,
    'active': '/data/user/0/' + PACKAGE + '/files/tool-providers/' + provider + '/active',
    'version': version, 'files': {k: v.decode() for k, v in files.items()}}
seed = OUT / 'inert-seed.cjs'
seed.write_text("const fs=require('node:fs'),path=require('node:path');const x=" + json.dumps(data) +
    ";fs.mkdirSync(x.directory,{recursive:true});for(const [k,v] of Object.entries(x.files))fs.writeFileSync(path.join(x.directory,k),v,{flag:'wx'});fs.writeFileSync(x.active,x.version,{flag:'wx'});console.log('inert synthetic provider layout prepared');", encoding='utf-8')
command('push', str(seed), '/data/local/tmp/provider-inert-seed.cjs')
node = apk.rsplit('/', 1)[0] + '/lib/arm64/libnode.so'
line = 'OPENSSL_CONF=/dev/null LD_LIBRARY_PATH=/data/user/0/' + PACKAGE + '/files/runtime/lib ' + shlex.quote(node) + ' /data/local/tmp/provider-inert-seed.cjs'
command('shell', 'run-as', PACKAGE, 'sh', '-c', shlex.quote(line))
for name, raw in files.items():
    assert command('exec-out', 'run-as', PACKAGE, 'cat', directory + '/' + name) == raw
command('shell', 'am', 'force-stop', PACKAGE)
subprocess.run([ADB, '-s', SERIAL, 'shell', 'run-as', PACKAGE, 'pkill', '-f', 'libnode.so'], capture_output=True)
command('shell', 'su', '-c', 'am start -n ' + PACKAGE + '/.zcode.runtime.ZCodeActivity')
for attempt in range(25):
    try:
        token = command('exec-out', 'run-as', PACKAGE, 'cat', 'files/runtime/bridge-token').decode().strip()
        req = urllib.request.Request('http://127.0.0.1:18765/status', headers={'X-Bridge-Token': token})
        with urllib.request.urlopen(req, timeout=2) as res:
            status = json.load(res)
        if status['phase'] == 'ready':
            req = urllib.request.Request('http://127.0.0.1:18765/carrier/tools', headers={'X-Bridge-Token': token})
            with urllib.request.urlopen(req, timeout=2) as res:
                tools = json.load(res)['tools']
            if any(t['toolId'] == 'text_digest_inspect' for t in tools):
                break
    except Exception:
        pass
    time.sleep(1)
else:
    raise RuntimeError('Existing product did not restart ready')
command('shell', 'run-as', PACKAGE, 'test', '!', '-e', marker)
assert not any(t['toolId'].startswith(provider) for t in tools)
(OUT / 'inert-startup.json').write_text(json.dumps({'verdict': 'PASS', 'apkSha256': expected,
    'syntheticProviderId': provider, 'versionHash': version, 'layout': directory,
    'markerAbsentAfterActualRestart': True, 'notModelExposed': True,
    'inputManifestAndScriptRetained': True, 'scope': 'valid import-layout startup behavior; no activation, provider execution or installation hooks'}, indent=2) + '\n', encoding='utf-8')
print('PASS actual product restart does not execute or expose unapproved import layout')
