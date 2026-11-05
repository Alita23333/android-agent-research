"""Assigned Android17 real-model independent provider and artifact acceptance."""
from pathlib import Path
import base64
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(os.environ.get('LOCAL_PROVIDER_EVIDENCE_DIR', str(ROOT / 'docs/handoff/evidence/local-provider1')))
ADB, NODE = os.environ['ANDROID_ADB'], os.environ['ACCEPTANCE_NODE']
SERIAL, PACKAGE = 'DEVICE_ANDROID17', 'dev.alita.androidagent'
identity = json.loads((EVIDENCE / 'build-identity.json').read_text(encoding='utf-8'))


def command(*args):
    return subprocess.check_output([ADB, '-s', SERIAL, *args])


apk = command('shell', 'pm', 'path', PACKAGE).decode().strip().removeprefix('package:')
actual = command('shell', 'run-as', PACKAGE, 'sha256sum', apk).decode().split()[0].upper()
assert actual == identity['apkSha256']
runtime = '/data/user/0/' + PACKAGE + '/files/runtime/'
provider_version = command('exec-out', 'run-as', PACKAGE, 'cat', 'files/tool-providers/text_digest/active').decode().strip()
assert len(provider_version) == 64 and all(c in '0123456789abcdef' for c in provider_version)
rows = []
for line in (ROOT / 'app/src/main/assets/zcode-runtime/payload-SHA256SUMS.txt').read_text().splitlines():
    expected, name = line.split(maxsplit=1)
    assert hashlib.sha256((ROOT / 'app/src/main' / name).read_bytes()).hexdigest() == expected
    if name.endswith('provider/personal_provider_config.json'):
        continue
    if name.startswith('assets/zcode-runtime/'):
        dest = runtime + name.removeprefix('assets/zcode-runtime/')
    elif name.startswith('assets/providers/text-digest/'):
        dest = 'files/tool-providers/text_digest/versions/' + provider_version + '/' + name.rsplit('/', 1)[1]
    else:
        dest = apk.rsplit('/', 1)[0] + '/lib/arm64/' + name.rsplit('/', 1)[1]
    got = command('shell', 'run-as', PACKAGE, 'sha256sum', dest).decode().split()[0]
    assert got == expected, name
    rows.append({'path': name, 'sha256': got})
(EVIDENCE / 'installed-payload.json').write_text(json.dumps({'apkSha256': actual, 'immutableHashes': rows,
    'providerVersion': provider_version}, indent=2) + '\n', encoding='utf-8')

text = 'Android 上的独立工具\nsecond line\n'.encode()
binary = b'\x00\x01\x7f\x80\xff'
inputs = [base64.b64encode(b).decode() for b in (text, binary)]
prompt = ('This is an authorized synthetic test of the new independent local data provider. '
    'Use ONLY mcp__android-host__text_digest_inspect, no Skill/Read/Bash/file/UI/network tools. '
    'First call it with {"base64":"!!!!"}, report its real INVALID_INPUT and recover. '
    'Then call it once on each of these exact canonical base64 values: ' + json.dumps(inputs) +
    '. Report the actual SHA256/bytes/UTF8/line count, local protocol trace and both returned '
    'artifact references. Do not invent references. End with LOCAL_PROVIDER_TASK_OK after tool results.')
result = subprocess.run([NODE, str(ROOT / 'tools/zcode/bridge-acceptance.cjs'), 'ui-lab', prompt],
    env=dict(os.environ, ANDROID_SERIAL=SERIAL), capture_output=True, timeout=180)
(EVIDENCE / 'model-task.json').write_bytes(result.stdout)
(EVIDENCE / 'model-task.err').write_bytes(result.stderr)
assert result.returncode == 0, 'Real model turn failed; retained evidence'
data = json.loads(result.stdout)
parts = [p for m in data['messages'] for p in m.get('parts', []) if p.get('type') == 'tool']
assert len(parts) == 3 and all(p['tool'] == 'mcp__android-host__text_digest_inspect' for p in parts)
assert all(p['state']['status'] == 'completed' for p in parts)
operations = [r for r in data['gatewayJournalRows'] if r['tool'] == 'mcp__android-host__text_digest_inspect']
assert len(operations) == 3 and sorted(r['result'] for r in operations) == ['INVALID_INPUT', 'ok', 'ok']
assert all(r['session'] == data['sessionId'] and r['decision'] == 'allow' for r in operations)
assert {json.loads(r['args'])['base64'] for r in operations} == {'!!!!', *inputs}
assert len(data['carrierCalls']) == 3
assert any('LOCAL_PROVIDER_TASK_OK' in p.get('text', '') for m in data['messages'] for p in m.get('parts', []) if p.get('type') == 'text')
verified = []
instances = set()
for part in parts:
    encoded = part['state']['input']['base64']
    if encoded == '!!!!':
        assert 'INVALID_INPUT' in part['state']['output']
        continue
    structured = part['state']['output'].split('Structured content:\n', 1)[1]
    payload = json.loads(structured)
    result_data = payload['data']
    raw = base64.b64decode(encoded)
    digest = hashlib.sha256(raw).hexdigest()
    assert result_data['sha256'] == digest and result_data['bytes'] == len(raw)
    assert result_data['utf8'] == (encoded == inputs[0])
    assert result_data['lineCount'] == (2 if encoded == inputs[0] else None)
    trace = result_data['_localProvider']
    assert trace['providerId'] == 'text_digest' and trace['rpcVersion'] == '2.0' and trace['protocolVersion'] == '1.0'
    assert trace['replyValidated'] and trace['requestId'] >= 2 and trace['method'] == 'tools/call'
    instances.add(trace['processInstanceId'])
    artifact = payload['artifacts'][0]
    assert len(payload['artifacts']) == 1 and artifact['name'] == 'digest.txt' and artifact['mimeType'] == 'text/plain'
    assert artifact['uri'].startswith(('/data/user/0/' + PACKAGE + '/files/artifacts/' + data['sessionId'] + '/',
        '/data/data/' + PACKAGE + '/files/artifacts/' + data['sessionId'] + '/'))
    report = command('exec-out', 'run-as', PACKAGE, 'cat', artifact['uri'])
    assert report == ('SHA-256: ' + digest + '\nBytes: ' + str(len(raw)) + '\n').encode()
    assert len(report) == artifact['size'] and hashlib.sha256(report).hexdigest()[:16] == artifact['id']
    name = 'digest-text.txt' if encoded == inputs[0] else 'digest-binary.txt'
    (EVIDENCE / name).write_bytes(report)
    verified.append({'bytes': len(raw), 'sha256': digest, 'artifact': artifact, 'localTrace': trace})
assert len(verified) == 2 and len(instances) == 1
(EVIDENCE / 'verification.json').write_text(json.dumps({'verdict': 'PASS', 'apkSha256': actual,
    'sessionId': data['sessionId'], 'independentProviderCalls': 2, 'hostRejectedCalls': 1,
    'gatewayRows': operations, 'verifiedArtifacts': verified, 'immutableHashes': len(rows),
    'scope': 'real model → MCP → dispatcher → Gateway-bound local JSON-RPC process and host artifacts'},
    ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('PASS real independent provider, malformed input recovery, exact Gateway outcomes and artifact readback')
