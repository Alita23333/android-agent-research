# Core Skill catalog Android15 receiving review — 2026-10-13

Disposition: ACCEPTED_SCOPED_CATALOG_COMPATIBILITY.
Incoming zcode-core-skill1-catalog-android15-20261012-r1, eight payload files, archive SHA-256
008DFB931F3EA1835CDD20095080EE8BBB834E0728DD2D39341E51909F78EAC9. Original ACCEPT_V1 integrity
PASS; all documents/results reviewed, no incoming code executed or phone operated. Three dependency
archives and required files verified. See core-skill1-android15-review-checks.json: 26 offline
receiving checks PASS, including raw command/result correspondence and five independently regenerated
fixture hashes. Full snapshot under docs/handoff/upstream-review/zcode-core-skill1-catalog-android15-20261012-r1.

## Accepted evidence

Assigned deviceDEVICE_ANDROID15, Android15/MODEL_ANDROID15, isolated APK809E54FC..., APK-owned Node24.18.0.
Ten recorded adb commands all exit0 and all targetDEVICE_ANDROID15. Installed APK and four runtime module
hashes in raw command stdout match recorded and supplied baseline. Exact supplied device driver
6F39C515... and Python wrapper350E7DAB... hashes match the sealed Codex package; no adaptation reported.
The final command's raw JSON equals catalog-results.json. No rebuild/install was requested or performed.

Seven catalog conditions reproduced: workspace authority, valid frontmatter discovered, missing
description absent, unknown metadata accepted, Android dependency supplement NOT enforced, input
files unchanged, generated safety config unchanged. Exact three returned names, enabled/workspace
fields, paths under exclusive new verify-ws/catalog-proof-1791815420056 and all five fixture hashes
were checked independently of the driver verdict. The absent-runtime/tool dependency case being
enabled=true is an observed gap, not a passing dependency admission feature.

Sender reports additional post-run device hashes and preservation of both earlier seven-file
fixtures. New five-file hashes are shipped and match; both old sets only have summarized 7/7 and
one explicit space-name hash, so their full independent preservation claim remains sender-supported,
not independently re-derived from a complete raw old-fixture hash set in this package. This does
not block the assigned catalog scope; the official driver does not address those old paths.

The supplied test passed first attempt. Ad-hoc probe failures (MSYS conversion, outer shell
reparsing, whitespace splitting) were retained with corrections; no runtime/library regression
inferred from those failed invocations. Automatic earlier host restart is an environment observation,
not a measured cause; pinned source identity stayed equal. Existing cold-start/a11y/350ms/search/VLM
residuals unchanged. No build means build log NOT_APPLICABLE. Android15 real-provider Skill task
NOT_TESTED and not substituted by catalog. No Gateway operation coverage for native Core context
reads is claimed; this round did not invoke a Skill or model.

## Mainline disposition and next instructions

Both-device native catalog behavior now corroborated. Android17's earlier real Skill task and
force-stop persistence remain separate accepted evidence on unchanged product APK87421D90 / runtime5 /
command-analysis1. Full Stage3 Skill import/dependency/version/provenance and second independent
JSON-RPC provider acceptance remain open.

Codex owns host import/dependency admission, source-backed immutable skill version selection into
Core-owned discovery, and bounded client I/O/deadline/strict metadata repair before a second provider
is exposed. Preserve single ZCode Core/Gateway/journal and existing local JSON-RPC protocol. Do not
promote historical Kotlin Skill/context/Agent loop or add a competing policy/journal.

ZCode: close this catalog task in the stated scope, preserve current Android15 APK/runtime/controls
and all fixtures, do not repeat catalog/model tests or clean/update/implement a capability. Wait for
the next pinned implementation/test package from Codex. No credential transfer, mock model proof,
architecture work or acknowledgement-only package requested. Next substantive test assignment will
be included directly in that package; user only reminds receipt through existing ACCEPT_V1.
