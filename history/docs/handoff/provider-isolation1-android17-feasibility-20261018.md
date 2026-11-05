# Provider isolation1: Android17 feasibility and declarative transport seam

Date2026-10-18. Disposition **PASS_TARGET_ISOLATION_FEASIBILITY_AND_UNIT_TESTED_DECLARATIVE_SEAM**.
This is not production admission or generic provider extensibility acceptance.

## Product state

Installed product remains `C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D`.
Final read-only postflight confirms ready/real/Node v24.18.0. No product installation, force-stop,
runtime/manifest/Gateway/journal/carrier/skill/UI or permission change occurred in this increment.
Android15 was not operated. The experiment installed a DIFFERENT package, dev.alita.providerprobe,
now stopped. No su command, SELinux modification, chmod or install-security bypass was used.

Uninstalled product candidate `372C173D761F6147F1BA2084D42E43BE24597948F705654F9F9F72F1D1FB8758`
contains the opt-in stdio transport changes below. Its runtime payload manifest is byte-identical
to C51DB531; main APK build/unit/lint proof must not be mistaken for native/model acceptance.

## Standalone target measurement

Probe source/project: `experiments/provider-isolation` (not included in root :app settings).
Successful run `1792297091188177800`; probe APK
`BA05BD39BE3C93062796251338C265AD62E895370011FC3ADE7A7D66EC3C6BC3`.
Raw evidence, exact source snapshots, APKs, commands and source/artifact identities are under
`docs/handoff/evidence/provider-isolation1`. See acceptance-summary.json for machine verification.

The experiment uses a non-exported Android isolated service, a first-party 16KB-aligned JNI shim,
read-only Binder descriptors and stdio pipes. All ten Node/runtime library byte hashes match the
existing validated runtime5 payload. Libraries ending in non-.so suffixes are packaged under
APK-compatible native filenames; no ELF code, DT_NEEDED or Core is patched. sqlite3 has no SONAME
and must retain actual filename libsqlite3.so. The shim uses Android's public descriptor loader and
the measured Node24.18.0 Start export; this ABI is version/hash-bound, not a promise across upgrades.

| Observation | Actual result |
|---|---|
| Device |DEVICE_ANDROID17,MODEL_ANDROID17,Android17 |
| Owner / isolated identity |owner UID10370; Node UID99229/PID20079 |
| Runtime |Node v24.18.0 using exact accepted library bytes |
| Protocol |JSON-RPC2.0 initialize (protocol1.0) and tools/call decoded; exactly2 replies |
| Data result |SHA256(isolation-fixture)=ba89d23f4ed4d2c6ba0a04d293954ffc3925fbe79da6f09bdddfda2a606c5f8c, matched by owner |
| Owner private sentinel read/write |both inaccessible, returned ENOENT in isolated view; owner confirms original bytes remain |
| Network |owner connected to its live loopback server; isolated Node connection to same port rejected EACCES |
| Cancel |during a synthetic30s request, Binder death observed15ms after cancel message; one sample, no SLA |
| Product |same C51DB531 hash before/after; final Host ready/real/v24.18.0 |

This fixture reads no real credentials or user workspace. Negative file access is against the
probe owner's actual synthetic private file. This Java protocol client does NOT exercise the
production Kotlin stdio adapter, model carrier, Gateway journal, or provider import management.
No Android15 isolation test, subprocess-descendant cleanup proof or arbitrary hostile-code safety
certification is implied. The platform/service mechanism and public FD API references are linked
in experiments/provider-isolation/README.md.

## Transport candidate implemented separately

Only JsonRpcStdioProvider.kt production source changed in the candidate; existing callers retain
their behavior unless the new optional inputs are supplied. No new registry or protocol.

- `declaredTools` accepts existing project ToolDefinition values and snapshots them. tools() and
  ToolRegistry registration return descriptions without starting a process or calling beforeStart.
- First execution starts the backend and performs normal protocol initialization. All declared
  IDs/version/description/schema/capabilities/effect/cancellation fields must match the real
  initialization response before tools/call; mismatch returns non-retryable
  PROVIDER_DEFINITION_MISMATCH. Definitions are checked again following a crash/restart.
- JSON object key order is canonicalized for matching declarations. Schema arrays remain strict;
  this is not general JSON Schema equivalence inference. Existing raw restart stability checks
  remain in place. Metadata does not create a capability or permission grant.
- `processFactory` can supply a host-owned Process facade over the future Binder/pipe backend.
  beforeStart integrity checks run before either factory or default ProcessBuilder. The default
  fixed providers continue using ProcessBuilder. No imported candidate uses these opt-ins yet.

Full JVM suite **68 tests,0 failures/errors/skips** (previous62 plus6 new boundary tests): discovery/
registration no-spawn proof, six mismatch fields before actual call, schema-key-order matching,
snapshot mutation isolation, pre-call cancellation no-spawn, and restart declaration mismatch.
Main candidate APK build successful; fresh lint report0errors/28warnings, with existing SDK/`!`
analysis warnings retained. Candidate has NOT been installed or exercised with a real model.

## Retained attempts and corrections

1. Initial experiment compile failed on Files.readString/writeString not provided by the Android
   compile API. Replaced with byte operations; original build-first.log retained.
2. Attempts1792296648926573600 and1792296895875000900 were rejected by install security. User
   explicitly permitted retries; later installation succeeded. No root bypass or setting change.
3. Run1792296919840144200 failed mapping app-private libc++ file into executable memory despite
   read-only FD transfer. nativeReturn and isolated log retained. No permission relaxation.
4. Attempt1792296998469862700 collected that older result during start; it is a harness stale-result
   failure, not new APK-native-route evidence. Unique launch/result runId binding was added.
5. Run1792297039839101500 could map APK libraries but Node dependency resolution failed because
   sqlite3 (no SONAME) had an alias basename. Preserve its original basename; ELF bytes unchanged.
6. Run1792297091188177800 passed all fixture checks. All earlier APKs, records and failures retained.

## Architecture decision and next implementation

Use this measured isolated-service route as the preferred bounded Node provider backend, subject
to production integration and acceptance. Do not enable arbitrary owner-UID imports based on
self-declared readOnly/effect metadata. This extends Android execution below the existing tools;
ZCode remains the sole Agent Core, with the same Gateway/journal/dispatcher/protocol boundaries.

Next Codex work: production Process/pipe adapter and strict library/provider version validation;
bounded startup, output, memory, cancellation/death and cleanup; non-executing package metadata;
explicit hash-bound native admission; exact Gateway invocation/result/journal binding and bounded
host artifact conversion; then actual independently imported tool/model/update/restart acceptance.
Root, Shizuku, PTY, Linux and generic privileged scripts remain outside this increment.

ZCode's existing provider-package1 RECORDING-ONLY supplement task remains unchanged. Do not repeat
native4, run these Android17 drivers on Android15, install this experiment there, or start a new
architecture task. No new test assignment is issued merely because this feasibility report exists.
