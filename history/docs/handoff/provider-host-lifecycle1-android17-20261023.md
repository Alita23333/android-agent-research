# provider-host-lifecycle1 Android17 scoped measurement — 2026-10-23

Production Kotlin/runtime unchanged from admission1 candidate4CE39DB6 (uninstalled).
Installed productionC51 pre/post hash unchanged, no production restart or model request.
Only test Activity/manifest/drivers added; no Gateway/journal/policy/registry schema change.

## Actual Service (separate test UID)

Run1792761833069280600 uses actual product ZCodeHostService, blank test-owned settings and
packaged runtime5. Port8765 preflight refuses an existing listener. No production credentials
copied; no candidate bootstrap override or manual child signal. Two real Service start/stop
cycles: parent/Core PIDs16323/16358 and16446/16476; stop returned true in108ms/115ms, both PIDs
absent and admission unlocked before restart. This proves idle actual Service/Core exit only:
there was no active model turn or active MCP child, so full descendant/cancellation proof remains.

## Actual UI

Run ui-1792762121917293400 creates one new private nonexecuting fixture. UI taps through approve,
retire, reapprove and revoke. Exact selected content/declaration pin checked after approval;
retire removes selection but keeps nonrevoked review; reapprove same pin; revoke removes selection
and marks reviewed version revoked. Other reviews/selections equal this final run's initial state.
No provider execution or model request. Test-only POST_NOTIFICATIONS normal ADB grant retained.

## Core stdin EOF compatibility

Run eof-1792762203661879900 starts immutable actual Core via APK-owned Node24.18.0 in a new
private HOME, creates only synthetic USER history (no assistant/model output), then closes stdin.
Two natural exits code0/signalnull in38ms/58ms. No Gateway/Service/active MCP claim from this test.
New script core-stdin-eof-test.cjs can be independently tested on Android15 without replacement.

## Failure and retention notes

Initial test compile used CoroutineScope instead of Activity context, fixed in test code.
First host wrapper parsed the `cat: no such file` text returned with adb exec-out exit0 as JSON;
wrapper now tolerates non-JSON/partial result reads. No failed Service acceptance is inferred.
UI first attempt did not navigate; second selected an earlier newly-created UI fixture and failed
its exact-id audit. Its test-only selection/record is retained, not silently erased. Final fresh
fixture uses descending unique ID so it appears first, and audit matches exact pin and all others.
No claim of first-try/zero-retry acceptance or cleanup of old fixture state.

A stage/driver name collision with historical provider-service1 was caught: new outputs/run moved
to provider-host-lifecycle1, old driver restored from frozen1792299540959343800 with verified
SHA DFF47F9623D8D8265F244EC03283C80020A80C5211A0DB5072049BDC1A476B1D. Historical immutable
run directories unchanged. New unversioned build-first/build-second/device-first logs were first
written under the reused name; prior existence/content of those names was not snapshotted, so no
complete-preservation claim for any former unversioned logs. New driver has distinct name.

## Next

Codex: active model/MCP descendants, imported-provider cancellation, force-stop/relaunch and
real model/provider/artifact/final answer in product package. Production host readiness not
refreshed; idle test Service proof must not be reported as production installation acceptance.
No fresh JVM suite required: production unchanged;134 previous passing tests remain dated prior
proof. Test APK builds passed, two failed wrapper/UI cases retained as above.
ZCode: exact Node/Core EOF compatibility task in HANDOFF; preserve Android15 baseline.
