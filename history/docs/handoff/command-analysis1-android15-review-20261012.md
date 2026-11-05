# command-analysis1 Android15 receiving review — 2026-10-12

Disposition: ACCEPTED_SCOPED_COMPATIBILITY. Incoming zcode-command-analysis1-android15-20261012-r1,
archive SHA-256 88BFCA12586B7B421376D8D4838B166D734A9BF838221EC6BBE12D08C2B33E96.
Fourteen payload files verified by the unchanged project ACCEPT_V1 tool. All four dependency
archive hashes and required paths verified; all delivered documents, source, manifest and results
reviewed as data. No incoming code executed, APK installed, phone operated, or production code changed.
Full snapshot: docs/handoff/upstream-review/zcode-command-analysis1-android15-20261012-r1.
Machine-readable offline evidence checks: command-analysis1-android15-review-checks.json (43 checks PASS).

## Accepted scope

A: isolated Android15 test integration. Delivered NodeService is byte-identical to the supplied
C0CDAA2CC07B73207F016653D5923E0A712EE12DBC94E6840B34D4EDAEB35E38 version; two asset-copy
additions match the pinned baseline. Declared/device-recorded bootstrap, Gateway, analysis adapter
and fixed worker hashes match the sealed task package and current product files. Authentication
module remains 47C56F1E...; Core/Node identity is reported unchanged. Receiver 40-entry manifest
text hash independently recomputes to 5FD3EF7E951F51E431F1325F38A51184F86CAA42E698F685B5DAA5795C45E84E.
Test APK 809E54FC8FAE16B16BC141F070831C3C607CCE0FEAE090B02D6D87B5835528CF is distinct from
Android17 product 87421D90... . Build/install association is sender-reported with wrapper hash
verification described; this review did not independently rebuild or read Android15.

B: raw log reports 14/14 checks, platform android, wrapper exit 0. Covers journal failure/no script,
forged operation, containment, input/output limits, timeout, cancellation and descendant cleanup.
This is accepted independent Android15 test evidence for designated fixed-code analysis, not
proof that arbitrary commands or user scripts are sandboxed.

C: supplied driver source actually spawns android-carrier.cjs and uses initialize/tools/list/tools/call.
Real empty Core session sess_1166045d-2c39-454b-9382-fa545b768c1a; read-only workspace_analyze
visible on MCP surface. Inventory returns exit 0 / seven files; malformed JSON returns isError,
INVALID_JSON and exit 3. Operation 725 is allow/ok, 726 allow/INVALID_JSON; each exact tool,
session and JSON file arguments matches its call. Two carrier-call events recorded. All seven
base64 payload hashes and final filesystem readback match the task INPUT.json; fixture is a NEW
child of the existing active app-private verify-ws workspace. Old cache fixture remains reported
untouched; no containment relaxation. Core-empty-session transport is not a model-issued call.

## Limits and non-blocking follow-ups

Android15 real-provider task is honestly NOT_TESTED. No genuine provider configured there; local
lab mocks were not used. Optional model coverage was conditional in the task book, so this does
not require artificial retries or credentials transfer. Android17's earlier genuine-model task
remains the product proof; it does not imply an Android15 genuine-model test.

The incoming test driver's automatic PASS checks are weaker than the full task: they accept >=2
journal rows, do not assert each argument/result/exit/hash, and do not check all discovery fields.
The receiving review independently checked those fields against the actual captured JSON, so the
present result is accepted. Before future reuse, strengthen the driver assertions rather than
trusting verdict alone. process.exit inside try also bypasses finally cleanup; future driver reuse
must end via exitCode and close/await child/SSE and timers. This is test code, not imported production.
The raw build log and original wrapper probe-identity JSON are not shipped; APK/source association
has the above sender-evidence limit. Next substantive test package should include them when run.
The upstream full asset manifest includes hashes of lab journal/hook state; do not promote its
layout, mutable state, or test fixtures into the product bundle. No database/key bytes were shipped.
First failures (staging syntax, shell quoting, missing reasoning option) and retried outcomes retained.
Known cold-start/Accessibility/350ms/model-search-VLM residuals remain scoped as in the reply.

## Baseline and next step

Product runtime5/productRevision command-analysis1, Gateway/journal v3, exact production APK
87421D90D5925373392CF33A3E9973E005CEDD4BC6494D362E135113261AB03E unchanged.
Accept this fixed-script analysis slice plus existing Android17 multi-step copy task; do not mark
full Stage2/3 command, Skill, independent provider acceptance complete.
Codex owns next ZCode Core Skill discovery/activation boundary and independent JSON-RPC provider
integration, plus Android17 final acceptance. ZCode preserves the tested Android15 baseline and
fixtures and waits for the next concrete source/test package; no autonomous architecture or new
production capability work, and no acknowledgement-only package required.
