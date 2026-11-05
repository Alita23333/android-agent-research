# Managed Skill bindings1 — Android17 scoped product acceptance

Date: 2026-10-17. Disposition: ACCEPTED_SCOPED_HOST_API_AND_MODEL_BINDING.

Installed APK `422CF3E5DB29F81A88B306ECE04E62102CE688395A9C0F6A30B3EB212D11674B`
replaces7BB49EEE on assigned Android17 `DEVICE_ANDROID17` / MODEL_ANDROID17. The frozen7BB49EEE APK remains
available for rollback. Runtime is0.16.9-runtime5; manifest productRevision is still literally
`skill-session-bindings1-candidate`. This scoped acceptance does not rename/rebuild that artifact.
No Android15 operation was performed; onlyDEVICE_ANDROID17 was connected this turn.

## What actually ran

The only new code since the pinned candidate is test-only:
`ManagedSkillBindingFixtureTest.kt`, `managed-skill-product-acceptance.py` and
`managed-skill-postflight.py`. Main APK bytes are identical to the earlier source-tested candidate.
The instrumentation APK was built successfully and installed against the checked target package.
The fixture requires Android17/modelMODEL_ANDROID17 and a numeric bound-proof-* ID; it uses the actual
AgentApplication graph/CoreSkillPackageStore to import ZIP bytes, enable the candidate, verify
the atomically published inventory, and read back the version. It does not call a model or add
an app/runtime test endpoint. Instrumentation stops the app; existing private ZCodeActivity is
relaunched using the already authorized debug root launch. Production root tools stay deferred.

Fixture ID: `bound-proof-1792243836049717400`.

| Evidence | Measured result |
|---|---|
| Native v1 import/enable/publication | Instrumentation OK (1 test), exit0 |
| First real model task | Core Skill then Read, resource body and final answer contain v1 proof |
| Native v2 update/enable/publication | OK (1 test), exit0; two retained immutable versions |
| Old session after update/relaunch | Core Skill body/base directory remain v1; Read uses same bound v1 path |
| New session after update | Core Skill and fresh Read use v2; final answer contains v2 proof |
| Explicit am force-stop/relaunch | Old session resumes and completes another v1 task |
| Durable existing host index | Old row pinsv1 hash, new row pinsv2 hash, both retain source/workspace/version |
| Fixture retirement | OK (1 test), exit0; future selection disabled, both immutable versions retained |
| Real provider/streaming regression | connectivity success, exact marker, streamed=true,30 RPC events |
| Cancellation regression | stopAccepted=true, cancelledEvidence=true,12 RPC events |
| Activity background/reconnect | before/background/after ready, sameRuntime=true, session readable |
| Prior provider session | sess_a5b744f0… resumed,5 persisted messages,3 completed text_digest parts retained |
| Packaged/installed payload |40 packaged SHA checks /39 immutable installed SHA checks pass |
| Disable controls | plugins=false, memory feature/extraction=false, Android host MCP remains stdio |
| Configuration transaction | Recovery marker absent after operations; no interrupted overlay remains |

Old managed session: `sess_b2e2e2e5-5c91-41c9-be8a-6d57c9d30a15`.
New managed session: `sess_b531774c-885c-4c2e-b316-a923e994c2f8`.
v1 hash: `f50e6ab043eb85bad28bb0408fa94afb5dbf5beefb1b0a5f38ea527754284fbc`.
v2 hash: `f199ddabaf81a3436504c60187b3813a3b16cfe8ec940785e914f807cee3bec7`.

The native setup intentionally uses a controlled ZIP fixture, not GUI file selection. Model
prompts do not contain the resource proof; actual tool parts supply it. Skill/Read are existing
Core read-only context operations. Their tool parts persist in the Core session; no fictitious
Android Gateway journal coverage is claimed. No shell/script/provider/write task was introduced.

## First failure, repair and exact cache distinction

Original run1792243836049717400 contains two real model turns. The initial v1 task passed.
The next resumed v1 task also loaded v1 and returned the correct v1 proof, but the acceptance
harness rejected the Read output: Core returned its existing unchanged-file message rather than
repeating the body. Full failure.json/task-1-5.json remain. No production source was changed.

Inspected actual Core source around line2455 defines that exact unchanged-file response. The
driver now accepts it only if the current model really issued Read of the exact pinned path,
the same session has an earlier completed Read containing the expected proof at that path,
the current physical resource bytes match independently, and the new assistant answer contains
the expected version proof. A fresh-content check is still required for the new v2 session.
This proves cache lineage and binding; it does NOT turn cache reuse into a fresh physical read.

Continuation1792243946380683500 reuses the same fixture/old session and produces three further
real model turns (oldv1/newv2/force-stopped oldv1), all PASS. Together there were five actual model
turns; the failed first harness run remains failed. The continuation verification lists3 because
it counts that continuation only. read-proof-* files explicitly distinguish freshContent from
reusedVerifiedHistory and verify physical bytes. No synthetic assistant/tool result was inserted.

The first read-only postflight attempt incorrectly used nested shell `$?` quoting for marker
absence; the outer Android shell expanded it, causing a false assertion. It was replaced with a
direct stat subprocess and explicit ENOENT verification. No runtime repair or config deletion was
needed. Final postflight passes. Existing build/lint warnings remain in the retained build log.

## Evidence

Root: `docs/handoff/evidence/skill-bindings1/`.

- `product/1792243836049717400/`: install/first native fixtures/raw commands/first real task and
  original harness failure; identity includes test APK hash.
- Its `continuation-1792243946380683500/`: raw commands, all three real task snapshots, read-proof
  records, durable session-bindings.json and verification.json.
- `product-postflight-20261017.json`: all40/39 payload/config/retirement/provider-history checks.
- `product-provider-turn-20261017.json`, `product-cancel-20261017.json`,
  `activity-reconnect-20261017.json`, `prior-provider-resume-20261017.json`: existing regression
  driver raw outputs. Activity output retains the benign adb brought-to-front warning before JSON.
- `native-fixture-build-20261017.log`: successful exact instrumentation build.
- Earlier candidate JVM50, source boundary16, directCore6, isolated Host/Core6, regression suites
  and frozen APK remain unchanged and are documented in the October16 report.

## Limits and next work

UI file import/enable switches remain unaccepted and disabled. This is not full Skill manager
completion. GUI integration can now use the validated host API and lifecycle rather than inventing
another Skill registry. Verify it on Android17 with an imported archive and explicit enable,
including missing dependency feedback and update/retirement behavior.

No claim of live in-flight update is made: the native update uses instrumentation, which stops
the app; measured proof is durable old-session recovery after update. Isolated tests already
cover serialized lifecycle transitions, but concurrent UI update requires its own product check.
Full search/vision/tapping/UI inspection, crash/restart fault injection and all arbitrary filesystem
or command paths were not rerun. Old provider tool history was checked; provider execution and
artifact bytes were not rerun in this turn. Gateway/journal/schema/Core bytes remain unchanged.

ZCode continues the existing pinned r2 Android15 unit16/directCore6 assignment. This report is
supplemental evidence; do not interrupt or repeat completed tests or install this APK on Android15.
Codex retains GUI integration, complex diagnosis and final Android17 version acceptance.
