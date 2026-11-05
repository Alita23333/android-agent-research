"""Android17 product-package acceptance. No direct carrier injection, no policy edits.

Stages are explicit; every invocation freezes its driver and retains independent evidence.
The native fixture only imports; exact version approval is exercised through product UI.
"""
from pathlib import Path
import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
APP, SERIAL = 'dev.alita.androidagent', 'DEVICE_ANDROID17'
BASELINE = 'C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D'
parser = argparse.ArgumentParser()
parser.add_argument('stage', choices=['prepare', 'first', 'restart', 'update', 'cancel', 'repair-install', 'service-stop', 'service-repair-install', 'reconnect'])
parser.add_argument('--run')
args = parser.parse_args()
RUN = args.run or str(time.time_ns())
assert RUN.isdigit() and (args.run or args.stage == 'prepare')
BASE = ROOT / 'docs/handoff/evidence/provider-model1' / RUN
BASE.mkdir(parents=True, exist_ok=True)
OUT = BASE / (args.stage + '-' + str(time.time_ns()))
OUT.mkdir(exist_ok=False)
shutil.copyfile(__file__, OUT / 'driver.py')
ADB = os.environ['ANDROID_ADB']
state_path = BASE / 'state.json'
state = json.loads(state_path.read_text('utf-8')) if state_path.exists() else dict(run=RUN, id='aa_model_' + RUN)
commands, events = [], []
token = ''
secrets = []
stream = None
stream_thread = None
stop_stream = threading.Event()
allowed = None
lock_path = BASE / 'device-stage.lock'
lock_held = False


def clean(s):
    for secret in [token, *secrets]:
        if secret:
            s = s.replace(secret, '[redacted]')
    return s


def save(name, value):
    (OUT / name).write_text(clean(json.dumps(value, ensure_ascii=False, indent=2)) + '\n', encoding='utf-8')


def checkpoint():
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def adb(*parts, check=True, private=False, timeout=90):
    result = subprocess.run([ADB, '-s', SERIAL, *parts], capture_output=True, timeout=timeout)
    if not private:
        commands.append(dict(argv=[ADB, '-s', SERIAL, *parts], exit=result.returncode,
            stdout=clean(result.stdout.decode('utf-8', 'replace')), stderr=clean(result.stderr.decode('utf-8', 'replace'))))
        save('commands.json', commands)
    assert not check or result.returncode == 0, 'device command failed; see retained commands'
    return result.stdout


def read_file(name, private=False, check=True):
    return adb('exec-out', 'run-as', APP, 'cat', name, private=private, check=check)


def request(route, body=None, timeout=30):
    r = urllib.request.Request('http://127.0.0.1:18765' + route,
        data=None if body is None else json.dumps(body).encode(),
        headers={'X-Bridge-Token': token, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(r, timeout=timeout) as response:
        return json.load(response)


def rpc(method, params, timeout=35):
    data = request('/rpc-wait', dict(method=method, params=params, timeoutMs=(timeout - 2) * 1000), timeout)
    assert not data.get('error'), method + ': ' + str(data.get('error'))
    return data.get('result')


def snapshot(label):
    remote = '/data/local/tmp/provider-model1-' + RUN + '.xml'
    adb('shell', 'uiautomator', 'dump', remote)
    raw = adb('exec-out', 'cat', remote)
    (OUT / (label + '.xml')).write_bytes(raw)
    return ET.fromstring(raw)


def text(tree, value):
    return next(n for n in tree.iter('node') if n.attrib.get('text') == value)


def tap(node):
    assert node.attrib.get('enabled') == 'true', 'UI control disabled'
    l, t, r, b = map(int, re.findall(r'\d+', node.attrib['bounds']))
    adb('shell', 'input', 'tap', str((l + r) // 2), str((t + b) // 2))
    time.sleep(.6)


def tools_ui():
    adb('shell', 'am', 'start', '-W', '--activity-clear-top', '-n', APP + '/.MainActivity')
    time.sleep(1)
    for i in range(3):
        tree = snapshot('tools-' + str(i))
        if any(n.attrib.get('text') == '独立本地工具' for n in tree.iter('node')):
            return tree
        tap(text(tree, '工具'))
    raise AssertionError('Tools navigation did not settle')


def approve_ui(revision):
    tree = tools_ui()
    title = text(tree, state['id'] + ' · ' + revision)
    parents = {child: parent for parent in tree.iter() for child in parent}
    card = title
    while not any(n.attrib.get('text') == '填写声明并评审' for n in card.iter('node')):
        card = parents[card]
    tap(text(card, '填写声明并评审'))
    tree = snapshot('editor')
    fields = [n for n in tree.iter('node') if n.attrib.get('class') == 'android.widget.EditText']
    tap(fields[0]); adb('shell', 'input', 'text', 'compute'); adb('shell', 'input', 'keyevent', '4')
    tree = snapshot('name-filled')
    fields = [n for n in tree.iter('node') if n.attrib.get('class') == 'android.widget.EditText']
    tap(fields[2]); adb('shell', 'input', 'text', state['description'].replace(' ', '%s')); adb('shell', 'input', 'keyevent', '4')
    tree = snapshot('description-filled'); tap(text(tree, '检查'))
    tree = snapshot('review-confirmation')
    text(tree, '确认准入此版本')
    # The UI displays the exact package and declaration identity before approval.
    assert any(state[revision]['contentHash'] in n.attrib.get('text', '') for n in tree.iter('node'))
    tap(text(tree, '确认准入'))
    reviews = json.loads(read_file('files/provider-reviews.json'))
    pin = next(r for r in reviews['selected'] if r['id'] == state['id'])
    assert pin['contentHash'] == state[revision]['contentHash'] and pin['toolIds'] == [state['id'] + '.compute']
    state[revision]['pin'] = pin
    save('approved-' + revision + '.json', pin); checkpoint()


def import_fixture(revision):
    out = adb('shell', 'am', 'instrument', '-w', '-e', 'class', APP + '.ManagedProviderModelFixtureTest',
        '-e', 'fixtureId', state['id'], '-e', 'revision', revision,
        APP + '.test/androidx.test.runner.AndroidJUnitRunner', timeout=120).decode()
    assert 'OK (1 test)' in out and 'FAILURES' not in out and 'INSTRUMENTATION_FAILED' not in out
    receipt = json.loads(read_file('cache/' + state['id'] + '-' + revision + '.json'))
    assert receipt['admissionUnchanged'] and receipt['registryAbsent']
    state[revision] = receipt; state['description'] = receipt['description']; checkpoint()
    save('import-' + revision + '.json', receipt)


def launch():
    global token
    adb('forward', 'tcp:18765', 'tcp:8765')
    # Start the exported product home and its normal UI entry; no privileged launcher.
    adb('shell', 'am', 'start', '-W', '--activity-clear-top', '-n', APP + '/.MainActivity')
    time.sleep(1)
    tree = snapshot('launch-home')
    for attempt in range(4):
        if any(n.attrib.get('text') in ['打开 Agent', '任务'] for n in tree.iter('node')):
            break
        time.sleep(1)
        adb('shell', 'am', 'start', '-W', '--activity-clear-top', '-n', APP + '/.MainActivity')
        tree = snapshot('launch-settled-' + str(attempt))
    if not any(n.attrib.get('text') == '打开 Agent' for n in tree.iter('node')):
        tap(text(tree, '任务')); tree = snapshot('launch-conversation')
    tap(text(tree, '打开 Agent'))
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            token = read_file('files/runtime/bridge-token', private=True).decode().strip()
            status = request('/status', timeout=2)
            if status['phase'] == 'ready':
                save('ready.json', status)
                config = json.loads(read_file('files/runtime/provider/personal_provider_config.json', private=True))
                providers = config['config']['providerConfigRules']['providerRules']
                for p in providers:
                    secrets.append(p['config']['access']['apiKey'])
                model = config['config']['modelConfigRules']['manualProviderModelRules'][0]
                state['selection'] = {k: model[k] for k in ['providerId', 'modelId']}
                state['workspace'] = dict(workspacePath=status['workspace'], workspaceKey='default')
                tools = request('/carrier/tools')['tools']
                ours = next(t for t in tools if t['toolId'] == state['id'] + '_compute')
                save('carrier-definition.json', ours); checkpoint()
                return status
        except (OSError, ValueError, KeyError, StopIteration):
            time.sleep(.5)
    raise AssertionError('Product runtime/carrier readiness deadline')


def begin_events():
    global stream, stream_thread
    stop_stream.clear()
    r = urllib.request.Request('http://127.0.0.1:18765/events', headers={'X-Bridge-Token': token})
    stream = urllib.request.urlopen(r, timeout=180)
    def consume():
        try:
            while not stop_stream.is_set():
                line = stream.readline()
                if not line:
                    break
                if not line.startswith(b'data:'):
                    continue
                e = json.loads(line[5:]); events.append(e)
                if e.get('type') == 'permission':
                    grant = allowed is not None and e.get('toolName') == 'mcp__android-host__' + state['id'] + '_compute' and not e.get('hardConfirm') and e.get('input') == allowed
                    answer = request('/respond', dict(requestId=e['requestId'], decision='allow' if grant else 'deny'))
                    events.append(dict(type='acceptance-permission-response', requestId=e['requestId'], granted=grant, result=answer))
        except Exception as error:
            if not stop_stream.is_set():
                events.append(dict(type='acceptance-stream-error', message=clean(str(error))))
    stream_thread = threading.Thread(target=consume, daemon=True)
    stream_thread.start()


def end_events():
    stop_stream.set()
    if stream is not None:
        # Break the blocking SSE read without waiting for its idle heartbeat.
        try:
            stream.fp.raw._sock.shutdown(2)
        except (AttributeError, OSError):
            pass
    if stream_thread is not None:
        stream_thread.join(3)
    if stream is not None:
        stream.close()
    save('events.json', events)


def create_session():
    c = rpc('session/create', dict(workspace=state['workspace'], model={**state['selection'], 'options': {'reasoningLevel': 'disabled'}},
        thoughtLevel='disabled', titleGenerationEnabled=False, dynamicWorkflowEnabled=False, offPeakToolEnabled=False))
    return c['session']['sessionId']


def model_turn(session, version, label):
    global allowed
    raw = ('independent-provider-' + RUN + '-' + label).encode()
    allowed = dict(base64=base64.b64encode(raw).decode())
    prior = request('/session/read?id=' + session)['snapshot']['messages']
    before_ids = {r['id'] for r in request('/gateway/journal?limit=500')['operations']}
    start = len(events)
    prompt = ('Use ONLY mcp__android-host__' + state['id'] + '_compute once with exactly ' + json.dumps(allowed) +
        '. This independently imported tool computes a checksum. Do not use Skill, Read, Bash, other tools or network. '
        'Report the returned version, SHA256, byte count, isolated UID/PID and host artifact path. '
        'End with PROVIDER_MODEL_OK only after receiving its actual result. Do not invent results.')
    rpc('session/send', dict(sessionId=session, content=prompt))
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        messages = request('/session/read?id=' + session)['snapshot']['messages']
        fresh = messages[len(prior):]
        if any(m.get('info', {}).get('role') == 'assistant' and m.get('info', {}).get('finish') == 'stop' for m in fresh):
            break
        time.sleep(.5)
    else:
        save(label + '-incomplete.json', messages)
        raise AssertionError('Real model completion deadline')
    save(label + '-messages.json', messages)
    parts = [p for m in fresh for p in m.get('parts', [])]
    tools = [p for p in parts if p.get('type') == 'tool']
    assert len(tools) == 1 and tools[0]['tool'] == 'mcp__android-host__' + state['id'] + '_compute', 'Actual model tool selection mismatch'
    part = tools[0]; assert part['state']['status'] == 'completed' and part['state']['input'] == allowed
    payload = json.loads(part['state']['output'].split('Structured content:\n', 1)[1])
    data = payload['data']; pin = state[version]['pin']
    assert data['version'] == version and data['bytes'] == len(raw) and data['sha256'] == hashlib.sha256(raw).hexdigest()
    assert data['_hostProvider']['contentHash'] == pin['contentHash'] and data['_hostProvider']['definitionHash'] == pin['definitionHash']
    assert data['_hostProvider']['backend'] == 'android-isolated-node'
    assert len(payload['artifacts']) == 1
    artifact = payload['artifacts'][0]
    assert artifact['uri'].startswith('/data/user/0/' + APP + '/files/artifacts/' + session + '/')
    physical = read_file(artifact['uri']); report = json.loads(physical)
    assert len(physical) == artifact['size'] and report['data'] == data and report['toolId'] == state['id'] + '.compute'
    (OUT / (label + '-artifact.json')).write_bytes(physical)
    ops = [r for r in request('/gateway/journal?limit=500')['operations'] if r['id'] not in before_ids and r['session'] == session and r['tool'] == part['tool']]
    assert len(ops) == 1 and ops[0]['result'] == 'ok' and ops[0]['decision'] == 'allow'
    assert json.loads(ops[0]['args']) == allowed and 'call_id=' + report['callId'] + ' ' in ops[0]['detail']
    assert 'provider_sha256=' + pin['contentHash'] in ops[0]['detail'] and 'declaration_sha256=' + pin['definitionHash'] in ops[0]['detail']
    calls = [e for e in events[start:] if e.get('type') == 'carrier-call' and e.get('callId') == report['callId']]
    assert len(calls) == 1
    owner_uid = adb('shell', 'run-as', APP, 'id', '-u').decode().strip()
    assert str(data['uid']) != owner_uid and data['pid'] > 0
    assert any(p.get('type') == 'text' and 'PROVIDER_MODEL_OK' in p.get('text', '') for p in parts)
    result = dict(sessionId=session, version=version, pin=pin, data=data, artifact=artifact,
        artifactSha256=hashlib.sha256(physical).hexdigest(), operation=ops[0], carrierEvent=calls[0],
        isolatedUidDistinctFromHost=True, modelIssued=True)
    save(label + '-verified.json', result); state[label] = result; checkpoint()
    return messages


def main():
    global lock_held, token
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as lock:
        lock.write(str(os.getpid()))
    lock_held = True
    assert adb('shell', 'getprop', 'ro.build.version.release').strip() == b'17'
    assert adb('shell', 'getprop', 'ro.product.model').strip() == b'MODEL_ANDROID17'
    if args.stage == 'prepare':
        assert not state_path.exists(), 'Use existing stage evidence, never silently overwrite a prepared run'
        apk_path = adb('shell', 'pm', 'path', APP).decode().strip().removeprefix('package:')
        before = adb('shell', 'run-as', APP, 'sha256sum', apk_path).decode().split()[0].upper()
        assert before == BASELINE
        adb('pull', apk_path, str(BASE / 'baseline.apk'))
        assert hashlib.sha256((BASE / 'baseline.apk').read_bytes()).hexdigest().upper() == before
        apk = ROOT / 'app/build/outputs/apk/debug/app-debug.apk'
        shutil.copyfile(apk, BASE / 'candidate.apk')
        state['baselineApk'] = before; state['candidateApk'] = hashlib.sha256(apk.read_bytes()).hexdigest().upper()
        save('identity.json', state); checkpoint()
        adb('install', '-r', str(BASE / 'candidate.apk'))
        adb('install', '-r', str(ROOT / 'app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk'))
        import_fixture('v1'); approve_ui('v1'); launch()
    elif args.stage == 'first':
        launch(); begin_events()
        state['oldSession'] = create_session(); checkpoint()
        model_turn(state['oldSession'], 'v1', 'first')
    elif args.stage == 'restart':
        status = launch(); old = state['oldSession']
        rpc('session/resume', dict(sessionId=old, workspace=state['workspace'], dynamicWorkflowEnabled=False, offPeakToolEnabled=False))
        before = request('/session/read?id=' + old)['snapshot']['messages']
        adb('shell', 'ps', '-A', '-o', 'UID,PID,PPID,NAME,ARGS')
        adb('shell', 'am', 'force-stop', APP)
        time.sleep(1)
        after = launch(); assert after['startedAt'] != status['startedAt']
        begin_events()
        rpc('session/resume', dict(sessionId=old, workspace=state['workspace'], dynamicWorkflowEnabled=False, offPeakToolEnabled=False))
        restored = request('/session/read?id=' + old)['snapshot']['messages']
        assert restored == before, 'Persisted full message state changed across force-stop'
        save('persisted-before.json', before); save('persisted-after.json', restored)
        model_turn(old, 'v1', 'restart')
    elif args.stage == 'update':
        # Instrumentation stops the owner process. Import cannot approve or alter its review file.
        import_fixture('v2'); approve_ui('v2'); launch(); begin_events()
        old = state['oldSession']
        rpc('session/resume', dict(sessionId=old, workspace=state['workspace'], dynamicWorkflowEnabled=False, offPeakToolEnabled=False))
        model_turn(old, 'v1', 'old-after-update')
        state['newSession'] = create_session(); checkpoint()
        model_turn(state['newSession'], 'v2', 'new-after-update')
        save('session-index.json', json.loads(read_file('files/sessions-index.json')))
    elif args.stage == 'cancel':
        global allowed
        launch(); begin_events()
        session = create_session(); state['cancelSession'] = session; checkpoint()
        raw = ('WAIT:cancel-' + RUN).encode()
        allowed = dict(base64=base64.b64encode(raw).decode())
        before_ids = {r['id'] for r in request('/gateway/journal?limit=500')['operations']}
        start = len(events)
        rpc('session/send', dict(sessionId=session, content='Use ONLY mcp__android-host__' + state['id'] +
            '_compute once with exactly ' + json.dumps(allowed) + '. Wait for its result. No other tools.'))
        deadline = time.monotonic() + 90
        call = None
        while time.monotonic() < deadline:
            calls = [e for e in events[start:] if e.get('type') == 'carrier-call' and e.get('toolId') == state['id'] + '_compute']
            if calls:
                call = calls[0]
                break
            time.sleep(.1)
        assert call, 'No real model carrier call before cancel'
        physical = []
        for _ in range(50):
            ps = adb('shell', 'ps', '-A', '-o', 'UID,PID,PPID,NAME,ARGS').decode()
            physical = [line.split() for line in ps.splitlines() if APP + ':provider' in line]
            if physical:
                break
            time.sleep(.1)
        save('cancel-active-processes.json', physical)
        assert len(physical) == 1, 'Need exact live isolated provider process before stop'
        active_pid = physical[0][1]
        owner_uid = adb('shell', 'run-as', APP, 'id', '-u').decode().strip()
        assert physical[0][0] != owner_uid
        save('cancel-messages-before.json', request('/session/read?id=' + session))
        stopped_at = time.monotonic()
        stop_reply = rpc('session/stop', dict(sessionId=session))
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            ps = adb('shell', 'ps', '-A', '-o', 'UID,PID,PPID,NAME,ARGS').decode()
            if not any(len(line.split()) > 1 and line.split()[1] == active_pid for line in ps.splitlines()[1:]):
                break
            time.sleep(.1)
        else:
            raise AssertionError('Cancelled isolated provider PID still alive')
        elapsed_ms = round((time.monotonic() - stopped_at) * 1000)
        time.sleep(1)
        after = request('/session/read?id=' + session)
        save('cancel-messages-after.json', after)
        ops = [r for r in request('/gateway/journal?limit=500')['operations'] if r['id'] not in before_ids and r['session'] == session and r['tool'] == 'mcp__android-host__' + state['id'] + '_compute']
        assert len(ops) == 1 and ops[0]['decision'] == 'allow' and ops[0]['result'] != 'ok'
        assert json.loads(ops[0]['args']) == allowed
        artifacts = adb('shell', 'run-as', APP, 'find', 'files/artifacts/' + session, '-type', 'f', check=False).decode()
        assert call['callId'] not in artifacts
        result = dict(sessionId=session, carrierCall=call, activeIsolatedPid=int(active_pid), activeUid=physical[0][0],
            processGone=True, exitAfterStopMs=elapsed_ms, stopReply=stop_reply, operation=ops[0],
            noSuccessRecorded=True, noCallArtifact=True, journalSettled=ops[0]['result'] is not None)
        save('cancel-verified.json', result); state['cancel'] = result; checkpoint()
        if state.get('repairedApk'):
            assert ops[0]['result'] == 'CANCELLED', 'Cancellation must settle the admitted journal operation'
            assert 'call_id=' + call['callId'] + ' ' in ops[0]['detail']
            assert 'provider_sha256=' + state['v2']['pin']['contentHash'] in ops[0]['detail']
            assert 'declaration_sha256=' + state['v2']['pin']['definitionHash'] in ops[0]['detail']
    elif args.stage in ['repair-install', 'service-repair-install']:
        apk_path = adb('shell', 'pm', 'path', APP).decode().strip().removeprefix('package:')
        current = adb('shell', 'run-as', APP, 'sha256sum', apk_path).decode().split()[0].upper()
        service_repair = args.stage == 'service-repair-install'
        assert current == (state['repairedApk'] if service_repair else state['candidateApk'])
        assert not state.get('serviceRepairedApk') if service_repair else not state.get('repairedApk')
        apk = ROOT / 'app/build/outputs/apk/debug/app-debug.apk'
        with zipfile.ZipFile(apk) as z:
            sums = z.read('assets/zcode-runtime/payload-SHA256SUMS.txt')
            for line in sums.decode().splitlines():
                h, name = line.split(maxsplit=1)
                packed = name.replace('jniLibs/', 'lib/', 1) if name.startswith('jniLibs/') else name
                assert hashlib.sha256(z.read(packed)).hexdigest() == h
        backup = read_file('files/provider-reviews.json')
        save('reviews-before.json', json.loads(backup))
        name = 'service-repaired-candidate.apk' if service_repair else 'repaired-candidate.apk'
        shutil.copyfile(apk, BASE / name)
        adb('install', '-r', str(BASE / name))
        state.setdefault('apkHistory', []).append(dict(previous=current, installed=hashlib.sha256(apk.read_bytes()).hexdigest().upper(), stage=args.stage))
        state['repairedApk'] = hashlib.sha256(apk.read_bytes()).hexdigest().upper()
        if service_repair:
            state['serviceRepairedApk'] = state['repairedApk']
        state['repairedPayloadSha256'] = hashlib.sha256(sums).hexdigest(); checkpoint()
        launch()
        assert read_file('files/provider-reviews.json') == backup
        installed = adb('shell', 'pm', 'path', APP).decode().strip().removeprefix('package:')
        assert adb('shell', 'run-as', APP, 'sha256sum', installed).decode().split()[0].upper() == state['repairedApk']
        # Verify actual installed immutable payload, excluding the host-materialized private config.
        verified = []
        for line in sums.decode().splitlines():
            h, name = line.split(maxsplit=1)
            if name.endswith('/personal_provider_config.json'):
                continue
            if name.startswith('assets/zcode-runtime/'):
                dest = 'files/runtime/' + name.removeprefix('assets/zcode-runtime/')
            elif name.startswith('assets/providers/text-digest/'):
                active = read_file('files/tool-providers/text_digest/active').decode().strip()
                dest = 'files/tool-providers/text_digest/versions/' + active + '/' + name.rsplit('/', 1)[1]
            else:
                assert name.startswith('jniLibs/arm64-v8a/')
                dest = installed.rsplit('/', 1)[0] + '/lib/arm64/' + name.rsplit('/', 1)[1]
            got = adb('shell', 'run-as', APP, 'sha256sum', dest).decode().split()[0]
            assert got == h, name
            verified.append(dict(path=name, sha256=got))
        save('installed-payload.json', verified)
    elif args.stage == 'service-stop':
        launch(); begin_events()
        session = create_session(); state['serviceStopSession'] = session; checkpoint()
        allowed = dict(base64=base64.b64encode(('WAIT:service-stop-' + RUN).encode()).decode())
        start = len(events)
        before_ids = {r['id'] for r in request('/gateway/journal?limit=500')['operations']}
        rpc('session/send', dict(sessionId=session, content='Use ONLY mcp__android-host__' + state['id'] +
            '_compute once with exactly ' + json.dumps(allowed) + '. Wait for the actual result. No other tools.'))
        deadline = time.monotonic() + 90
        call = None
        while time.monotonic() < deadline:
            calls = [e for e in events[start:] if e.get('type') == 'carrier-call' and e.get('toolId') == state['id'] + '_compute']
            if calls:
                call = calls[0]; break
            time.sleep(.1)
        assert call, 'Need actual model call before Service stop'
        physical = []
        for _ in range(50):
            ps = adb('shell', 'ps', '-A', '-o', 'UID,PID,PPID,NAME,ARGS').decode()
            physical = [line.split() for line in ps.splitlines() if APP + ':provider' in line]
            if physical: break
            time.sleep(.1)
        assert len(physical) == 1
        rows = {int(parts[1]): parts for line in ps.splitlines()[1:] if len(parts := line.split()) >= 4}
        status = request('/status'); core_pid = status['childPid']
        assert core_pid in rows
        bootstrap_pid = int(rows[core_pid][2])
        assert bootstrap_pid in rows and 'bootstrap.cjs' in ' '.join(rows[bootstrap_pid])
        owned = {bootstrap_pid, core_pid}
        for _ in range(len(rows)):
            extra = {pid for pid, parts in rows.items() if int(parts[2]) in owned}
            if extra <= owned: break
            owned |= extra
        carriers = [pid for pid in owned if 'android-carr' in ' '.join(rows[pid])]
        assert carriers, 'Need actual MCP process descendant before stop'
        owned.add(int(physical[0][1]))
        save('service-owned-processes-before.json', [rows[pid] for pid in sorted(owned)])
        tree = tools_ui()
        control = text(tree, '停止 Agent 以管理工具')
        stopped_at = time.monotonic(); tap(control)
        deadline = time.monotonic() + 15
        survivors = owned
        while time.monotonic() < deadline:
            ps_after = adb('shell', 'ps', '-A', '-o', 'UID,PID,PPID,NAME,ARGS').decode()
            pids = {int(parts[1]) for line in ps_after.splitlines()[1:] if len(parts := line.split()) >= 4}
            survivors = owned & pids
            if not survivors: break
            time.sleep(.2)
        save('service-stop-process-outcome.json', dict(ownedPids=sorted(owned), survivingPids=sorted(survivors), elapsedMs=round((time.monotonic()-stopped_at)*1000)))
        assert not survivors, 'Actual Service stop left owned Core/MCP/provider PID alive'
        tree = snapshot('service-stopped-ui')
        # Refresh reads the controller lease after asynchronous service cleanup.
        tap(text(tree, '刷新')); tree = snapshot('service-stopped-refreshed')
        assert any(n.attrib.get('text', '').startswith('Agent 已停止，可修改准入') for n in tree.iter('node'))
        end_events()
        after = launch(); assert after['startedAt'] != status['startedAt']
        ops = [r for r in request('/gateway/journal?limit=500')['operations'] if r['id'] not in before_ids and r['session'] == session and r['tool'] == 'mcp__android-host__' + state['id'] + '_compute']
        assert len(ops) == 1 and ops[0]['result'] != 'ok'
        result = dict(sessionId=session, carrierCall=call, ownedPids=sorted(owned), survivors=[], operation=ops[0],
            admissionUnlockedInActualUi=True, relaunched=True, journalSettled=ops[0]['result'] is not None,
            scope='Actual product Service UI stop during real model/isolated provider call; no manual process kill or force-stop')
        save('service-stop-verified.json', result); state['serviceStop'] = result; checkpoint()
        assert ops[0]['result'] == 'CANCELLED', 'Service-stop cancellation left journal operation incomplete'
        assert 'call_id=' + call['callId'] + ' ' in ops[0]['detail']
        assert 'provider_sha256=' + state['v2']['pin']['contentHash'] in ops[0]['detail']
        assert 'declaration_sha256=' + state['v2']['pin']['definitionHash'] in ops[0]['detail']
        begin_events()
        state['afterServiceStopSession'] = create_session(); checkpoint()
        model_turn(state['afterServiceStopSession'], 'v2', 'after-service-stop')
    elif args.stage == 'reconnect':
        adb('forward', 'tcp:18765', 'tcp:8765')
        token = read_file('files/runtime/bridge-token', private=True).decode().strip()
        before = request('/status')
        session = state['oldSession']
        messages = request('/session/read?id=' + session)['snapshot']['messages']
        adb('shell', 'input', 'keyevent', 'HOME')
        background = request('/status')
        after = launch()
        restored = request('/session/read?id=' + session)['snapshot']['messages']
        assert before['phase'] == background['phase'] == after['phase'] == 'ready'
        assert before['startedAt'] == background['startedAt'] == after['startedAt'] and restored == messages
        result = dict(sameRuntime=True, sessionId=session, exactMessagesRetained=True,
            beforeStartedAt=before['startedAt'], afterStartedAt=after['startedAt'])
        save('reconnect-verified.json', result); state['reconnect'] = result; checkpoint()
    state['completed-' + args.stage] = str(OUT.relative_to(ROOT)); checkpoint()
    save('result.json', dict(verdict='PASS_SCOPED_' + args.stage.upper(), state=state,
        scope='Real model stages use session/send only, actual product UI approval. Per-call approval supplied by exact-tool/exact-input test responder; not manual Gateway UI confirmation.'))
    print(json.dumps(dict(verdict='PASS_SCOPED_' + args.stage.upper(), run=RUN, evidence=str(OUT))))


try:
    main()
except BaseException as error:
    save('failure.json', dict(type=type(error).__name__, message=clean(str(error))))
    print('FAIL retained evidence ' + str(OUT), flush=True)
    raise
finally:
    end_events()
    if lock_held:
        lock_path.unlink()
