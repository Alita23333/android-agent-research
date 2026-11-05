# Provider session1 host-boundary acceptance — 2026-10-18

Disposition: PASS_SCOPED_DURABLE_PROVIDER_SESSION_METADATA; NOT_PRODUCTION_ADMISSION_OR_EXECUTION_ACCEPTANCE.

Candidate 8D0998B273F689FDEE771BA505BACF080324D1689A6C70EF0969FE385E89B132 frozen/uninstalled. Installed product remains C51DB531DCC9CB9CB398FAA061E9B53724E099E8456F1D3666A1E4604865C98D. Final read-only authenticated host status ready / real / v24.18.0. Android15 not operated.

Implemented in the existing SkillSessionBindings lifecycle and sessions-index.json:
- Optional host-owned providerBindings.selected()/verify(pin) adapter. Never taken from Core/model parameters, installed active pointers or provider self-description. Production bootstrap leaves it unset, so imported production providers remain disabled.
- Exact bounded snapshot fields id/version/contentHash/definitionHash/toolIds. Duplicate provider IDs (case folded), reserved names, invalid hashes, unknown fields, duplicate/colliding wire tool IDs and unsupported async/truthy verifiers are refused.
- Session create deep-copies the reviewed host snapshot. Resume/send/tool resolution verify the original durable row against host verification; resume does not inspect the latest selection. Legacy/empty sessions remain empty. Revocation/integrity failure refuses before Core or dispatch. Retained selected versions can be retired without altering old rows.
- Snapshot stored alongside managedSkills in the SAME existing session row and same atomic index write. Metadata includes workspace and binding version. Post-Core recheck, returned session-ID check, write-failure poison, child deferral and cancellation bypass preserve existing lifecycle behavior.
- Native versioned Dispatcher carrier calls must match the session content hash AND reviewed declaration hash before Gateway admission. Production adapter and providerDefinitionHash publication do not exist yet; thus this is a fail-closed fence, NOT enabled production provider routing. Global-worker v2 cannot silently service an old-v1 session. Resolving and executing that v1 package remains future work.

Verification:
- Host Node v24.19.0: 15 session-boundary tests PASS; existing16 Skill tests PASS; actual unchanged Core lifecycle/provider metadata10 PASS; existing Core Skill6 PASS. Unit fixture uses fake Core and explicit inert-file verifier, not LocalProviderCatalog. Actual Core test uses synthetic USER-only history and explicit fixture verifier; no model or provider execution.
- Android17 DEVICE_ANDROID17 / MODEL_ANDROID17, existing separate isolationTest APK735864E4... unchanged: same unit15 PASS under actual Node24.18.0, actual Core lifecycle/provider metadata10 PASS. Final run1792331615811093600, exact source/readback hashes retained. Reconstructed host binding resumes old session with original v1 metadata while new session retains v2. This is host object reconstruction and Core close/resume, NOT full Android process-death/reboot or restored-provider execution proof.
- JVM106, zero failures/errors/skips; APK build PASS; regenerated lint0errors/28existingwarnings. Existing Gateway settlement22, authorization15, cancellation, Phase8/internal boundary, config-disable9, workspace analysis12 and Skill control28 regressions pass.
-40 packaged payload hashes verified. Only five asset changes vs settlement1: bootstrap, Skill session module, runtime manifest, payload SHA list and generated isolated-runtime manifest. Gateway source/auth/journal/Core/native libraries/compiled Android manifest unchanged. Runtime remains0.16.9-runtime5, productRevision provider-session1-boundary-candidate.

First failures retained:
1.1792331482746511300: derivative Android wrapper referred to a nonexistent local test filename; adb push failed after candidate fixture files/dependencies had been copied. No test execution. Original driver snapshot at device-driver-first-attempt.py; command log retained.
2.1792331544501513800: unit15 passed; actual Core failed because wrapper omitted release provider/zcode-builtin.json. Original executed driver and raw failure kept. Added only this public release config to test fixture, no personal config/credential copy.
3.1792331572552618900: unit15 passed; actual Core listen EINVAL because long TMPDIR + generated UUID Unix socket exceeded108-byte path limit. Kept driver and raw stderr. Shortened Core TMPDIR to the same test app's private cache base (no permission/SELinux/root change); final run passes. Prior fixtures retained.
4. Audit wrapper initially expected TAP footer from host default reporter; log actually contains Unicode info footer. Frozen failed audit/log; corrected footer parsing only. Tests not rerun for this audit-only fix.

Remaining production work: reviewed admission persistence/UI and verifier adapter tied to actual immutable LocalProviderCatalog bytes and reviewed declarations; exact old-version Dispatcher resolver; declaration-hash publication; startup registration from explicit host approval only; model/carrier/Gateway/isolated provider/physical artifact/update/cancel/full process restart acceptance. No production provider registration, review grants, model-visible imported tool, root, Shizuku or Android15 operation added here. No new journal, policy matrix, model loop or session store.

Evidence: evidence/provider-session1/acceptance-summary.json; candidate.apk; sources; JVM XML; logs; all four device run directories; failed wrapper snapshots. Acceptance does not imply arbitrary package correctness or production tool execution.
