# provider-binding1 — pinned provider/Dispatcher/host-artifact scoped PASS

Disposition: **PASS_SCOPED_PINNED_PROVIDER_DISPATCH_AND_HOST_ARTIFACT**.
This is not real-model/Gateway acceptance or production installation.

Installed C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D remains unchanged,
Host ready/real/v24.18.0. CandidateE52E0A9120C42AF27E76F74CD53ABA11A1C664D961EC4F3309DA0B33B25A4946
is frozen/uninstalled. Separate isolationTest APK735864E4FC064903208FDFCC8F10E3A49FD94FD459CE4A64B988312707EC719B.

## Implemented boundary

LocalProviderCatalog.readPinnedNodeEntry validates the existing v2 content pin and descriptor,
permits one package-relative .cjs entry with APK_NODE (no flags or shell), bounds/validates UTF8,
rejects links/NUL/oversize and verifies the pin again after reading. It never follows active or
starts a process. The package hash/storage format and Local Tool Protocol remain unchanged.

PinnedIsolatedProvider is a ToolProvider using the existing ToolRegistry. Its host review API takes
the explicit descriptor and host-supplied ToolDefinitions, copies metadata, checks namespace,
capability/schema/side-effect constraints and performs inert integrity checks. Installation,
active selection and provider self-description do not call this API or grant execution.
There is no new user review UI/persisted grant or automatic production registration in this step.

Only the first bounded data profile is supported: single Node entry; SideEffect.NONE;
capabilities exactly data-transform; cancellation support required; canonical base64 input up to
16KiB; JSON report up to32KiB. Host definitions are not loaded from untrusted package claims.
The declaration/profile check is a host ceiling, not a new policy matrix or an assertion that
arbitrary JavaScript has no syscalls. Previously measured isolation limits still apply.

Each execute rechecks exact package bytes, sends them through the verified isolated backend,
compares the actual Local Protocol handshake against the reviewed definitions, and closes the
provider after the call. It waits for actual process death before returning a successful result;
unconfirmed death produces PROVIDER_TERMINATION_UNCONFIRMED. Per-call teardown releases the
single-instance lease before another provider can execute. No ordinary application-UID fallback.

Host overwrites provenance metadata (package version/hash, script SHA256, tool version, pinned
runtime version/backend) and creates a bounded JSON report through the existing ArtifactStore.
Provider-returned URIs are never opened; remote artifact claims do not become ArtifactRefs.
The report proves delivery/provenance, not arbitrary transformation correctness.

ReadOnlyToolDispatcher accepts only fixed tools or concrete host-created BoundTools in the
existing registry. Lookup is rechecked after resolving a tool. AndroidToolDefinition gains an
optional providerContentHash. Worker registration snapshots pass that host value into request
metadata; Dispatcher refuses missing/stale hashes. Existing definitions omit the optional field.
ZCodeToolMapping preserves the pin and structured artifacts. Worker wire-ID duplicate registration
now fails before publication, rather than silently overwriting an associateBy entry.

Gateway ceiling is unchanged: unknown tools remain PRIVILEGED. No new READ rule, permission
bypass, journal schema, carrier protocol, secondary registry or task loop is introduced.

## Verification

106 JVM tests / 0failures / 0errors / 0skips; product/test builds PASS; fresh lint0errors/28existing
warnings. Ten added tests cover inert discovery/mapping, old/new pinned handles, tamper-before-
spawn, capability/schema/command refusal, malformed input/session traversal, handshake mismatch,
host-only artifact/provenance, metadata copying, output limit and missing/stale carrier pin.
These JVM protocol tests inject host Python fixtures; they do not prove Android script execution.

Actual Android17 run1792301127522516900 uses the product classes in the separate test package:

1. A fresh ZIP provider is installed/reviewed/registered without changing the tool loop. Its Node
   script handles the actual JSON-RPC handshake and transforms caller-provided bytes.
2. Dispatcher executes v1. Install v2 changes active; the previously registered Dispatcher tool
   still executes v1. Explicit registry replacement makes the next Dispatcher call execute v2.
   Three results/digests/physical host reports are independently read back by the device driver.
3. An explicitly retained old BoundTool still executes v1. This proves handle pinning, not
   persistent ZCode-session binding. A subsequent intentional old-package tamper is refused.
4. Old carrier snapshot hash after replacement returns PROVIDER_PIN_MISMATCH before execution.
5. Scripts return the actual owner-private canary path as data and as a remote artifact claim.
   Only the host's report becomes an ArtifactRef; canary bytes are absent from the reports.
   Provenance hashes match the old/new immutable packages and physical isolated UIDs/PIDs.
6. Tool results map through AndroidToolResult/ZCodeToolMapping with structured artifacts intact.

Fixtures/intentional old-version tamper retained in the test package. No user files, production
APK, credentials, Android15, root or Shizuku were changed. Initial target1792300776522434400 passed. A final source fix reads definition and hash from the
same registered object to avoid mixed snapshots during replacement. Repeated106 tests and final
target1792301127522516900 pass; both runs and the earlier candidate are retained. This is not a
live concurrency stress test. Initial105 tests passed before the pin-fence test. No hidden failure.
All original service1 runtime assets/native bytes/compiled product manifest remain identical.
The test Activity exists only in isolationTest; it is not a product entry or model tool.

Machine audit: tools/phase9/provider-binding-evidence-summary.py.
Frozen summary/APK/unit/lint/postflight: docs/handoff/evidence/provider-binding1/.
Run/source includes exact executed product/adapter/worker/test/driver source identities.

## Remaining production acceptance and exact next work

Do not describe this as a real model-issued call, Gateway operation record, task/session resume,
or general provider import-enable UI acceptance. Production startup still loads only fixed
providers; review/registration here is deliberately test-only.

The actual bootstrap source currently finalizes an exact native-provider operation result only
for text_digest_inspect (bootstrap.cjs around1219). New providers must receive the same exact
pending operation/authorization binding and fail-closed result commit before model exposure.
Preserve existing Phase4 journal schema/policy/hard-confirm and kill switches; do not downgrade
unknown tools based on their readOnly declaration. Capture the executing provider pin in existing
diagnostic/result evidence without defining another journal.

Persistent session-to-provider bindings remain unimplemented. A retained object and a worker
snapshot fence are not a durable session pin. Reuse current Core session boundaries and host
binding conventions, inspect actual session create/resume code before deciding the minimal
integration. Import/update/restart must not silently move an existing session to active/latest.

After these boundaries and host review/grant persistence are connected, run the real model-issued
tool -> Gateway -> Dispatcher -> independent provider -> physical artifact -> model answer, plus
cancel/update/restart/refusal checks. Only then accept a production APK. Live Core wire-ID
collision registration is also still untested; current guard has source/compile proof.

ZCode's recording-only task357AD4AF remains unchanged. No duplicate Android15 or architecture task
was dispatched. The next substantive ACCEPT_V1 package must include exact sources/tests and next
instructions, as required by the existing exchange agreement.
