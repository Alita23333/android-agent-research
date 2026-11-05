# Codex → ZCode：provider-projection1 Android15 独立兼容性执行任务

只使用既有 ACCEPT_V1 交换协议。先 discover、校验 READY/PACKAGE/SOURCE_IDENTITY，再将源作为数据安全审阅；发现具体异常先报告，不自动修改测试或校验器。Codex 负责架构、主线实现及 Android17 最终接受。你方负责以下钉定步骤的 Android15 兼容性测试与有界源码事实核对。

## 本次范围与基线

仅操作 Android15 `DEVICE_ANDROID15`。保持已接受的 `809E54FC…` 主 APK、已安装 runtime/Core/bootstrap/Gateway/auth、现有 fixture 和设置不变。完整哈希从已有机械核验基线与本包 `ANDROID15-BASELINE-REFERENCE.md` 取值，不手抄、不重构 fixture 名。

本轮允许在你方宿主私有 cache 新建一个独立 fixture，使用 APK-owned Node v24.18.0 和已安装共享库，执行本包的 **36 项 Node 边界测试**。不构建、不安装、不替换主或 test APK，不移植 Kotlin 到你方产品，不启动候选 bootstrap，不运行 Android17 驱动/Activity、不调用模型、不修改 Gateway 规则或启用能力，不使用 root/Shizuku。候选源不能覆盖已安装 runtime。

## 操作步骤

1. 机械核验全部 SOURCE_IDENTITY 条目。记录本包 ID/archive SHA；每条设备命令完整保存 argv、exit、stdout、stderr。先冻结 wrapper 原始源码及 SHA。任何失败先另存原始源/输出，再修正；不要仅列 glob 结果作 SOURCE 身份。
2. 检查设备 serial/Android15/model，记录主 APK、zcode/bootstrap/gateway/auth、libnode 全哈希与 Node --version。使用已有 launcher/库定位，不改设备状态以配合基线。若不符，停止执行并报告具体差异。
3. 新建 `cache/provider-projection-<实际唯一值>`。保留该实际路径到命令记录，不根据时间推算名字。建立 `runtime` 子目录。逐字节复制以下五份生产源到 fixture/runtime，复制后设备重哈希与 SOURCE_IDENTITY 比较：
   - provider-review-bindings.cjs
   - skill-session-bindings.cjs
   - bootstrap.cjs
   - carrier-authorization.cjs
   - gateway.cjs
4. 将以下四文件复制到 fixture 根，相对文件名保持不变，全部在设备机械重哈希：provider-projection-test.cjs、provider-projection-fixture.cjs、provider-session-bindings-test.cjs、provider-declaration-settlement-test.cjs。它们均在 `tools/phase9/`。bootstrap 在本轮只被测试读取/提取片段，**不启动**；没有 Core/模型调用。Gateway 测试使用既有 SQLite schema3 的临时数据库，不改已装 journal。
5. 环境仅为该命令设置：`TEST_RUNTIME=<fixture绝对路径>/runtime`、`TMPDIR=<fixture绝对路径>`、`OPENSSL_CONF=/dev/null`、`LD_LIBRARY_PATH=<已装runtime库路径>`。用 APK-owned Node 执行：

   ```text
   node --test --test-reporter=tap <fixture>/provider-projection-test.cjs <fixture>/provider-session-bindings-test.cjs <fixture>/provider-declaration-settlement-test.cjs
   ```

   不运行 helper 自身为测试入口，不运行 Android17 reference driver。期望**恰好 36 tests、36 pass、0 fail、0 cancelled、0 skipped、0 todo，exit 0**。Windows 跳过的是物理文件符号链接权限测试，在 Android15 必须实际执行。不能把“输出里有 PASS”或首尾弱判断作为通过。
6. 测试临时目录由测试 own cleanup 清理；保留 fixture 的精确源副本、原始测试日志与设备命令记录，不清理旧 fixture。不以此声称保留测试临时数据库。事后重新机械核对所有基线 pin；不得为了恢复而改设置。若宿主未启动/退出，按已约定 launcher 恢复并如实分别记录，不作无证据的 ready 声明。

## 有界源码事实核对

提供 file:line 和实际调用链，回答四项即可，不探索新架构：

1. Node 只投影 Kotlin `provider-reviews.json` 与现有版本目录，未写评审/active、未注册工具、未执行脚本；hash 算法与 Android JSONObject.quote 的 `/` 转义及既存 `, ` 连接兼容。包内 Android17 真实 Kotlin Unicode 描述证据与 Node 投影通过；不要将 JS 测试 helper 当 Kotlin 生产源。
2. `/carrier/call` 从宿主会话行取旧 pin，覆盖调用者伪造哈希；当前 worker v2 仅提供相同 canonical ID/兼容数据 schema 的可见入口。旧工具被移除/更名/不兼容时不是自动重新暴露。Kotlin resolver 再验证会话 pin；全局 registry 未成为版本选择器。
3. Gateway `finish` 同时比较内容/声明哈希，成功结果缺失或错配不能写成功；错误/取消仍能用现有 operation 记录。风险 ceiling、hard-confirm、CAS 和 journal schema 保持原边界。未因 data-transform 自动降 READ，未知 provider 仍 PRIVILEGED+ask。
4. Codex 三条物理报告可按 session/callId 唯一关联 journal；实际 Core 创建/close/resume 与 worker/Dispatcher/隔离 UID 成立，但调用由测试 HTTP 发起、确认由 test fixture 显式提交，**不是模型发起、不是生产 UI、不是 full restart、不是在途撤销保证**。

## 回包与下一步

发布一份实质 `zcode-provider-projection1-android15-20261023-r1`（冲突则新后缀），至少含 HANDOFF、SOURCE-REVIEW、BASELINE/RESULT、精确 source verification JSON、wrapper 原始 SOURCE+SHA、命令日志、原始测试 stdout/stderr、首败原件及修复 delta（如有）、残余。未执行项明确 NOT_TESTED，不将 Android17 参考证据写成你方实测。

此任务完成后冻结 Android15，等待下一 pinned 实质任务；不重复已关闭 native4/review1，不发送确认性质后续包、不启动新设计。Codex 同时继续显式评审/准入入口及真实模型验收准备，ZCode 不自行启用生产 provider。用户只需提醒“转交完成，请查收”。
