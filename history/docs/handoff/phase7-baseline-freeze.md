# Phase 7 Product Baseline Freeze

Date: 2026-09-29  
Status: **GREEN / FROZEN**  
Authoritative receiving-product status: `docs/handoff/zcode-integration-status.md`  
Target device: adb `DEVICE_ANDROID17`, Redmi `MODEL_ANDROID17`, Android 17 / API 37, arm64-v8a  
Other connected devices: out of scope and untouched

## Hold rule

This snapshot is the accepted product boundary while ZCode Workflow performs Phase 8 pre-research. No production write capability, Shizuku capability, root capability, carrier expansion, policy change, journal change, rollback change, or hard-confirm change may be built from this document.

When a Phase 8 handoff appears, re-read the complete read-only Workflow export at:

`${USER_HOME}\Documents\A!g!E!n!T!\AGENT ON ANDROID workflow\export`

Compare it with this snapshot and `zcode-integration-status.md` before changing production code. Phase 8 contracts are authoritative for any boundary they cover.

## Frozen runtime identity

| Item | Frozen value |
|---|---|
| Runtime manifest version | `0.16.9-runtime3` |
| Runtime description | Route-A payload, Phase 0-7 |
| Node | `24.18.0`, APK-owned arm64 binary |
| Bash | `5.3.20`, APK-owned arm64 binary |
| Runtime manifest SHA-256 | `858AA26B19ACA0D3116508CF1D3ADB46ADE2CB96E9687756A09FC19A99664B6D` |
| Product payload manifest SHA-256 | `6FA56572BFA950CD6DAF583AD168D3034E0D94EEBB818864FB4875A8FDB6F029` |
| ZCode 0.16.9 SHA-256 | `B1DF2EF3E5BD76C4AF3ECB296BC003A10D3F13191A26610BD0BA940FEADAD529` |
| Gateway SHA-256 | `E92E4142A1F201ACC1FEFB7C92EAA32EDF6D82C8D454722B3A46A84CD03675CA` |
| Bootstrap SHA-256 | `42459B3F2386DA74894C4F9D780AC8AC274C34C1DBF7117E44BF890FE99EB876` |
| Android carrier SHA-256 | `0F49C79C2382E33DF76B53181803094FD479554E2A3CB4F508540494758D313C` |
| Web Search SHA-256 | `E5BBE82FDF35A655355A92ABA4217B6CAE2D844E773DBB1874C5418FEDB4F693` |

The bootstrap differs from the upstream runtime3 bootstrap only by the already accepted product boundary repair that preserves carrier `ArtifactRef` arrays. Route C is absent.

## Frozen Gateway and storage identity

| Item | Frozen value |
|---|---|
| Gateway generation | production Gateway v2 from Phase 7 |
| Journal schema | SQLite `user_version=2` |
| Journal tables | `operation`, `network_request`, `allow_rule` |
| Journal mode | WAL |
| Carrier | production user-configured MCP carrier |
| Carrier routes | bridge-inline `web_search`; Kotlin worker for Android read-only tools |
| Model-visible Android tools | `device_info.identity`, `ui.inspect`, `web_search` |
| Android dispatcher | `ReadOnlyToolDispatcher` |
| Search backend accepted | Tavily over production HTTPS |

The target device has an app-private `files/gateway/backups` directory, currently empty. Its presence is baseline evidence only; it is not an accepted Phase 8 backup contract.

## Frozen APK identity

| Item | Frozen value |
|---|---|
| Package | `dev.alita.androidagent` |
| Version | `0.1.0` (`versionCode=1`) |
| APK bytes | `69,914,425` |
| APK SHA-256 | `6F43F9E99712D847B0E15B1DD71C617036BB24DAABC0717FEFD1A3BAEED32FD5` |
| Installed APK SHA-256 on `DEVICE_ANDROID17` | `6F43F9E99712D847B0E15B1DD71C617036BB24DAABC0717FEFD1A3BAEED32FD5` |
| 16 KiB static APK alignment | PASS |

The local build artifact and the installed package matched byte-for-byte at freeze time.

## Accepted regression evidence

| Suite or vertical slice | Frozen result |
|---|---|
| Upstream Phase 7 handoff manifest | 12/12 hashes PASS |
| Upstream runtime3 payload manifest | 40/40 hashes PASS |
| Product packaged runtime/native validation | 31/31 relevant entries PASS |
| Phase 4 Gateway safety suite | 22/22 PASS |
| Phase 7 search/Gateway suite on host Node | 57/57 PASS |
| Phase 7 search/Gateway suite on APK-owned Node | 57/57 PASS |
| Journal v2 fresh/migration suite | 8/8 PASS |
| JVM/Robolectric tests | PASS |
| Android instrumentation | PASS for functional product tests; private credential seed fixture skipped when absent |
| Android lint and APK assembly | PASS |
| Real provider turn and streaming | PASS |
| Cancellation | PASS |
| Activity reconnect | PASS |
| Runtime crash/restart | PASS |
| Force-stop/relaunch and session resume | PASS |
| Persisted ZCode messages/session state | PASS |
| Model-visible `device_info.identity` | PASS |
| Model-visible `ui.inspect` | PASS |
| Real Tavily-backed `web_search` | PASS, HTTP 200, normalized result and cited final answer |

Exact sessions, journal rows, observations, package hashes, upstream package hashes and preserved Phase 7 residuals remain in `zcode-integration-status.md`.

## Freeze verification rule

During the hold, changes are limited to documentation and disabled/non-production test scaffolding. A later production change must first verify these frozen hashes or explicitly record which authoritative Phase 8 payload replaces them. No existing hash should be silently refreshed in this document.
