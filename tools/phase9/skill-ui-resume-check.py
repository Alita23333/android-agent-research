"""After explicit product force-stop/relaunch, resume the retired UI-imported v1 session."""
from pathlib import Path
import json
import os
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
ADB = os.environ['ANDROID_ADB']
APP, SERIAL = 'dev.alita.androidagent', 'DEVICE_ANDROID17'
RUN = ROOT / 'docs/handoff/evidence/skill-ui1/1792247177543398800'
proof = json.loads((RUN / 'result.json').read_text())
session, skill = proof['oldSession'], proof['skill']
token = subprocess.check_output([ADB, '-s', SERIAL, 'exec-out', 'run-as', APP, 'cat', 'files/runtime/bridge-token']).decode().strip()

def request(route, body=None):
    req = urllib.request.Request('http://127.0.0.1:18765' + route,
        data=None if body is None else json.dumps(body).encode(), headers={'X-Bridge-Token': token, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=40) as response:
        return json.load(response)

def rpc(method, params):
    result = request('/rpc-wait', dict(method=method, params=params, timeoutMs=30000))
    assert not result.get('error'), str(result.get('error'))
    return result['result']

status = request('/status')
assert status['phase'] == 'ready'
identity = dict(workspacePath=status['workspace'], workspaceKey=Path(status['workspace']).name)
rpc('session/resume', dict(sessionId=session, workspace=identity, dynamicWorkflowEnabled=False, offPeakToolEnabled=False))
before = request('/session/read?id=' + session)['snapshot']['messages']
rpc('session/send', dict(sessionId=session, content='For this validation actually call the Skill tool now to reload ' + skill +
    ', even if it was loaded earlier, then actually call Read on its references/rule.txt. Do not answer from prior history. '
    'Reply with the exact resource line. Only Skill and Read; no writes or other tools.'))
for _ in range(240):
    messages = request('/session/read?id=' + session)['snapshot']['messages']
    if any(m.get('info', {}).get('role') == 'assistant' and m.get('info', {}).get('finish') == 'stop' for m in messages[len(before):]):
        break
    time.sleep(.5)
else:
    raise AssertionError('resumed model task did not complete')
parts = [p for m in messages[len(before):] for p in m.get('parts', [])]
tools = [p for p in parts if p.get('type') == 'tool']
(RUN / ('retired-session-resume-attempt-' + str(time.time_ns()) + '.json')).write_text(json.dumps(dict(sessionId=session, beforeCount=len(before), messages=messages), indent=2) + '\n')
assert tools and all(p['tool'] in {'Skill', 'Read'} and p['state']['status'] == 'completed' for p in tools)
assert any(p['tool'] == 'Skill' and p['state']['input']['skill'] == skill and proof['v1Hash'] in p['state']['output'] for p in tools)
expected = 'UI_RESOURCE_' + skill + '_1'
reference = '/data/data/' + APP + '/files/core-skill-packages/' + skill + '/versions/' + proof['v1Hash'] + '/references/rule.txt'
reads = [p for p in tools if p['tool'] == 'Read' and p['state']['input'].get('file_path') == reference]
history = any(p.get('tool') == 'Read' and p.get('state', {}).get('input', {}).get('file_path') == reference and
    expected in p.get('state', {}).get('output', '') for m in before for p in m.get('parts', []))
assert any(expected in p['state']['output'] or (history and p['state']['output'] == 'Wasted call — file unchanged since your last Read. Refer to that earlier tool_result instead.') for p in reads)
assert any(p.get('type') == 'text' and expected in p.get('text', '') for p in parts)
assert subprocess.check_output([ADB, '-s', SERIAL, 'exec-out', 'run-as', APP, 'cat', reference]).decode() == expected + '\n'
(RUN / 'retired-session-resume.json').write_text(json.dumps(dict(verdict='PASS', sessionId=session,
    oldHash=proof['v1Hash'], retiredSkill=skill, messages=messages, physicalReferenceMatches=True,
    scope='real model v1 after UI retirement and host force-stop/relaunch; repeated Read may use verified Core cache'), indent=2) + '\n')
print('PASS retired UI-imported v1 session after force-stop/relaunch; real model Skill/Read')
