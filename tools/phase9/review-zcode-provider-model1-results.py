"""Offline receiving review only; no incoming execution, network or device interaction."""
from pathlib import Path
import ast,hashlib,importlib.util,json,re,shlex,zipfile
ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'docs/handoff';EX=ROOT.parent/'AGENT HANDOFF EXCHANGE'
ID='zcode-provider-model1-android15-20261025-r1';BASE=DOC/('incoming-'+ID)
OUT=DOC/'evidence/provider-model1-receiving';OUT.mkdir(exist_ok=True)
checks=[]
load=lambda p:json.loads(p.read_text('utf-8-sig'))
sha=lambda b:hashlib.sha256(b).hexdigest().upper()
def check(name,value):
    checks.append(dict(name=name,passed=bool(value)));assert value,name
spec=importlib.util.spec_from_file_location('reviewed_exchange',ROOT/'tools/handoff/file-exchange.py')
ex=importlib.util.module_from_spec(spec);spec.loader.exec_module(ex)
v=ex.verify(EX/'zcode-to-codex'/ID)
check('COMPLETE eighteen payload files exact archive',v['integrity']=='PASS' and v['completion']=='COMPLETE' and v['fileCount']==18 and v['archiveSha256']=='9577A21F4288A6206C76EB3784EF4737D75A1346AE893034C5A2D343E90C9377')
with zipfile.ZipFile(EX/'zcode-to-codex'/ID/'bundle.zip') as z:
    for name in z.namelist():check('sealed extracted bytes '+name,z.read(name)==(BASE/name).read_bytes())
meta=load(BASE/'PACKAGE.json');check('one dependency',len(meta['dependencies'])==1);dep=meta['dependencies'][0]
dv=ex.verify(EX/'codex-to-zcode'/dep['packageId'])
check('exact assigned dependency',dep['packageId']=='codex-provider-model1-20261025-r1' and dv['archiveSha256']==dep['archiveSha256']=='76C88F5572D89B33378745E724EFC8AC32C043A247EF7CE863BD055CBD615075')
with zipfile.ZipFile(EX/'codex-to-zcode'/dep['packageId']/'bundle.zip') as z:
    for name in dep['requiredPaths']:check('required dependency bytes '+name,z.read(name)==(DOC/'outgoing'/dep['packageId']/name).read_bytes())
    pins=json.loads(z.read('SOURCE_IDENTITY.json'));rows=load(BASE/'results/source-verification.json')
    check('sixteen unique complete identity rows',len(rows)==len(pins)==16 and len({r['path'] for r in rows})==16 and {r['path'] for r in rows}==set(pins))
    for r in rows:check('source per-entry '+r['path'],r['match'] is True and r['actual']==r['expected']==pins[r['path']]==sha(z.read(r['path']))==sha((ROOT/r['path']).read_bytes()))
    ref=json.loads(re.search(r'```json\s*(.*?)\s*```',z.read('ANDROID15-BASELINE-REFERENCE.md').decode(),re.S).group(1))
    expected_pass=[l for l in z.read('results/build-and-regression/cancellation-existing22.log').decode().splitlines() if l.startswith('PASS ')]
expected={k:ref[k] for k in ['android','model','apkSha256']}
expected.update({'pin:'+k:r['expected'] for k,r in ref['runtimePins'].items()});expected.update(libnode=ref['libnodeSha256'],node=ref['nodeVersion'])
copies=[('app/src/main/assets/zcode-runtime/'+n,'runtime/'+n) for n in ['bootstrap.cjs','gateway.cjs','carrier-authorization.cjs']]
copies += [('tools/phase9/'+n,n) for n in ['provider-abandoned-carrier-test.cjs','provider-declaration-settlement-test.cjs','provider-settlement-regression.cjs']]
titles=['abandoned native carrier: '+x for x in ['cancel','runtime-exit','session-change','journal-failure','wrong-scope','already-finished','ui-not-owned','provider-timeout']]
titles+=['declaration settlement: '+x for x in ['match','wrong-definition','missing-definition','invalid-definition','definition-without-content','cancelled']]
fixtures=[]
for label,sub,count in [('first','results/first-failure-attempt1',31),('final','results',38)]:
    p=BASE/sub;records=load(p/'commands-and-exits.json');pre=load(p/'baseline-pre.json')
    check(label+' exact command count and serial/exit',len(records)==count and all(r['exit']==0 and r['argv'][1:3]==['-s','DEVICE_ANDROID15'] for r in records))
    check(label+' sealed baseline match',pre==expected)
    keys=['apkSha256',*['pin:'+k for k in ref['runtimePins']],'libnode']
    for i,k in enumerate(keys):check(label+' raw pre '+k,records[3+i]['stdout'].split()[0].upper()==expected[k])
    check(label+' Android version model Node',records[1]['stdout'].strip()=='15' and records[2]['stdout'].strip()=='MODEL_ANDROID15' and records[9]['stdout'].strip()=='v24.18.0')
    fixture=records[11]['stdout'].strip();fixtures.append(fixture)
    check(label+' realpath private fixture',fixture+'/runtime'=='/data/user/0/dev.zcode.nodepoc/'+records[10]['argv'][-1] and shlex.split(shlex.split(records[11]['argv'][-1])[0])==['realpath',fixture])
    for i,(name,dest) in enumerate(copies):
        at=12+3*i
        check(label+' byte exact copy '+dest,records[at]['argv'][3]=='push' and records[at+1]['argv'][-1]==records[10]['argv'][-1].removesuffix('/runtime')+'/'+dest and records[at+2]['stdout'].split()[0].upper()==pins[name])
    apk=records[0]['stdout'].strip().removeprefix('package:');node=apk.rsplit('/',1)[0]+'/lib/arm64/libnode.so'
    env=['OPENSSL_CONF=/dev/null','LD_LIBRARY_PATH=/data/user/0/dev.zcode.nodepoc/files/runtime/lib','TMPDIR='+fixture,'TEST_RUNTIME='+fixture+'/runtime',node]
    cmd=shlex.split(shlex.split(records[30]['argv'][-1])[0])
    check(label+' exact stage a command environment no reporter override',cmd==env+['--test',fixture+'/provider-abandoned-carrier-test.cjs',fixture+'/provider-declaration-settlement-test.cjs'])
    raw=(p/'tap.stdout').read_bytes();out=raw.decode()
    check(label+' raw stage a command-output identity',records[30]['stdout'].encode()==raw and records[30]['stderr'].encode()==(p/'tap.stderr').read_bytes()==b'')
    counts={k:int(n) for k,n in re.findall(r'(?m)^[#ℹ\s]*\b(tests|pass|fail|cancelled|skipped|todo)\s+(\d+)\s*$',out)}
    check(label+' anchored exact summary fields',counts=={'tests':14,'pass':14,'fail':0,'cancelled':0,'skipped':0,'todo':0})
    individual=re.findall(r'(?m)^✔ (.*?) \([\d.]+ms\)\s*$',out)
    check(label+' fourteen exact individual tests',individual==titles)
    if label=='final':
        check('final exact stage b command',shlex.split(shlex.split(records[31]['argv'][-1])[0])==env+[fixture+'/provider-settlement-regression.cjs'])
        raw=(p/'settlement.stdout').read_bytes();out=raw.decode()
        check('final raw stage b output and empty stderr',records[31]['stdout'].encode()==raw and records[31]['stderr'].encode()==(p/'settlement.stderr').read_bytes()==b'')
        check('final exact22 assertion names and result line',[l for l in out.splitlines() if l.startswith('PASS ')]==expected_pass and len(expected_pass)==22 and out.splitlines()[-1]=='RESULT 22 PASS')
        post=load(p/'baseline-post.json')
        check('final complete unchanged post hashes',post=={k:expected[k] for k in keys})
        for i,k in enumerate(keys):check('final raw post '+k,records[32+i]['stdout'].split()[0].upper()==expected[k])
    else:
        check('first recorded attempt ends at stage a before settlement/postflight',len(records)==31 and not (p/'settlement.stdout').exists() and not (p/'baseline-post.json').exists())
check('two distinct observed fixture paths',fixtures[0]!=fixtures[1])
summary=load(BASE/'results/BASELINE-RESULT.json')
check('final fixture and copy summary',summary['fixtureActualPath']==fixtures[1] and summary['copiedByteExact']=={dest:pins[name] for name,dest in copies})
check('final summary baseline',summary['baseline']['pre']==expected and summary['baseline']['post']==load(BASE/'results/baseline-post.json') and summary['baseline']['allMatch'] is True)
check('wrapper declared exact frozen SHA',summary['executedWrapper']['sha256']==sha((BASE/summary['executedWrapper']['path']).read_bytes()))
old=(BASE/'results/first-failure-attempt1/wrapper-source.py').read_text('utf-8');new=(BASE/'source/wrapper.txt').read_text('utf-8')
ast.parse(old);ast.parse(new)
check('first reporter assertion fails before second execution',old.index("'tests14': '# tests 14' in tap_out")<old.index("assert r1.returncode == 0 and tap['tests14']")<old.index('r2 = call('))
check('final reporter adaptation is substring gate so receiver uses stronger anchored matching',"'tests14': 'tests 14' in tap_out" in new)
review=(BASE/'results/SOURCE-REVIEW.md').read_text('utf-8')
check('four bounded answers',all('## Q'+str(i) in review for i in range(1,5)))
check('source and runtime wiring limits retained','NOT exercised' in review and 'NO' in review and 'deliveryKind' in review)
receipts=[load(p) for p in (EX/'receipts/zcode').glob(dep['packageId']+'-*.json')]
check('actual ZCode INTEGRATED dependency receipt',any(r.get('state')=='INTEGRATED' and r.get('archiveSha256')==dep['archiveSha256'] for r in receipts))
result=dict(disposition='ACCEPTED_SCOPED_COMPATIBILITY_WITH_RECORD_CORRECTIONS',archiveSha256=v['archiveSha256'],offlineChecks=len(checks),checks=checks,sourceEntries=16,
 finalResult=dict(nodeTests=14,sqliteAssertions=22,exitCodes=[0,0],stderrBytes=[0,0]),
 corrections=['Attempt1 records exactly31 commands ending after stage a; stage b and postflight not reached. Both-stages-twice prose is contradicted by source/control flow and records.',
 'Already-completed intent fails matches precheck before SQL CAS; a distinct settlement regression tests the CAS race.',
 'Cancellation error results have no returned provider provenance to compare; finish validates host expected pin shapes and writes host-bound hashes. Success-only returned-pin equality remains conditional on response.ok.',
 'writableEnded guard proves completed HTTP response not resettled by close; it does not prove every disconnect/timeout/race globally.',
 'Final wrapper substring counts are weaker than anchored numeric assertions; receiver independently checked anchored counts and all14 names.'],
 incomingExecution=0,deviceActions=0,productionEdits=0,
 remaining='Codex Web deliveryKind diagnosis. ZCode baseline frozen; no rerun/acknowledgement-only/correction-only package requested; carry corrections into next substantive report.')
(OUT/'offline-review.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(disposition=result['disposition'],offlineChecks=len(checks))))
