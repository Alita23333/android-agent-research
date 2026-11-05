# DSHA 与 Android ZCode 产品的复用评估

评估日期：2026-10-03。DSHA 源码固定到 `edba958027a4e9bd32f481a321e02d31b9a99ba9`（提交时间 2026-10-02）。只读参考 checkout：`${USER_HOME}/.codex/tmp/dsha-review-20261003`。本次没有构建或在手机安装 DSHA，没有改动产品执行架构。

## 结论

继续当前项目，按固定版本抽取 DSHA 的宿主/工具链组件，成本与风险更可控。DSHA 能提供 Ubuntu 部署、PTY、设备通道、维护屏障和更新经验；它不能替代 ZCode Core、生产 Gateway、journal v3、工作区事务和 rollback。直接 fork 的主要新增成本是将一个 DSH 专用启动器改成多 Agent 宿主，并把所有 Android 执行入口纳入既有 Gateway。

这里的“复用”指源码/组件适配。检查到的实现并不是可直接导入的独立 Android library：DSHA 是单 `:app`、Java 17、两个 flavor、arm64-only，多个类依赖静态全局状态、DSH 路径及维护组件。

## 证据及当前产品边界

- DSHA `runtime/ContainerRuntime.java` 已抽象 proot/proroot，但 `ProotBootstrap` 同时处理 rootfs、DSH 安装、插件、配置迁移和持久数据绑定。
- `runtime/RuntimeHostPorts.java` 是宿主配置/诊断注入接口，不是 AgentRuntime SPI。
- `core/HarnessController.java` 固定构造 DSH 命令、DSH_HOME、BrowserAuth 链接捕获和 cookie 交换，启动前执行 DSH-specific 迁移/插件登记。
- 当前 `ZCodeHostService.kt` 已有独立进程监督、退避、runtime hash 校验与 carrier 启动。
- 当前 `Capability.kt` 的 `CapabilityProvider` 仅有 descriptors/refresh；`CapabilityResolver` 是探测/选择器，没有执行 API。`EnhancedProviders.kt` 的 Shizuku 为 PENDING 占位，Root 为探测实现，不代表生产执行已完成。
- `docs/handoff/zcode-integration-status.md` 的设备缺席段落已滞后于 `docs/handoff/evidence/phase8/` 的现场记录；不能据旧文字认为 Phase 8 完全未落地，也不能因此宣称最终全矩阵已完成。

## 1. 模块复用矩阵

| 模块 | 可复用对象 | 改造点/限制 | 优先级 |
|---|---|---|---|
| Ubuntu deployment | rootfs 解包、摘要核验、工具包锁、分步安装、受管更新/试运行 | 去掉 DSH readiness 条件、插件注入与 `.dsh` 迁移；分开基础环境、工具包、Agent 包；缺失生成资产需重建 | 中 |
| proroot | ContainerRuntime 的 argv/env 组装、原始二进制打包方式、guest 生命周期 | 同伴库/nativeLibraryDir、API37/16KB/取消实测；运行中未知副作用不能换 proot 重放；闭源许可单独核验 | 中，实验后端 |
| terminal | PtySession、Termux emulator/view、JNI 出生身份握手、会话跨 UI 重建 | 去掉 ProotBootstrap/RuntimeTasks 强耦合；PTY 入口抽成 backend launch；人类终端与模型命令区分 | 高 |
| updater | UpdateEngine、ResumableDownload、APK 包名/签名/摘要检查、后台下载状态 | 换发布源与签名；运行时更新的试运行由 ZCode-specific 验收实现 | 高，后续产品化 |
| watchdog | 退避、进程身份、停止哨兵、维护屏障 | 不复制第二个 ZCode supervisor；可给 Ubuntu guest 和设备连接单独监督；不回放 Agent 动作 | 高，选择性 |
| wireless ADB | mDNS、配对状态、TLS/SPAKE2、保活及 Python scripts | 当前依赖 Ubuntu/Python 与 `/root/.dsh` 密钥/脚本；移出 HarnessController，凭据不暴露给普通工具链 | 中 |
| virtual display | 独立 display、认证连接、generation/frameSeq、心跳与撤销 | 将固定 root-first 选择改为 resolver；适配设备资源锁、Gateway 和 UI observation 身份；API37厂商实测 | 低，独立阶段 |
| plugin UX | 来源/版本/停用/依赖/预览/隔离/更新/回滚提示模式 | npm/Cordis 插件图不可当 Skill 或 MCP 配置；当前 ZCode unrelated plugins 必须保持关闭 | 中，主要复用交互概念 |

DSHA MIT 主许可并不覆盖全部二进制。THIRD_PARTY_NOTICES 记录终端模块 Apache-2.0、proot GPL-2.0、proroot proprietary（禁止分发修改过的二进制）。保留相应来源/许可；不能把整个 APK 素材当 MIT。

## 2. 不能替代的六个组件

| 当前组件 | DSHA 为什么不等价 |
|---|---|
| Gateway（runtime4/v3事务能力） | DeviceShellPolicy 是通道命令白名单；HttpShellService 的 token 是连接认证。两者都不等于全部 Agent invocation 的 durable intent、hard-confirm 和 host policy ceiling |
| Journal v3 | DSHA 安装、备份、插件和受管运行时日志记录另一类生命周期；不能替代 operation/write_txn 及 txn_id 相关性 |
| workspace transaction | HostDataTransaction/ManagedRuntimeTransaction 面向安装/数据维护；不等于 target_rel、expect_hash、absent、backup、verify 的每次工作区操作 |
| rollback | 运行时前代回退、归档恢复不能替代每次 workspace action 的 after-image 前提、backup integrity 和新的 Gateway transaction |
| CapabilityResolver | DSHA 各处 availability/channel choose 不能统一表示 scope、权限、健康和最低权限选择；VirtualScreenChannels 当前按 root→Shizuku→ADB 顺序 |
| ZCode runtime | DSHA 自带 DSH/插件/profile/session，工具 ABI、权限事件和模型供应商/session 协议不同 |

DSHA 的设备白名单作为 backend 的静态硬限制可以保留；它只能缩小最终可执行集合。不能新增第二套可放宽授权的确认模型，也不能把 backend 自动选择解释为 Gateway 授权。

## 3. ZCode 作为第二 Agent runtime

技术上可行；现有代码未提供即插即用的第二 Agent 接口。最小 adapter 应定义 runtimeId、bundle identity、start/stop/status、endpoint/auth、session adapter、capability requirements、maintenance lease。DSH 用现有启动器适配，ZCode 用现有 APK-owned Bionic Node/runtime4 启动器适配。

ZCode 保持在 Android native 环境，Ubuntu 作为可选工具执行环境。不能让 ZCode readiness 依赖 `/usr/local/lib/node_modules/@deepseek-ai/dsh/...`，不能把 DSH_HOME、BrowserAuth 或 DSH profile 注入 ZCode。两个 runtime 的模型配置、session store、token、进程代次独立；共享的是宿主设备资源调度和 backend。

如果将来要求 DSH runtime 同样遵守现有 Gateway ceiling，必须单独证明其 permission broker/tool loop 和所有 internal side effects 也受约束。只有 ZCode 接入 Gateway 不代表整个 fork 已统一权限。

## 4. Ubuntu 作为 ToolchainProvider

建议拆清责任：ToolchainProvider 声明运行时版本/工具/依赖和环境健康；ExecutionBackend 管进程、输出、PTY、超时与取消；CapabilityResolver 选能力；Gateway 授权并记账。

一个具体链路：ZCode tool → Gateway → toolchain adapter → Ubuntu backend → 结构化结果/产物；结果要包含 backendId、runtime version/hash、executionId、exit code、cancelled/uncertain 状态。

第一步用 scratch workspace 和明确输入/输出产物，避免生产 workspace 被 guest 直接修改。产物导回必须经已定义的 workspace transaction。不能照搬 `/sdcard` 全挂载、`.dsh` 数据绑定或 ADB 凭据。

重要限制：scratch 与减少 binds 不是同 UID 的安全沙箱。proroot/proot 任意代码仍可能触达 App UID 可达的数据；开放任意 shell/脚本前必须明确信任边界。需要强制防止绕 Gateway 时，应另外验证 UID/进程隔离或受控执行方案，不能用容器名称保证隔离。此次评估不落实新沙箱架构。

## 5. Root/Shizuku/ADB 接入 resolver

可将每个 DSHA 通道包装为 CapabilityProvider（探测/撤销）和 execution backend（执行/取消）。resolver 本身不是 backend。

请求中的 backend/provider 身份、权限层级与范围必须与 Gateway 已授权操作一致；不能失败后静默改用更强 root 通道。AVAILABLE 应基于 live handshake/实际 UID，而不是仅有开关或已安装。执行返回结果未知时标记 uncertain，先核对副作用，绝不跨通道重放。

原 RootShell 的 `[EXIT=n]`/`[EXECUTION_UNKNOWN]` 文本需映射为 AndroidToolResult/AndroidToolError；保留原始诊断的脱敏版本和截断标记。Shizuku Binder death、ADB disconnect、su deny、超时、取消分别映射。RootShell 一次性 app_process 协议及 Shizuku Binder 都不是 Android Local Tool Protocol JSON-RPC 2.0；应在 provider 内部转换，不能修改已有外部协议。

## 6. 数据/生命周期/权限冲突

| 领域 | 冲突与处理 |
|---|---|
| 路径与数据格式 | DSHA `/root/.dsh`、`user-data-v5/dsh`、legacy guest data 与当前 files/workspaces/<active> 不同；README 的 Documents/dshdata 不是唯一现行数据真相。Session store 禁止合并，仅将导出/导入作为显式功能 |
| ABI | Ubuntu Node/glibc 与 APK Node/Bionic 不可混用 native modules；建立独立工具链包、库路径、CA/DNS配置与版本证明 |
| 身份 | packageName/uid/签名变更会影响 Keystore、su grants、Shizuku grants、无障碍组件名与 FileProvider。fork 不能假定保留现有 API key/授权 |
| 生命周期 | DSHA 全局维护与 guest/PTY lease 会阻止环境更新；应按 runtime/env 作用域接入。DSH watchdog 不能重启 ZCode 会话；用户 stop 高于自愈 |
| 观察身份 | current treeId/nodeId 与 virtual generation/displayId/frameSeq 含义不同；两个 observation 空间不可互换；仍共用设备独占锁 |
| 授权 | DSHA 的长期能力开关≠具体参数授权；token≠授权；容器 root≠Android root。最终为 Gateway allow ∩ backend 硬限制 ∩系统可用性 |
| 绕路 | HTTP /exec、PTY、DocumentsProvider、plugins、guest shell、virtual input 不能成为模型绕过 Gateway 的第二入口。人类维护入口须明确标识，不冒充 Agent journal 覆盖 |
| 扩展 | DSH npm/Cordis plugin ≠ SKILL.md ≠ MCP ≠独立JSON-RPC provider；分开安装、版本、启用与授权 |
| 更新与恢复 | DSHA updater/runtime trial 不能覆盖 ZCode hash manifest；APK/Ubuntu/DSH/ZCode/toolchain分别管理；备份恢复不能伪造 workspace rollback |

## 7. 净工作量（工程估算，非实测承诺）

口径：单名熟悉两个仓库的开发者；先完成当前 Phase8最终回归；仅当前 ARM64/API37设备；保留既有全部安全验收；不做DSH会话转换、旧Android兼容版、语音/LAN/独立救援等完整对等功能。每个工作日按完整开发+验证时间计；任务共享改造，所以不把单模块估计直接相加。

| 可比交付 | 当前项目抽取DSHA组件 | Fork DSHA再迁移ZCode |
|---|---|---|
| 仅新增可选Ubuntu工具链+PTY，保留现有ZCode | 约8–15人日 | 约15–25人日（还需Agent/宿主解耦与基线迁移） |
| 再加Root/Shizuku/ADB adapter、updater/插件管理体验与完整回归 | 合计约20–35人日 | 合计约30–50人日 |

误差约±50%，取决于容器源码抽取深度、原生包复现、设备兼容和Gateway覆盖证明。如果目标改为“完整DSHA的备份/救援/LAN/旧Android兼容产品，加第二Agent”，fork 更值得重新评估，不能用上表估算该更大范围。

建议先做不改Agent架构的两个spike：①DSHA PTY运行生命周期适配，②干净Ubuntu scratch工具链运行/取消。完成后再修正估计。当前Phase8尾部回归和同步报告仍需收尾，不因本评估变为已通过。

## 可核查的上游文件

所有路径对应固定提交 `edba958027a4e9bd32f481a321e02d31b9a99ba9`：

- `app/src/main/java/com/deepseekharness/app/runtime/{ContainerRuntime,ProotBootstrap,RuntimeHostPorts,WebProcessManager,InstallPipeline,ManagedRuntimeAssets,RuntimeTrial,BoundedGuestLifetime}.java`
- `app/src/main/java/com/deepseekharness/app/{PtySession,HarnessService,DeviceBridgeService,DeviceShellExecutor,RootShell,ShizukuShell}.java`
- `app/src/main/java/com/deepseekharness/app/core/{HarnessController,UpdateEngine,PluginRepository,MaintenanceCoordinator,RuntimeTasks}.java`
- `app/src/main/java/com/deepseekharness/app/bridge/AdbBridge.java`
- `app/src/main/java/com/deepseekharness/app/vscreen/{VirtualScreenManager,VirtualScreenChannels}.java`
- `app/src/main/java/com/deepseekharness/app/backup/{UserDataLayout,HostDataTransaction}.java`
- `app/src/main/java/com/deepseekharness/app/util/{DeviceShellPolicy,VirtualScreenPolicy,ProcessIdentity,UpdatePolicy}.java`
- `docs/security-model.md`、`LICENSE`、`THIRD_PARTY_NOTICES.md`、`tools/termux-jni/`。

本地检查重点：`Capability.kt`、`EnhancedProviders.kt`、`ZCodeHostService.kt`、`ZCodeRuntimeBundle.kt`、`ZCodeCarrierWorker.kt`、`AndroidToolDispatcher`/adapter contracts、`gateway.cjs`、`workspace-files.cjs`、`contracts/journal.sql`。
