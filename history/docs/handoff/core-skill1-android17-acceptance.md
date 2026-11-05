# Core Skill native slice — Android17 measured acceptance, 2026-10-12

Disposition: ACCEPTED_NATIVE_SKILL_TASK_SCOPE. No APK/Core/Gateway/journal/runtime production code
changed. Existing candidate APK 87421D90D5925373392CF33A3E9973E005CEDD4BC6494D362E135113261AB03E,
runtime0.16.9-runtime5/productRevision command-analysis1, Core0.16.9 B1DF2EF3... remain pinned.
This is a new native Skill task proof, not full Stage3 Skill installation/dependency/version/provider acceptance.

## Implemented artifacts and observed Core boundary

Added a SKILL.md/reference template at docs/project/fixtures/core-skill-organize and a real device
acceptance driver tools/phase9/core-skill-acceptance.py. Skill directories are data additions inside
an app-private synthetic workspace; no APK rebuild or second Skill registry/ContextAssembler.
Core source resolves workspace .agents/skills and .zcode/skills, validates required metadata,
discovers via skills/referenceCatalog (ZCode Protocol, not JSON-RPC), and loads through native Skill.
plugins.enabled:false, memory controls and existing android-host MCP declaration stayed unchanged.
Native Skill loads guidance into the main conversation, with SkillPort ownership in the Core.

Native Core Skill permission metadata explicitly has needsApproval:false / sideEffectScope:session;
Read is also an existing Core read adapter. These calls did not enter permission broker/Gateway.
Their completed tool parts and loaded content persisted in the Core session and survived restart.
Do not claim Gateway coverage for Core context reads. This observation does not grant scripts,
providers, mutations or Android invocation any bypass: all analysis and file mutations below use
the already accepted Gateway route. No new policy rule, runtime patch or read privilege was introduced.
A production Skill management UI must present this distinction and preserve context provenance;
this proof does not provide root/workspace-external confinement for all native Core read adapters.

## Real task and independent verification

Final fixture skill organize-proof-1791814285377418300; task folder skill-proof-1791814285377418300.
Real configured provider session sess_99a63be8-7e70-4abb-bd0e-8eb87e0fad8c.
One native Skill call, one Read of that exact reference, three workspace_analyze calls and six
workspace_file_create calls. Skill body guided the task, and the report contains the unique phrase
only present in the lazy reference. Actual malformed JSON returns INVALID_JSON/exit3; model
continued after the failure. Five classified copies plus RESULTS.md were created transactionally.
Independent phone reads prove all seven originals unchanged and all five copies byte-identical.
Three exact-session analysis rows report ok/INVALID_JSON/ok; six successful transaction rows with
rel match six created paths. Separate broker intent rows retain existing schema/semantics.
Whole generated safety config hash remained byte-identical. No PC-side task execution substitutes
for phone script/file operations; PC drives tests and checks results only. No Android15 operation.

Force-stop/relaunch of assigned Android17 product: unreachable after stop, new runtime ready,
same session resumed; ten messages/nine completed assistant messages, eleven persisted tool parts
including one completed Skill and one completed reference Read. Root used only by existing debug
Activity launcher. Existing Accessibility cold-start/force-stop residual unchanged, not retested here.
First assertion-scope failure and second driver field mismatch retained; --verify-only prevents
repeated model/mutation actions. See first-failures.txt and earlier captured evidence.

Evidence directory: docs/handoff/evidence/core-skill1/1791814285377418300.
verification.json, force-resume.json, persisted-skill-state.json, RESULTS.md and raw model-task.json
are local. No provider config/token/private DB/screenshot shipped.

## Catalog behavior and remaining product work

Isolated catalog-device driver measured seven conditions PASS on Android17: workspace authority,
valid frontmatter discovered, missing description absent, unknown metadata not rejecting a skill,
Android supplement NOT enforced, input files unchanged, safety config unchanged. Supplement with
an explicitly nonexistent runtime/tool remains catalog enabled=true: this is a measured gap, not
a passing product dependency check. Fixtures live in a NEW nested test workspace; no model invokes
these catalog-only test skills. No existing fixtures or runtime files changed.

Next production step: host import/validation and immutable version selection must publish only
enabled, dependency-satisfied content to Core-discoverable roots. Core owns catalog/body/context;
host owns ZIP/path checks, actual runtime/capability availability and version provenance. Need
source-backed session version-pinning decision before implementing updates; no shadow Kotlin loop.
Also deferred: second independent local JSON-RPC provider integration and artifact/timeout/cancel/
protocol tests. Current JsonRpcStdioProvider has post-read size checks (readLine allocates first),
no response deadline, weak malformed-envelope validation and a default-to-NONE side-effect fallback.
Fix these client admission/lifetime boundaries before exposing a new provider, with existing local
protocol unchanged. Do not mistake bundled Node or legacy provider loader for production proof.

ZCode next task: only the exact isolated Core catalog compatibility driver under its Android15
app UID, source-identity and raw logs. No genuine model credential needed; no new runtime, Skill
installer, provider, Gateway policy or architecture implementation. Codex leads remaining mainline.
