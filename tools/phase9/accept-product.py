"""Final-APK acceptance. Fixture UI only; hard confirmations are denied by harness."""
from pathlib import Path
import json, os, subprocess, sys, time
import urllib.request

root = Path(__file__).resolve().parents[2]
evidence = root / 'docs/handoff/evidence/phase9/final'
evidence.mkdir(parents=True, exist_ok=True)
node = r'C:\Program Files\nodejs\node.exe'
adb = r'C:\Android\Sdk\platform-tools\adb.exe'
env = dict(os.environ, ANDROID_SERIAL='DEVICE_ANDROID17', ANDROID_ADB=adb)
reports = []

def run(name, *args):
    result = subprocess.run([node, str(root / 'tools/zcode/bridge-acceptance.cjs'), *args],
                            cwd=root, env=env, capture_output=True, timeout=210)
    (evidence / (name + '.json')).write_bytes(result.stdout)
    (evidence / (name + '.err')).write_bytes(result.stderr)
    if result.returncode:
        raise RuntimeError(name + ': harness failed; inspect saved stderr')
    data = json.loads(result.stdout.decode('utf-8-sig'))
    return data

def checked(name, data, condition):
    if not condition:
        raise AssertionError(name + ': acceptance assertions failed')
    reports.append({'name': name, 'pass': True})
    (evidence / ('summary-' + sys.argv[1] + '.json')).write_text(
        json.dumps({'serial': 'DEVICE_ANDROID17', 'checks': reports}, indent=2), encoding='utf-8')
    print('PASS ' + name, flush=True)

def launch():
    subprocess.run([adb, '-s', 'DEVICE_ANDROID17', 'shell', 'am', 'start', '--activity-clear-top',
        '-n', 'dev.alita.androidagent/.zcode.runtime.UiLabActivity'], check=True, capture_output=True)
    time.sleep(1.2)

def tool_ok(data, tool):
    parts = [p for m in data.get('messages', []) for p in m.get('parts', [])
             if p.get('type') == 'tool' and p.get('tool') == 'mcp__android-host__' + tool]
    successful = []
    for part in parts:
        state = part.get('state', {})
        output = state.get('output', '')
        if isinstance(output, str):
            try:
                output = json.loads(output.split('\n\nStructured content:\n')[-1])
            except (ValueError, TypeError):
                continue
        if state.get('status') == 'completed' and isinstance(output, dict) and output.get('ok'):
            successful.append(output)
    calls = [x for x in data.get('carrierCalls', []) if (x.get('toolId') or x.get('call', {}).get('toolId')) == tool]
    rows = [x for x in data.get('gatewayJournalRows', []) if x.get('tool') == 'mcp__android-host__' + tool]
    return bool(successful and calls and rows), successful

def runtime():
    d = run('real-turn', 'turn')
    checked('real-turn-streaming', d, d['finalMarkerPresent'] and d['streamed'] and d['snapshotMessageCount'] >= 3)
    sid = d['sessionId']
    d = run('cancellation', 'cancel')
    checked('cancellation', d, d['stopAccepted'] and d['cancelledEvidence'])
    d = run('activity-reconnect', 'reconnect', sid)
    checked('activity-reconnect', d, d['sameRuntime'] and d['sessionReadable'] and d['afterPhase'] == 'ready')
    d = run('runtime-crash-restart', 'crash-restart')
    checked('runtime-crash-restart', d, d['restarted'] and d['phase'] == 'ready')
    d = run('session-resume', 'resume', sid)
    checked('session-resume', d, d['resumed'] and d['messageCount'] >= 3 and d['persistedAssistantMessages'] >= 1)
    d = run('force-stop-relaunch', 'force-resume', sid)
    checked('force-stop-relaunch', d, d['unreachableAfterStop'] and d['relaunchedReady'] and d['newRuntime']
            and d['resumed'] and d['persistedMessageCount'] >= 3 and d['persistedAssistantMessages'] >= 1)

def visual():
    launch()
    d = run('model-screenshot', 'ui-lab', 'Call mcp__android-host__ui_screenshot once. Report the returned shotId and dimensions. Do not call other tools. End with SCREENSHOT_ACCEPTANCE_OK only if it succeeded.')
    ok, results = tool_ok(d, 'ui_screenshot')
    checked('model-screenshot', d, ok and results[0]['bytes'] <= 153600)
    launch()
    d = run('model-real-vision', 'ui-lab', 'Call mcp__android-host__ui_see with question "Read the visible counter and main button label", force true. This is the test fixture. Report actual returned text; end with REAL_VISION_ACCEPTANCE_OK only if it succeeded. Do not click or navigate.')
    ok, results = tool_ok(d, 'ui_see')
    checked('model-real-vision', d, ok and 'increment' in results[0].get('text', '').lower() and 'count' in results[0].get('text', '').lower())
    launch()
    d = run('model-coordinate-tap', 'ui-lab', 'This is our UiLab test fixture. Call ui_dump to locate INCREMENT, then ui_screenshot, then ui_tap at the center of INCREMENT using its fresh shotId and label Increment. Click exactly once. Report whether the result verifies count=1. Use only the mcp__android-host__ tools. Do not navigate or modify anything else.')
    ok, results = tool_ok(d, 'ui_tap')
    checked('model-coordinate-tap', d, ok and results[0].get('verified') and 'count=1' in json.dumps(results[0]))

def previous():
    d = run('device-identity', 'device-tool')
    checked('device-identity', d, True)  # Harness asserts provider/physical/journal evidence.
    launch()
    d = run('ui-inspect', 'ui-tool')
    checked('ui-inspect', d, True)
    d = run('web-search', 'web-search', 'Android AccessibilityService takeScreenshotOfWindow official documentation')
    checked('web-search', d, d['toolResultPresent'] and d['citedUrlPresent'] and d['inlineDispatchEvidence'])

def workspace():
    fixture = 'phase9/model-visible-regression.txt'
    target = 'files/workspaces/default/' + fixture
    exists = subprocess.run([adb, '-s', 'DEVICE_ANDROID17', 'shell', 'run-as', 'dev.alita.androidagent', 'test', '-e', target])
    if exists.returncode == 0:
        raise RuntimeError('Dedicated fixture already exists; refusing to replace unknown data')
    env['ZCODE_ACCEPTANCE_FILE'] = fixture
    for action in ['create', 'overwrite', 'append', 'delete']:
        d = run('workspace-' + action, 'workspace-tool', action)
        checked('workspace-' + action, d, d['toolResultPresent'] and any(t['state'] == 'completed' for t in d['txns']))
        if action == 'overwrite':
            op = next(o['id'] for o in d['operations'] if o['result'] == 'ok')
            token = subprocess.check_output([adb, '-s', 'DEVICE_ANDROID17', 'exec-out', 'run-as', 'dev.alita.androidagent',
                                              'cat', 'files/runtime/bridge-token']).decode().strip()
            req = urllib.request.Request('http://127.0.0.1:18765/gateway/rollback',
                   data=json.dumps({'id': op}).encode(), headers={'X-Bridge-Token': token, 'Content-Type': 'application/json'})
            rollback = json.load(urllib.request.urlopen(req, timeout=30))
            (evidence / 'workspace-rollback.json').write_text(json.dumps(rollback, indent=2), encoding='utf-8')
            physical = subprocess.check_output([adb, '-s', 'DEVICE_ANDROID17', 'exec-out', 'run-as', 'dev.alita.androidagent', 'cat', target]).decode()
            checked('workspace-rollback', rollback, rollback.get('ok') and rollback.get('operation') != op and physical == 'created-by-zcode')

if __name__ == '__main__':
    {'runtime': runtime, 'visual': visual, 'previous': previous, 'workspace': workspace}[sys.argv[1]]()
