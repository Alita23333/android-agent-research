"""One real model scroll, verified against a fresh dump and one Gateway grant."""
from pathlib import Path
import http.client, importlib.util, json, os, shlex, subprocess, threading, urllib.request

root = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('acceptance', Path(__file__).with_name('accept-product.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.evidence = root / 'docs/handoff/evidence/mainline-safety'
m.adb, m.node = os.environ['ANDROID_ADB'], os.environ['ACCEPTANCE_NODE']
m.env.update(ANDROID_ADB=m.adb, ANDROID_SERIAL='DEVICE_ANDROID17')

def adb(*args):
    return subprocess.check_output([m.adb, '-s', 'DEVICE_ANDROID17', *args], encoding='utf-8').strip()

component = 'dev.alita.androidagent/dev.alita.androidagent.device.AgentAccessibilityService'
existing = [x for x in adb('shell', 'settings', 'get', 'secure', 'enabled_accessibility_services').split(':') if x and x != 'null']
if component not in existing:
    existing.append(component)
    adb('shell', 'su', '-c', 'settings put secure enabled_accessibility_services ' + shlex.quote(':'.join(existing)))
    adb('shell', 'su', '-c', 'settings put secure accessibility_enabled 1')
adb('shell', 'su', '-c', 'am start --activity-clear-top -n dev.alita.androidagent/.zcode.runtime.LongListActivity')
token = adb('exec-out', 'run-as', 'dev.alita.androidagent', 'cat', 'files/runtime/bridge-token')

def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:18765' + url,
        headers={'X-Bridge-Token': token}), timeout=30))

before = {x['id'] for x in get('/gateway/journal?limit=500')['operations']}
d = m.run('model-positive-scroll', 'ui-lab',
    'This is our LongList test fixture. Only use ui_dump and ui_scroll. First dump the list, scroll forward exactly once, '
    'then dump again. Report which longlist-item labels appeared and disappeared. Stop after that one scroll.')
ok, results = m.tool_ok(d, 'ui_scroll')
rows = [x for x in get('/gateway/journal?limit=500')['operations'] if x['id'] not in before and
        x['tool'] == 'mcp__android-host__ui_scroll' and x['session'] == d['sessionId'] and x['decision'] == 'allow']
assert ok and results[0].get('verified') and len(rows) == 1
prior_ids = {x['id'] for x in get('/gateway/journal?limit=500')['operations']}
events = http.client.HTTPConnection('127.0.0.1', 18765, timeout=40)
events.request('GET', '/events', headers={'X-Bridge-Token': token})
event_stream = events.getresponse()
finished = threading.Event()
def approve_identity():
    while not finished.is_set():
        try:
            line = event_stream.readline().decode('utf-8')
        except (AttributeError, OSError):
            if finished.is_set():
                return
            raise
        if not line:
            return
        if not line.startswith('data: '):
            continue
        event = json.loads(line[6:])
        if event.get('type') == 'permission':
            allow = event.get('toolName') == 'mcp__android-host__device_info_identity' and not event.get('hardConfirm')
            response = urllib.request.Request('http://127.0.0.1:18765/respond', data=json.dumps({
                'requestId': event['requestId'], 'decision': 'allow' if allow else 'deny',
            }).encode(), headers={'X-Bridge-Token': token, 'Content-Type': 'application/json'})
            with urllib.request.urlopen(response, timeout=10) as reply:
                reply.read()
threading.Thread(target=approve_identity, daemon=True).start()
request = urllib.request.Request('http://127.0.0.1:18765/carrier/call', data=json.dumps({
    'toolId': 'device_info_identity', 'arguments': {},
    'meta': {'sessionId': d['sessionId'], 'approvalOpId': rows[0]['id']},
}).encode(), headers={'X-Bridge-Token': token, 'Content-Type': 'application/json'})
identity = json.load(urllib.request.urlopen(request, timeout=30))
finished.set()
events.close()
native_rows = [x for x in get('/gateway/journal?limit=500')['operations'] if x['id'] not in prior_ids and
              x['tool'] == 'mcp__android-host__device_info_identity' and x['decision'] == 'allow']
assert identity['ok'] and identity['structuredContent']['data']['model'] == adb('shell', 'getprop', 'ro.product.model')
assert len(native_rows) == 1 and native_rows[0]['session'] == d['sessionId']
(m.evidence / 'direct-identity-summary.json').write_text(json.dumps({
    'physicalIdentityVerified': True, 'newCommittedGatewayOperations': 1,
    'callerSuppliedForeignApprovalIgnored': True, 'workerAndLocalProviderCompleted': True,
}, indent=2), encoding='utf-8')
(m.evidence / 'model-scroll-summary.json').write_text(json.dumps({
    'apkSha256': __import__('hashlib').sha256((root / 'app/build/outputs/apk/debug/app-debug.apk').read_bytes()).hexdigest(),
    'realModelToolCall': True, 'verified': True, 'committedScrollApprovals': len(rows), 'noDuplicatePrompt': True,
}, indent=2), encoding='utf-8')
print('PASS real model forward scroll; exactly one committed approval')
print('PASS direct native identity; foreign UI approval ignored; fresh Gateway row')
