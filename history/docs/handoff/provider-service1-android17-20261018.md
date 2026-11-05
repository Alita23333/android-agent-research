# provider-service1 — product-code isolated backend scoped PASS

Disposition: **PASS_SCOPED_PRODUCT_ISOLATED_BACKEND**, not model admission or production install.

Installed product C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D remains unchanged.
Uninstalled product candidate7D7449333FFCE203963ACB98DF999B188B3131582686AE3497B30A84D738930B.
Executed isolationTest APK210D1ED59774BDC0AE657CF7503CE626661EBFDC578F8ECC849D2206A4B9B190.
Only Android17 DEVICE_ANDROID17 was operated. Final Host postflight ready/real/v24.18.0; no restart needed.

## Architecture and production code

The existing Local Tool Protocol1 / JSON-RPC2 transport now has a concrete isolated backend:

JsonRpcStdioProvider.cancellableProcessFactory -> IsolatedNodeRuntime -> IsolatedProviderProcess
-> IsolatedNodeEndpoint -> nonexported isolated IsolatedNodeService -> exact existing Node24.18.0.

There is no model-facing registration or imported-provider admission in this increment. Dispatcher,
Gateway, journal, policy, Core and carrier sources are untouched. Direct test execution is confined
to a separate test application ID and must not be presented as Gateway/model/journal acceptance.

- IsolatedNodeRuntime checks script bytes against the supplied immutable content pin, bounds script
  size/NUL/wall limit, verifies the original runtime SHA manifest, every open native library against
  that manifest and the shim against its generated manifest. Hashing uses duplicated descriptors;
  the same already-open read-only originals are duplicated into the endpoint. No owner-UID fallback.
  A supplied content pin is an integrity check, not an admission or permission grant.
- IsolatedNodeEndpoint owns duplicated library FDs and three pipes. Partial construction closes
  every allocated FD. Binding rejection/exception/null/timeout close the undispatched gate; late
  callbacks cannot send START. Once START was dispatched, termination requests STOP and only
  Binder death completes process exit. Unbind failure still attempts all child-FD cleanup and
  releases the instance lease. Consumer streams remain caller-owned after normal exit.
- Before START, releasing a closed gate means no user code was dispatched; it does not prove an
  idle Android service process has physically died. The launch is aborted and no Process is handed
  to the caller. After START, tests separately verify death acknowledgement before lease reuse.
- IsolatedNodeService requires actual isolated UID + the product AgentApplication graph unset,
  links host Binder death to self-termination, permits one launch and validates payload bounds.
  It has a bounded wall watchdog and kills returned/failed Node instances. No root or permissions.
- New first-party NDK shim loads exact existing library bytes with android_dlopen_ext FD loading,
  then calls the pinned24.18.0 Node Start ABI. No Node/Core binary patch. Script crosses as UTF8
  bytes, including supplementary Unicode, instead of JNI modified UTF8 string conversion.
- Native limits: FD soft/hard512, core0, CPU ceiling derived from wall limit plus1second, fixed
  Node old-space64MiB/semi-space8MiB. Environment cleared, only HOME/OPENSSL_CONF/PATH supplied.
  This does not bound total native/ART RSS or establish complete descendant containment.

One host-owned instance lease is held until close/death (or pre-dispatch gate abort). This excludes
simultaneous instances. Future admission must close/evict an idle provider before switching to
another persistent provider; generic multi-provider switching is not accepted by this test.

## Packaging and build

tools/phase9/prepare-product-isolation.py is a preBuild input/output task. It requires Python and
Android Clang selected through DevTools (ISOLATED_RUNTIME_PYTHON / ANDROID_CLANG). It downloads
nothing. Generated app/build/isolated-runtime contains the separate shim, native-library copies
and isolated-provider-runtime.json. Existing Node is reused from the original native source set.
Versioned .so names receive packaging aliases; libsqlite3.so retains its actual basename.
Original runtime manifest, SHA list, Core, libraries and licensing/source metadata are unchanged.
Generated aliases duplicate already licensed bytes, rather than create a second runtime version.
New shim has nonempty ELF LOAD segments all aligned16KB. Exact original asset/native bytes are
independently compared against frozen C51, not merely assumed from build success.

The isolationTest build type uses applicationId dev.alita.androidagent.isolationtest, with the
same product Application/service/endpoint/runtime/LocalProtocol classes. Only that source set has
the fixture and exported ServiceProbeActivity. Product debug manifest excludes this Activity;
debug APK excludes the test fixture. No public test route is added to the product package.

## Acceptance and exact attempts

96 JVM tests / 0failures / 0errors / 0skips. Ten new endpoint tests cover partial pipe allocation,
bind false/exception/null/death, pre-connect cancellation/late callback suppression, unbind failure,
post-dispatch stop waiting for death, pre-start close and connection deadline. Earlier86 pass.
Full product+isolationTest builds and fresh lint pass0errors/28existingwarnings. SDK/!path analysis
noise and deprecated Parcelable warnings remain in raw logs; no warning-free claim.

Final actual-device run: evidence/provider-service1/1792299540959343800, same product classes in
separate package. Owner UID10417 graph initialized; four actual isolated UIDs99243..99246 graph
unset. No instrumentation shadow substitutes for these identities.

1. Declared discovery starts no process; first execute negotiates the real provider through existing
   JsonRpcStdioProvider. Result has validated RPC/LocalProtocol/processInstance metadata.
2. Physical Node24.18.0/hash/Unicode match; owner-private synthetic read/write ENOENT; sentinel
   remains unchanged; isolated network EACCES with successful owner-loopback positive control.
3. Runtime readback: FDs512/512; core0/0; V8 heap limit92274688bytes (88MiB); env keys exactly
   HOME, OPENSSL_CONF, PATH. V8 heap limit is not total process memory.
4. A second simultaneous instance is rejected busy. Running tool cancellation returns CANCELLED;
   actual death is awaited, then a fresh process/session successfully negotiates and calls again.
5. An idle script is terminated by the700ms wall watchdog; a subsequent process starts successfully.
   Unreported death maps to host status70, not an invented kernel exit status or timeout contract.
6. Natural completion returns host-reported0 and drains the Unicode stdout intact. Wrong script
   content pin is rejected before another process starts. All four instance leases are reusable.

Retained first failures, not first-pass success:

- First combined build failed lint on two API33 InputStream calls with min31. Replaced with a
  bounded compatibility read; final fresh lint passes. Original product-build.log retained.
- Runs1792299203409274200,1792299279992218100,1792299374367559300 failed before protocol reply.
  Real graph isolation already passed. Diagnostic showed dlopen's missing-libsqlite3 message;
  next bounded diagnostic proved all128 FD slots below the chosen128 cap were already occupied.
- Only the descriptor budget/headroom guard and diagnostic counter changed for the A/B repair:
  use512 with fail-closed headroom check. Run1792299429577716000 then passed all four lifecycle
  processes; each showed initial128 FDs. No library byte/permission/SELinux/loader-namespace change.
- Added resource readback assertions to the test fixture, rebuilt, and final run above passed.
  Its APK/raw commands/source identities/native-build/ELF/logs are frozen. All5 runs retained.

FD loading follows the public [NDK dynamic linker API](https://developer.android.com/ndk/reference/group/libdl).
The missing dependency investigation also consulted [AOSP linker source](https://android.googlesource.com/platform/bionic/+/master/linker/linker.cpp).
Those references explain the mechanism; the FD-budget diagnosis is supported by the actual A/B
and resource readback, not inferred solely from upstream source or error wording.

## Next mainline step and residuals

Connect immutable provider version + host-reviewed declarations/admission to this backend through
the existing Dispatcher/Gateway boundary. Keep journal-before-execution, host policy ceiling,
request-bound authorization and host-owned artifacts. Run real model-issued imported tool,
artifact, cancel, update/old pin, process/session restart and refusal tests before accepting a new
production APK. No second registry, policy matrix, journal, carrier or Agent loop.

Host-death linkage exists in source but has not been independently fault-injected. Full native
RSS/descendant and arbitrary script sandbox guarantees, Android15 compatibility and multi-provider
session switching remain unproven. No root/Shizuku/Ubuntu/PTY capability is introduced.
ZCode's existing recording-only supplement357AD4AF remains unchanged; no duplicate test or
architecture assignment sent. Future substantive handoff must pin exact source/tests and next
instructions using existing ACCEPT_V1.

Machine audit: tools/phase9/provider-service-evidence-summary.py.
Frozen acceptance-summary.json/candidate.apk/product-manifest.xml/unit-results/lint/postflight:
docs/handoff/evidence/provider-service1/. Final source snapshots are inside the run/source tree.
