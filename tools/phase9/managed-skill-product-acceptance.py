"""Real host store -> installed candidate -> unchanged Core -> genuine model; Android17 only."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
ADB = os.environ['ANDROID_ADB']
APP, SERIAL = 'dev.alita.androidagent', 'DEVICE_ANDROID17'
CANDIDATE = '422CF3E5DB29F81A88B306ECE04E62102CE688395A9C0F6A30B3EB212D11674B'
BASELINE = '7BB49EEE3538D728BB2D4ACFA1A09116046092265E0C323FF1E3DCC26594EE3D'
CONTINUE = len(sys.argv) == 3 and sys.argv[1] == '--continue-run'
assert len(sys.argv) == 1 or CONTINUE
RUN = sys.argv[2] if CONTINUE else str(time.time_ns())
assert RUN.isdigit()
SKILL = 'bound-proof-' + RUN
EVIDENCE = ROOT / 'docs/handoff/evidence/skill-bindings1/product' / RUN
ORIGINAL = EVIDENCE
if CONTINUE:
    assert (ORIGINAL / 'failure.json').is_file()
    EVIDENCE = EVIDENCE / ('continuation-' + str(time.time_ns()))
EVIDENCE.mkdir(parents=True, exist_ok=False)
commands = []
token = None
receipts = {}

def save(name, data):
    (EVIDENCE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def adb(*args, record=True):
    p = subprocess.run([ADB, '-s', SERIAL, *args], capture_output=True, timeout=180)
    if record:
        commands.append(dict(argv=[ADB, '-s', SERIAL, *args], exit=p.returncode,
            stdout=p.stdout.decode('utf-8', errors='replace'), stderr=p.stderr.decode('utf-8', errors='replace')))
        save('commands-and-exits.json', commands)
    assert p.returncode == 0, 'device command failed; see evidence'
    return p.stdout

def request(route, body=None):
    req = urllib.request.Request('http://127.0.0.1:18765' + route,
        data=None if body is None else json.dumps(body).encode(),
        headers={'X-Bridge-Token': token, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=40) as response:
        return json.load(response)

def rpc(method, params):
    result = request('/rpc-wait', dict(method=method, params=params, timeoutMs=30000))
    assert not result.get('error'), method + ': ' + str(result.get('error'))
    return result['result']

def launch():
    global token
    adb('shell', 'su', '-c', 'am start -n ' + APP + '/.zcode.runtime.ZCodeActivity')
    for _ in range(60):
        try:
            token = adb('exec-out', 'run-as', APP, 'cat', 'files/runtime/bridge-token', record=False).decode().strip()
            status = request('/status')
            if status.get('phase') == 'ready':
                return status
        except (OSError, AssertionError, ValueError):
            pass
        time.sleep(0.5)
    raise AssertionError('runtime readiness deadline')

def fixture(revision=None, retire=False):
    args = ['shell', 'am', 'instrument', '-w', '-e', 'class', APP + '.ManagedSkillBindingFixtureTest',
        '-e', 'fixtureId', SKILL]
    args += ['-e', 'fixtureAction', 'retire'] if retire else ['-e', 'revision', revision]
    args += [APP + '.test/androidx.test.runner.AndroidJUnitRunner']
    out = adb(*args).decode()
    assert 'OK (1 test)' in out and 'FAILURES' not in out, 'native host fixture failed'
    if retire:
        return None
    receipt = json.loads(adb('exec-out', 'run-as', APP, 'cat', 'cache/' + SKILL + '-' + revision + '-receipt.json'))
    save('native-revision-' + revision + '.json', receipt)
    return receipt

def snapshot(session):
    return request('/session/read?id=' + session)['snapshot']['messages']

def model_turn(session, revision, old_count=0):
    prompt = ('Use the Skill tool to load the installed skill named ' + SKILL +
        '. Follow its current instructions and read its references/rule.txt using Read. '
        'Return the exact resource line and the version from those instructions. '
        'Only Skill and Read are permitted for this controlled test; do not write or use other tools.')
    rpc('session/send', dict(sessionId=session, content=prompt))
    deadline = time.monotonic() + 120
    observations = []
    while time.monotonic() < deadline:
        messages = snapshot(session)
        observations.append(dict(messages=len(messages), parts=sum(len(m.get('parts', [])) for m in messages)))
        if any(m.get('info', {}).get('role') == 'assistant' and m.get('info', {}).get('finish') == 'stop'
               for m in messages[old_count:]):
            break
        time.sleep(0.5)
    else:
        save('incomplete-' + revision + '.json', dict(messages=messages, observations=observations))
        raise AssertionError('real model task did not finish')
    fresh = messages[old_count:]
    parts = [p for m in fresh for p in m.get('parts', [])]
    tools = [p for p in parts if p.get('type') == 'tool']
    save('task-' + revision + '-' + str(old_count) + '.json', dict(sessionId=session, messages=messages, observations=observations))
    assert tools and all(p['tool'] in {'Skill', 'Read'} and p.get('state', {}).get('status') == 'completed' for p in tools)
    assert any(p['tool'] == 'Skill' and p['state']['input'].get('skill') == SKILL for p in tools)
    expected = 'RESOURCE_' + SKILL + '_' + revision
    reference = receipts[revision]['directory'] + '/references/rule.txt'
    reads = [p for p in tools if p['tool'] == 'Read' and p['state']['input'].get('file_path') == reference]
    assert reads, 'missing real model Read of the bound immutable path'
    cache_text = 'Wasted call — file unchanged since your last Read. Refer to that earlier tool_result instead.'
    history = [p for m in messages[:old_count] for p in m.get('parts', []) if p.get('type') == 'tool' and p.get('tool') == 'Read'
        and p.get('state', {}).get('input', {}).get('file_path') == reference and expected in p.get('state', {}).get('output', '')]
    assert any(expected in p['state'].get('output', '') or (history and p['state'].get('output', '') == cache_text) for p in reads), 'Read content/cache lineage mismatch'
    assert adb('exec-out', 'run-as', APP, 'cat', reference).decode() == expected + '\n', 'physical immutable resource mismatch'
    save('read-proof-' + revision + '-' + str(old_count) + '.json', dict(reference=reference,
        freshContent=any(expected in p['state'].get('output', '') for p in reads),
        reusedVerifiedHistory=any(p['state'].get('output', '') == cache_text for p in reads), physicalBytesMatch=True))
    assert any(p.get('type') == 'text' and expected in p.get('text', '') for p in parts)
    return messages

def main():
    assert adb('shell', 'getprop', 'ro.build.version.release').decode().strip() == '17'
    assert adb('shell', 'getprop', 'ro.product.model').decode().strip() == 'MODEL_ANDROID17'
    current = adb('shell', 'pm', 'path', APP).decode().strip().removeprefix('package:')
    assert adb('shell', 'run-as', APP, 'sha256sum', current).decode().split()[0].upper() == (CANDIDATE if CONTINUE else BASELINE)
    apk = ROOT / 'docs/handoff/evidence/skill-bindings1/skill-session-bindings1-candidate.apk'
    assert hashlib.sha256(apk.read_bytes()).hexdigest().upper() == CANDIDATE
    test = ROOT / 'app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk'
    save('identity.json', dict(serial=SERIAL, skill=SKILL, baseline=BASELINE, candidate=CANDIDATE,
        testApkSha256=hashlib.sha256(test.read_bytes()).hexdigest().upper(), scope='test-only host API fixture; GUI import NOT_TESTED'))
    if not CONTINUE:
        adb('shell', 'am', 'force-stop', APP)
        adb('install', '-r', str(apk))
        adb('install', '-r', str(test))
    adb('forward', 'tcp:18765', 'tcp:8765')
    first = json.loads((ORIGINAL / 'native-revision-1.json').read_text()) if CONTINUE else fixture('1')
    receipts['1'] = first
    status = launch()
    identity = dict(workspacePath=status['workspace'], workspaceKey=Path(status['workspace']).name)
    save('status.json', {k: status.get(k) for k in ['phase', 'workspace', 'nodeVersion', 'mode']})
    def create():
        return rpc('session/create', dict(workspace=identity, mode='build', model=dict(providerId='deepseek', modelId='deepseek-flash', options=dict(reasoningLevel='disabled')),
            thoughtLevel='disabled', titleGenerationEnabled=False, dynamicWorkflowEnabled=False, offPeakToolEnabled=False))['session']['sessionId']
    old = json.loads((ORIGINAL / 'old-session.json').read_text())['sessionId'] if CONTINUE else create()
    old_messages = snapshot(old) if CONTINUE else model_turn(old, '1')
    save('old-session.json', dict(sessionId=old, messages=len(old_messages)))
    second = json.loads((ORIGINAL / 'native-revision-2.json').read_text()) if CONTINUE else fixture('2')
    receipts['2'] = second
    assert second['hash'] != first['hash'] and second['retainedVersions'] == 2
    launch()
    rpc('session/resume', dict(sessionId=old, workspace=identity, dynamicWorkflowEnabled=False, offPeakToolEnabled=False))
    old_messages = model_turn(old, '1', len(old_messages))
    new = create()
    model_turn(new, '2')
    adb('shell', 'am', 'force-stop', APP)
    launch()
    rpc('session/resume', dict(sessionId=old, workspace=identity, dynamicWorkflowEnabled=False, offPeakToolEnabled=False))
    old_messages = model_turn(old, '1', len(old_messages))
    index = json.loads(adb('exec-out', 'run-as', APP, 'cat', 'files/sessions-index.json'))
    rows = {r['sessionId']: r for r in index}
    assert rows[old]['managedSkills'][0]['hash'] == first['hash']
    assert rows[new]['managedSkills'][0]['hash'] == second['hash']
    save('session-bindings.json', dict(old=rows[old], new=rows[new]))
    fixture(retire=True)
    launch()
    save('verification.json', dict(verdict='PASS', oldSession=old, newSession=new, realModelTurns=3 if CONTINUE else 4,
        continuedFromFailure=str(ORIGINAL) if CONTINUE else None,
        oldVersionHash=first['hash'], newVersionHash=second['hash'], retiredFromFutureSelection=True,
        scope='native host install/enable/publisher -> installed product binding -> real Skill/Read -> update and force-stop resume; GUI NOT_TESTED'))
    print('PASS real managed Skill product task/update/force-stop; evidence ' + str(EVIDENCE))

if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        save('failure.json', dict(type=type(error).__name__, message=str(error), evidence=str(EVIDENCE)))
        print('FAIL; retained evidence ' + str(EVIDENCE))
        raise
