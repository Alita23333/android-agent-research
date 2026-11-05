# provider-projection1 — Android17 Core / Gateway / isolated-provider transport

Date: 2026-10-23. Disposition **PASS_SCOPED_CORE_GATEWAY_PROVIDER_TRANSPORT**.

The production Node host now reads the existing Kotlin review file/catalog, verifies exact package
and Android declaration identities, and passes immutable per-session pins through the existing
carrier/Android Dispatcher boundary. No new registry, review schema, journal table, permission
matrix or Route C patch. Imported production startup enrollment and user review UI remain disabled.

## Measured chain

Separate test APK, real runtime5 / Core0.16.9 / APK-owned Node24.18.0, own UID/root/config/port8766.
Actual Kotlin ZIP import + explicit trusted fixture review writes provider-reviews.json. Description
contains Chinese, emoji, slash and </script>, so Android JSONObject.quote/hash compatibility is
proved against real Kotlin output, not solely the JS helper. Real Core session/create pins v1;
publish/review v2, register only v2 in the worker, create another actual Core session. Execute old
session -> v1; Core close/resume old -> v1; new session -> v2. Calls deliberately supply wrong
content/declaration metadata; host session routing replaces it with the reviewed exact pins.

Every call traverses HTTP carrier, existing Gateway prompt/operation, production Kotlin worker,
Android Dispatcher/session resolver, isolated JSON-RPC provider and host-created physical report.
The test explicitly answers the normal Gateway prompt; unknown provider remains PRIVILEGED+ask.
The three operations join uniquely by session/callId to physical reports and both hash fields.
UIDs are isolated app UIDs, distinct from the owner. No root or Android15 operation.

Final Android17 fixture: `1792732851631460000`. Operations4/5/6; physical versions v1/v1/v2.
First complete device fixture1792732635982405900 also passed; final repeat follows manifest
productRevision/payload metadata refresh. Both source snapshots and APKs retained. No device failure
in these two runs. Windows first file-link test failed EPERM; original source/log retained, then
explicit Windows-only skip; actual Android file links still required and passed.

## Verification

- Android Node boundary36: 36pass/0fail/0skip, actual filesystem links and SQLite.
- Windows Node boundary36: 35pass/0fail/1skip (file-link privilege); not claimed zero-skip.
- Existing Gateway settlement regression22: PASS.
- JVM118: 0fail/0error/0skip. Product/test APK builds PASS.
- Lint: 0errors/28existing warnings; known !path analyzer exception present in raw log,
  completed report and BUILD SUCCESSFUL retained. Not a warning-free claim.
- All41 payload SHA rows verified against candidate APK, runtime assets/native bytes match the
  separate tested APK. Core/Gateway/journal.sql/native/production Manifest unchanged vs previous
  uninstalled candidate4B2343D3…; six expected asset modifications plus one new module.

## Frozen identities

- Installed production APK: `C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D` (pre/post equal, not reinstalled).
- Uninstalled candidate: `5A30BEED7F0A35749B3CF7BC4E7AE3C790B67CE951114F67DB0B2F7AB31BDD64`.
- Separate test APK: `464ACE79BB8F91F4FBCA589F7EAAC0B6349F191E5EE172435A3F3ABCDD625342`.
- runtime-manifest.json: `C319EC51E8AEA1426C34D24EF41B9BDE087D5D3D2952F1494EBAE62E9FD4EF02`.
- payload-SHA256SUMS.txt: `0640BA1FB3F540CF1B1C61773A715D84255D6B221B75AC04B99352A28B51A52D`.
- Version remains 0.16.9-runtime5; productRevision=provider-projection1-session-routing-candidate.

## Limits and next work

This is test-originated HTTP transport with actual Core sessions and explicit test answers, **not
a model-issued tool call/final answer or production approval UI**. No production host restart,
force-stop resume, imported-provider in-flight cancellation/revocation, power-loss or final product
installation acceptance. Current production host readiness NOT_VERIFIED; no restart/readiness
request performed. Historical last probe unavailable remains historical, not a fresh observation.

Node adapter is read-only and does not enroll imported packages. Fixed tools remain on their
existing route. Stable canonical ID/profile can route an old declaration; removed/renamed/schema-
incompatible tools fail closed rather than being automatically re-exposed. Retirement/revocation
limits remain the existing resolver boundaries; do not claim cancellation of retained handles.

Codex next: explicit host review/admission UI/startup enrollment using existing stores, followed
by real model/Gateway/provider/artifact/cancellation/restart acceptance. ZCode next: pinned Android15
compatibility36 and four bounded source questions per attached task; no production implementation.

Local evidence: docs/handoff/evidence/provider-projection1/acceptance-summary.json, final fixture
1792732851631460000/result.json, commands-and-exits.json, artifact-0/1/2.json and android-boundary-tests.log.
Exchange remains original ACCEPT_V1; no confirmation-only package.
