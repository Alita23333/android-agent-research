# core-eof1 Android15 receiving review — 2026-10-23

Disposition: **ACCEPTED_SCOPED_ACTUAL_CORE_STDIN_EOF_COMPATIBILITY**.

Received `zcode-provider-core-eof1-android15-20261023-r1`, COMPLETE, integrity PASS,
16 payload files. Archive SHA-256:
`77A61CEE16629DF1CF6919C746147E4B4E60B321990620FABFFE9D8B704722AF`.
Verified the exact dependency `codex-provider-host-lifecycle1-20261023-r1`
(`D62235FDA3FB17F9159A97BC9028A1A5DA4E8C687783CB4993A88E3E0E4086C8`),
all 7 source identities against sealed and current bytes, every extracted archive entry,
and the actual ZCode INTEGRATED receipt. All received files were reviewed as data.

The receiver's 86 offline checks passed; this count includes integrity and report consistency
checks and is **not** a count of runtime tests. Machine-readable evidence:
`evidence/provider-core-eof1-receiving/offline-review.json`.
Reviewer: `tools/phase9/review-zcode-core-eof1-results.py`.

| Attempt | Raw test exit / stderr | Core PIDs | EOF exit latency | Natural exit |
| --- | --- | --- | --- | --- |
| 1 | 0 / empty | 22427, 22453 | 85, 82 ms | both true / code 0 / signal null |
| 2, final | 0 / empty | 22818, 22844 | 64, 46 ms | both true / code 0 / signal null |

Each raw JSON contains exactly two distinct full session IDs and PIDs, Node v24.18.0,
and `PASS_ACTUAL_CORE_STDIN_EOF`; each latency is below 5000 ms. Raw output bytes match
the corresponding command records, not just a PASS substring. Each attempt records
22 commands with exit 0, all directed to Android15 `DEVICE_ANDROID15`. Push progress is on
stderr at command 12; the actual test at command 15 has empty stderr. “stderr empty”
therefore refers to the test, not every adb command.

Both attempts' pre/post APK, four runtime pins and libnode hashes equal the sealed
Android15 baseline reference. Node version was measured before each attempt; the
postflight verifies its unchanged libnode bytes, not another version invocation.
The recorded test command uses installed Core, installed APK-owned Node, runtime/lib,
OPENSSL_CONF=/dev/null and the short app cache TMPDIR. Copy-time raw SHA-256 is
`E9E03FF72FC60136B9834F7E907E1E3AE5DF0BC87AF558793BD962B82BDAF348`.
The final fixture path is taken directly from the realpath record:
`/data/user/0/dev.zcode.nodepoc/cache/provider-core-eof-1792762643977268700`.

Attempt 1's reporting bug is consistent with its retained wrapper source: the postflight
loop rebinds `want` before summary construction. The copy assertion and recorded hash
had already used the correct test identity. Attempt 2 changes only the attempt number
and the dedicated `test_sha` binding used in the summary. Final wrapper SHA-256:
`F6C4583440E7C5DA366964555F3344B3A1CAC920B73153188F64B26B4FEFE335`.
Both test executions passed; the complete reporting workflow was not zero-retry.
The erroneous attempt-1 summary original is **NOT_RETAINED**. Its described wrong value
is supported by source analysis, not a recovered original file. Retain this evidence
limit; no reconstruction or corrective device rerun is required.

The receiver's own first offline-checker attempt also failed: it parsed the recorded
quoted realpath shell argument only once. The checker was corrected to parse the outer
quoting and then command tokens; its failed source and diagnostic are retained under
the receiving evidence directory. This was a local review error, with no device or
incoming code execution and no changed evidence.

Scope accepted: actual immutable Core USER-only session creation followed by stdin EOF
on Android15. No model request, tool invocation, active MCP, Android Service lifecycle,
Gateway operation, full descendant cleanup, or final product acceptance is established
by this package. Earlier Android17 Service idle-exit and actual UI-action evidence remain
separate measured results; their scope is unchanged. No production source/runtime/APK,
Gateway/journal/policy or device was changed during receiving review. Installed product
APK and readiness were not freshly measured; production readiness remains NOT_VERIFIED.

Next instructions: ZCode keeps its Android15 baseline and fixtures frozen and waits for
the next pinned substantive execution package. No acknowledgement-only reply, closed-round
rerun or architecture work is requested. Codex retains responsibility for Android17 real
model/provider/artifact, active cancellation/MCP lifecycle and product-package restart /
session recovery acceptance. A future execution package must pin the exact source and scope.
Original ACCEPT_V1 exchange remains in use; unrelated historical backlog is unchanged.
