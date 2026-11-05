# local-provider1 Android17 product acceptance — 2026-10-13

ACCEPTED_SCOPED_INDEPENDENT_PROVIDER. Final installed/frozen debug APK
B87638B935F77D225FD2EAD46D1C163B992D8398A5B7359362A9185D65A4650B.
Previous accepted87421D90 remains frozen; first functional candidate3B79A98F and its evidence
retained in candidate-before-autoload-ceiling. Runtime0.16.9-runtime5/productRevision local-provider1,
Core0.16.9 B1DF2EF3..., APK-owned Node24.18.0/Bash5.3.20 unchanged; Gateway/journal schema3.
No competing Agent/Skill/context loop or protocol, no Route C, no new root/Shizuku/shell capability.

## Implementation

Existing JsonRpcStdioProvider now bounds byte lines before UTF8 decoding/allocation, limits frame
queue, applies stdin/response/init deadlines, validates JSON-RPC version/id/result/error, rejects
unknown side-effect values/duplicate names/major incompatibility and serializes calls. Cancellation
is bound to the current call/session; late cancellation cannot terminate a later call. Restart
re-negotiates and refuses changed tool definitions. Actual negotiated minor recorded. Direct child
termination only; no claim of process-group sandboxing for arbitrary plugins. Fixed APK provider
launches no descendants. Provider-owned stderr remains diagnostics, not protocol.

Added independent providers/text-digest/provider.json + provider.cjs: canonical explicit base64,
<=16KiB, SHA256/bytes/UTF8/line count. No input paths, shell/code, network or child execution. Local
JSON-RPC2.0/version1.x is separate from MCP and Core NDJSON. APK-owned Node resolved by catalog;
verified runtime libraries only, new immutable content digest is length-framed (content-v2), existing
versions retained. Installed content verified before load; unknown imported archives are stored
inert in production, no on-import/on-restart code execution. Legacy diagnostics not enabled.

Host loads fixed provider after RuntimeBundle SHA verification, exposes exact text_digest.inspect
under data-transform-only ceiling. Input validated before provider invocation. Existing dispatcher
performs call, verifies returned hash/bytes against explicit input, creates bounded digest.txt via
existing ArtifactStore. Typed artifact refs cross the existing worker/MCP result boundary and
persist with the Core tool part. Provider result is data; artifact storage is host-owned, not a
new local-provider wire format. Worker propagates session ID and observes active Gateway binding
for cancellation. Bootstrap finishes only exact admitted operation ID, emits failure if result
commit/binding fails; existing journal schema unchanged. Gateway adds one explicit READ tool row.
The Core loop is untouched. Full generic provider enable/grant UI is still deferred.

## Measured acceptance

40 JVM tests / 0 failures/errors (10 provider boundary tests); five actual Android17 client tests
on APK-owned Node: unsupported major/effect, oversize/string ID, timeout/cancel/recovery, late old
cancel isolation, crash/re-negotiation/changed definition. Eight actual standalone protocol cases:
init metadata, UTF8, binary, malformed input, forbidden command property, 16KiB boundary, overflow,
MCP method rejection. Tests run as app UID, no root execution.

Seven actual-source/SQLite Gateway result/admission cases pass, including mismatched binding,
closed journal, zero affected row, exact READ admission and no journal/no admission. Existing
carrier admission15, config-disable9, internal-boundary and MCP-cancellation regressions pass.
Build/debug/test APK and lint tasks successful; existing SDK/path warnings retained in build.log.
39 packaged SHA entries verified, 38 installed immutable entries match (personal config excluded).

Actual product restart with a synthetically valid unapproved provider layout: marker absent,
not model-exposed, primary APK matched. JVM also proves inert startup and tampered bundled-version
rejection. No hook/script of that unapproved provider executed. Files retained as test fixtures.

Final real configured model session sess_a5b744f0-762e-443e-9de1-74b83a573ff8:
invalid canonical data rejected by host before local invocation, then independent provider processes
39-byte UTF8 and 5-byte binary input. Three actual MCP/carrier/dispatcher calls, two validated local
JSON-RPC replies with numeric IDs and same independent process-instance trace. Three exact-session
Gateway operations report INVALID_INPUT/ok/ok; two returned artifacts independently read on phone
match exact report content, size and ID hash. No PC substitution for execution. Force-stop/relaunch
resumes same session and preserves three tool parts/two artifact refs and bytes. Existing physical
identity model turn still returns Redmi/MODEL_ANDROID17/arm64-v8a/API37. Full UI/search/vision matrix not
re-run: their source behavior unchanged apart from shared native result/cancellation plumbing.

Root used only by existing debug Activity launcher; no Android15 command issued by Codex. No API
keys, user config, databases, images, APK/Core binaries or private keys exported to ZCode.

## Limits and next steps

This proves a second independent local provider through unchanged Core loop/shared Gateway,
result/cancel/artifact/session mechanism. It does NOT complete generic provider activation,
third-party sandboxing, group cancellation, Skill dependency/version/import management or full
Stage3. Skill native task remains accepted separately; Core ignoring android.yaml dependency
supplements remains an open host admission task. GUI artifact browsing/export remains separate
from verified artifact refs/files; reports are pulled to this evidence directory for inspection.

First partial patch application failed verification (no code applied); corrected exact source
patch. A successful first candidate was deliberately superseded after discovering unrestricted
legacy autoload; all its evidence retained. Final code/phone tests were re-run. No production
acceptance failure hidden. Mainline source/report association in SOURCE_IDENTITY.json and frozen
APK. Protocol/scanner unchanged.

ZCode next assignment: exact client compatibility source in androidTest only plus fixed independent
Node protocol probe. Do not alter its primary809E54FC host/runtime/Gateway or integrate product
adapter architecture; no model credentials/mocks. Independent Android15 results are pending.
