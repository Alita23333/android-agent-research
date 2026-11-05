"""Android17 separate test app only; preview/cancel UI, with unchanged review-file hash."""
from pathlib import Path
import hashlib,json,os,subprocess,time,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/handoff/evidence/provider-admission1'/('ui-'+str(time.time_ns()))
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
try:
    assert adb('shell','getprop','ro.build.version.release').strip()==b'17'
    path=adb('shell','pm','path','dev.alita.androidagent').decode().strip().removeprefix('package:')
    assert adb('shell','run-as','dev.alita.androidagent','sha256sum',path).decode().split()[0].upper()=='C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D'
    before=review_hash()
    # Notification permission belongs only to this separate disposable test package.
    # Normal ADB runtime-permission grant avoids the ROM's notification dialog consuming taps.
    adb('shell','pm','grant',TEST,'android.permission.POST_NOTIFICATIONS')
    adb('shell','am','start','-n',TEST+'/dev.alita.androidagent.MainActivity')
    time.sleep(2);root=snapshot('home')
    # Test-package notification dialog may appear on its first MainActivity launch.
    permissions=[n for n in root.iter('node') if n.attrib.get('resource-id')=='com.android.permissioncontroller:id/permission_allow_button']
    if not permissions:
        permissions=[n for n in root.iter('node') if n.attrib.get('package')=='com.android.permissioncontroller' and
                     n.attrib.get('text')=='始终允许' and n.attrib.get('class')=='android.widget.Button']
    if permissions:click(permissions[0]);root=snapshot('home-permission-resolved')
    click(text(root,'工具'));time.sleep(1);root=snapshot('tools')
    assert text(root,'独立本地工具') is not None
    assert any('Agent 已停止' in n.attrib.get('text','') for n in root.iter('node'))
    candidate=text(root,'填写声明并评审');assert candidate.attrib.get('enabled')=='true';click(candidate)
    root=snapshot('editor');fields=[n for n in root.iter('node') if n.attrib.get('class')=='android.widget.EditText']
    assert len(fields)==3
    click(fields[0]);adb('shell','input','text','compute')
    adb('shell','input','keyevent','4')
    root=snapshot('name-filled')
    fields=[n for n in root.iter('node') if n.attrib.get('class')=='android.widget.EditText']
    click(fields[2]);adb('shell','input','text','UI_preview_fixture')
    adb('shell','input','keyevent','4');root=snapshot('editor-filled')
    click(text(root,'检查'));time.sleep(1);root=snapshot('confirmation')
    assert text(root,'确认准入此版本') is not None
    values=[n.attrib.get('text','') for n in root.iter('node')]
    assert any('包内容 SHA-256' in v for v in values) and any('声明 SHA-256' in v for v in values)
    assert any('16 KiB' in v and 'Gateway' in v for v in values)
    click(text(root,'返回修改'));root=snapshot('returned-editor')
    assert any(n.attrib.get('text')=='UI_preview_fixture' for n in root.iter('node'))
    click(text(root,'取消'));root=snapshot('cancelled')
    assert not any(n.attrib.get('text')=='确认准入此版本' for n in root.iter('node'))
    after=review_hash();assert before==after
    result=dict(verdict='PASS_UI_PREVIEW_CANCEL_ONLY',reviewSha256Before=before,reviewSha256After=after,
        scope='Actual Compose editor/preview/back/cancel; no approval click/model or HostService start/stop',
        driverSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(evidence=str(OUT),**result)))
finally:adb('shell','am','force-stop',TEST,check=False)
