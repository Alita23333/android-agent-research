"""Read-only exact product/package identity and redacted production controls."""
from pathlib import Path
import hashlib, json, subprocess, shlex, xml.etree.ElementTree as ET
import zipfile
root = Path(__file__).resolve().parents[2]
main = root / 'app/src/main'
runtime = main / 'assets/zcode-runtime'
out = root / 'docs/handoff/evidence/phase9/final'
adb = r'C:\Android\Sdk\platform-tools\adb.exe'
package, serial = 'dev.alita.androidagent', 'DEVICE_ANDROID17'
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest().upper()
def command(*args):
    return subprocess.check_output([adb, '-s', serial, *args], text=True, encoding='utf-8').strip()
apk_device = command('shell', 'pm', 'path', package).split('package:')[1]
native = apk_device.rsplit('/',1)[0] + '/lib/arm64/'
entries=[]
apk = root / 'app/build/outputs/apk/debug/app-debug.apk'
archive = zipfile.ZipFile(apk)
for line in (runtime / 'payload-SHA256SUMS.txt').read_text().splitlines():
    expected, relative = line.split(maxsplit=1)
    local = main / relative
    assert digest(local).lower() == expected.lower(), relative + ': source integrity failed'
    zipped = relative.replace('jniLibs/', 'lib/', 1) if relative.startswith('jniLibs/') else relative
    assert hashlib.sha256(archive.read(zipped)).hexdigest().lower() == expected.lower(), relative + ': APK payload mismatch'
    if relative == 'assets/zcode-runtime/provider/personal_provider_config.json':
        entries.append({'path':relative,'sha256':expected.upper(),'packagedMatch':True,
                        'installedMatch':None,'reason':'Host-materialized mutable provider config; same documented runtime validator exclusion'})
        continue
    if relative.startswith('jniLibs/arm64-v8a/'):
        remote = native + relative.split('/')[-1]
    else:
        remote = 'files/runtime/' + relative.removeprefix('assets/zcode-runtime/')
    measured = command('exec-out', 'run-as', package, 'sha256sum', remote).split()[0]
    assert measured.lower() == expected.lower(), relative + ': installed integrity failed'
    entries.append({'path':relative,'sha256':expected.upper(),'packagedMatch':True,'installedMatch':True})
installed = command('shell','sha256sum',apk_device).split()[0].upper()
assert installed == digest(apk), 'Installed APK differs from tested artifact'
cfg = json.loads(command('exec-out','run-as',package,'cat','files/.zcode/cli/config.json'))
controls={'pluginsEnabled': cfg.get('plugins',{}).get('enabled'),
          'memoryFeature':cfg.get('features',{}).get('memory'),
          'memoryExtraction':cfg.get('memory',{}).get('extractionEnabled'),
          'mcpServers':list(cfg.get('mcp',{}).get('servers',{})),
          'carrierType':cfg.get('mcp',{}).get('servers',{}).get('android-host',{}).get('type')}
assert controls['pluginsEnabled'] is False and controls['memoryFeature'] is False and controls['memoryExtraction'] is False
assert 'android-host' in controls['mcpServers'] and controls['carrierType']=='stdio'
tests=[]
for path in (root/'app/build/test-results/testDebugUnitTest').glob('*.xml'):
    suite=ET.parse(path).getroot()
    tests.append({k:suite.attrib[k] for k in ['name','tests','failures','errors']})
manifest=json.loads((runtime/'runtime-manifest.json').read_text())
upstream=root.parent/'AGENT ON ANDROID workflow/export'
consumed={}
for relative in ['codex-phase9-handoff/SHA256SUMS.txt','codex-runtime-payload/SHA256SUMS.txt',
                 'codex-runtime-payload/assets/zcode-runtime/runtime-manifest.json']:
    path=upstream/relative
    if path.exists(): consumed[relative]=digest(path)
report={'serial':serial,'runtimeVersion':manifest['version'],'journalSchema':3,
        'apkSha256':digest(apk),'installedApkSha256':installed,
        'runtimeManifestSha256':digest(runtime/'runtime-manifest.json'),
        'payloadManifestSha256':digest(runtime/'payload-SHA256SUMS.txt'),
        'packagedPayloadMatches':len(entries),'installedPayloadMatches':sum(e['installedMatch'] is True for e in entries),
        'payload':entries,'controls':controls,'jvmTests':tests,
        'upstreamManifests':consumed,
        'visionConfigMode':command('exec-out','run-as',package,'stat','-c','%a','files/runtime/vision/vision_config.json')}
(out/'release-identity.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:report[k] for k in ['runtimeVersion','apkSha256','runtimeManifestSha256','payloadManifestSha256','installedPayloadMatches','controls','visionConfigMode']},indent=2))
