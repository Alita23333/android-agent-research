# License & redistribution status (per shipped artifact)

| Artifact | Origin | License | Redistribution in APK |
|---|---|---|---|
| libnode.so (Node 24.18.0) | Termux nodejs-lts 24.18.0-1 deb | MIT (+ bundled deps' notices) | ✅ permitted, retain license texts |
| node deps: libcrypto.so.3, libssl.so.3 | Termux openssl 1:3.6.3 | Apache-2.0 | ✅ permitted |
| libicudata.so.78, libicui18n.so.78, libicuuc.so.78 | Termux libicu 78.3 | ICU/Unicode license | ✅ permitted |
| libsqlite3.so | Termux libsqlite 3.53.4 | Public Domain | ✅ permitted |
| libz.so.1 | Termux zlib 1.3.2 | zlib | ✅ permitted |
| libcares.so | Termux c-ares 1.34.8 | MIT | ✅ permitted |
| libc++_shared.so | Termux libc++ 30 | Apache-2.0 WITH LLVM-exception | ✅ permitted |
| libbash.so (bash 5.3.20) | Termux bash 5.3.20 deb | GPL-3.0-or-later WITH Bison exception | ⚠️ standalone-binary distribution is the Termux model, but **legal review required before any distributable build**; escape hatch: static toybox/mksh or ROM-provided shell (rejected for V1: upstream requires bash/zsh basename) |
| libreadline.so.8, libhistory.so.8 | Termux readline 8.3.6 | GPL-3.0 | ⚠️ same review (LGPL alternative: libedit) |
| libncursesw.so.6 | Termux ncurses | X11 (MIT-style) | ✅ (verify ncurses "Q-free" status in review) |
| libiconv.so, libcharset.so | Termux libiconv 1.19 | LGPL-2.1 | ⚠️ dynamic linking OK; keep relinkability notice |
| libandroid-support.so | Termux libandroid-support 29-1 | MIT-style (Termux) | ✅ |
| zcode.cjs 0.16.9 | ZCode desktop install resources/glm | **UNKNOWN — upstream terms not documented** | ❌ unresolved: permitted for internal testing in the owner's product workspace; DO NOT distribute externally before ZCode-side license confirmation |
| zcode-builtin.json (revision 30) | ZCode desktop install resources/config/provider | same as zcode.cjs | ❌ same unresolved status |
| bootstrap.cjs, gateway.cjs, contracts, manifest | this project (Phase 2-5 outputs) | project-owned | ✅ (follow the product's overall license) |

Testing with this payload inside the owner's product workspace is authorized
for the acceptance matrix; the two ❌ rows are the only blockers for any
external distribution.
