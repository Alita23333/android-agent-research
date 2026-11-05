"""Actual product Service in separate Android17 test UID. No production install, root or model."""
from pathlib import Path
import hashlib,json,os,subprocess,time,shutil
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'docs/handoff/evidence/provider-host-lifecycle1'/str(time.time_ns());OUT.mkdir(parents=True)
ADB=os.environ['ANDROID_ADB'];TEST='dev.alita.androidagent.isolationtest';PRODUCT='dev.alita.androidagent';rows=[]
def adb(*args,check=True):
 p=subprocess.run([ADB,'-s','DEVICE_ANDROID17',*args],capture_output=True,timeout=45)
 rows.append(dict(argv=[ADB,'-s','DEVICE_ANDROID17',*args],exit=p.returncode,stdout=p.stdout.decode('utf-8','replace'),stderr=p.stderr.decode('utf-8','replace')))
 (OUT/'commands.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8');assert not check or p.returncode==0
 return p
def baseline():
 path=adb('shell','pm','path',PRODUCT).stdout.decode().strip().removeprefix('package:')
 value=adb('shell','run-as',PRODUCT,'sha256sum',path).stdout.decode().split()[0].upper()
 assert value=='C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D';return value
try:
 assert adb('shell','getprop','ro.build.version.release').stdout.strip()==b'17'
 before=baseline();apk=ROOT/'app/build/outputs/apk/isolationTest/app-isolationTest.apk';shutil.copy2(apk,OUT/'test.apk')
 sources={}
 for name in ['app/src/main/java/dev/alita/androidagent/zcode/runtime/ZCodeHostService.kt','app/src/main/java/dev/alita/androidagent/zcode/runtime/ZCodeRuntimeBundle.kt',
              'app/src/main/java/dev/alita/androidagent/zcode/runtime/ZCodeCarrierWorker.kt',
              'app/src/isolationTest/java/dev/alita/androidagent/execution/isolation/HostLifecycleProbeActivity.kt',str(Path(__file__).relative_to(ROOT))]:
  p=ROOT/name;dest=OUT/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);sources[name]=hashlib.sha256(p.read_bytes()).hexdigest()
 (OUT/'identity.json').write_text(json.dumps(dict(testApkSha256=hashlib.sha256(apk.read_bytes()).hexdigest(),productionBefore=before,sources=sources),indent=2)+'\n')
 adb('install','-r',str(apk));adb('shell','am','force-stop',TEST)
 adb('shell','am','start','-n',TEST+'/dev.alita.androidagent.execution.isolation.HostLifecycleProbeActivity','--es','runId',OUT.name)
 result=None
 for _ in range(100):
  p=adb('exec-out','run-as',TEST,'cat','files/host-lifecycle-result.json',check=False)
  if p.returncode==0:
   try:r=json.loads(p.stdout)
   except ValueError:time.sleep(.2);continue
   if r.get('runId')==OUT.name:
    result=r;(OUT/'result.json').write_bytes(p.stdout)
    if r.get('verdict')!='RUNNING':break
  time.sleep(1)
 baseline()
 owner=adb('shell','pidof',TEST,check=False).stdout.decode().strip()
 if owner:(OUT/'owner-logcat.txt').write_bytes(adb('logcat','-d','--pid='+owner,check=False).stdout)
 assert result and result.get('verdict')=='PASS_SCOPED_ACTUAL_SERVICE_IDLE_CORE_EXIT','See retained failure '+str(OUT)
 print(json.dumps(dict(evidence=str(OUT),result=result)))
finally:adb('shell','am','force-stop',TEST,check=False)
