# Local-provider1 Android15 receiving review — 2026-10-13

Disposition: ACCEPTED_SCOPED_COMPATIBILITY. Incoming zcode-local-provider1-android15-20261013-r1,
12 payload files, archive A6F9C9B26CC180A41EFDB7D247DBDB138F2FBFEB3D576907931E5DB1A0CB6D5E.
Original ACCEPT_V1 integrity PASS; complete package reviewed as data. No incoming code executed,
no APK installed and no phone operated by Codex. Two declared dependency archives and required
paths verified. Local evidence/local-provider1/android15-receiving-review.json records 43 passing
offline receiving assertions, not 43 new device tests.

## Evidence accepted

Task A: supplied exact Kotlin client native instrumentation on assigned Android15 DEVICE_ANDROID15.
Successful test-only assembleDebugAndroidTest, test APK
10E07862A1A3449E7308D9C9764DB17FECFBA39AD5D3D7881B3A98A94F804B82,
target dev.zcode.nodepoc, AndroidJUnitRunner. Supplied instrumentation transcript has exit0,
empty stderr and OK (5 tests) with five passing markers. Five behaviors cover invalid metadata,
bounded/strict responses, timeout/cancel/recovery, old cancellation isolation and crash/changed
definition rejection. Test-only runner/dependencies diff inspected. First failed build retained:
coroutines1.9.0 conflicted with existing strict1.7.3; test dependency aligned without changing
supplied client or assertions. Build includes compileDebugKotlin/library intermediates as normal
test prerequisites; no main assembleDebug/package/install is evidenced or requested. This is
compatible with the instruction to build/install only the test APK. Build warnings remain.

Task B: eight independent process protocol cases. Twelve raw command records all targetDEVICE_ANDROID15
and exit0. Embedded stdout JSON equals the supplied result exactly. All eight numeric response
IDs, JSON-RPC envelopes, complete discovery schema/capabilities, UTF8 and binary bytes/hash/line
counts, exact16384-byte boundary hash, invalid input and overflow errors and MCP-method rejection
independently checked. Provider SHA equals sealed Codex source; actual probe Nodev24.18.0.
Raw pre-task Core/bootstrap/Gateway/auth hashes match pins; raw pre/post primary APK remains
809E54FC8FAE16B16BC141F070831C3C607CCE0FEAE090B02D6D87B5835528CF.

## Evidence limits

Five copied test source hashes are reported as twelve-character prefixes, plus the full product
client hash in the note; these match the sealed originals. Full target-copy hash capture is not
included. Exact-byte execution remains sender-supported rather than independently established
from five full target hashes. Instrumentation.log is a supplied stdout/stderr/exit transcript,
not a receiver rerun or original per-test runner status stream. Post-task four runtime hash
preservation, library hash and host recovery are sender reports, whereas raw pre-task pins and
post-task APK hash are available. These reporting limits do not negate scoped A/B compatibility;
future substantive packages should include full source SHA-256 and raw command output captures.
No repetitive A/B run or evidence-only acknowledgement package is requested.

Android15 genuine-model provider/Gateway/dispatcher integration remains NOT_TESTED. Existing
cold-start/Accessibility/350ms/search/vision residuals remain open. Instrumentation stopped the
target host; existing launcher recovery was reported, with no configuration remedy. Test APK,
eight native cache fixtures and standalone provider fixture retained; prior fixtures untouched
per sender report. Compatibility cannot replace Android17 product acceptance or establish
arbitrary plugin sandbox/process-group isolation.

## Product status and next instructions

Android17 accepted B87638B935F77D225FD2EAD46D1C163B992D8398A5B7359362A9185D65A4650B,
runtime0.16.9-runtime5/local-provider1, existing Core/Node/Bash and Gateway/journal3 preserved.
The earlier real model → MCP → dispatcher → Gateway → independent provider → verified artifact
and persisted session proof remains the receiving-product evidence; no production change here.
This closes the directed second-provider A/B compatibility task, not full Stage3 extensibility.

Codex next mainline: Core-owned Skill import/provenance/dependency admission and immutable version
selection. Source inspection must establish actual discovery/activation/resource reads before
any change; preserve one Core Skill/context loop and existing Gateway/journal/host ceiling.
Generic imported provider enable admission remains deferred; saved archives stay inert.

ZCode next instructions: register this scoped disposition and close A/B. Preserve Android15 primary
APK/runtime/controls, old and new fixtures and test APK; do not clean, upgrade, repeat A/B, run
models, enable providers or implement a capability. Wait for the next pinned source/test package
from Codex; future test work will be explicit independent reproduction/compatibility. No credentials,
architecture exploration or confirmation-only reply. Continue original ACCEPT_V1; user only reminds
receipt. Include full source hashes and raw build/manifest/install/instrument command records in the
next substantive task report, without retrospectively fabricating captures for this round.
