"""Offline audit of actual standalone run, exact runtime bytes and uninstalled transport candidate."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/handoff/evidence/provider-isolation1'
RUN = BASE / '1792297091188177800'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


identity = load(RUN / 'identity.json')
result = load(RUN / 'result.json')
assert result['runId'] == RUN.name and result['verdict'] == 'PASS'
assert identity['productionBefore'] == identity['productionAfter'] == dict(apkSha256='C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D')
assert sha(RUN / 'probe.apk') == identity['apkSha256']
assert sha(ROOT / 'tools/phase9/provider-isolation-device-probe.py') == identity['driverSha256']
assert result['ownerUid'] != result['isolatedUid'] == result['toolResult']['data']['uid']
data = result['toolResult']['data']
assert data['node'] == 'v24.18.0' and data['privateRead'] == data['privateWrite'] == dict(allowed=False, code='ENOENT')
assert data['network'] == dict(allowed=False, code='EACCES') and result['ownerNetworkPositiveControl']
assert data['sha256'] == hashlib.sha256(b'isolation-fixture').hexdigest() and result['privateSentinelUnchanged']
assert result['cancelDeathMs'] == 15 and result['protocolReplies'] == 2 and result['initializeResult']['protocolVersion'] == '1.0'
commands = load(RUN / 'commands-and-exits.json')
assert all(r['argv'][1:3] == ['-s','DEVICE_ANDROID17'] for r in commands)
assert all('install' not in r['argv'] or 'ProviderIsolationProbe-debug.apk' in r['argv'][-1] for r in commands)
assert all('force-stop' not in r['argv'] or r['argv'][-1] == 'dev.alita.providerprobe' for r in commands)
with zipfile.ZipFile(RUN / 'probe.apk') as bundle:
    for library in identity['payload']['libraries']:
        assert hashlib.sha256(bundle.read('lib/arm64-v8a/' + library['packagedName'])).hexdigest() == library['sha256']
        assert sha(ROOT / 'app/src/main' / library['source']).lower() == library['sha256']
    shim = bundle.read('lib/arm64-v8a/libnodeprobe.so')
    assert hashlib.sha256(shim).hexdigest().upper() == sha(ROOT / 'experiments/provider-isolation/build/payload/jniLibs/arm64-v8a/libnodeprobe.so')
elf = (BASE / 'shim-elf.txt').read_text()
alignments = [int(line.split()[-1],16) for line in elf.splitlines() if line.strip().startswith('LOAD')]
assert alignments and all(value >= 16384 for value in alignments)
units = load(BASE / 'declared-tools-unit-summary.json')
assert [units[k] for k in ['tests','failures','errors','skipped']] == [68,0,0,0]
assert 'BUILD SUCCESSFUL' in (BASE / 'declared-tools-build-lint.log').read_text(encoding='utf-8')
assert 'BUILD SUCCESSFUL' in (BASE / 'declared-tools-lint-fresh.log').read_text(encoding='utf-8')
shutil.copyfile(ROOT / 'app/build/reports/lint-results-debug.txt', BASE / 'declared-tools-lint-results.txt')
assert '0 errors, 28 warnings' in (BASE / 'declared-tools-lint-results.txt').read_text()
candidate = ROOT / 'app/build/outputs/apk/debug/app-debug.apk'
shutil.copyfile(candidate, BASE / 'declared-tools-candidate.apk')
with zipfile.ZipFile(candidate) as current, zipfile.ZipFile(ROOT / 'docs/handoff/evidence/provider-package1/candidate.apk') as accepted:
    assert current.read('assets/zcode-runtime/payload-SHA256SUMS.txt') == accepted.read('assets/zcode-runtime/payload-SHA256SUMS.txt')
for file in (ROOT / 'app/build/test-results/testDebugUnitTest').glob('*.xml'):
    out = BASE / 'unit-results' / file.name
    out.parent.mkdir(exist_ok=True)
    shutil.copyfile(file, out)
source_files = [p for p in (ROOT / 'experiments/provider-isolation/src').rglob('*') if p.is_file()]
source_files += [ROOT / 'experiments/provider-isolation' / n for n in ['README.md','settings.gradle.kts','build.gradle.kts','gradle.properties']]
source_files += [ROOT / n for n in [
    'app/src/main/java/dev/alita/androidagent/tools/JsonRpcStdioProvider.kt',
    'app/src/test/java/dev/alita/androidagent/LocalProviderBoundaryTest.kt',
    'tools/phase9/prepare-provider-isolation-probe.py','tools/phase9/provider-isolation-device-probe.py',
    'tools/phase9/provider-isolation-evidence-summary.py']]
sources = []
for path in source_files:
    relative = path.relative_to(ROOT).as_posix()
    sources.append(dict(path=relative, sha256=sha(path)))
    out = RUN / 'accepted-source' / relative
    out.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(path,out)
summary = dict(verdict='PASS_TARGET_ISOLATION_FEASIBILITY_AND_UNIT_TESTED_DECLARATIVE_SEAM',
    productionDisposition='UNCHANGED_C51DB531; no imported tool admission/production integration accepted',
    run=RUN.name, probeApkSha256=identity['apkSha256'], uninstalledCandidateApkSha256=sha(candidate),
    exactRuntimeLibraries=len(identity['payload']['libraries']), shimLoadAlignments=alignments,
    localProtocolVersion='1.0', rpcVersion='2.0', ownerUid=result['ownerUid'], isolatedUid=result['isolatedUid'],
    privateRead=data['privateRead'], privateWrite=data['privateWrite'], network=data['network'], cancelDeathMs=15,
    unitTests=68, lintErrors=0, lintWarnings=28,
    executedProbeDriver=dict(path='tools/phase9/provider-isolation-device-probe.py', sha256=identity['driverSha256']),
    sourceIdentities=sources,
    retainedFailures=['First probe build used unavailable Files.readString/writeString API; fixed Java calls',
        'Two INSTALL_FAILED_USER_RESTRICTED attempts; user permitted retry, third install succeeded',
        'App-private library FD executable mapping denied',
        'Stale old result collected in one APK-native attempt; unique run IDs added',
        'sqlite3 without SONAME missing under alias; actual basename retained with identical bytes'],
    residuals=['Standalone synthetic fixture, not real model or Gateway execution',
        'Uninstalled transport candidate has unit/build/lint proof only',
        'No Android15 isolation test or generic provider import acceptance',
        'One cancellation observation, no descendant/race/budget guarantee',
        'Node Start export tied to exact24.18.0 payload ABI; production backend/resource/artifact/admission work remains'])
(BASE / 'acceptance-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:summary[k] for k in ['verdict','probeApkSha256','uninstalledCandidateApkSha256','unitTests','cancelDeathMs']}))
