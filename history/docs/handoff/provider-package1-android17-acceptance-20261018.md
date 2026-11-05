# Provider package storage1 — Android17 scoped acceptance

Date: 2026-10-18. Disposition: **ACCEPTED_SCOPED_PROVIDER_PACKAGE_STORAGE**.

Installed/frozen APK `C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D`.
Frozen `docs/handoff/evidence/provider-package1/candidate.apk`. Previous D944F72F Skill UI,
422CF3E5 bindings and 7BB49EEE guard artifacts remain retained. Assigned device DEVICE_ANDROID17 /
MODEL_ANDROID17 / Android17 only. Android15 was inventoried as connected but was not operated.

## Changes and boundaries

Exactly two production files changed: LocalProviderCatalog.kt and JsonRpcStdioProvider.kt.
Existing provider package layout/hash v2, Local Tool Protocol1.x/JSON-RPC2, ZCode Core, Gateway,
journal3, carrier, dispatcher whitelist, runtime manifest and complete runtime payload unchanged.
Literal runtime productRevision remains `skill-session-bindings1-candidate`.

Import checks now cover malformed manifests/UTF8, path traversal and conflicts including parent
case, duplicates, discarded siblings, entry/byte/metadata/depth limits and reserved built-in IDs.
Version copy/verification precedes atomic publish, and synced atomic pointer replacement precedes
selection. No partial pointer or replaced old version on tested commit failure. Links/special files
are rejected. Discovery and load recheck exact stored bytes/descriptor; child startup and crash
recovery recheck the original immutable pin. Recovery verification failures become explicit,
non-retryable PROVIDER_INTEGRITY_FAILED. Hash framing remains compatible with existing bundles.

Import, listing and factory creation do not execute candidate code. Existing production imports
remain inert: no new model tool, admission grant or alternate tool registry was introduced.

## Measured results

| Check | Exact evidence and result |
|---|---|
| Full JVM suite |62 tests,0 failures/errors/skips; includes11 new package cases and1 new crash-recovery integrity case |
| Build |Debug main + test APK build successful; raw build-unit-lint.log |
| Fresh lint |Explicit --rerun-tasks completed; freshly generated report0 errors/28 warnings, existing SDK/`!` path-analysis warnings retained |
| Native package storage |LocalProviderPackageDeviceTest literal OK (4 tests),0.112s,exit0,stderr empty; physical symlink and atomic failure behavior included |
| Existing native stdio |LocalProviderDeviceTest literal OK (5 tests),107.996s,exit0,stderr empty; no first-pass speed or whole-suite low-latency guarantee inferred |
| Real model/digest |sess_00f1e7a4-ab61-4953-8309-e22b2fb94a9a: exactly3 model-issued MCP calls, invalid base64 refused at host then2 valid independent process calls; journal outcomes INVALID_INPUT/ok/ok; exact hashes/bytes and2 physical host artifacts verified |
| Real model/identity after restart |sess_1a27491e-04f1-4273-8077-cbd567f96c75: completed device_info_identity, actualMODEL_ANDROID17/arm64-v8a/API37, validated JSON-RPC local trace and final marker |
| Force-stop/relaunch |New runtime, resumed digest session with6 persisted messages and5 finished assistant messages |
| Prior provider session |Existing sess_a5b744f0… resumed:5 messages,3 completed digest tool parts retained |
| Payload/config/Skill retention |40 packaged/39 immutable installed hashes match; plugins/memory disabled, Android MCP stdio retained; retired ui-proof-1792247038894 keeps2 versions; no unfinished config transaction |

Primary evidence directory `docs/handoff/evidence/provider-package1`. Wrapper and native test APK
identities are in build-identity.json. Instrumentation fixtures remain in private app cache.

## First failure, diagnostics and limitations

The first JVM attempt ran22 tests with1 failure: Windows refused physical symlink creation due to
host privilege (FileSystemException). Raw first log and XML retained. The physical symlink case
was moved to the native Android test, which passed without skips; no ACL/security setting was
changed and the production check was not weakened. The final JVM suite has zero skips.

The native stdio run took107.996s. While awaiting it Codex inspected the assigned app's runner log
and sent SIGQUIT to its test process15686 for diagnostic purposes. The run completed with all5
tests passing; do not infer the reason for its long wall time or claim a new end-to-end cancellation
latency bound. Native source keeps the existing timeout/cancellation assertions. The added JVM
recovery integrity case proves callback denial/error mapping, not Android scheduling guarantees.

The combined build reused an older lint report, so fresh lint was requested separately. See the
final lint log/report and acceptance-summary for the actual disposition; existing SDK/`!` path
analysis warnings are retained rather than represented as warning-free validation.

No repeat of the full Skill GUI, search, vision or UI-action matrix. No imported provider process
admission, generic artifact-path acceptance, arbitrary command/script/root/Shizuku capability,
new policy/journal or model loop acceptance. Source hash verification is not an execution sandbox.
Remaining work: docs/project/local-provider-admission-gap-20261018.md.
