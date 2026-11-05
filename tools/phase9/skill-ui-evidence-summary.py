"""Offline audit of genuine model snapshots and successful UI result; no device interaction."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/handoff/evidence/skill-ui1'
RUN = BASE / '1792247177543398800'
load = lambda file: json.loads(file.read_text(encoding='utf-8-sig'))
report, identity = load(RUN / 'result.json'), load(RUN / 'identity.json')
assert report['verdict'] == 'PASS' and b'OK (1 test)' in (RUN / 'instrumentation.stdout').read_bytes()
assert (RUN / 'instrumentation.stderr').read_bytes() == b''
assert hashlib.sha256((RUN / 'candidate.apk').read_bytes()).hexdigest().upper() == identity['candidate']
assert hashlib.sha256((RUN / 'test.apk').read_bytes()).hexdigest().upper() == identity['test']
rows = []
for file, start, version, session in [('skill-ui1-1-0-model.json', 0, '1', report['oldSession']),
    ('skill-ui1-1-5-model.json', 5, '1', report['oldSession']), ('skill-ui1-2-0-model.json', 0, '2', report['newSession'])]:
    data = load(RUN / file)
    assert data['sessionId'] == session
    parts = [p for m in data['messages'][start:] for p in m.get('parts', [])]
    tools = [p for p in parts if p.get('type') == 'tool']
    assert tools and all(p['tool'] in {'Skill', 'Read'} and p['state']['status'] == 'completed' for p in tools)
    expected_hash = report['v1Hash'] if version == '1' else report['v2Hash']
    skill = [p for p in tools if p['tool'] == 'Skill']
    reads = [p for p in tools if p['tool'] == 'Read']
    assert skill and reads and all(p['state']['input']['skill'] == report['skill'] and expected_hash in p['state']['output'] for p in skill)
    assert all('/versions/' + expected_hash + '/references/rule.txt' in p['state']['input']['file_path'] for p in reads)
    proof = 'UI_RESOURCE_' + report['skill'] + '_' + version
    fresh = any(proof in p['state']['output'] for p in reads)
    assert fresh or (start > 0 and any(proof in p.get('state', {}).get('output', '') for m in data['messages'][:start] for p in m.get('parts', []) if p.get('tool') == 'Read'))
    assert any(p.get('type') == 'text' and proof in p.get('text', '') for p in parts)
    rows.append(dict(file=file, sessionId=session, version=version, skillCalls=len(skill), readCalls=len(reads), freshReadContent=fresh))
retired = load(RUN / 'retired-session-resume.json')
assert retired['verdict'] == 'PASS' and retired['oldHash'] == report['v1Hash'] and retired['physicalReferenceMatches']
commands = load(RUN / 'commands-and-exits.json')
assert all(row['argv'][1:3] == ['-s', 'DEVICE_ANDROID17'] and row['exit'] == 0 for row in commands)
post = load(BASE / 'postflight.json')
assert post['verdict'] == 'PASS' and post['apkSha256'] == identity['candidate'] and post['packagedCount'] == 40 and post['immutableInstalledCount'] == 39
sources = ['app/src/main/java/dev/alita/androidagent/MainActivity.kt', 'app/src/main/java/dev/alita/androidagent/MainViewModel.kt',
    'app/src/androidTest/AndroidManifest.xml', 'app/src/androidTest/java/dev/alita/androidagent/SkillManagerUiDeviceTest.kt',
    'app/src/androidTest/java/dev/alita/androidagent/SkillFixtureDocumentsProvider.java']
summary = dict(verdict='PASS', disposition='ACCEPTED_SCOPED_SKILL_UI_AND_LIVE_VERSIONING', apkSha256=identity['candidate'],
    testApkSha256=identity['test'], uiRun=RUN.name, modelTasks=rows, retiredSessionResume=True,
    priorFailedInstrumentationRuns=7, successfulInstrumentationTests=1,
    sourceIdentities=[dict(path=p, sha256=hashlib.sha256((ROOT / p).read_bytes()).hexdigest().upper()) for p in sources],
    scope='real SAF/UI and model Skill/Read, live v1/v2 and retired restart; no arbitrary script/provider/root capability acceptance')
(BASE / 'acceptance-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print('PASS offline genuine UI/model evidence audit; source/artifact identities recorded')
