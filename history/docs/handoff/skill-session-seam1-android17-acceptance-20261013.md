# Core Skill session seam and control-path acceptance — 2026-10-13

Product disposition: ACCEPTED_SCOPED_CONTROL_GUARD_AND_INERT_STORAGE.
Installed/frozen APK 7BB49EEE3538D728BB2D4ACFA1A09116046092265E0C323FF1E3DCC26594EE3D, runtime0.16.9-runtime5,
productRevision skill-package1-control-guard. Core B1DF2EF3.../Node24.18.0/Bash5.3.20 unchanged;
Gateway/journal schema3 unchanged; Gateway source SHA256 D5C1A772B40A39F8F02D344D191A932AC121AF42ABBA5219362C1B7AAD23C89B.
Previous accepted B87638B9 and uninstalled36ACECBF candidates retained. New host Skill storage/UI
is installed with explicit stored/not-enabled state; GUI import interaction itself NOT_TESTED.
Full Core-managed Skill activation/session pinning remains NOT_IMPLEMENTED/NOT_ACCEPTED.

## Incoming compatibility closed

zcode-skill-package1-android15-20261013-r1, archive
9F8B1B42B1AC6F8167DF34B9968C9BC99BFFEC31BA2E75DAC40DCBF783CF57EB,10files COMPLETE/integrity PASS.
33 offline receiving checks PASS; native3 exact-source storage compatibility accepted. Full copied
source hashes and raw test/pre/post runtime evidence verified. Actual ZCode INTEGRATED receipt for
our source976C512B... also verified. No Codex Android15 operation or incoming-code execution.
See skill-package1-android15-review-20261013.md; no empty acknowledgement-only package sent.

## Actual Core selection seam (existing accepted B87638B9)

A new Android17 nested workspace with its own .git/.zcode/config.json and two private cache Skill
roots was used. Global production config and immutable input files remained byte-identical.
Native Core API catalog/create/import-fixture/close/resume produced9 checks PASS:
workspace v1, old session v1; change configured skills.roots to v2 -> workspace/new session v2
while LIVE old session remains v1. Close/resume old under CURRENT v2 config -> old becomes v2.
Close, restore v1 config, resume -> old becomes v1. This is a measured RESUME GAP, not a promise
that Core persists Skill versions. Core unchanged. No runtime memory patch/port replacement.

This probe imports a clearly labelled SYNTHETIC USER-ONLY history fixture via the existing
importedHistory schema solely to obtain a durable session row. No generated assistant transcript,
model request or Skill activation. Native data/protocol proof cannot substitute for a real model
Skill task. First attempt missed required workspace in session catalog params (-32602); second
used empty non-durable sessions (-32004 on resume). Both failures retained. Synthetic persisted
fixture then passed; final dual-app explicit-argument source re-tested9 PASS on Android17.
No force-stop of these Skill fixture sessions is claimed; close/resume was measured. Full process
restart/actual Skill body and lazy resource reads remain future binding acceptance requirements.

## Guard needed before root projection

Actual old Gateway in isolated desktop full-mode fixtures authorized ordinary workspace_file_create
for .zcode/config.json, zcode.json and .agents/skills/example/SKILL.md, with durable intent only;
no execution leg/device mutation. Core sources load project configs/Skill roots, so such files
must not become ordinary tool-write targets in the managed lifecycle. Original gateway source
retained under evidence/skill-session-seam1/gateway-before-control-guard.cjs. Readiness probe first
queried operation rows wrongly; inline intent is in write_txn. Corrected probe uses actual intent
rows, preserving that distinction rather than claiming an operation before mutation.

Small production repair in EXISTING resolveWorkspaceTarget: normalized path segments named
.zcode, .agents or zcode.json (case-insensitive) return existing path_reserved. Descendant/nested
and absolute variants share the same check. Permission precheck, execution resolution and
rollback retain their existing logic/schema/policy; no competing matrix/journal/confirmation.
This covers resolver-based workspace file and upstream Write/Edit paths, not arbitrary commands,
script sandboxing or every potential future filesystem API. Authoring ordinary draft SKILL.md
outside control roots stays allowed; native Skill reads/host installer/config writes unaffected.

## Guard/product acceptance

28 actual-source desktop/SQLite cases and28 installed-APK Node/SQLite cases on Android17 PASS:
all four file mutations denied before intent/ask in ask/supervised/full; relative/absolute/nested
paths; direct intent/execution defense; nearby ordinary names; normal journalled create/rollback.
48 JVM0fail/errors/skips, build/lint PASS with existing warnings. Existing lifecycle/rollback,
carrier admission15/cancellation, fixed analysis12, provider7, config-disable9/internal-boundary
regressions PASS. Source/APK39 payload entries match; installed38 immutable entries match;
mutable personal provider config excluded per existing contract. No runtime binaries synthesized.

Real model session sess_5c132442-b7c3-46c0-8e8c-0c0c317741d6: exact3 tool calls. Control-file create
refused path_reserved, no execution/carrier/intent for that target. Ordinary21-byte file created,
analysis inventory exact bytes/hash returned, physical readback verified. Two carrier calls and
three Gateway rows (write approval + completed write + READ result). Explicit subsequent rollback
operation644 succeeded and actual file absence confirmed. Model final answer matches completed
negative/positive observations. This is not a model-issued Skill activation.

First real-model test used explicit Core toolAllowlist to narrow tools; calls skipped normal
approval and positive writes failed ws_intent_unclaimed. Model-driver completion alone was NOT
accepted. Host execution remained fail-closed; negative execution resolution also refused. That
trace retained under model-attempt1-allowlist-*; test-only allowlist option removed. Corrected
helper uses explicit toolDenylist to hide unrelated tools while preserving permission broker;
then genuine negative/positive task passed. Do not use toolAllowlist as a harmless visibility-only
setting or manufacture Gateway intents to make such tests pass. Production Core/Gateway not
changed to accommodate this failure. Verification initially tried parsing combined text+structured
output as a single JSON document; parsing both existing sections and checking equality resolved
that driver error without changing results or repeating the model task.

Force-stop/relaunch new task resumed6 messages, runtime ready; older provider task resumed5
messages/three provider parts/two artifact refs, both exact physical report bytes/hashes remain.
Post-restart memory/plugins kill switches false and android-host MCP stdio declaration intact.
Root only existing debug Activity launcher, no system setting/root capability expansion. Full
UI/a11y/search/vision/stream/cancellation matrix not rerun: sources unchanged and this scoped
acceptance does not renew those proofs. Previous known residuals retain their status.

## Next integration requirements owned by Codex

Persist managed Skill content hashes/source/selected version alongside host session identity,
apply verified roots before Core create/resume using supported config/API and serialize lifecycle
transitions through both RPC entry paths. No projection until binding durability/integrity holds.
On timeout/late Core response/config failure, fail closed rather than guessing which snapshot
initialized. Resume must restore recorded versions, not select today's candidate. Check duplicate
names/default/home roots and resource path identity; immutable package paths remain outside model
workspace-write reach. Host metadata persistence is not a new operation journal or Core Skill loop.

Native Skill/Read context observations retain Core's existing semantics; do not relabel them as
Gateway operations. Model toolAllowlist can alter approval semantics, so managed package exposure
must not use it to bypass the broker. Keep root/tool/permission dependency declarations as requests
subject to host ceiling. Verify a real Skill/body/resource task, update during run, restart/resume,
missing dependencies and mutation rejection before enabling imported packages. Generic provider
admission, arbitrary scripts, Root/Shizuku/PTY/Linux/DSHA work remain deferred.
