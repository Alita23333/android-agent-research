# provider-process1 — scoped Process lifecycle acceptance

Disposition: **PASS_SCOPED_PROCESS_FACADE**, not production provider admission.

Installed product remains C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D.
Read-only final Host check: ready / real / v24.18.0. Only the independent experiment package
dev.alita.providerprobe was updated/stopped, only on Android17 DEVICE_ANDROID17. No Android15 action.

## Implementation and boundary

Added product `execution/IsolatedProviderProcess.java`: a Java Process facade supplied through
the existing JsonRpcStdioProvider.processFactory. Endpoint owns transport and actual death
notification. Discovery still need not launch code; no provider registration/admission is added.

The facade exposes existing stdin/stdout/stderr streams, bounded startup wait, normal/timed
waitFor, isAlive, exitValue, idempotent destroy/destroyForcibly. Cancellation is a request;
only endpoint-confirmed death completes waitFor. Late ready cannot revive a stopped process.
Startup failure/deadline/interruption request termination; there is no owner-UID fallback.
Endpoint cleanup exceptions cannot suppress an already confirmed death. Consumers close their
streams; exit itself permits draining buffered output. Endpoint.start/terminate must be
nonblocking, and the endpoint must remember termination before a late connection.

JsonRpcStdioProvider now explicitly branches on factory presence rather than using an Elvis
fallback. A selected factory returning no process fails instead of executing the ordinary
application-UID command. The existing Local Tool Protocol and Gateway are unchanged.

The experiment compiles an exact copied product facade. Experiment-only BinderNodeEndpoint
passes the same immutable library FDs/stdio pipes to the existing isolated Node service, retains
stop across a late bind, verifies a different UID, and acknowledges death through Binder.
This endpoint is not registered in the product manifest or reachable from a model tool.

## Exact evidence

- Final product candidate (not installed):
  7D1C449F9320EAEF1E83B8FFB41D59801AD66EFE65B0492A209A722C49317B4F.
- Final experiment APK:
  0E2A49A9F90496A5061743E2FAAD58A83E490895FD7EC99119A9D4B9CC6A7668.
- Final Android17 run: evidence/provider-process1/1792298042836113300.
  Fresh run ID, frozen source identities, raw commands, binary, result and isolated log retained.
- Exact10 runtime library hashes match their existing runtime5 source and packaged bytes.
  JSON-RPC2 / Local Tool Protocol1.0 initialize and tools/call succeed; Node24.18.0 and digest match.
- Different isolated UID; synthetic owner-private read/write ENOENT and owner bytes unchanged;
  owner-loopback positive control succeeds, isolated connection denied EACCES. No credentials used.
- destroy followed by destroyForcibly, timed waitFor completes after death, isAlive false and
  exitValue137. **17ms** observed. 137 is host cancellation mapping after Binder death, not a
  kernel waitpid result. This is one observation, not a cancellation service-level guarantee.
- Full80 JVM tests, 0 failures/errors/skips. Ten facade lifecycle tests, plus two added existing
  protocol tests: facade-backed cancellation/fresh-session recovery and selected-backend failure
  without executing the owner-UID fallback marker. Python in these tests runs on the host;
  these tests prove protocol integration, not Android isolation.
- Product and experiment build PASS; fresh lint0errors/28existingwarnings. Existing SDK/path
  analysis diagnostic noise retained. No warning-free claim.
- Offline summary verifies all product assets, native libraries and compiled manifest byte-identical
  to C51. Product changes in this increment are facade + fail-closed factory selection only.
  The earlier declarative discovery candidate remains part of current source.

First experiment compilation failed on Java definite assignment and ambiguous Process imports.
Original probe-build.log retained; fixed probe-build-retry.log passed. Earlier successful target
run1792297957028475200 used the facade before cleanup-exception handling (14ms); its exact
generated source was retained before regeneration. Final target was repeated after that change.
No failed run is being represented as a first-pass success. Driver changes and raw sources
are pinned in final run/source-sha256.json.

Machine audit: tools/phase9/provider-process-evidence-summary.py.
Frozen summary: docs/handoff/evidence/provider-process1/acceptance-summary.json.

## Remaining work and next bounded implementation

1. Move a hardened Binder endpoint/service into the product only behind explicit host admission.
   Crucially, isolated service startup must bypass AgentApplication.onCreate graph initialization:
   it must not open product database/settings or start bundled providers. Preserve current runtime
   SHA validation and exact Node ABI; no runtime/Core patch or app-UID fallback.
2. Define cancellation while factory startup is pending. Current JsonRpcStdioProvider registers
   call cancellation after start(); a startup deadline alone is not immediate user cancellation.
   Do not claim this is solved by the facade's interrupt handling.
3. Add transport cleanup/startup-race and resource limits tests before model exposure. Current
   Binder endpoint is experimental; CPU/memory/descendant containment, concurrent isolated
   instances and all late-bind failure paths have not passed target acceptance.
4. Connect immutable version-bound host metadata/admission into existing Dispatcher/Gateway;
   retain policy ceiling, journal-before-execution and host-owned artifact handling. No third
   policy, registry, journal, carrier or protocol.
5. Only then run the real model-issued imported-provider/artifact/restart/update vertical slice
   and accept a new production version. This increment does not prove that acceptance.

No ZCode architecture assignment or Android15 repeat is needed for this bounded increment.
Its existing recording-only F1-F3 evidence supplement task357AD4AF remains unchanged; a future
substantive package will pin exact test sources and next instructions via existing ACCEPT_V1.
