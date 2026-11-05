"""Pin scoped product proof and a deterministic Android15 task for the original exchange v1."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'docs/handoff';EV=DOC/'evidence/provider-model1'
BASE=EV/'1792764185483531200';AC=EV/'acceptance-20261025-1792937892173990600';summary=json.loads((AC/'acceptance-summary.json').read_text('utf-8'))
ID='codex-provider-model1-20261025-r1';DEST=DOC/'outgoing'/ID;DEST.mkdir(parents=True,exist_ok=False)
roles={};identities={}
def put(name,data,role):
    p=DEST/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data if isinstance(data,bytes) else data.encode());roles[name]=role
def copy(p,name,role):put(name,p.read_bytes(),role)
copy(DOC/'provider-model1-product-acceptance-20261025.md','PRODUCT-RESULT.md','documentation')
copy(DOC/'outgoing/codex-provider-host-lifecycle1-20261023-r1/ANDROID15-BASELINE-REFERENCE.md','ANDROID15-BASELINE-REFERENCE.md','contract')
put('HANDOFF.md','''# provider-model1 — substantive product result and next pinned Android15 task

ACCEPT_V1 only. Date2026-10-25. Read every required file and verify SOURCE_IDENTITY per entry
before executing any supplied source. No credentials, APK, database or runtime binary included.
PRODUCT-RESULT.md is evidence, not permission to transplant production code to the installed app.

## Receiving-product result

Android17 now installed1FF91047068AF96339F2E451016C593DE28FDD360D3325B351D0A24B9966B8F9.
ZCode Core0.16.9/runtime5/Node24.18.0/Gateway/journal3/local JSON-RPC2 remain authoritative.
Actual model-issued imported provider, real UI admission, v1/v1/v2 session pinning and artifact /
operation / trace joins passed. Two real cancellation settlement gaps were measured then repaired:
bootstrap abandonment uses the existing exact CarrierAuthorization.finish CAS; actual Service
requests existing session/stop before destroying bridge/Worker. No new schema, permission model,
registry or policy. Final ordinary cancellation row664 CANCELLED / isolated process death141ms;
actual UI Service stop row661 CANCELLED /5ownedPIDs gone781ms / admission unlocked / new v2 report662;
final force-stop exact persisted messages + old-session v1 report663; Activity reconnect same runtime.
Measurements are observations, not universal deadlines. Read all failures/limits in PRODUCT-RESULT.
134 JVM pass;lint0/28;14 Node tests +22 SQLite regressions;40installed immutable payload pins.
Existing Web consumer deliveryKind schema errors remain; not full product UI/Stage2/3 completion.

## Your exact task: Android15 compatibility, without installation or production mutation

1. Verify this archive and every SOURCE_IDENTITY entry mechanically, preserving per-entry JSON.
   Review executable source before running it. Confirm onlyDEVICE_ANDROID15/Android15/MODEL_ANDROID15.
   Read ANDROID15-BASELINE-REFERENCE.md; discover current APK path using pm path. Mechanically
   compare full APK/fourruntimepins/libnode hashes and Node24.18.0 before and after. Do not use
   this reference's historic APK path. Freeze wrapper source and record all argv/exit/stdout/stderr.
2. Create a NEW app-UID private cache fixture under dev.zcode.nodepoc; record actual realpath.
   Do NOT replace installed runtime. Copy exactly these reviewed files into fixture/runtime:
   app/src/main/assets/zcode-runtime/{bootstrap.cjs,gateway.cjs,carrier-authorization.cjs}.
   Copy tools/phase9/provider-abandoned-carrier-test.cjs, provider-declaration-settlement-test.cjs,
   provider-settlement-regression.cjs into the fixture root. Hash every device copy against the
   pinned entry. No installed config/token/journal/credentials are inputs to these tests.
3. Use the already installed APK-owned libnode.so and installed runtime/lib; no download/build/
   install/root/Settings changes. Env OPENSSL_CONF=/dev/null, LD_LIBRARY_PATH=<installed runtime/lib>,
   TMPDIR=<fixture>, TEST_RUNTIME=<fixture/runtime>. Capture Node --version. Execute sequentially:
   a. node --test <fixture>/provider-abandoned-carrier-test.cjs <fixture>/provider-declaration-settlement-test.cjs
      Require exit0, exact TAP tests14/pass14/fail0/cancelled0/skipped0/todo0. Preserve full stdout/
      stderr separately; report any nonempty stderr honestly instead of suppressing it.
   b. node <fixture>/provider-settlement-regression.cjs
      Require exit0, exactly22 individual PASS lines plus literal RESULT22PASS (with spaces as in
      source: RESULT 22 PASS). These are22 logic assertions, not22 model/tool executions.
   The tests instantiate their own Gateway/SQLite in temporary directories and remove only their
   own temporary test roots. Outer fixture and copied source must remain. No Core/model/provider
   process is started. Do not run the Android17 product driver, instrumentation, or APK.
4. Four bounded source answers with actual file:line facts, no architecture exploration:
   Q1 Does abandon settlement reuse exact operation/scope/dualpin/CAS and fail closed on journal
      failure, wrong scope or prior completion? Does nativeDispatcher=false leave the UI writer alone?
   Q2 Are session cancel/change, transport close and timeout wired to that helper, and ordinary
      completed responses protected by writableEnded? Distinguish real tests from source assertions.
   Q3 Does actual Service stop request existing token-gated /rpc session/stop before Worker/bridge
      cleanup? What is the fallback if this request cannot be confirmed? Do NOT assert a universal
      stop deadline, rollback guarantee, or completion after a crashed/unreachable bridge.
   Q4 Do product evidence and limitations remain consistent: old rows655/658 untouched, native
      import fixture versus ZIP picker, scoped per-call responder versus manual UI approval,
      deliveryKind residual, and sequential final proof versus earlier overlapping orchestration?
5. Afterward verify all baseline hashes unchanged; don't clean/update old fixtures. If no installed
   host was stopped, no launcher/recovery is needed. Freeze failures before retrying; never overwrite
   the first-attempt source/output. Long hashes/constants must be parsed or mechanically copied,
   not manually transcribed. Return original build logs only if you built (no build requested).
6. Publish ONE substantive result package through original v1 with raw evidence, wrapper SOURCE
   identity, per-entry verification, source answers and honest NOT_TESTED. Scope is Android15 Node /
   SQLite compatibility and bounded source review only. No model/Core/Service/Android17 claims.
   Then hold the baseline and wait for another pinned substantive task; no acknowledgement-only pack.

## Codex next instructions

Codex retains architecture/mainline/Android17 acceptance ownership. Next diagnose the existing
Web event-subscription deliveryKind mismatch, then continue useful command/Skill/provider tasks.
Do not begin Root/Shizuku or invent a new Gateway/journal/carrier. Publication is not ZCode receipt
or task completion. User only reminds the receiving side to collect this sealed package.
''','documentation')
put('STATUS.md',f'''# Scoped product baseline

PASS_SCOPED_PRODUCT_MODEL_PROVIDER_AND_CANCELLATION. APK {summary['apkSha256']}.
Payload {summary['payloadSha256']}. Runtime5 unchanged version;Gateway/journal3/protocols unchanged.
ZCode Android15 keeps809E54FC frozen. Codex visited onlyDEVICE_ANDROID17. No credentials or binaries delivered.
Stage results dated2026-10-23 and2026-10-25 are distinguished. Detailed limits in PRODUCT-RESULT.md.
''','notice')
source_names=[
 'app/src/main/assets/zcode-runtime/bootstrap.cjs','app/src/main/assets/zcode-runtime/gateway.cjs',
 'app/src/main/assets/zcode-runtime/carrier-authorization.cjs','app/src/main/assets/zcode-runtime/runtime-manifest.json',
 'app/src/main/assets/zcode-runtime/payload-SHA256SUMS.txt','app/src/main/assets/zcode-runtime/contracts/journal.sql',
 'app/src/main/java/dev/alita/androidagent/zcode/runtime/ZCodeHostService.kt',
 'app/src/main/java/dev/alita/androidagent/zcode/runtime/ZCodeGatewayClient.kt',
 'app/src/main/java/dev/alita/androidagent/zcode/runtime/ZCodeCarrierWorker.kt',
 'app/src/androidTest/java/dev/alita/androidagent/ManagedProviderModelFixtureTest.kt',
 *['tools/phase9/'+n for n in ['provider-abandoned-carrier-test.cjs','provider-declaration-settlement-test.cjs',
 'provider-settlement-regression.cjs','provider-model-product-acceptance.py','provider-model-evidence-summary.py',Path(__file__).name]]]
for name in source_names:
    p=ROOT/name;identities[name]=hashlib.sha256(p.read_bytes()).hexdigest().upper();copy(p,name,'test' if name.startswith('tools/') or '/androidTest/' in name else 'source')
put('SOURCE_IDENTITY.json',json.dumps(identities,indent=2)+'\n','contract')
for p in AC.iterdir():
    if p.is_file():copy(p,'results/final/'+p.name,'result')
for p in (AC/'unit-tests').glob('*.xml'):copy(p,'results/unit-tests/'+p.name,'result')
for p in EV.glob('*.log'):copy(p,'results/build-and-regression/'+p.name,'result')
# Retain each executed model proof, both actual production failures, and every failed driver.
for directory in sorted(BASE.iterdir()):
    if not directory.is_dir():continue
    for p in sorted(directory.iterdir()):
        if not p.is_file():continue
        include=(p.name.endswith('-verified.json') or p.name.endswith('-artifact.json') or p.name.endswith('-messages.json')
            or p.name in ['failure.json','result.json','commands.json','driver.py','events.json','persisted-before.json','persisted-after.json','service-stop-process-outcome.json','service-owned-processes-before.json','installed-payload.json']
            or p.suffix=='.xml')
        if include:copy(p,'results/android17/'+directory.name+'/'+p.name,'result')
for p in (EV/'acceptance-20261025').iterdir():
    if p.name.startswith('summary-first'):copy(p,'results/summary-first-failure/'+p.name,'result')
spec=dict(protocolVersion=1,packageId=ID,sender='codex',recipient='zcode',scope='product-model-provider-cancellation-result-and-directed-android15-node-sqlite-compatibility',
 baseline='Android17 installed1FF; Android15 frozen809E54FC unchanged',changeSummary='Actual product model/provider/version/artifact/restart proof and two measured cancellation settlement repairs; next14Node plus22SQLite directed Android15 checks',
 completion='COMPLETE',missingItems=[],requiredPaths=sorted(roles),fileRoles=roles,
 dependencies=[dict(packageId='codex-provider-host-lifecycle1-20261023-r1',archiveSha256='D62235FDA3FB17F9159A97BC9028A1A5DA4E8C687783CB4993A88E3E0E4086C8',requiredPaths=['ANDROID15-BASELINE-REFERENCE.md','SOURCE_IDENTITY.json'])])
(DOC/'exchange-provider-model1-20261025-r1-spec.json').write_text(json.dumps(spec,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(packageId=ID,files=len(roles),sourceEntries=len(identities))))
