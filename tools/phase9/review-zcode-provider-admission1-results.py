"""Offline source/evidence review; never executes received code or accesses devices."""
from pathlib import Path
import hashlib,importlib.util,json,xml.etree.ElementTree as ET,zipfile

ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'docs/handoff'
EXCHANGE=ROOT.parent/'AGENT HANDOFF EXCHANGE'
BASE=DOC/'incoming-zcode-provider-admission1-source-review-20261023-r1'
OUT=DOC/'evidence/provider-admission1-receiving';OUT.mkdir(parents=True,exist_ok=True)
checks=[]
def check(name,condition):
    checks.append(dict(name=name,passed=bool(condition)));assert condition,name
load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda b:hashlib.sha256(b).hexdigest().upper()
spec=importlib.util.spec_from_file_location('reviewed_exchange',ROOT/'tools/handoff/file-exchange.py')
exchange=importlib.util.module_from_spec(spec);spec.loader.exec_module(exchange)
v=exchange.verify(EXCHANGE/'zcode-to-codex'/BASE.name.removeprefix('incoming-'))
check('incoming COMPLETE integrity and four files',v['integrity']=='PASS' and v['completion']=='COMPLETE' and v['fileCount']==4)
check('incoming exact archive',v['archiveSha256']=='A12AD310764A67832C7731BF1ED7CDE96A4564170FB68C6C7DDD8219F8313DEF')
with zipfile.ZipFile(EXCHANGE/'zcode-to-codex'/v['packageId']/'bundle.zip') as z:
    for name in z.namelist():check('extracted exact sealed bytes '+name,z.read(name)==(BASE/name).read_bytes())
meta=load(BASE/'PACKAGE.json');check('one dependency',len(meta['dependencies'])==1)
dep=meta['dependencies'][0];d=exchange.verify(EXCHANGE/'codex-to-zcode'/dep['packageId'])
check('exact outgoing dependency',dep['packageId']=='codex-provider-admission1-20261023-r1' and d['archiveSha256']==dep['archiveSha256']=='5EADE4A91684FB6FB66A9EBE925AE4E238AE44F1AAAA08295A56A299F8EA5CAB')
sealed=DOC/'outgoing'/dep['packageId']
with zipfile.ZipFile(EXCHANGE/'codex-to-zcode'/dep['packageId']/'bundle.zip') as z:
    for name in dep['requiredPaths']:check('dependency required '+name,z.read(name)==(sealed/name).read_bytes())
    pins=json.loads(z.read('SOURCE_IDENTITY.json'));rows=load(BASE/'results/source-verification.json')
    check('34 unique verification rows',len(rows)==len(pins)==34 and len({r['path'] for r in rows})==34 and {r['path'] for r in rows}==set(pins))
    for row in rows:
        name=row['path'];expected=pins[name]
        check('source per-entry '+name,row['match'] is True and row['expected']==row['actual']==expected==sha(z.read(name))==sha((ROOT/name).read_bytes()))
    # Check evidence as sealed data rather than rerunning any driver/test.
    prefix='results/android17/1792760006423232400/'
    result=json.loads(z.read(prefix+'result.json'))
    check('actual prior controlled transport verdict',result['verdict']=='PASS_SCOPED_ADMISSION_CORE_RESTART_TRANSPORT')
    check('all eight admission checks true',all(result['checks'][k] is True for k in ['inertImport','previewInert','approveDeferred','activeMutationsRejected','firstStopQuiescent','registryRemovedOnStop','secondStopQuiescent','oldPinRetainedAcrossRestart']))
    check('two runtime generations',len(result['starts'])==2 and len(result['shutdowns'])==2)
    for i,row in enumerate(result['reports']):
        raw=z.read(prefix+f'artifact-{i}.json');artifact=json.loads(raw);data=artifact['data'];pin=result['newPin'] if i==2 else result['oldPin']
        expected=['v1','v1','v2'][i]
        check('physical version and hash '+str(i),data['version']==expected and sha(raw).lower()==row['physicalReportSha256'])
        check('physical reviewed pins '+str(i),data['_hostProvider']['contentHash']==pin['contentHash'] and data['_hostProvider']['definitionHash']==pin['definitionHash'])
        matches=[op for op in row['operations'] if op['session']==row['sessionId'] and 'call_id='+artifact['callId']+' ' in op['detail']]
        check('exact successful journal join '+str(i),len(matches)==1 and matches[0]['decision']=='allow' and matches[0]['result']=='ok' and matches[0]['id']==[9,10,11][i] and 'provider_sha256='+pin['contentHash'] in matches[0]['detail'] and 'declaration_sha256='+pin['definitionHash'] in matches[0]['detail'])
    counts=dict(tests=0,failures=0,errors=0,skipped=0);target={}
    for name in z.namelist():
        if name.startswith('results/unit-tests/') and name.endswith('.xml'):
            root=ET.fromstring(z.read(name))
            for k in counts:counts[k]+=int(root.attrib[k])
            if root.attrib['name'].endswith(('ProviderAdmissionControllerTest','ZCodeCarrierWorkerLifecycleTest')):target[root.attrib['name']]=int(root.attrib['tests'])
    check('JVM134 exact XML total',counts==dict(tests=134,failures=0,errors=0,skipped=0))
    check('new test counts12 plus4',sorted(target.values())==[4,12])
    check('lint0 errors28warnings','0 errors, 28 warnings' in z.read('results/lint-results-debug.txt').decode())
    for name in ['results/build-repaired-final.log','results/build-probe-reader-repair.log']:check('successful build '+name,'BUILD SUCCESSFUL' in z.read(name).decode())
    ui=json.loads(z.read('results/ui-1792760188831031400/result.json'))
    check('UI preview cancel unchanged review file',ui['verdict']=='PASS_UI_PREVIEW_CANCEL_ONLY' and ui['reviewSha256Before']==ui['reviewSha256After'])
    for name in ['first-owner-logcat.txt','second-owner-logcat.txt']:
        log=z.read('results/'+name).decode();check('actual fatal diagnostic reader '+name,'FATAL EXCEPTION: Thread-7' in log and 'java.io.InterruptedIOException: read interrupted by close() on another thread' in log and 'AdmissionProbeActivity' in log)
review=(BASE/'results/SOURCE-REVIEW.md').read_text('utf-8')
check('all six source answers present',all('## Q'+str(i) in review for i in range(1,7)))
check('source review retains actual Service residual','UNMEASURED' in review and 'NOT' in review and 'test-HTTP-initiated' in review)
receipts=[load(p) for p in (EXCHANGE/'receipts/zcode').glob(dep['packageId']+'-*.json')]
check('actual ZCode INTEGRATED outgoing receipt',any(r.get('state')=='INTEGRATED' and r.get('archiveSha256')==dep['archiveSha256'] for r in receipts))
summary=dict(disposition='ACCEPTED_SCOPED_OFFLINE_SOURCE_REVIEW',archiveSha256=v['archiveSha256'],checkCount=len(checks),checks=checks,
    sourceEntries=34,incomingExecution=0,deviceActions=0,productionEdits=0,
    clarifications=['No findings means no defect reported within six bounded offline questions, not global security/no-bypass proof.',
        'Only explicit production UI entry writes approval; trusted host review APIs also exist. The review does not prove that every possible caller must be UI.',
        'Cleanup is fail-closed when not quiescent, not a universal deadline guarantee.',
        'All runtime/model/Service/UI-confirmation limits in sealed STATUS and residuals retained.'],
    remaining=['Actual production Service stop/Core+MCP descendant exit measurement','Actual UI approval/retire/revoke taps',
        'Real model/provider/artifact/cancellation/force-stop recovery and Android17 final acceptance'])
(OUT/'offline-review.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(disposition=summary['disposition'],offlineChecks=len(checks))))
