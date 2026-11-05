# Skill UI1 — Android17 product acceptance

Date: 2026-10-17. Disposition: ACCEPTED_SCOPED_SKILL_UI_AND_LIVE_VERSIONING.

Installed/frozen APK:
`D944F72FF15E77AAF3E486990581541EEEFE338C0E888AAE10C6BB91E9CFFCAC`.
Frozen path: `docs/handoff/evidence/skill-ui1/skill-ui1-current.apk`.
Previous accepted422CF3E5 and7BB49EEE remain available for rollback.
Assigned device: Android17 /MODEL_ANDROID17 /DEVICE_ANDROID17. Android15 was connected but never operated.

## Product change

Only two production files changed: MainActivity.kt and MainViewModel.kt. The Skills screen now
uses the existing CoreSkillPackageStore for real ZIP import, explicit enable/disable and retirement.
New-byte updates remain disabled until enabled again; existing sessions retain immutable versions.
Missing dependency/invalid packages cannot be enabled; an already enabled item can still be disabled.
The screen explains the new-session scope and shows version/hash/source and exact missing items.
Accessible descriptions identify each switch and removal button.

Archive reads, store mutations, inventory discovery and hash checks now run on Dispatchers.IO.
A synchronous busy flag prevents overlapping UI operations and disables affected controls; finally
releases it. The existing host store remains the authority for dependency and integrity checks.
Re-import of identical enabled bytes gets accurate feedback rather than incorrectly saying disabled.
No installer/script hook or capability grant is added.

No Core/Node/Bash/bootstrap/binding-module/Gateway/journal/carrier/protocol change. The complete
runtime payload manifest is byte-identical to422CF3E5; all14 r2 pinned source identities still match.
Runtime remains0.16.9-runtime5; its literal productRevision remains skill-session-bindings1-candidate
because this is an APK UI change, not another runtime payload. Legacy diagnostics stay false.

## Successful physical flow

Successful instrumentation run: `1792247177543398800`, literal OK (1 test), exit0, stderr empty,
Time26.187. Test APK SHA256:
`6AD2004AB844F3C479C48B5ABAA668A15722FBB78D9B0D7E3113701494DAD21E`.

The test presses the actual app controls and uses the real system OpenDocument result. On this
phone the OEM picker first opens; the test navigates More -> View more files to Google DocumentsUI,
opens the fixture document root, chooses a ZIP and receives its content URI in the app. No mocked
ActivityResult, direct ViewModel mutation, fake model response or synthetic imported history is used.

A read-only DocumentsProvider exists only in the test APK, guarded for the assigned Android17
model. Its three ZIPs live in the test application's private files. It is protected by
MANAGE_DOCUMENTS and grants the selected read URI through SAF. No shared-storage fixture or
production plugin/provider capability is added. The real model uses the existing configured service.

| Check | Observed result |
|---|---|
| Select v1 ZIP through actual picker | Product source is content://dev.alita.androidagent.test.skillfixtures/document/01-skill-v1.zip; imported disabled |
| Press actual enable switch | UI becomes checked, existing store/inventory enabled |
| Real model task1 | Exactly one Skill and one Read; fresh v1 resource and correct final answer |
| Import v2 while old session is alive | Same ID/new hash; UI becomes unchecked, requires explicit enable |
| Real model task2 on live old session | Exactly one Skill and Read of v1; unchanged-file Read cache is explicitly distinguished |
| Real model task3 on new session | Exactly one Skill and Read; fresh v2 resource and correct final answer |
| Import missing-dependency ZIP | UI shows runtimes:python and permissions:root; switch disabled/unchecked; host disabled |
| Press actual removal buttons | Both fixture cards retire from discovery; old immutable v1/v2 directories remain |
| Explicit force-stop/relaunch after retirement | Old v1 session resumes; subsequent model-issued Skill/Read and final v1 proof pass |
| Offline raw snapshot audit | IDs/hashes/paths/call names/results verified for all three successful UI tasks |
| Packaged / immutable installed payload |40/40 packaged,39/39 immutable installed hashes match |
| Safety configuration | plugins/memory feature/memory extraction=false; Android-host MCP stdio retained; no transaction marker |
| Prior provider history | Explicitly resumed prior session,5 messages and3 completed text_digest parts retained |
| JVM/build/lint |50 tests,0 failures/errors/skips; APK/test build and final lint successful |

Fixture: `ui-proof-1792247038894`.
v1 hash: `ce63a69417e56440873ec049c4caa59fc7a9b06ca4af4e93e45a929e892dbf08`.
v2 hash: `210cdec819163aba257e6b771bc3237f5ac964cfd3ce8c7b69cb2b5496bb7f11`.
Old session: `sess_cc9b05a7-9912-4594-b673-ab2bf72505e1`.
New session: `sess_9c6694cc-5e24-4d1f-b61b-48fa68c143a3`.

Skill/Read are Core context tools with persisted session parts. No Android Gateway operation row
is fabricated for them. UI package management is an explicit user operation on private package
storage, not a new model-visible write tool. Gateway ceiling and journal schema stay unchanged.

## Retained failures and limits of evidence

There were seven unsuccessful instrumentation attempts before the complete passing run. Every
attempt retains its own candidate/test hashes, raw commands, stdout/stderr/result/failure files
under its numeric evidence directory. The main APK remained D944F72F throughout; only test code
was repaired between attempts. These failures are NOT green runs.

| Attempt | Failure and repair |
|---|---|
|1792246349808059000|Old Espresso initialization calls missing InputManager.getInstance on Android17, before test body. Replaced test input/observation with public UiAutomation; no dependency or product patch.|
|1792246450534822800|Instrumentation.startActivitySync launch/idle wait exceeded45s. Test uses explicit shell Activity launch and observed-control waits.|
|1792246557891973300|Driver assumed documentsui; actual first picker was com.android.fileexplorer. Added observed OEM More -> View more files route.|
|1792246693241287400|UI traversal did not complete; aborted at RUNNING. No pass claimed. Later attempts investigated retained picker tasks and provider startup independently.|
|1792246782248891500|Main navigation text not visible while an earlier external picker remained on top. Retry cancels only known picker windows before explicit app launch.|
|1792246901330515300|Fixture root unavailable; logs prove standalone Kotlin test provider lacked Kotlin runtime. Converted test-only provider to Java/platform APIs. Run aborted, not accepted.|
|1792247038830156400|Import,3 model turns, live versioning and dependency checks passed; stale/temporarily disabled control during asynchronous retirement/notice cleanup failed the full test. Driver refreshes controls and waits for enabled action; model assertions unchanged.|

The final passing run includes the same complete flow, including both removals. A stale
skill-ui1-failure.png from earlier device cache was also copied by the original evidence collector
into the passing directory; it is NOT passing evidence and is excluded from outgoing material.
Future collection now skips that stale failure image on a successful run. Only the three named
successful screenshots were inspected for layout; there is no change to model or UI assertions.

After force-stop, the first follow-up model prompt answered from history without issuing the
required tool calls, so the strict resume checker failed. A second prompt explicitly required
actual calls and passed without relaxing the tool/path/content assertions. Its full snapshot also
retains the earlier history-only answer. Repeated Read may use Core's unchanged-file cache, with
earlier actual content, exact version path, physical resource bytes and final answer checked.
The successful UI run has3 model turns; the post-retirement check is additional. The earlier
cleanup-failed run also had3 model turns; do not silently merge these into a first-attempt pass.

The first postflight tried reading a prior provider session immediately after restart before it
was resumed, yielding no messages. Explicit supported resume restored it; final postflight passes.
No session data, runtime or policy repair was needed.

## Evidence and remaining work

Evidence root: docs/handoff/evidence/skill-ui1. Successful numeric directory contains raw1-test
output, identity, result,3 real model snapshots,3 success screenshots and retired-session-resume
snapshots. acceptance-summary.json independently audits the saved real outputs and source hashes;
postflight.json holds40/39 payload/config checks. Original failed directories and build logs remain.

The UI lifecycle above is accepted on Android17. This is not broad Android15 UI acceptance,
arbitrary ZIP-provider/cloud compatibility, generic script/command capability, independent provider
import activation, root/Shizuku/PTY/Linux acceptance, or a fresh full search/vision/gesture matrix.
The prior native API/model-binding acceptance and Android15 source compatibility remain valid.

Next: ZCode performs a bounded offline source/evidence review of this exact GUI integration;
Android15 primary809E54FC remains untouched. Codex addresses concrete findings, then continues
the mainline independent local-tool extensibility work through existing dispatcher/Gateway/local
JSON-RPC boundaries. No competing Core/registry/policy/journal design is authorized.

## Outgoing synchronization

Published/verified `codex-skill-ui1-20261017-r2`, COMPLETE102files/integrity PASS, archive SHA256
`810D16478495E5E0AC114753E138330C09582B5E15B09E20822B05702608DE57`.
Includes current source hashes, full results/failures, actual main/test manifest separation and
the12-item bounded offline source/evidence task. Android15 operations are explicitly not assigned.
ZCode receipt/execution remains pending; no counterpart receipt was fabricated.

r2 supersedes r1 by adding the actual main and packaged production manifests so provider separation
can be directly inspected. Production/test executable source, APK identities and test results did
not change. The immutable r1 remains historical; the receiver is told to reuse inspection, not run
another task. Images/APKs/credentials/runtime binaries are excluded from both exchange packages;
successful image hashes are supplied, and images remain locally available for review.
