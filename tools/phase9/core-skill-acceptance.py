"""Real Core Skill discovery/load/resource/task proof on the assigned product device.

Test-only fixture setup; no runtime or config mutation. No external script installation.
"""
from pathlib import Path
import base64
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
ADB = os.environ['ANDROID_ADB']
NODE = os.environ['ACCEPTANCE_NODE']
SERIAL, PACKAGE = 'DEVICE_ANDROID17', 'dev.alita.androidagent'
APK_HASH = '87421D90D5925373392CF33A3E9973E005CEDD4BC6494D362E135113261AB03E'
WORKSPACE = '/data/user/0/' + PACKAGE + '/files/workspaces/default'
RUNTIME = '/data/user/0/' + PACKAGE + '/files/runtime'
VERIFY_ONLY = len(sys.argv) == 3 and sys.argv[1] == '--verify-only'
assert len(sys.argv) == 1 or VERIFY_ONLY, 'usage: core-skill-acceptance.py [--verify-only numeric-run-id]'
RUN = sys.argv[2] if VERIFY_ONLY else str(time.time_ns())
assert RUN.isdigit()
EVIDENCE = ROOT / 'docs/handoff/evidence/core-skill1' / RUN
if not VERIFY_ONLY:
    EVIDENCE.mkdir(parents=True, exist_ok=False)
else:
    assert EVIDENCE.is_dir()


def adb(*args):
    return subprocess.check_output([ADB, '-s', SERIAL, *args])


def request(route, body=None):
    token = adb('exec-out', 'run-as', PACKAGE, 'cat', 'files/runtime/bridge-token').decode().strip()
    req = urllib.request.Request('http://127.0.0.1:18765' + route,
        data=None if body is None else json.dumps(body).encode(),
        headers={'X-Bridge-Token': token, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=35) as res:
        return json.load(res)


def save(name, value):
    (EVIDENCE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def read(relative):
    return adb('exec-out', 'run-as', PACKAGE, 'cat', 'files/workspaces/default/' + relative)


adb('forward', 'tcp:18765', 'tcp:8765')
apk = adb('shell', 'pm', 'path', PACKAGE).decode().strip().removeprefix('package:')
actual = adb('shell', 'run-as', PACKAGE, 'sha256sum', apk).decode().split()[0].upper()
assert actual == APK_HASH, 'Product changed; review before preparing a new fixture'
status = request('/status')
assert status['phase'] == 'ready', 'Start existing product runtime first'
device_node = apk.rsplit('/', 1)[0] + '/lib/arm64/libnode.so'
config_relative = 'files/.zcode/cli/config.json'
config_before = adb('exec-out', 'run-as', PACKAGE, 'cat', config_relative)
cfg = json.loads(config_before)
assert cfg['plugins']['enabled'] is False and cfg['features']['memory'] is False
assert cfg['memory']['extractionEnabled'] is False
assert cfg['mcp']['servers']['android-host']['type'] == 'stdio'

skill = 'organize-proof-' + RUN
folder = 'skill-proof-' + RUN
skill_root = '.agents/skills/' + skill
template = ROOT / 'docs/project/fixtures/core-skill-organize'
if VERIFY_ONLY:
    identity = json.loads((EVIDENCE / 'identity.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(config_before).hexdigest() == identity['configHashBefore']
    data = json.loads((EVIDENCE / 'model-task.json').read_text(encoding='utf-8'))
    entry = identity['catalogEntry']
    fixture = json.loads((ROOT / 'docs/project/fixtures/organizing-input.json').read_text(encoding='utf-8'))
else:
    files = []
    for p in sorted(template.rglob('*')):
        if p.is_file():
            text = p.read_text(encoding='utf-8').replace('__RUN_ID__', RUN)
            rel = skill_root + '/' + p.relative_to(template).as_posix()
            files.append({'path': rel, 'base64': base64.b64encode(text.encode()).decode()})
            out = EVIDENCE / 'skill' / p.relative_to(template)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding='utf-8')
    fixture = json.loads((ROOT / 'docs/project/fixtures/organizing-input.json').read_text(encoding='utf-8'))
    for f in fixture['files']:
        raw = bytes.fromhex(f['content']) if f['encoding'] == 'hex' else f['content'].encode()
        files.append({'path': folder + '/' + f['path'], 'base64': base64.b64encode(raw).decode()})
    setup = EVIDENCE / 'prepare.cjs'
    setup.write_text("const fs=require('node:fs'),path=require('node:path');const root=" + json.dumps(WORKSPACE) +
        ";const files=" + json.dumps(files) + ";for(const f of files){const p=path.join(root,f.path);"
        "if(!p.startsWith(root+'/'))throw Error('outside fixture');fs.mkdirSync(path.dirname(p),{recursive:true});"
        "fs.writeFileSync(p,Buffer.from(f.base64,'base64'),{flag:'wx'});}console.log('new skill and fixture prepared');",
        encoding='utf-8')
    adb('push', str(setup), '/data/local/tmp/core-skill-prepare-' + RUN + '.cjs')
    cmd = 'OPENSSL_CONF=/dev/null LD_LIBRARY_PATH=' + shlex.quote(RUNTIME + '/lib') + ' ' + shlex.quote(device_node) + ' /data/local/tmp/core-skill-prepare-' + RUN + '.cjs'
    adb('shell', 'run-as', PACKAGE, 'sh', '-c', shlex.quote(cmd))
    catalog = request('/rpc-wait', {'method': 'skills/referenceCatalog', 'params': {
        'workspace': {'workspacePath': WORKSPACE, 'workspaceKey': 'default'}}, 'timeoutMs': 25000})
    save('catalog.json', catalog)
    entries = catalog.get('result', {}).get('skills', [])
    entry = next((x for x in entries if x['name'] == skill), None)
    assert entry and entry['enabled'] and entry['scope'] == 'workspace', 'Core did not discover the new SKILL.md'
    assert entry['path'].endswith('/' + skill_root + '/SKILL.md')
    save('identity.json', {'serial': SERIAL, 'apkSha256': actual, 'skillName': skill,
        'fixture': folder, 'runtimeVersion': '0.16.9-runtime5', 'productRevision': 'command-analysis1',
        'skillFileSha256': hashlib.sha256(read(skill_root + '/SKILL.md')).hexdigest(),
        'configHashBefore': hashlib.sha256(config_before).hexdigest(), 'catalogEntry': entry})
    prompt = ('Use the Skill tool to load the installed skill named ' + skill +
        ' before doing anything else. Complete its guided task on the synthetic workspace-relative '
        'directory ' + folder + '. Follow the skill and its referenced report rule. '
        'The only permitted calls are Skill, Read for that skill reference, workspace_analyze '
        'and workspace_file_create as instructed. This is test data. No other tool or directory.')
    result = subprocess.run([NODE, str(ROOT / 'tools/zcode/bridge-acceptance.cjs'), 'ui-lab', prompt],
        env=dict(os.environ, ANDROID_SERIAL=SERIAL), capture_output=True, timeout=180)
    (EVIDENCE / 'model-task.json').write_bytes(result.stdout)
    (EVIDENCE / 'model-task.err').write_bytes(result.stderr)
    assert result.returncode == 0, 'Real model harness failed; retain evidence'
    data = json.loads(result.stdout)

parts = [p for m in data['messages'] for p in m.get('parts', []) if p.get('type') == 'tool']
allowed = {'Skill', 'Read', 'mcp__android-host__workspace_analyze', 'mcp__android-host__workspace_file_create'}
assert parts and all(p['tool'] in allowed for p in parts)
assert all(p.get('state', {}).get('status') == 'completed' for p in parts)
skill_parts = [p for p in parts if p['tool'] == 'Skill']
resource_parts = [p for p in parts if p['tool'] == 'Read']
assert len(skill_parts) == 1, 'No exact genuine Core Skill call'
assert skill_parts[0]['state']['input']['skill'] == skill
assert entry['name'] in skill_parts[0]['state']['output']
assert len(resource_parts) == 1, 'Skill resource was not read exactly once'
assert 'SKILL_RESOURCE_PROOF_' + RUN in resource_parts[0]['state']['output']
assert resource_parts[0]['state']['input']['file_path'].endswith('/' + skill_root + '/references/report-rule.md')
rows = [r for r in data['gatewayJournalRows'] if r.get('session') == data['sessionId']]
# Core Skill/Read are existing read-only context adapters with needsApproval:false.
# They persist tool parts in the Core session, not Android Gateway operations.
# Keep that distinction explicit; do not invent Gateway coverage for those tools.
analysis = [r for r in rows if r['tool'] == 'mcp__android-host__workspace_analyze']
assert len(analysis) == 3 and sorted(r['result'] for r in analysis) == ['INVALID_JSON', 'ok', 'ok']
assert all(r['decision'] == 'allow' for r in analysis)
creates = [p for p in parts if p['tool'] == 'mcp__android-host__workspace_file_create']
assert len(creates) == 6
for part in creates:
    args = part['state']['input']
    assert args['path'].startswith(folder + '/')
    assert any(r['tool'] == part['tool'] and r['decision'] == 'allow' and r['result'] == 'ok'
        and json.loads(r['args']).get('rel') == args['path'] for r in rows), 'Missing successful Gateway create'
for f in fixture['files']:
    assert hashlib.sha256(read(folder + '/' + f['path'])).hexdigest().upper() == f['sha256']
copies = [('inbox/report.txt', 'organized/documents/report-imported.txt'),
    ('inbox/notes.md', 'organized/documents/notes.md'), ('inbox/空格 notes.txt', 'organized/documents/空格 notes.txt'),
    ('inbox/measurements.csv', 'organized/data/measurements.csv'), ('inbox/opaque.bin', 'organized/other/opaque.bin')]
for src, dst in copies:
    assert read(folder + '/' + src) == read(folder + '/' + dst)
report = read(folder + '/RESULTS.md').decode()
assert 'SKILL_RESOURCE_PROOF_' + RUN in report and 'INVALID_JSON' in report
assert any('CORE_SKILL_TASK_OK' in p.get('text', '') for m in data['messages'] for p in m.get('parts', []) if p.get('type') == 'text')
assert adb('exec-out', 'run-as', PACKAGE, 'cat', config_relative) == config_before, 'Safety config changed'
for p in sorted(template.rglob('*')):
    if p.is_file():
        expected = p.read_text(encoding='utf-8').replace('__RUN_ID__', RUN).encode()
        assert read(skill_root + '/' + p.relative_to(template).as_posix()) == expected, 'Skill resource changed'
(EVIDENCE / 'RESULTS.md').write_text(report, encoding='utf-8')
save('verification.json', {'verdict': 'PASS', 'sessionId': data['sessionId'], 'apkSha256': actual,
    'skillName': skill, 'skillCalls': sum(p['tool'] == 'Skill' for p in parts),
    'referenceCalls': sum(p['tool'] == 'Read' for p in parts), 'analysisCalls': len(analysis),
    'createCalls': sum(p['tool'] == 'mcp__android-host__workspace_file_create' for p in parts),
    'preservedOriginalFiles': 7, 'verifiedCopies': 5, 'reportPhrase': 'SKILL_RESOURCE_PROOF_' + RUN,
    'configUnchanged': True, 'contextAudit': 'Skill and Read recorded as Core session tool parts; no Gateway-operation claim',
    'gatewayAudit': 'three analysis rows and six successful create rows; Core broker intents retained separately',
    'scope': 'Core discovery/load/resource-guided model task; not Skill manager/version/dependency acceptance'})
print('PASS real Core Skill guided task; evidence: ' + str(EVIDENCE))
