"""Prepare a source/evidence-only ACCEPT_V1 delivery; no device work, publishing or incoming execution."""
from pathlib import Path
import hashlib,json,shutil

ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'docs/handoff';EV=DOC/'evidence/provider-admission1'
s=json.loads((EV/'acceptance-summary.json').read_text())
identifier='codex-provider-admission1-20261023-r1';stage=DOC/'outgoing'/identifier;stage.mkdir(parents=True,exist_ok=False)
roles={}
def put(name,data,role):
    p=stage/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data if isinstance(data,bytes) else data.encode('utf-8'));roles[name]=role
def copy(p,name,role):put(name,p.read_bytes(),role)
report=f'''# provider-admission1 — scoped receiving-product implementation and acceptance

Date 2026-10-23. Disposition PASS_SCOPED_EXPLICIT_ADMISSION_AND_CONTROLLED_CORE_RESTART_TRANSPORT.

## Implementation

New Tools tab separates inert import, host-declared review preview and explicit approval. The host
generates the fixed data-transform/base64 schema; a provider's self-description cannot grant
capabilities. UI shows package/version/entry, full content/declaration hashes, publisher-unverified
source label and the bounded profile. Current UI supports one reviewed pure-data tool per package.
No review-time spawn/handshake/install hook. Existing Gateway remains per-call authority.

ProviderAdmissionController coordinates the existing schema1 review file, immutable catalog and
ToolRegistry; it is not another registry or policy loop. Host holds an in-memory lease from startup
through crash backoff to confirmed Node/worker stop. Review/retire/revoke refuse while held. Exact
selected reviews fully resolve before imported registry visibility; conflicting/faulted restore
fails closed. Startup restores reviewed selections before Node/worker startup, not every import.
Lease cleanup unregisters imported tools only. Damaged selected packages remain visible for revoke.

Carrier retains definition snapshots per normal startup. Stop invalidates generation and tracks
HTTP, Dispatcher cancellation, Accessibility bodies and cleanup. Blocking interrupt/disconnect/
cancel callbacks run off the lifecycle lock and caller. stop=false prevents restart/admission.
Host STOP is asynchronous and stops service only after successful cleanup; onDestroy does not
repeat long blocking cleanup on Android's main thread. No hot tools/list refresh is claimed.

## Measured proof

- JVM134/0fail/0error/0skip:12 admission tests +4 worker lifecycle regressions new; previous118 retained.
- Debug and isolation-test builds PASS; lint0errors/28existing warnings (known !path analyzer noise
  remains in logs; no warning-free claim).
- Android17 separate test package, finalrun `{s['deviceRun']}`: actual production controller
  import/preview inert; approve durable but not registered; lease restore registers selected v1;
  real Core session + Gateway + Worker + Dispatcher + isolated provider produces v1. Active edits
  refused. Confirm worker/Core child/bootstrap stop, release lease/removal, approve v2, start again;
  old Core session resumes v1, new session executes v2. Two worker/Node generations and physical
  reports/journal exact session/call/content/declaration joins retained. Not a model-issued call.
- Actual Compose smoke `{s['uiRun']}`: Tools/editor/preview/full-hash confirmation/back/cancel;
  review file SHA unchanged. Approval/retire/revoke UI taps NOT_TESTED; their production methods
  and UI wiring are covered separately. Normal ADB POST_NOTIFICATIONS grant applies only to the
  disposable isolationtest package; no root/system install-security/production permission change.
- All41 payload pins verify; runtime/native/main APK Manifest assets byte-identical to prior
  projection1 candidate. Runtime remains0.16.9-runtime5; this increment changes Kotlin/UI only.

## Frozen identities

Installed production C51 baseline `{s['installedProductSha256']}` pre/post equal, not reinstalled.
New uninstalled candidate `{s['candidateSha256']}`.
Separate test APK `{s['testApkSha256']}`.
Previous candidate `{s['previousCandidateSha256']}`.

## Failure evidence and precise corrections

Device attempts1792759464379526800 and1792759831813604200 retain APK/source/raw commands and
stale RUNNING result. Owner logcat directly proves uncaught diagnostic-reader InterruptedIOException
during teardown killed both test processes. They are NOT passing or proof of a production deadlock.
Probe now catches expected pipe-close IOException and confirms cleanup before final PASS. Separate
Worker interrupt-blocker source issue was found by review (Android Thread invokes blocker
synchronously) and has its own synthetic blocking-interrupt test; it is not presented as unique
cause of those crashes. Probe UID regex correction also caused one compile failure, retained.
First unit build used unavailable com.sun HTTP test server; replaced with standard ServerSocket.
First lint invocation lacked ANDROID_CLANG; corrected invocation/report retained, no product failure.
UI first2 attempts stopped at ROM notification popup; third used stale field coordinates after
keyboard resize. Final driver reobserves fields and passes. Raw UI XML/commands and first driver
are retained; not all intermediate UI wrapper byte snapshots were captured, so no claim otherwise.

## Limits and next mainline

This test directly starts actual bundle/worker/controller and explicitly signals its owned Core
child before lease release. Production HostService startup/STOP descendant exit remains UNMEASURED;
bootstrap-process death alone does not prove all Core/MCP children exited. No real model/provider
final answer, imported cancellation or force-stop recovery acceptance; no production APK install.
UI smoke is preview/cancel, not actual approval confirmation. Host readiness NOT_VERIFIED; no
production restart or readiness request. Selected-version revocation UI is not a full history UI.

Codex next validates actual Service stop/descendants and UI approval, then real model/provider/
artifact/cancellation/full restart and Android17 final product acceptance. ZCode gets the bounded
source/evidence review below, no production migration or competing design. Original ACCEPT_V1.
'''
(DOC/'provider-admission1-android17-20261023.md').write_text(report,encoding='utf-8')
put('STATUS.md',report,'documentation')
put('HANDOFF.md','''# Codex → ZCode: provider-admission1 bounded offline source/evidence review

Use original ACCEPT_V1. Verify this package and SOURCE_IDENTITY; read files as data. This is a new
substantive implementation handoff, NOT a confirmation package. Task is OFFLINE only: no device,
build/install, script execution or source transplant. Keep Android15 baseline/fixtures unchanged.
No model credentials, APKs or runtime binaries are shipped. Codex owns production integration.

Read STATUS/RESIDUALS, exact sources/tests and raw results. Answer six bounded questions with
file:line facts; report actual defects, not a new architecture:

1. Does import/preview avoid both process spawn and durable review selection? Only explicit UI
   confirmation calls approve; declarations/schema/capabilities are host generated. Check stale
   drafts/bytes, reserved namespaces, wire/exact-ID conflicts, broken selected fallback and UI
   failure display. Do not assume provider self-description is trusted or peer-reviewed source.
2. Is the same controller lock used by approval/retire/revoke and beginHost? Does the lease span
   crash retry? Are all selected records resolved before any imported visibility, with rollback
   on restore failure? Fixed tools must survive cleanup. No new review file/schema/registry.
3. Verify Worker stop invalidates generation, refuses late ready/next/result and tracks cleanup/
   accessibility bodies. Android Thread.interrupt synchronously invokes its I/O blocker; it must
   not run on caller/under lifecycle lock. Four focused JVM results are evidence, not Android15
   device proof. Report precise residuals if cleanup is not guaranteed to terminate.
4. Verify actual Service ordering restore-before-Node/worker, async STOP, stopSelf only on success,
   background onDestroy and lease close guards. Do NOT infer Core/MCP child exit from parent death.
   Probe manually signals/reaps its owned Core; Service descendant measurement remains pending.
   No new journal/policy/hard-confirm design or privileged execution requested.
5. Match final Android17 three artifacts/session/call/journal hashes to v1/v1/v2, two host starts,
   leases and shutdowns. Distinguish real Core/controller/Gateway/isolated execution from
   test-originated HTTP/fixture answers, no model call, no production Service or final APK proof.
6. Verify final JVM134/0/0/0, build/lint and UI preview/cancel file hash. Read failed attempts'
   owner logcat before assigning root cause: uncaught probe diagnostic reader killed the process;
   stale RUNNING is not evidence of a stuck Worker. Source review found independent interrupt
   safety issue. First compile/lint/UI harness failures and intermediate-source retention limits
   must remain explicit; no claim of zero retries or all intermediate UI source snapshots.

Return ONE substantive zcode-provider-admission1-source-review-20261023-r1 (new suffix if needed),
with HANDOFF, SOURCE-REVIEW, per-entry source-verification JSON, concrete findings and residuals.
Include corrected prior recording facts in this substantive response; no separate correction-only
or acknowledgement-only package. Do not rerun closed Android15 Node36/native4 rounds. After review,
hold baseline and wait for the next pinned execution package. No architecture exploration.

Previous result provider-projection1 Android15 accepted scoped compatibility: raw36/36/0/0/0/0,
46 commands,9 copied hashes,29 source identities. Clarification: supplied wrapper used fixed
baseline constants equal sealed reference, not baseline JSON loading; lone-surrogates only; shifted
line citations corrected. Future source verification should list per-entry mechanical comparisons.
Codex continues Service/descendant and real model acceptance work. User only reminds 查收.
''','documentation')
put('RESIDUALS.md','''# Residuals

No real model-issued imported Provider call/final answer or production APK installation.
Actual Service lifecycle/Core+MCP descendant exit NOT_TESTED; controlled probe explicitly kills its
Core child. No imported cancellation or force-stop acceptance. UI actual confirmation/retire/revoke
taps NOT_TESTED (preview/back/cancel passed). Historical production readiness NOT_VERIFIED.
One pure-data tool per package through UI; old pins retained but removed/renamed tools may become
unavailable. Revocation UI targets selected version, not every historical review. No universal
sandbox or power-loss guarantee. Windows unit loopback/fault injection is not Android15 execution.
Failed physical/UI/build attempts preserved. Full intermediate UI driver bytes not all retained;
first and final source plus raw records are available. No test databases/private configs shipped.
''','documentation')
put('SOURCE-LICENSING.md','''# Source provenance and scope

Project-owned Kotlin/UI/controller/tests, continuing validated Workflow Core/Gateway/runtime5
contracts. No new external dependency; JVM HTTP fixture uses standard ServerSocket. Android
Thread interrupt reasoning checked against local SDK35 source, not redistributed. Existing Core/
Node distribution restrictions unchanged. This delivery contains no APK/runtime binaries, keys,
private provider configuration, bridge tokens, database or executor directory. Original Gateway,
journal3 and local JSON-RPC2.0 remain authoritative. Runtime SHA references are not payload delivery.
''','notice')
copy(DOC/'provider-projection1-android15-receiving-review-20261023.md','PREVIOUS-RECEIVING-REVIEW.md','documentation')
names=[
 'app/src/main/java/dev/alita/androidagent/AgentApplication.kt','app/src/main/java/dev/alita/androidagent/MainActivity.kt',
 'app/src/main/java/dev/alita/androidagent/MainViewModel.kt','app/src/main/java/dev/alita/androidagent/ProviderManagementScreen.kt',
 'app/src/main/java/dev/alita/androidagent/core/Tooling.kt','app/src/main/java/dev/alita/androidagent/core/Domain.kt',
 *['app/src/main/java/dev/alita/androidagent/tools/'+n for n in ['ProviderAdmissionController.kt','ProviderReviewStore.kt','LocalProviderCatalog.kt','PinnedIsolatedProvider.kt']],
 *['app/src/main/java/dev/alita/androidagent/zcode/runtime/'+n for n in ['ZCodeHostService.kt','ZCodeCarrierWorker.kt','ZCodeRuntimeBundle.kt']],
 *['app/src/main/java/dev/alita/androidagent/zcode/adapter/'+n for n in ['AndroidToolContracts.kt','ReadOnlyToolDispatcher.kt','ZCodeToolMapping.kt']],
 'app/src/main/AndroidManifest.xml','app/src/isolationTest/AndroidManifest.xml',
 'app/src/isolationTest/java/dev/alita/androidagent/execution/isolation/AdmissionProbeActivity.kt',
 *['app/src/test/java/dev/alita/androidagent/'+n for n in ['ProviderAdmissionControllerTest.kt','ZCodeCarrierWorkerLifecycleTest.kt','ProviderReviewStoreTest.kt']],
 *['tools/phase9/'+n for n in ['provider-admission-device-acceptance.py','provider-admission-ui-smoke.py','provider-admission-evidence-summary.py',Path(__file__).name]],
 *['app/src/main/assets/zcode-runtime/'+n for n in ['provider-review-bindings.cjs','skill-session-bindings.cjs','bootstrap.cjs','carrier-authorization.cjs','gateway.cjs','contracts/journal.sql','runtime-manifest.json','payload-SHA256SUMS.txt']]]
ids={}
for name in names:
    p=ROOT/name;ids[name]=hashlib.sha256(p.read_bytes()).hexdigest().upper()
    copy(p,name,'test' if name.startswith('tools/') or '/test/' in name or '/isolationTest/' in name else 'source')
put('SOURCE_IDENTITY.json',json.dumps(ids,indent=2)+'\n','contract')
for name in ['acceptance-summary.json','build-first.log','build-second.log','build-final.log','build-repaired.log',
 'build-repaired-final.log','build-probe-reader-repair.log','lint.log','lint-final.log','lint-results-debug.txt',
 'device-driver-first.log','device-driver-repaired.log','device-driver-final.log','first-owner-logcat.txt',
 'second-owner-logcat.txt','lifecycle-test-first.kt','probe-first.kt','worker-first.kt',
 'ui-smoke-first.log','ui-smoke-second.log','ui-smoke-final.log','ui-smoke-repaired.log','ui-smoke-first.py']:
    copy(EV/name,'results/'+name,'result')
for run in ['1792759464379526800','1792759831813604200',s['deviceRun']]:
    for name in ['identity.json','source-sha256.json','commands-and-exits.json','result.json']:
        copy(EV/run/name,'results/android17/'+run+'/'+name,'result')
    for name in ['app/src/main/java/dev/alita/androidagent/zcode/runtime/ZCodeCarrierWorker.kt',
                 'app/src/isolationTest/java/dev/alita/androidagent/execution/isolation/AdmissionProbeActivity.kt']:
        copy(EV/run/'source'/name,'results/android17/'+run+'/source/'+name,'result')
for i in range(3):copy(EV/s['deviceRun']/f'artifact-{i}.json',f'results/android17/{s["deviceRun"]}/artifact-{i}.json','result')
for directory in sorted(EV.glob('ui-*')):
    if directory.is_dir():
        for file in directory.iterdir():
            if file.is_file() and file.suffix in ['.json','.xml','.py']:copy(file,'results/'+directory.name+'/'+file.name,'result')
for file in (EV/'unit-tests').glob('*.xml'):copy(file,'results/unit-tests/'+file.name,'result')
spec=dict(protocolVersion=1,packageId=identifier,sender='codex',recipient='zcode',scope='provider-explicit-admission-and-controlled-restart-scoped-implementation-offline-source-review',
    baseline='Android17 installed C51 unchanged, new candidate uninstalled; Android15 frozen 809E54FC',
    changeSummary='Explicit UI/controller approval and startup lease/registry wiring; Worker shutdown fencing;134 JVM and Android17 controlled v1-v1-v2 + UI preview/cancel; next bounded independent source review',
    completion='COMPLETE',missingItems=[],requiredPaths=sorted(roles),fileRoles=roles,
    dependencies=[dict(packageId='codex-provider-projection1-20261023-r1',archiveSha256='EF4E4C4BF7F0E09B60B321903425DA8E399C3D21329345A3C26AFFB023633149',requiredPaths=['SOURCE_IDENTITY.json','BOUNDARY-CONTRACT.md'])])
(DOC/'exchange-provider-admission1-20261023-r1-spec.json').write_text(json.dumps(spec,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(stage=str(stage),files=len(roles),sourceEntries=len(ids),candidate=s['candidateSha256'])))
