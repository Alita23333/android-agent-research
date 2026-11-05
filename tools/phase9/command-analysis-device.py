"""Assigned Android17 product-payload tests + synthetic workspace setup only."""
from pathlib import Path
import hashlib, json, os, shlex, subprocess, time, urllib.request

root = Path(__file__).resolve().parents[2]
adb = os.environ['ANDROID_ADB']
serial, package = 'DEVICE_ANDROID17', 'dev.alita.androidagent'
evidence = root / 'docs/handoff/evidence/command-analysis1'
evidence.mkdir(parents=True, exist_ok=True)

def command(*args):
    return subprocess.check_output([adb, '-s', serial, *args], encoding='utf-8').strip()

runtime = '/data/user/0/' + package + '/files/runtime'
apk = command('shell', 'pm', 'path', package).splitlines()[0].removeprefix('package:')
node = apk.rsplit('/', 1)[0] + '/lib/arm64/libnode.so'
token = command('exec-out', 'run-as', package, 'cat', 'files/runtime/bridge-token')
def request(path):
    with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:18765' + path,
        headers={'X-Bridge-Token': token}), timeout=10) as response:
        return json.load(response)
for attempt in range(20):
    try:
        token = command('exec-out', 'run-as', package, 'cat', 'files/runtime/bridge-token')
        status = request('/status')
        if status.get('phase') == 'ready': break
    except Exception: pass
    time.sleep(1)
else: raise RuntimeError('product runtime did not become ready')
rows = []
for line in (root / 'app/src/main/assets/zcode-runtime/payload-SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
    expected, name = line.split(maxsplit=1)
    assert hashlib.sha256((root / 'app/src/main' / name).read_bytes()).hexdigest() == expected
    if name.endswith('provider/personal_provider_config.json'): continue
    dest = (runtime + '/' + name.removeprefix('assets/zcode-runtime/')) if name.startswith('assets/') else (apk.rsplit('/',1)[0]+'/lib/arm64/'+name.rsplit('/',1)[1])
    actual = command('shell', 'run-as', package, 'sha256sum', dest).split()[0]
    assert actual == expected, name
    rows.append({'path':name,'sha256':actual})
command('push',str(root / 'tools/phase9/workspace-analysis-regression.cjs'),'/data/local/tmp/agent-analysis-regression.cjs')
relative = 'cache/analysis-regression-' + str(time.time_ns())
script = 'mkdir -p '+relative+'/tmp && cp /data/local/tmp/agent-analysis-regression.cjs '+relative+'/test.cjs && cd '+relative+' && TMPDIR="$PWD/tmp" TEST_RUNTIME='+shlex.quote(runtime)+' OPENSSL_CONF=/dev/null LD_LIBRARY_PATH='+shlex.quote(runtime+'/lib')+' '+shlex.quote(node)+' test.cjs'
result = command('shell','run-as',package,'sh','-c',shlex.quote(script))
(evidence/'native-script-regression.log').write_text(result+'\n',encoding='utf-8')
assert '"checks":14' in result and '"platform":"android"' in result
fixture = json.loads((root / 'docs/project/fixtures/organizing-input.json').read_text(encoding='utf-8'))
folder = 'command-analysis-' + str(time.time_ns())
setup = evidence/'materialize.cjs'
setup.write_text("const fs=require('node:fs'),path=require('node:path');const root="+json.dumps('/data/user/0/'+package+'/files/workspaces/default/'+folder)+";if(fs.existsSync(root))throw Error('existing fixture');const files="+json.dumps(fixture['files'],ensure_ascii=False)+";for(const f of files){const p=path.join(root,f.path);fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,Buffer.from(f.content,f.encoding==='hex'?'hex':'utf8'),{flag:'wx'});}console.log('seven synthetic files prepared');",encoding='utf-8')
command('push',str(setup),'/data/local/tmp/agent-analysis-materialize.cjs')
command('shell','run-as',package,'sh','-c',shlex.quote('OPENSSL_CONF=/dev/null LD_LIBRARY_PATH='+runtime+'/lib '+node+' /data/local/tmp/agent-analysis-materialize.cjs'))
identity={'serial':serial,'apkSha256':command('shell','run-as',package,'sha256sum',apk).split()[0],
    'runtimeVersion':'0.16.9-runtime5','productRevision':'command-analysis1','node':status.get('nodeVersion'),
    'installedImmutableCount':len(rows),'hashes':rows,'fixtureRelative':folder,'nativeChecks':14,
    'scope':'installed product payload; synthetic fixture only; not model task proof'}
(evidence/'device-identity.json').write_text(json.dumps(identity,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in identity.items() if k!='hashes'},indent=2))
