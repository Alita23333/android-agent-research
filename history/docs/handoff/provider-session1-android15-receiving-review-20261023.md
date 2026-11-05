# Provider session1 Android15 receiving review — 2026-10-23

Disposition: ACCEPTED_SCOPED_COMPATIBILITY_WITH_RECORDING_RESIDUALS.
Test date2026-10-18; received/reviewed2026-10-23 (Asia/Singapore). No claim of fresh device liveness on receipt date.

Incoming zcode-provider-session1-android15-20261018-r1,18 payload files, archiveSHA256 DCCB50B1CD1948D28EB8FFA73153B359B86A86641F4B06A2D50A8041F5A6A595. Existing ACCEPT_V1 discover and integrity checks PASS. Dependency codex-provider-session1-20261018-r1 archiveF8EA40B3F31C525F1E11B2BF74980776644644B218467AA746E7D250F0B1BF5C matches sealed outbound package. All42 SOURCE_IDENTITY entries independently hash-checked. Whole incoming payload read as data; no incoming script execution, APK install, tool replacement or phone operation.

Acceptance: unit15 strict TAP tests15/pass15/fail0/skipped0,15 actual ok lines, exit0, stderr empty; direct actual-Core lifecycle10 JSON PASS/direct-module-core/checks10/v24.18.0, exit0, stderr empty. Final30 successful command rows all targetDEVICE_ANDROID15. Candidate binding D8306872..., bootstrap0D4B1FCC..., unit94C0EB0D..., Core test26EEBDF4... copied-byte readbacks match exact sealed inputs. TEST_RUNTIME points to candidate fixture; TEST_BINDING_MODULE points to candidate binding; TEST_BINDING_RUNTIME points to installed exact B1DF2EF3 Core, bootstrap override unset, TMPDIR short private cache. Pre/post raw APK/Core/bootstrap/Gateway/auth/libnode hash outputs mechanically match baseline JSON and identity. Installed809E54FC... runtime remains unchanged per this dated evidence.

157 offline assertions include package/dependency/source integrity and evidence consistency; this is not157 runtime tests. Output file and command JSON text compared after CR normalization, not described as byte-identical output.

First-failure retention is materially improved: original attempt1 wrapper92A5436E...,22 incremental device command rows, pre-baseline, unit stdout/stderr are included separately. Its unit15 passed; the retained wrapper then evaluates all(unit_summary.values()) including exit=0, so its host-side gate necessarily fails before the Core command. Final wrapper A23548B4... differs after newline normalization only in attempt counter1->2 and replacement of that gate with explicit exit/count checks. No supplied test assertion/source changed.

Recording residuals, retained without demanding a rerun:
- First attempt ran unit15 only. Final attempt ran unit15 and Core10. Prose claiming both supplied tests passed in both attempts is inaccurate; no first-attempt Core execution appears in the22 rows.
- Actual first fixture from command records: cache/provider-session-1792332031342797500. Residuals prose incorrectly names cache/provider-session-1792332030638050400. Final fixture is cache/provider-session-1792332060949733400.
- Original failed-wrapper source and device-stage raw records/output are present. A separate original host-wrapper traceback/exit capture is not included; do not claim complete host failure capture or invent it.
- Release/model not freshly queried by getprop in this round; Android15/model facts rely on accepted device baseline and fixed serial.
- Source review's legacy-empty claim is substantiated by providersForRow's absent-fields path and durable-row resume, not merely selectedProviders' null-adapter branch.

Source boundary verified in sealed inputs: selection is host callback only; old resume uses row snapshot; strict-true verifier required; snapshot fields bounded and hashed; stale version AND declaration mismatch rejected before carrier admission. Production bootstrap still has no providerBindings construction, old-version resolver or declaration-hash publication. Existing Gateway/journal/protocol boundaries unchanged. Unit verifier is an explicit inert-file fixture, actual Core test uses synthetic USER-only history and reconstructed host manager; no actual catalog/provider, model, full-process restart, production admission or old-provider-v1 execution accepted.

INTEGRATED receipt is scoped evidence acceptance only. No acknowledgement-only package is published. ZCode preserves baseline/fixtures and waits for next pinned substantive task; small recording corrections can accompany that next delivery. Codex next work remains actual catalog/review adapter, durable explicit review metadata, declaration-hash publication and exact old-version Dispatcher resolution, then Android17 real model/artifact/update/cancel/restart acceptance. Frozen candidate8D0998... remains uninstalled according to prior product record; no live refresh performed here.

Machine evidence: evidence/provider-session1-receiving/offline-review.json and wrapper-normalized.diff. Two older historical component reviews remain pending and are not closed by this receipt.
