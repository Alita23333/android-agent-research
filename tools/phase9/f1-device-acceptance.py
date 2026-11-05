"""Controlled F1 device faults; keep generated config backup on-device, never export credentials."""
from pathlib import Path
import hashlib, json, os, shlex, subprocess, time, urllib.request

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'docs/handoff/evidence/phase9-f1'
ADB = os.environ['ANDROID_ADB']
SERIAL = 'DEVICE_ANDROID17'
PKG = 'dev.alita.androidagent'
CFG = 'files/.zcode/cli/config.json'
BACKUP = CFG + '.f1-acceptance-original'
CONTROL = 'files/carrier.disabled'

def adb(*args, check=True):
    p = subprocess.run([ADB, '-s', SERIAL, *args], capture_output=True, timeout=30)
    if check and p.returncode:
        raise RuntimeError('device operation failed (output withheld)')
    return p.stdout

def private(script):
    return adb('shell', 'run-as ' + PKG + ' sh -c ' + shlex.quote('set -eu; ' + script))

def stop():
    adb('shell', 'am', 'force-stop', PKG)
    adb('shell', 'run-as', PKG, 'pkill', '-f', 'libnode.so', check=False)
    time.sleep(1)

def start():
    adb('shell', 'su', '-c', 'am start -n ' + PKG + '/.zcode.runtime.ZCodeActivity')
    adb('forward', 'tcp:18765', 'tcp:8765')

def status():
    token = adb('exec-out', 'run-as', PKG, 'cat', 'files/runtime/bridge-token').decode().strip()
    req = urllib.request.Request('http://127.0.0.1:18765/status', headers={'X-Bridge-Token': token})
    return json.load(urllib.request.urlopen(req, timeout=3))

def wait(phase):
    end = time.monotonic() + 50
    while time.monotonic() < end:
        try:
            s = status()
            if s.get('phase') == phase:
                return s
        except Exception:
            pass
        time.sleep(1)
    raise AssertionError('expected phase not observed: ' + phase)

def flags():
    cfg = json.loads(adb('exec-out', 'run-as', PKG, 'cat', CFG))
    return {'pluginsOff': cfg.get('plugins', {}).get('enabled') is False,
            'memoryOff': cfg.get('features', {}).get('memory') is False,
            'extractionOff': cfg.get('memory', {}).get('extractionEnabled') is False,
            'carrierDeclared': cfg.get('mcp', {}).get('servers', {}).get('android-host', {}).get('type') == 'stdio'}

def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    rows = []
    start(); wait('ready')
    assert private(f'test ! -e {BACKUP}; test ! -e {CONTROL}; echo clean').decode().strip() == 'clean'
    original_hash = hashlib.sha256(adb('exec-out', 'run-as', PKG, 'cat', CFG)).hexdigest()
    stop(); private(f'mv {CFG} {BACKUP}')
    try:
        # App-owned read-only file permits parse but denies the preflight write.
        private(f"printf '{{}}' > {CFG}; chmod 400 {CFG}")
        start(); s = wait('config-disable-failed'); time.sleep(2)
        s = status(); assert s.get('childPid') is None
        assert 'EACCES' in s.get('configDisableError', '')
        rows.append({'case': 'readable-config-write-denied', 'phase': s['phase'], 'childPid': s.get('childPid'),
                     'diagnosticPresent': bool(s.get('configDisableError')), 'pass': True})
        stop(); private(f'chmod 600 {CFG}; printf broken-json > {CFG}')
        start(); s = wait('config-disable-failed'); assert s.get('childPid') is None
        rows.append({'case': 'corrupt-config', 'phase': s['phase'], 'childPid': s.get('childPid'),
                     'diagnosticPresent': bool(s.get('configDisableError')), 'pass': True})
        stop(); private(f'rm {CFG}')
        start(); wait('ready'); f = flags(); assert all(f.values())
        rows.append({'case': 'regenerate-recovery-carrier-on', **f, 'pass': True})
        stop(); private(f'touch {CONTROL}')
        start(); wait('ready'); f = flags()
        assert f['pluginsOff'] and f['memoryOff'] and f['extractionOff'] and not f['carrierDeclared']
        rows.append({'case': 'kill-switch-off', **f, 'pass': True})
    finally:
        stop()
        # Only remove our generated fixture file/control; restore original byte-for-byte.
        private(f'if test -d {CFG}; then rmdir {CFG}; elif test -f {CFG}; then rm {CFG}; fi; '
                f'if test -f {CONTROL}; then rm {CONTROL}; fi; mv {BACKUP} {CFG}')
        restored_hash = hashlib.sha256(adb('exec-out', 'run-as', PKG, 'cat', CFG)).hexdigest()
        assert restored_hash == original_hash
        start(); wait('ready')
    (EVIDENCE / 'device-faults.json').write_text(json.dumps({'serial': SERIAL, 'checks': rows,
        'originalRestoredBeforeNormalBoot': True, 'productionConfigSecretsExported': False}, indent=2), encoding='utf-8')
    print('Device F1 faults/recovery/kill-switch: 4 PASS; original config restored.')

if __name__ == '__main__':
    main()
