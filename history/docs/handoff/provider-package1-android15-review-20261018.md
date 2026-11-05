# Android15 provider-package1 receiving review — 2026-10-18

Disposition: **NATIVE4_COMPATIBILITY_SUPPORTED / NEEDS_REVISION_PROVENANCE_ONLY**.
The four storage tests do not need to be repeated. No product defect is established.

Received `zcode-provider-package1-android15-20261018-r1`, 11 payload files, COMPLETE/integrity PASS.
Actual READY/ZIP SHA-256:
`27571429591754E4623802DEED64445CCDB14429B1FA4F37CABE5713E687EC2B`.
The user's pasted synopsis contains one extra D (65 characters); the validated immutable package
and its actual 64-character digest are authoritative. No archive corruption was detected.

All payloads, package metadata, source review, raw build/manifest/commands/instrumentation and
residuals were read. Codex performed 64 offline source/identity/evidence checks; machine record
`docs/handoff/evidence/provider-package1/android15-receiving-review-20261018.json`. These are
receiving checks, not new device tests. No incoming code, build, APK, phone or model was executed.

## Supported results

- Both sealed dependency archives match. All29 sent source identities match; all five reported
  newly copied executable/test files match the exact supplied bytes. Kept Domain identity matches.
  The separately kept ToolProvider interface is a documented test-only arrangement; its source
  bytes were not supplied, so equivalence beyond the reported hash/declaration is sender-reported.
- Raw command11 invokes exactly LocalProviderPackageDeviceTest onDEVICE_ANDROID15 and the proper test runner.
  It reports four dots, literal `OK (4 tests)`,Time0.312,exit0,empty stderr; one invocation and no
  instrumentation retry in the supplied24-command history. Native4 behavior is supported by this
  outcome and the exact pinned test source, not by an Android15 product integration claim.
- Raw pre/post APK, four runtime files and libnode hashes match known809E54FC baseline. Node version
  raw output is v24.18.0. Only a test APK was installed. Its reported hash/size is sender-attested
  (binary intentionally absent); actual manifest dump targets dev.zcode.nodepoc and AndroidJUnitRunner.
- Command19's ECONNREFUSED is retained as the post-instrumentation host-stopped probe. Command20 uses
  the existing launcher; command21 shows ready/real/verify-ws/v24.18.0. Four private fixture directories
  are retained. This expected stopped-host probe is distinct from the reported baseline-script typo.
- Actual ZCode INTEGRATED receipt matches our10911060… task archive. This is ZCode's receipt on our
  outgoing task; it does not replace Codex's disposition on this incoming result package.

## Recording findings requiring a supplement

### F1 — Executed script identity is not established by output-file hashes

`runtime-identity.json.executedRecorderScripts["manifest-raw.txt"]` is
`49A127B50F608ABB55C6519845D812DD16B9AE71276BFC4EF9040A04C7560E34` — exactly the hash of
the shipped aapt manifest OUTPUT. That file is a manifest dump, not executable recorder source.
Other labels name .txt records, with no actual recorder source bytes or unambiguous path/type map.
The prose says three scripts while the object has four entries. Therefore the claim that actual
executed wrapper source hashes were supplied cannot be accepted from this evidence.

Separate artifact/output identity from executed source identity. Supply original recorder/driver
bytes and their source hashes when retained; distinguish the original failed baseline version from
the corrected version. If source is unavailable, mark NOT_RETAINED/NOT_INDEPENDENTLY_VERIFIABLE;
do not fabricate a reconstructed original, re-label output hashes as source, or rerun tests.

### F2 — One old source hash contradicts another result document

For the previous LocalToolProtocol.kt copy:

- copy-log.json: `780914405E47088336F4C5BEF432BE1D2D282E5392D726829366BDB4DAF74AC8`.
- test-build-identity.json: `780914405E4775561D8BE63390440FF41C398A5CF65243E2987F45C1B63DB17E`.

Both describe the same replaced file but differ after the shared prefix. The NEW source hash
`FCAF7C30…` does match our exact source, so this does not invalidate the tested new implementation.
Correct the provenance using retained original bytes/evidence; if unavailable, withdraw the old
byte-identity claim explicitly. Do not hand-copy another long hash.

### F3 — First baseline failure is described, not supplied as original raw evidence

The claimed transposed constant is described in HANDOFF/STATUS/residuals. The supplied command
history contains the corrected successful baseline, but no first failed recorder source/output.
Its only nonzero command is the expected host-stopped probe above. Provide retained first-failure
source/output, or state that it was not retained. A new simulation is not original evidence.
The actual successful device hashes are correct; no device fault is inferred from this gap.

## Action and preserved state

Codex writes NEEDS_REVISION limited to these recording points. A substantive v1 correction task
requests original evidence/correct labels only, no test rerun/build/install/phone operation or
architecture work. Original incoming package remains immutable. Native4 PASS and supported pins
are retained rather than being erased by the documentation findings.

Product stays last measured accepted C51DB531… /runtime5/Gateway+journal3. Android15 stays809E54FC…
as reported by its own assigned tester; Codex has not operated it. Generic imported-provider
admission remains unresolved and Codex-owned. No root/Shizuku/script capability or second policy,
journal/registry/carrier is introduced. Mainline admission work need not wait for this recording
supplement; final closure of this result package must preserve its actual provenance limits.
