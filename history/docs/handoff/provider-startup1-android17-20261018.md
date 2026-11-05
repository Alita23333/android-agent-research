# provider-startup1 — cancellable startup and isolated Application guard

Disposition: **PASS_SCOPED_CANCELLABLE_STARTUP**, not production imported-provider admission.

Installed C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D preserved.
Uninstalled candidate: 87FD0B1CCC3C884A8C6BB6DE9C9626EE1201AF6A5C3C9DF0555153BA4CB1C802.
Standalone test APK: 64EC05624E7041B5ED50F9C478AFB5E5552D38FC67C5C74BB3E114EA56EEE42A.

## Product implementation

- AgentApplication.onCreate returns immediately after super.onCreate when Process.isIsolated()
  is true. This precedes all registry, database, settings, filesystem and provider graph accesses.
  Public SDK35 API presence checked locally; actual Android17 service reports isIsolated true.
  No service or tool admission was added to the product manifest.
- JsonRpcStdioProvider accepts an opt-in cancellableProcessFactory taking the existing call's
  CancellationSignal. It is mutually exclusive with the legacy factory and requires declared
  tools, so discovery remains non-executing. Existing callers do not change behavior.
- Start checks cancellation before integrity validation, after validation and after factory return.
  A process returned during cancellation is killed/closed before a protocol reader or handshake
  starts. Factory startup cancellation maps to CANCELLED/non-retryable rather than START_FAILED.
  Version verification and no-application-UID-fallback behavior remain intact.
- IsolatedProviderProcess.launch has an overload accepting a BooleanSupplier backed by that same
  signal. It checks before bind, every10ms during bounded startup wait, and after readiness.
  It retains no signal callback after launch. Cancellation throws InterruptedIOException;
  timeout and thread interruption remain distinct paths. Aborted startup closes consumer pipes
  and requests endpoint termination; death remains endpoint-acknowledged, never inferred from
  merely sending terminate. A cooperative, nonblocking host endpoint/factory is required.

## Verification

Full86 JVM tests, 0 failures/errors/skips; product/probe builds PASS; fresh lint0errors/28existing
warnings. Six added tests: pre-cancelled launch releases without bind; cancellation during pending
startup; readiness/cancellation race; isolated Application returns with no attached base Context
and graph unset; original call signal maps pending startup to CANCELLED; cancellation at factory
return kills the process without protocol reads/writes. Prior80 tests remain green.

Application guard proof is source/Robolectric proof. The standalone target service does not run
the product Application; this must not be presented as product isolated-service acceptance.

Only Android17 DEVICE_ANDROID17 was operated. Final two device runs use the same pinned test APK:

| Run | Observation |
| --- | --- |
| 1792298603781943800 | Real isolated service announces UID99234/start timestamp before scheduling Node entry after3000ms. Host cancels while launch waits. Cancellation error validated; Binder death acknowledged22ms after cancel; service age at death21ms, before delayed entry; readyCount0. |
| 1792298608451768900 | Normal isolated Node24.18.0 initialize/tools-call/hash PASS. Private read/write ENOENT, owner sentinel unchanged, isolated network EACCES with owner positive control. Running cancel/death/waitFor PASS, host-mapped status137, observed24ms, stderr empty. |

Elapsed realtime is the same device clock in both processes. Death age is checked against the
fixture's delayed-entry boundary, rather than treating absence of a ready event as sufficient
proof. The delayed fixture is test-only; no production startup delay or protocol changes.
Times are observations, not cancellation SLAs. 137 is host mapping, not a kernel waitpid result.

Earlier pair1792298506636710400/1792298519124769200 both passed before explicit clock evidence
was added. All4 raw attempts/APKs/sources remain. No first failure in this increment; unit-first
passed84 before adding two protocol tests, final passed86. Build/path diagnostic noise retained.
Experiment child-FD cleanup now attempts all descriptors even after one close failure and uses
finally to release them if unbind fails; this is not a claim of comprehensive cleanup coverage.

Audit verifies frozen source/driver hashes, exact10 existing runtime libraries, candidate assets/
native libraries/compiled manifest byte-identical to C51, and installed APK pre/post identity.
Read-only product postflight remains ready/real/v24.18.0. No root/Shizuku or Android15 operation.
Machine evidence: docs/handoff/evidence/provider-startup1/acceptance-summary.json.
Audit driver: tools/phase9/provider-startup-evidence-summary.py.

## Next integration and limits

The pending-start cancellation contract and Application guard are ready for product endpoint
integration. Next move a hardened Binder endpoint/service into the product, retaining runtime
hash checks and exact Node ABI. Before enablement, cover partial pipe allocation, null binding,
late bind, all cleanup races, process-instance exclusion and resource limits. Existing experimental
Binder endpoint has not passed that complete suite. A legacy arbitrary blocking factory is not
made cancellable by this change; only the opt-in host backend receives the signal.

Then connect immutable host declarations/admission through existing Dispatcher/Gateway/journal
and host-owned artifacts. Real model-issued imported-provider/update/restart acceptance remains
pending. Do not expose imported tools or broaden policy based on these scoped process results.
No new Core, registry, policy, carrier, local protocol or journal architecture introduced.

ZCode recording-only supplement task357AD4AF remains unchanged; no Android15 repeat or new
architecture task dispatched. Next substantive exchange must pin exact sources/tests/instructions
using the existing ACCEPT_V1 protocol.
