"""Android17 separate test app only; preview/cancel UI, with unchanged review-file hash."""
from pathlib import Path
import hashlib,json,os,subprocess,time,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/handoff/evidence/provider-host-lifecycle1'/('ui-'+str(time.time_ns()))
OUT.mkdir(parents=True,exist_ok=False)
ADB=os.environ['ANDROID_ADB'];TEST='dev.alita.androidagent.isolationtest';SERIAL='DEVICE_ANDROID17'
records=[]
def adb(*args,check=True):
    p=subprocess.run([ADB,'-s',SERIAL,*args],capture_output=True,timeout=30)
    records.append(dict(argv=[ADB,'-s',SERIAL,*args],exit=p.returncode,stdout=p.stdout.decode('utf-8','replace'),stderr=p.stderr.decode('utf-8','replace')))
    (OUT/'commands.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert not check or p.returncode==0
    return p.stdout
def snapshot(label):
    remote='/data/local/tmp/'+OUT.name+'.xml'
    adb('shell','uiautomator','dump',remote)
    data=adb('exec-out','cat',remote);(OUT/(label+'.xml')).write_bytes(data)
    return ET.fromstring(data)
def center(node):
    import re
    l,t,r,b=map(int,re.findall(r'\d+',node.attrib['bounds']));return str((l+r)//2),str((t+b)//2)
def click(node): adb('shell','input','tap',*center(node));time.sleep(.5)
def text(root,value):
    return next(n for n in root.iter('node') if n.attrib.get('text')==value)
def review_hash():
    return adb('shell','run-as',TEST,'sha256sum','files/provider-reviews.json').decode().split()[0]
def reviews():
    return json.loads(adb('exec-out','run-as',TEST,'cat','files/provider-reviews.json'))
def approve():
    root=snapshot('before-editor-'+str(len(records)))
    click(text(root,'填写声明并评审'));root=snapshot('editor-'+str(len(records)))
    fields=[n for n in root.iter('node') if n.attrib.get('class')=='android.widget.EditText']
    click(fields[0]);adb('shell','input','text','compute');adb('shell','input','keyevent','4')
    root=snapshot('name-'+str(len(records)));fields=[n for n in root.iter('node') if n.attrib.get('class')=='android.widget.EditText']
    click(fields[2]);adb('shell','input','text','UI_approval_fixture');adb('shell','input','keyevent','4')
    root=snapshot('filled-'+str(len(records)));click(text(root,'检查'));time.sleep(1)
    root=snapshot('confirm-'+str(len(records)));assert text(root,'确认准入此版本') is not None
    click(text(root,'确认准入'));time.sleep(1)
try:
    assert adb('shell','getprop','ro.build.version.release').strip()==b'17'
    path=adb('shell','pm','path','dev.alita.androidagent').decode().strip().removeprefix('package:')
    baseline=adb('shell','run-as','dev.alita.androidagent','sha256sum',path).decode().split()[0].upper()
    assert baseline=='C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D'
    apk=ROOT/'app/build/outputs/apk/isolationTest/app-isolationTest.apk'
    (OUT/'test.apk').write_bytes(apk.read_bytes());(OUT/'driver.py').write_bytes(Path(__file__).read_bytes())
    adb('install','-r',str(apk));adb('shell','am','force-stop',TEST)
    adb('shell','am','start','-n',TEST+'/dev.alita.androidagent.execution.isolation.HostLifecycleProbeActivity','--ez','prepareUiOnly','true')
    time.sleep(2)
    fixture=json.loads(adb('exec-out','run-as',TEST,'cat','files/ui-admission-fixture.json'))
    initial=reviews();assert not any(r['id']==fixture['id'] for r in initial['selected'])
    adb('shell','pm','grant',TEST,'android.permission.POST_NOTIFICATIONS')
    adb('shell','am','start','-n',TEST+'/dev.alita.androidagent.MainActivity');time.sleep(2)
    root=snapshot('home')
    for attempt in range(3):
        click(text(root,'工具'));time.sleep(1);root=snapshot('tools-'+str(attempt))
        if any(n.attrib.get('text')=='独立本地工具' for n in root.iter('node')):break
    assert any(n.attrib.get('text')==fixture['id']+' · ui1' for n in root.iter('node'))
    approve();approved=reviews();pin=next(r for r in approved['selected'] if r['id']==fixture['id'])
    assert pin['contentHash']==fixture['contentHash'] and pin['toolIds']==[fixture['id']+'.compute']
    root=snapshot('approved');click(text(root,'停用新会话'));root=snapshot('retire-confirm');click(text(root,'确认停用'));time.sleep(1)
    retired=reviews();assert not any(r['id']==fixture['id'] for r in retired['selected'])
    row=next(r for r in retired['reviews'] if r['snapshot']==pin);assert row['revoked'] is False
    approve();reapproved=reviews();assert next(r for r in reapproved['selected'] if r['id']==fixture['id'])==pin
    root=snapshot('reapproved');click(text(root,'撤销所选版本'));root=snapshot('revoke-confirm');click(text(root,'确认撤销'));time.sleep(1)
    revoked=reviews();assert not any(r['id']==fixture['id'] for r in revoked['selected'])
    assert next(r for r in revoked['reviews'] if r['snapshot']==pin)['revoked'] is True
    assert [r for r in revoked['reviews'] if r['snapshot']['id']!=fixture['id']]==initial['reviews']
    assert revoked['selected']==initial['selected']
    assert adb('shell','run-as','dev.alita.androidagent','sha256sum',path).decode().split()[0].upper()==baseline
    result=dict(verdict='PASS_ACTUAL_UI_APPROVE_RETIRE_REAPPROVE_REVOKE',fixture=fixture,pin=pin,
       originalReviewEntriesUnchanged=True,originalSelectedUnchanged=True,productionApk=baseline,
       testApkSha256=hashlib.sha256(apk.read_bytes()).hexdigest(),scope='UI metadata only, inert nonexecuting fixture; no model/provider execution or production install')
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(evidence=str(OUT),**result)))
finally:adb('shell','am','force-stop',TEST,check=False)
