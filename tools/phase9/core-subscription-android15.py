"""Directed Android15 protocol compatibility only; never installs/replaces runtime or invokes model."""
from pathlib import Path
import hashlib,json,os,re,shlex,subprocess,time
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(os.environ['SUBSCRIPTION_EVIDENCE_ROOT'])/('android15-subscription-'+str(time.time_ns()));OUT.mkdir(parents=True,exist_ok=False)
(OUT/'wrapper.py').write_bytes(Path(__file__).read_bytes())
APP,SERIAL='dev.zcode.nodepoc','DEVICE_ANDROID15';ADB=os.environ['ANDROID_ADB'];records=[]
def save(n,v):(OUT/n).write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
def run(*a):
 p=subprocess.run([ADB,'-s',SERIAL,*a],capture_output=True,timeout=90)
 records.append(dict(argv=[ADB,'-s',SERIAL,*a],exit=p.returncode,stdout=p.stdout.decode('utf-8','replace'),stderr=p.stderr.decode('utf-8','replace')));save('commands.json',records)
 assert p.returncode==0,'See retained command failure'
 return p.stdout
def shell(cmd):return run('shell','run-as',APP,'sh','-c',shlex.quote(cmd))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest().upper()
ref=json.loads(re.search(r'```json\s*(.*?)\s*```',(ROOT/'ANDROID15-BASELINE-REFERENCE.md').read_text('utf-8'),re.S).group(1))
pins={k:v['expected'] for k,v in ref['runtimePins'].items()}
assert run('shell','getprop','ro.build.version.release').strip()==b'15'
assert run('shell','getprop','ro.product.model').strip()==b'MODEL_ANDROID15'
apk=run('shell','pm','path',APP).decode().strip().removeprefix('package:');node=apk.rsplit('/',1)[0]+'/lib/arm64/libnode.so'
def baseline():
 data=dict(apk=run('shell','run-as',APP,'sha256sum',apk).decode().split()[0].upper(),libnode=run('shell','run-as',APP,'sha256sum',node).decode().split()[0].upper())
 data['pins']={k:run('shell','run-as',APP,'sha256sum','files/runtime/'+k).decode().split()[0].upper() for k in pins}
 assert data['apk']==ref['apkSha256'] and data['libnode']==ref['libnodeSha256'] and data['pins']==pins
 return data
save('baseline-pre.json',baseline())
helper=ROOT/'tools/phase9/core-subscription-protocol-test.cjs';expected=json.loads((ROOT/'SOURCE_IDENTITY.json').read_text('utf-8'))['tools/phase9/core-subscription-protocol-test.cjs'];assert sha(helper)==expected
cache='cache/'+OUT.name;run('shell','run-as',APP,'mkdir','-p',cache)
actual=shell('realpath '+cache).decode().strip();assert actual=='/data/user/0/'+APP+'/'+cache
tmp='/data/local/tmp/'+OUT.name+'.cjs';run('push',str(helper),tmp);run('shell','run-as',APP,'cp',tmp,cache+'/test.cjs')
assert run('shell','run-as',APP,'sha256sum',cache+'/test.cjs').decode().split()[0].upper()==expected
env='OPENSSL_CONF=/dev/null LD_LIBRARY_PATH=/data/user/0/'+APP+'/files/runtime/lib TMPDIR=/data/user/0/'+APP+'/cache TEST_CORE=/data/user/0/'+APP+'/files/runtime/zcode.cjs '
try:
 assert shell(env+shlex.quote(node)+' --version').decode().strip()=='v24.18.0'
 output=shell(env+shlex.quote(node)+' '+shlex.quote(actual+'/test.cjs'));r=records[-1]
 (OUT/'protocol.stdout').write_bytes(output);(OUT/'protocol.stderr').write_text(r['stderr'],encoding='utf-8')
 result=json.loads(output)
 assert result['verdict']=='PASS_ACTUAL_CORE_SUBSCRIPTION_PROTOCOL' and result['node']=='v24.18.0' and result['checks']==5
 assert result['missingDeliveryKind']==result['invalidDeliveryKind']==-32602
 assert len(result['positive'])==2 and all(x['sessionId']==result['sessionId'] and type(x['eventSeq']) is int and x['eventSeq']>=0 and x['events']==[] for x in result['positive'])
 assert result['readMessageCount']==1 and result['naturalExit']==dict(code=0,signal=None) and r['stderr']==''
 save('identity.json',dict(wrapperSha256=sha(OUT/'wrapper.py'),helperSha256=expected,fixtureActualPath=actual,node='v24.18.0',scope='Installed immutable Core in isolated HOME; no model/tool/Service/product integration'))
 save('result.json',result)
finally:save('baseline-post.json',baseline())
print(json.dumps(dict(evidence=str(OUT),verdict=result['verdict'])))
