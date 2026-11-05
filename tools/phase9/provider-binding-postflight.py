"""Read-only installed product liveness. Credential output is never persisted."""
from pathlib import Path
import json
import os
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
ADB = os.environ['ANDROID_ADB']
PKG = 'dev.alita.androidagent'
records = []


def run(*args, credential=False):
    argv = [ADB, '-s', 'DEVICE_ANDROID17', *args]
    process = subprocess.run(argv, capture_output=True, timeout=20)
    records.append(dict(argv=argv, exit=process.returncode,
        stdout='<credential withheld>' if credential else process.stdout.decode('utf-8', 'replace'),
        stderr=process.stderr.decode('utf-8', 'replace')))
    assert process.returncode == 0, 'postflight read failed; credential output withheld'
    return process.stdout


run('forward', 'tcp:18765', 'tcp:8765')
path = run('shell', 'pm', 'path', PKG).decode().strip().removeprefix('package:')
digest = run('shell', 'run-as', PKG, 'sha256sum', path).decode().split()[0].upper()
assert digest == 'C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D'
token = run('exec-out', 'run-as', PKG, 'cat', 'files/runtime/bridge-token', credential=True).decode().strip()
with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:18765/status', headers={'X-Bridge-Token': token}), timeout=5) as response:
    status = json.load(response)
safe = dict(apkSha256=digest, phase=status.get('phase'), mode=status.get('mode'), node=status.get('nodeVersion', status.get('node')))
assert safe == dict(apkSha256=digest, phase='ready', mode='real', node='v24.18.0')
out = ROOT / 'docs/handoff/evidence/provider-binding1'
(out / 'product-postflight.json').write_text(json.dumps(safe, indent=2)+'\n', encoding='utf-8')
(out / 'postflight-commands.json').write_text(json.dumps(records, indent=2)+'\n', encoding='utf-8')
print(json.dumps(safe))
