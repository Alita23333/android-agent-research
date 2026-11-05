# Android15 seam and session-binding results — receiving review

Date: 2026-10-17. Disposition: ACCEPTED_SCOPED_ANDROID15_COMPATIBILITY.

Two new packages were discovered through the original ACCEPT_V1 exchange and independently
verified before extraction/read-only review:

| Package | Files | Archive SHA-256 |
|---|---:|---|
| zcode-skill-session-seam1-android15-20261017-r1 |10|C476DF02CF5D291BA647F667B5380B2C38E6BE550A1E445CCDE6B0F26F6F36E4|
| zcode-skill-bindings1-android15-20261017-r1 |9|BE5BEEA84B9E8F867A1F375DC68CEEB2972FB30575A1736BF5EC19B277F9EBBC|

Both COMPLETE/integrity PASS, no missing paths/items. All HANDOFF/STATUS/residual material, raw
stdout/stderr, commands/exit records and identities were read. No incoming source was executed,
no APK installed, no device command issued by Codex during this receiving review.

## Evidence accepted

Offline reviewer `tools/phase9/review-zcode-bindings1-results.py` passed64 checks across75 captured
ADB records (19seamA +26seamB +30bindings). Every recorded command selectedDEVICE_ANDROID15 and exited0.
The full APK/Core/Node/bootstrap/Gateway/auth hashes are equal before/after in each command set.
The Android15 APK remains809E54FC… and installed GatewayCD9FE220…, not the product candidate.

SeamA: exactly the nine assigned checks are true, raw captured stdout equals probe JSON, stderr
empty. Driver and wrapper full hashes match the assigned source. The result explicitly includes
the old Core resume GAP: live old session staysv1, new usesv2, but close/resume under currentv2
rebuildsv2; restoringv1 config rebuildsv1. This is expected source behavior, NOT durable product
binding acceptance. Synthetic user-only imported history remains clearly labeled.

SeamB: all28 literal PASS rows and final RESULT28PASS are present. Raw stdout equals the separate
regression log, stderr empty. Copied Gateway/workspace-files/test hashes match the exact candidate
source; TEST_RUNTIME and TEST_FIXTURE_PARENT point to the new cache fixture. Source-only SQLite
tests validate control-path denial, ordinary create and rollback. Installed runtime was not replaced.

Bindings: all16 TAP case names/order match the sealed r2 source exactly; tests16/pass16/fail0/
cancelled0/skipped0/todo0. Four copied source hashes match r2 and device-side SHA output. Raw
stdout/stderr for both runs match separate files. Actual Core result is PASS, direct-module-core,
checks6, Nodev24.18.0, retainedHostFixture=null. Only the two assigned tests ran; no optional Host
bootstrap path. The sealed source shows the actual assertions behind the six-check result, not
just a prose declaration. Unit responses are fake by design; direct Core uses a separate temporary
HOME and synthetic USER-only history, with no model/activation task.

The sender reports all tests first-attempt successful; supplied captures contain no failures or
retries. This is an evidence-bounded statement, not proof of unrecorded activity. Host startup is
reported separately as the existing launcher procedure and is outside these75 wrapper captures.

## Small evidence discrepancy

The ZCode INTEGRATED receipt for the r2 assignment says identity.json carries a wrapper hash.
It does not: that file carries copied module/bootstrap/tests hashes plus runtime pins and runs.
SeamA DOES supply wrapperSha256 and it matches. For bindings, full device argv/results and exact
copied source bytes are available, so this omission does not invalidate the assigned compatibility
results. We do not claim independent byte-identity proof of the executed Python wrapper. Future
substantive results should include its hash explicitly and align receipt text to actual fields.
No repeat or empty correction package is requested for this bounded round.

The receiving checker initially selected both the setup-copy command and execution command for
seamA because both mention probe.cjs; its selector was corrected to require the execution's
OPENSSL_CONF environment. The full raw-output assertion then passed unchanged. No incoming source,
expected result or product code was changed.

## Synchronization and next instruction

Actual sender INTEGRATED receipts were checked for our seam1 source package207DBAC7…, r2 binding
sourceFC2A9D69… and supplemental product evidence67B36127…. Their archive identities match.
The supplemental Android17 baseline422CF3E5/scoped host-API/model binding has been registered
by ZCode as data only. Both current Android15 assignments can close in the stated scope.

Codex records scoped INTEGRATED receipts for the two incoming result packages and continues
user-facing ZIP import/enable/update/retirement on Android17. GUI behavior is still unaccepted
and disabled in the current product. ZCode holds primary809E54FC/runtime/config/fixtures and
waits for the next exact source/test package; no repeated tests or architecture investigation.
No acknowledgement-only outgoing package is produced. Original v1 protocol remains in use.

Android15 real-model/GUI/Host-bootstrap/search/VLM/350ms/cold-start residuals remain unchanged;
these results do not expand Android17 acceptance either. Two historical Phase9 incoming packages
still show pending in discovery; neither was a new delivery or included in these task closures.

Machine review: `docs/handoff/evidence/skill-bindings1/android15-receiving-review-20261017.json`.
Original extracted packages: `docs/handoff/incoming-zcode-skill-*-android15-20261017-r1/`.
