# Skill session bindings1 — candidate and bounded test results

Date: 2026-10-16. Status: IMPLEMENTED_CANDIDATE, not a new accepted product baseline.

The installed Android17 product remains APK
`7BB49EEE3538D728BB2D4ACFA1A09116046092265E0C323FF1E3DCC26594EE3D`,
runtime5 / skill-package1-control-guard. Assigned serial `DEVICE_ANDROID17`, Android17 / MODEL_ANDROID17.
Before/after hashes of APK, Core, Node, bootstrap, Gateway and carrier authorization were checked
in the final physical-device fixture and remain equal. No operation on Android15 was performed.
Original ACCEPT_V1 discovery found no new incoming package, rejected=0; two historical pending
items remain. The previous seam1 Android15 assignment has no newly delivered result.

## Implementation

Core still owns discovery, activation, model context and tools. Its bytes remain B1DF2EF3…;
Node/Bash, Gateway/journal3, policy and carrier protocols remain unchanged.

`CoreSkillPackageStore` adds explicit enable/disable state and an atomically published admission
inventory outside Core roots. Imports start disabled. An update with new bytes disables future
selection until explicitly enabled; identical re-import keeps selection and original provenance.
Retirement disables future selection and retains immutable versions for existing sessions.
Missing dependencies cannot be enabled. Publication includes all retained versions with availability
and source information, without granting declared capabilities or executing scripts.

`skill-session-bindings.cjs` is a host lifecycle coordinator, not another Skill registry or Agent
loop. It uses supported project `skills.roots`, actual Core catalog/create/resume, and the existing
host sessions-index.json. Before create/resume it verifies the selected whole-tree hashes and
available dependencies, serializes the configuration transition, and restores the original config
bytes afterward. The persisted host row carries managedSkills (ID/hash/name/version/source/path),
managedSkillWorkspace and binding version. Resume uses that row, even after update/retirement.
No new operation journal is introduced. Legacy explicit roots remain unchanged when no managed
version is selected; managed selection rejects conflicting project roots/plugin/MCP overrides.

Core catalog paths must match the selected immutable SKILL.md paths exactly; duplicate names or
default-root shadowing refuse a successful binding. Missing index, changed bytes, stale inventory,
failed durable binding and uncertain RPC completion fail closed. A private recovery marker stores
the original config bytes and checksum before overlay; startup repairs an interrupted overlay
before Core launches. It does not represent an Android operation or replace journal rollback.
An unresolved lifecycle timeout or restore/write failure requires restarting the runtime.

Bootstrap forwards host requests through the coordinator with separate internal wire IDs, keeps
server reverse requests/notifications flowing, and bypasses the queue for session/stop. Session
fork and workspace/generateText remain unavailable when managed bindings exist until child binding
has its own proven lifecycle. New native executions, root, Shizuku, PTY and script capabilities
are not introduced.

Production UI enable switches are deliberately still disabled. This prevents treating these
boundary tests as acceptance of the user-facing import/enable/task lifecycle. The APK candidate
contains the coordinator and publisher, but has NOT been installed.

## Measured results

| Verification | Result | Scope |
|---|---|---|
| JVM | 50 tests, 0 failures/errors/skips | Includes 2 new publisher/selection/dependency cases |
| assembleDebug / lintDebug | BUILD SUCCESSFUL | Existing SDK/path-analysis warnings retained; not a device acceptance |
| PC coordinator tests | 16/16 | Fake Core responses explicitly marked, no model proof |
| PC unchanged Core direct protocol | 6 checks PASS | String wire IDs, catalog, create/close/resume, original version |
| PC actual Host HTTP/bootstrap/Core | 6 checks PASS | Full forwarding/index/config path, isolated HOME |
| Android17 coordinator tests | 16/16, zero skips, exit0 | APK-owned Node24.18.0; candidate source in private cache |
| Android17 unchanged Core direct protocol | 6 checks PASS, exit0 | Original v1 on resumed old session, v2 on new session |
| Android17 actual Host HTTP/bootstrap/Core | 6 checks PASS, exit0 | Port18765; separate private HOME/workspace; no active-product changes |
| Existing config / authorization / control path / provider / analysis | 9 / 15 / 28 / 7 / 12 PASS | Actual source regressions; cancellation and internal boundary regressions also PASS |
| Candidate packaged payload | 40/40 SHA-256 matches | Includes required new module, unchanged Core/native payload |

Protocol fixtures import explicitly synthetic USER-only history to obtain a durable Core row.
There are no fabricated assistant messages, model calls, Skill activations or tool results.
The 6-check direct and Host routes overlap in purpose: they are not 12 independent task scenarios.
Host fixtures retain their private files for inspection and stop their own spawned processes;
the direct fixture removes its own temporary HOME. No receiving-product APK is reinstalled.

Candidate APK:
`docs/handoff/evidence/skill-bindings1/skill-session-bindings1-candidate.apk`

SHA-256: `422CF3E5DB29F81A88B306ECE04E62102CE688395A9C0F6A30B3EB212D11674B`.
Runtime remains `0.16.9-runtime5`, productRevision `skill-session-bindings1-candidate`.
This hash is a build artifact identity, not release acceptance.

## Failures and repairs retained

Android17 source-r1: all16 tests succeeded but the wrapper expected TAP while Node chose the
spec reporter. The wrapper now explicitly requests TAP; no assertion was removed.

Android17 source-r2: unit16 passed; Core failed listen(EINVAL) because the deeply nested TMPDIR
made its Unix socket exceed the platform path limit. Using the existing short app cache TMPDIR
fixed the harness. No runtime/SELinux/socket limit was changed.

Android17 source-r3/r4 passed; final source-final reran the current complete driver with expanded
pre/post runtime pins. All raw commands/stdout/stderr and source hashes are retained separately.

PC Host attempt1 had an empty-inventory fixture initialization bug. Attempt2 passed the behavioral
checks but failed cleanup on a Windows directory watcher lock; both are failures, not accepted
green runs. Host fixtures now intentionally retain inspection files; spawned processes are stopped
and HTTP agents closed before final PASS output. PC Host attempt3 and Android17 final exited0.

## Evidence and remaining acceptance

Evidence root: `docs/handoff/evidence/skill-bindings1/`. See candidate-identity.json, JVM/build
logs, regression logs, binding-unit.log, core-protocol.log, bootstrap-core-protocol-r3.log and
android17-source-final/{identity.json,commands-and-exits.json,*stdout,*stderr}. Earlier failures
remain under their original paths. Source identities are included in the outgoing sealed package.

Next Codex work: review the full RPC/session mutation surface, run native publisher integration,
then candidate installation and actual product lifecycle acceptance before enabling UI selection.
Require genuine model-issued Skill activation and resource read, v1/v2 task isolation, actual
force-stop/relaunch/resume of bound sessions, persistence/integrity failures, old provider/session
regressions and reserved control-path protection. Test the actual GUI import/enable path separately.
No full Skill, command Stage2/3 or independent-provider lifecycle completion is claimed here.

ZCode receives only source compatibility tasks on its Android15 baseline: candidate unit16 and
direct unchanged-Core protocol6 in new private cache. The Android17 Host clone path and candidate
APK are not assigned to it. Finish any outstanding seam1 A9/B28 first, reuse completed results,
and return one substantive evidence package with exact source/runtime identities and all failures.

## Outgoing synchronization

Published and independently verified `codex-skill-bindings1-20261016-r2`: 65 files, COMPLETE,
integrity PASS; archive SHA-256
`FC2A9D69165748B45EE42B73E48209B92150E530343DB7807453E368FF1B91E2`.
HANDOFF.md includes the exact next Android15 task and the required subsequent Codex action.
ZCode receipt/execution is pending; no counterpart receipt was fabricated.

r2 explicitly supersedes r1. Initial packaging recorded a null identity for a nonexistent
SkillPackageTypes.kt reference. The actual declarations are in CoreSkillPackageStore.kt and
Skills.kt; r2 includes Skills.kt and removes that invalid identity. Executable module/test bytes
are unchanged. Immutable r1 is retained with its historical hash; r2 tells the receiver not to
execute r1 separately. This was a packaging error, not a product/test behavior failure.
