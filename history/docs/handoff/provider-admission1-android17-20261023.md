# provider-admission1 — scoped receiving-product implementation and acceptance

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
- Android17 separate test package, finalrun `1792760006423232400`: actual production controller
  import/preview inert; approve durable but not registered; lease restore registers selected v1;
  real Core session + Gateway + Worker + Dispatcher + isolated provider produces v1. Active edits
  refused. Confirm worker/Core child/bootstrap stop, release lease/removal, approve v2, start again;
  old Core session resumes v1, new session executes v2. Two worker/Node generations and physical
  reports/journal exact session/call/content/declaration joins retained. Not a model-issued call.
- Actual Compose smoke `ui-1792760188831031400`: Tools/editor/preview/full-hash confirmation/back/cancel;
  review file SHA unchanged. Approval/retire/revoke UI taps NOT_TESTED; their production methods
  and UI wiring are covered separately. Normal ADB POST_NOTIFICATIONS grant applies only to the
  disposable isolationtest package; no root/system install-security/production permission change.
- All41 payload pins verify; runtime/native/main APK Manifest assets byte-identical to prior
  projection1 candidate. Runtime remains0.16.9-runtime5; this increment changes Kotlin/UI only.

## Frozen identities

Installed production C51 baseline `C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D` pre/post equal, not reinstalled.
New uninstalled candidate `4CE39DB616545DA903CC56A102428480FA9BB428122D97D0CAF9E9C9E5594340`.
Separate test APK `78784996E81E8C5E43C0DAA4684B7937C941386FA3DF6823E3FC813247C0F458`.
Previous candidate `5A30BEED7F0A35749B3CF7BC4E7AE3C790B67CE951114F67DB0B2F7AB31BDD64`.

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
