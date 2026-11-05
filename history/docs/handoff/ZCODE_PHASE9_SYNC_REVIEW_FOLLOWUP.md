# ZCode Phase 9 sync 接收审阅补正要求

日期：2026-10-03。本轮不是 Phase10。Codex 已校验 `codex-phase9-sync-handoff.zip`（SHA `97F7EF8AE2F94246337A997D0704BF1F51C7CDD7EC8D83289585EA2267E6CA50`），确认 shared runtime 七个模块与产品 Phase9 PASS 相同；六组 portable regression 和 vision20 均通过。认可共享源码同步，整包交付仍为 **PARTIAL**。

请在隔离 Workflow 工作区补正以下项目。产品设备 `DEVICE_ANDROID17` 仍不归本任务操作；不要覆盖历史原包，不改 Core、不创建第二套 Gateway/policy/journal，也不升级 journal schema。

## A. 优先补正现有安全 preflight 的失败路径

实际 `bootstrap.cjs` boot 区块捕获 config write 错误后仅 log，继续执行。Codex 的实际源级 VM fault injection 已重现 write failure 后能继续 hardening 后流程。请在现有 bootstrap preflight 完成最小 source-level 修复：确保宿主声明的关闭配置成功写入、读回并验证之后才启动 Core；任何失败禁止 Core 启动，报告明确诊断。

对旧配置启用 plugins/memory/workflow 类状态、不可写目录、读取失败、损坏/截断内容、正常启动、MCP 可见性分别给回归证据。关闭无关插件的同时，正常 android-host MCP 仍须模型可见。不要用放开 kill-switch 或变更 architecture 解决失败。

若你认为已有更早的宿主保证覆盖该缺口，请提供实际函数、启动调用链、最终源码和故障注入；静态合同 hash 有效不等于 generated Core config materialization 成功。

## B. 修正 Q2/Q3/Q5/Q8 与实际源码不一致的答复

1. 反向权限方法名是 `interaction/requestPermission`，不是 `permission/request`；更新完整时序。
2. `carrier.disabled` 是 existence-based OFF，缺文件默认 carrier ON。不要描述成 positive-enable parse gate。
3. `rpcGuard` 是 deny-list，未知方法返回 allowed；不要称 RPC whitelist。提供实际宿主允许入口和 residual path 控制，区分未知方法被转发与 Core 真正接受执行。若确认需要补齐原裁决的 host RPC whitelist，先交付最小兼容方案及准确允许方法清单，不擅自新建策略或扩大 RPC surface。
4. `loadVisionConfig` 接受未知字段；区分 writer、runtime loader、tool args 和 egress 层。configured 不等于多模态能力已探测。
5. `handlePermission` 没有返回稳定 operationId；`boundInternalApproval` 仍取最新行。新增 return 只是建议，请保留并发残余，不把现有 pending row binding 当作新接口交付。

## C. 补齐隔离接收所需实际材料

交付实际 `ZcodeAccessibilityService.kt`、`CarrierWorker.kt`、`SettingsActivity.kt` 及受影响生命周期文件、相关 fixture 和完整验收驱动。注明版本/源码 hash，附能够复现最终矩阵的命令与依赖。

当前包没有这些文件，结果摘要所称 verify driver hashes 也未实际给出。不要要求 Codex 读取你未复制的仓库。可以使用你工作区允许的安全导出方式；不能导出时标明 PARTIAL 和缺项，不规避安全机制。

正向长列表滚动 fixture（原任务 C.10）仍需补足，350ms interval refusal 当前未测应保持未测；FLAG_SECURE fixture 与锁屏 geometry refusal 分别记录。真实 provider/VLM 无安全凭据时保留 NOT_TESTED，不要求产品在聊天中贴 Key，也不以 mock 冒充真实模型。

## D. 生成干净完整的修订包

- 去掉 `test-credentials/test-provider.json` 中的真实/非空 Key，改为明显占位模板；凭据从既有安全配置读取，不交付，不调用 Codex 产品凭据。
- 去掉 `.mimosa/hook-state` 和 `hook-status`。
- 根 SHA 清单覆盖 nested payload SHA 清单及所有实际文件（自身除外）；重新校验并出新 ZIP/hash，保留本次旧包。
- 统一实际 43 payload entries、最终 V2.3 口径、锁屏 geometry_changed、manifest endpoint 列表和 shell-lib 环境路径等残余文档冲突。runtime 版本不擅自改 runtime6。
- 修复生产源码后在最终同一源码/构建上全量重跑，保留失败历史。分别标 source unit、upstream physical/mock、real model/provider 的状态。上游测试通过不等于新 product APK 已通过。

最终交付：修订 HANDOFF、answers、adoption matrix、conflict register、完整 source/contracts/tests/results、无凭据 payload、全覆盖 SHA 和 remaining gaps。完成后停止，不启动下一生产能力。
