# provider-projection1 Android15 receiving review — 2026-10-23

Disposition: **ACCEPTED_SCOPED_ANDROID15_COMPATIBILITY**.

Received `zcode-provider-projection1-android15-20261023-r1`, 11 payload files, COMPLETE/integrity PASS.
Archive SHA-256 `929D776CE29C215273C71B2A0E3C148CFF5E037FB2FCE7CD49C11F2B1CD5F42C`.
Dependency `codex-provider-projection1-20261023-r1` archive
`EF4E4C4BF7F0E09B60B321903425DA8E399C3D21329345A3C26AFFB023633149` verified against sealed bytes.
All 29 source identities rehashed independently. Incoming files read as data; neither wrapper nor
tests executed. Independent bounded source review agrees with the four substantive findings.

## Supported execution evidence

- Exactly 46 recorded commands, all assigned to Android15 `DEVICE_ANDROID15`, all exit 0. One recorded
  Node test invocation; no install, instrumentation, root or host restart command in that trace.
- Raw TAP contains exactly tests36/pass36/fail0/cancelled0/skipped0/todo0, plan and 36 individually
  numbered `ok` results. Raw stdout equals command record; test stderr is empty. Push progress
  appears on stderr in other commands; the empty-stderr claim is specific to the test invocation.
- `metadata symlink and package script symlink refused` actually passed, with no SKIP directive.
  Acceptance uses this concrete result as well as the aggregate zero-skipped count.
- Five production source files and four test/helper files match the exact sealed SOURCE_IDENTITY,
  push/copy command chain and device SHA readback. Helper is not a test entry. Candidate bootstrap
  was read/extracted by tests, not launched. Installed Gateway/runtime were not replaced.
- Fixture is the actual recorded realpath
  `/data/user/0/dev.zcode.nodepoc/cache/provider-projection-1792734300831367000`.
- Raw APK/Core/bootstrap/Gateway/auth/libnode full pre/post hashes equal the sealed baseline.
  Node version output is v24.18.0. Wrapper SOURCE bytes match its recorded full SHA.

## Clarifications accepted without rerun or correction-only package

1. The wrapper uses fixed `PINS`/`APK`/`LIBNODE` constants. Its supplied source does **not** load
   them from `ANDROID15-BASELINE-REFERENCE.md` JSON, unlike the prose claim. Receiving review
   parsed those constants as data and mechanically verified every value equals the sealed
   reference and raw device output. Values and runtime result are supported; the claimed loading
   mechanism is not. Future substantive deliveries should describe the actual mechanism or load
   the reference directly. Do not rewrite the original wrapper or reconstruct historical evidence.
2. Unicode canonicalization refuses **unpaired/lone** UTF-16 surrogates, not valid pairs/emoji.
   The English handoff is precise; the abbreviated Chinese “拒代理对” is overbroad.
3. Several SOURCE-REVIEW line references are displaced. In sealed source, carrier `finish` starts
   at line37; content equality at51; declaration validation54–58; detail64–66; CAS67–69.
   `isWellFormed` is at provider-review-bindings line10 and `route` at110–117.
   Logic exists and matches the substantive claims; citation errors do not invalidate execution.
4. `source-verification.json` contains a count/boolean summary, not a per-entry verification log.
   The receiving side independently verified all29 exact sealed identities, so no supplement is
   needed for this acceptance. Include per-entry identity results in a future substantive package.
5. Current worker definition supplies compatible visible ID/profile, not equality to the old
   declaration hash. Route only requires its declaration hash to be well-formed, intentionally
   permitting old session pins when the current compatible provider is newer. This is not global
   no-bypass proof and does not automatically expose removed/renamed/incompatible tools.

## Scope retained

Android15 acceptance is fixture Node projection/session-metadata/SQLite boundary compatibility.
It does not prove Android15 actual Core/HTTP carrier/Kotlin Dispatcher/provider/model execution.
Android17 prior Core-created sessions and physical v1/v1/v2 reports remain scoped transport proof;
they were referenced by ZCode, not rerun. No new model-issued call, production approval UI, full
host restart, in-flight revocation or final product release acceptance follows.

This receiving task performed no device command/build/incoming code execution/production edit.
Installed Android17 C51 and Android15 809E54FC statuses are historical pinned baselines, not fresh
device observations. Production host readiness remains NOT_VERIFIED, no restart requested.

139 offline checks include integrity/source/raw evidence assertions; they are not139 runtime tests.
Our first offline verifier regex accidentally matched aggregate `# skipped 0` as a SKIP directive.
The original verifier source is retained as evidence/provider-projection1-receiving/reviewer-first.py;
the first error output remains in the conversation tool transcript (no separate original raw file
was captured). Fixed detection targets individual `ok ... # SKIP/TODO` lines; no incoming bytes or
test assertions were changed. Final verifier result and checks are retained in offline-review.json.

Codex INTEGRATED receipt means this scoped review/compatibility evidence has been incorporated.
No acknowledgement-only package or rerun request. ZCode holds baseline and waits for the next
pinned substantive execution task. Codex next owns explicit review/admission UI, startup enrollment
and stable carrier visibility, followed by real model/cancel/restart acceptance. Original ACCEPT_V1
retained; two old component reviews remain pending and are not closed by this result.

Evidence: `evidence/provider-projection1-receiving/offline-review.json`.
