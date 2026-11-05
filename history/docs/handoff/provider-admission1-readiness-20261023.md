# Provider admission1 — readiness after projection1 acceptance

Read-only implementation preparation, 2026-10-23. No production edit/device action in this review.
Canonical receiving baseline remains scoped provider-projection1 transport acceptance; imported
production admission and real model-issued provider execution are not yet accepted.

## Reusable boundaries

- `ProviderReviewStore` already owns trusted review, selected snapshots, exact resolver, retirement
  and revocation. Reuse its schema1 file; no second review/admission database or registry.
- `LocalProviderCatalog` import remains storage only. `active` does not grant execution or replace
  immutable old session pins. Node projection now validates real Kotlin-written records.
- Existing host session index, AndroidToolRequest/Result, concrete BoundTool resolver, Gateway
  permission/operation/CAS journal and isolated JSON-RPC provider remain the execution chain.
- `MainViewModel.importProvider` production branch only stores the package (133–143);
  AgentApplication loads fixed bundled device-info (59–65), Host loads fixed digest (128–134).
  These are facts about current disabled imported enrollment, not a completed UI admission path.

## Remaining integration gaps

1. Explicit review UI must show exact package/source/content identity and bounded actual granted
   data profile before saving trusted declarations through the existing store. Import/selection/
   provider self-description must not silently enroll. No arbitrary shell/root/general filesystem
   profile is part of this increment. Choosing the trusted declaration input requires concrete
   implementation, not treating an executable manifest as authority.
2. Startup must restore only exact selected/nonrevoked reviewed records through the existing
   registry/Dispatcher before carrier snapshots definitions. Invalid review/package fails closed
   with visible feedback. No discover-and-execute-all startup path.
3. `ZCodeCarrierWorker.runLoop` reads Dispatcher definitions once (186–196). Running registry changes
   do not automatically update model-visible tools. `stop` (132–135) interrupts without proving
   blocking HTTP is closed. Do not assume hot worker restart is race-free; choose and test an
   explicit visibility lifecycle before implementing refresh. This is not an approved new protocol.
4. `ToolRegistry` has register/replace but no unregister (Tooling24–49). Retirement/revocation must
   have clear subsequent-call/visibility behavior while preserving old-session retirement semantics;
   do not claim cancellation of already resolved/in-flight calls without implementation and tests.
5. Settings copy `MainActivity:275` still describes import-time handshake and same-UID execution.
   Update it alongside admission UI to reflect inert import and the exact supported isolated
   profile, without promising arbitrary scripts are sandboxed.

## Acceptance sequence for Codex

First verify explicit review persistence and startup enrollment in the separate test package using
actual product methods; retain refusal of missing/tampered/revoked records. Validate tool visibility
lifecycle without changing permission ceiling. Then real model-issued imported provider call,
visible Core tool event, Gateway operation, Android Dispatcher, isolated provider and physical report
plus model final answer. Follow with update/old-pin/cancellation/full host restart cases and Android17
product-package acceptance. A UI build or Android15 Node test cannot substitute for these stages.

ZCode remains scoped independent Android15 tester, waiting for a package with exact sources and
steps once this implementation is concrete. Do not send it architecture exploration or another
confirmation-only exchange. User continues to provide only receipt reminders.
