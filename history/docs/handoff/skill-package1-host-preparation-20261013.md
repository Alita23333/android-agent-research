# Skill-package1 host lifecycle preparation — 2026-10-13

Status: HOST_STORAGE_SCOPED_PASS. This is an implemented, tested host package store, not full
Core Skill integration, model activation, session version pinning or Stage3 acceptance.
Android17 installed primary remains B87638B935F77D225FD2EAD46D1C163B992D8398A5B7359362A9185D65A4650B.
Built candidate36ACECBF4E476DCC9E91E93FE4DFCB07A77F45526C3643E5D189F7C64D7E9C9F is frozen but
NOT installed/accepted as the new product baseline. Runtime5/local-provider1, Core/Node/Bash,
Gateway/journal3, runtime payload and carrier remain unchanged. Main app UI changes are built,
not device UI acceptance. Root used only the existing authorized debug Activity launcher to
restore the primary runtime after instrumentation; status ready/real/Node24.18.0/default measured.

## Implemented boundary

CoreSkillPackageStore stores imported ZIP data under files/core-skill-packages, outside native
Core default roots and outside the legacy files/skills. It is host package management, not a
second Skill registry/context loop. No new model tool, provider, Core patch or policy matrix.
Names/description and ordinary/block scalar frontmatter validated; unknown metadata preserved in
original SKILL.md. Strict UTF8, paths/duplicates/case collisions, single skill/no outside siblings,
500-entry/20MiB expansion and100KB instruction limits. No hooks executed, software installed,
privilege granted or Core root projection performed. Resource links planted later are rejected.

Each version uses a length-framed whole-tree SHA256 and verified copy, keeping prior directories.
Source recorded per hash; identical reimport preserves original source. Candidate index uses
synced temporary data and same-directory ATOMIC_MOVE/REPLACE_EXISTING; unsupported replacement
fails without deleting the previous index. Retire hides future selection and retains pinned bytes.
Pins here are host storage receipts only, not a promise that a running ZCode session is pinned.
Resource reads recheck whole version integrity/containment/size. Metadata tampering fails closed.

android.yaml supports a deliberately bounded subset: runtimes/tools/platforms/permissions with
scalar, inline list or indented list values. Unknown fields/duplicate/malformed supplements leave
package stored but unavailable, with explicit reason; original bytes retained. This is not a
complete YAML parser. Missing declarations mean requirements unspecified, not proven executable.
Inventory is host supplied; production currently has no validated runtime/tool/permission inventory
so runtime/tool/permission requirements conservatively stay missing. Root declarations confer no
permission, even on rooted phones. No installer or generic tool capability admission is added.

Production import/list/remove UI now uses this package store; enabled switch disabled and notice
says stored/not enabled. Legacy diagnostic path remains under existing false flag. Existing Core
fixture discovery remains unchanged. UI deletion means retire, not byte cleanup. Physical purge
and provenance trust/signing/revocation remain deferred. No automatic legacy skill migration.

## Verification and retained failures

48 JVM tests0fail/errors/skips, including8 new package tests; assembleDebug, Android test build
and lint pass (existing warnings remain). Android17 installs ONLY test APK
CB0FF391B1F57E3760A186C65886E8DCB19ADD8F2B8B830365DED34BE1DD239A,
manifest target dev.alita.androidagent/AndroidJUnitRunner verified before install. Native3 PASS:
update/reload/retire preserves old bytes/source; missing deps/inert script/traversal rejected;
real symlink and version mutation cannot be read. All test fixtures app-private cache, retained.
Primary APK and Core/bootstrap/Gateway/auth hashes verified before/after, no production install.
Evidence and raw command output: docs/handoff/evidence/skill-package1.

First JVM run: two expected rejection exception types not captured, Windows symlink creation
unavailable. Assertions now require an Exception rejection rather than just unchecked exceptions;
AssertionError remains uncaught so an accepted invalid package fails. Symlink proof moved to real
Android native test, no silent skip. Next run exposed missing source in updated index on the host;
index replacement changed from AtomicFile to explicit synchronized atomic NIO replace, then update,
reload and provenance tests pass on host and phone. No device-cause claim for the host failure.
First native run: Android SafeZipPathValidator rejected traversal with ZipException before our
validator; native helper likewise captures Exception while assertion failures still propagate.
First failures and source changes retained, final native3 passed. Tests remain strict; no fallback.

## Actual Core seam and next mainline

Exact Core B1DF2EF3... source facts saved with offsets/excerpts in core-seam-source-facts.json.
resolveDefaultSkillRoots reads configured extraRoots plus default home/project roots. Main app
construction creates NodeSkillAdapter from config.skills.roots and disabledPaths; Skill calls
loadSkill which performs fresh discovery then reads actual path. Workspace catalog constructs
fresh adapter; session catalog uses live session app. session/create/resume protocol accepts no
SkillPort/roots field. Immutable package directories outside default roots can be supplied via
existing skills.roots, but this alone does NOT prove session pinning or permission admission.

Next Codex work: test actual per-session config snapshot behavior and resume reconstruction;
choose host projection using supported config/API and bind exact selected hashes to Core sessions
without modifying minified runtime. Serialize config/lifecycle transitions or fail closed on any
race; validate Core discovery, Skill body and later resource reads at old/new versions, including
restart/resume. Default unmanaged roots/duplicate names and future read protection must be scoped
explicitly. Do not expose imported packages before source-backed/device-tested session mapping.
No new Kotlin Agent/ContextAssembler/Skill loop or competing Gateway/journal. Full Skill importing,
activation, dependency enforcement before model discovery and session pinning remain NOT_ACCEPTED.
