# ZCode Android 合流差异与首个纵向切片

日期：2026-09-28  
状态：实施输入  
目标设备：`adb` serial `DEVICE_ANDROID17`，型号 `MODEL_ANDROID17`，Android 17 / API 37 / arm64-v8a

## 1. 本次检查结论

当前工程还不是 ZCode Android 主线的实现。它是一套已经能在真机运行的 Kotlin Agent 原型，拥有 Accessibility、`su`、结构化工具、本地 JSON-RPC Provider、Skill 导入、模型调用和任务存储，但主循环仍由 Kotlin `AgentEngine` 驱动。

Workflow PoC 已经证明未经修改的 ZCode 0.16.9 可以由 APK-owned Node 24.18.0 在目标 Android 17 设备运行，并完成真实模型流式回答、ZCode 内置 Shell/文件工具、Activity 重连、Provider 配置和 Phase 2/3 宿主能力验证。因此合流工作应把这些已验证实现迁入当前应用壳，再让现有 Android 能力经过正式 Gateway 暴露给 ZCode，而不是重新设计 Agent runtime。

首个 production 纵向切片必须是：

```text
ZCode model
  → ZCode model-visible tool
  → Android host adapter
  → Android Tool Gateway
  → existing local JSON-RPC provider
  → device result
  → ZCode tool result
  → ZCode final answer
```

第一项工具是 `device_info.identity`，第二项是只读 `ui.inspect`。在这两项闭环通过前，不接 workspace 写入、Shizuku 或 root。

## 2. 裁决边界

以下约束直接采用最新用户裁决和 `phase4-adjudication.md`，高于早期 spike、research 和带有 locked/authoritative 字样的历史文档：

1. Route A 已接受：保留 ZCode Agent Core、APK-owned Node 24、ZCode Provider/Session/Context/Skill/Tool loop。
2. Route C 不用于 V1 production：不得在运行时内存 patch `zcode.cjs` 的两个 factory body。其测试只证明研究 prototype 可行。
3. Android 侧执行统一经过 upstream permission broker、Android Tool Gateway、host RPC whitelist 和 policy ceiling。
4. 无法可靠 Gateway 化的 core-internal 副作用路径必须 fail-closed 或 config-disabled；回归测试必须证明残余绕过不可达。
5. hard safety 高于 Full Access/yolo；destructive/critical 不可被 allow rule 绕过。
6. journal 写入失败时不得执行；unattended hard-confirm 必须 deny；rollback 是新的 Gateway operation。
7. ZCode Protocol 与 Android Local Tool Protocol 保持分离，通过 Adapter 转换。

## 3. 当前工程与目标架构的差异

| 层次 | 当前工程 | Workflow/ZCode 已验证或已裁决目标 | 差异与动作 |
|---|---|---|---|
| Agent Core | Kotlin `AgentEngine`、`ContextAssembler`、Kotlin tool loop | ZCode 0.16.9 Agent Core | 冻结 Kotlin Core；迁入 ZCode runtime 后删除顶层职责 |
| 模型层 | Kotlin OpenAI-compatible provider | ZCode Provider 与严格 personal provider config | 迁入 `SecureStore`/`ProviderConfigWriter`；模型请求由 ZCode 发出 |
| Session | Kotlin RunStore/事件 | ZCode SQLite + Android host index | ZCode 为会话真相源；首次 send 前设置有效 reasoning level |
| Skill | Kotlin `SkillRuntime` 和 ZIP 导入 | ZCode Skill/Plugin loop | 保留安全导入与 Android capability metadata，正文加载交给 ZCode |
| ZCode runtime | 不存在 | APK-owned Node、bootstrap、`zcode.cjs`、builtin config | 从 Phase 2/3 PoC 迁入并固定哈希/来源/许可证 |
| ZCode transport | 不存在 | token-gated loopback + ZCode NDJSON Protocol | 迁入 NodeService、bridge 和 reverse request handling |
| 主 UI | Compose 聊天 | ZCode Web UI；Android 设置/确认仍原生 | 短期可用 PoC UI 验证 transport；最终复用上游 UI |
| Android adapter | Kotlin 工具直接注册到 Kotlin loop | ZCode tool ↔ host request/result adapter | 新建明确的 schema/error/artifact/cancellation 映射 |
| Tool Gateway | 只有 ToolExecutor 与基础 policy | Gateway 是 Android 执行唯一入口 | 新建 authoritative Gateway；内置与外部工具共用 |
| 权限 | 基础副作用标记、危险命令检查、UI approval | upstream broker + host policy ceiling + hard-confirm pack | 实现五类动作、范围授权、unattended deny 和 provenance |
| Journal | 通用 RunStore/SQLite 事件 | 独立 `filesDir/journal/journal.sqlite`，WAL，Gateway 单写者 | 新建正式 schema；no journal write → no execution |
| Rollback | 无正式 backup/rollback operation | rollback 也是新的 Gateway operation | workspace 写入阶段实现备份、关联和审计 |
| Local Provider | JSON-RPC 2.0 stdio Provider 已存在 | 保留为 Host ↔ provider 边界 | 在 Gateway 后接入，由 ZCode adapter 暴露，协议不合并 |
| Accessibility | 已有 inspect/observe、快照与动作能力 | 作为 Android capability provider | 首批只暴露 `ui.inspect`；增加语义压缩与观察 ID 规则 |
| Root | `su -c` 已验证 | 最后接入受策略约束的 root provider/broker | 当前保留但不得进入首个纵切；后续替换认证 broker |
| Shizuku | 当前工程未实现 | Phase 3 provider 骨架 | 在 workspace write 之后、root 之前接入 |
| Native/Rust | 规划存在，正式 broker 未完成 | APK native capability 与后续认证 broker | 不阻塞只读纵切；进入 root 阶段再落实 |

## 4. 已可直接复用的当前代码

### 4.1 `device_info.identity`

`examples/providers/device-info` 和现有 `JsonRpcStdioProvider` 已经证明：独立进程能够通过 Android Local Tool Protocol 注册工具、接收调用并返回结构化结果。这里不修改 Provider 协议，只新增两层：

1. `ZCodeToolAdapter` 把 ZCode tool schema/call 转成宿主请求。
2. Android Tool Gateway 在调用 Provider 前完成分类、策略、journal、执行与结果限制。

只读调用仍要写 journal，以验证所有 Android 执行都经过 Gateway。只读工具可以自动允许，但不得拥有 shell、文件写入、root 或 UI 动作能力。

### 4.2 `ui.inspect`

现有 `AgentAccessibilityService` 已具备真实 Accessibility 树读取、观察快照和界面变化后的过期控制。首批迁移仅开放读取：

- 输入：可选深度、节点上限和文本/可操作节点过滤。
- 输出：当前包名、窗口、压缩语义树、唯一 observation ID、截断信息。
- 权限：只授予 Accessibility inspect，不附带 click/input/swipe/screenshot。
- 失败：服务未启用、窗口不可读和快照过期使用稳定错误分类。

点击、输入和手势属于后续有状态能力，不能借 `ui.inspect` 的权限进入。

## 5. 尚缺失的关键实现

### 5.1 ZCode runtime 和宿主生命周期

当前仓库没有以下内容：

- `app/src/main/assets` 中的 bootstrap、`zcode.cjs`、真实 `zcode-builtin.json` 和 Node 依赖。
- `app/src/main/jniLibs/arm64-v8a` 中的 APK-owned Node/Bash 及依赖库。
- `NodeService`、`RuntimeEnv`、loopback token、WebView/ZCode RPC client。
- ZCode Protocol 的反向请求响应、streaming event、取消和重连。

这些内容应从 `workflow/spike/poc-app` 迁入，不重写已经实测通过的启动环境。

### 5.2 production 工具载体

上游 `app-server --stdio` 没有公开直接注入 `ExecutionPort`/`FileSystemPort` factory 的入口。Route C 虽然通过 12/12 prototype 测试，但已明确不能成为 production 依赖。

首选路径是验证 APK-owned MCP/tool carrier 是否能在所需 kill switches 下稳定注册只读工具，然后让该载体只调用 host adapter。这里 MCP 是 ZCode 侧的工具承载方式；Host 到独立 Provider 仍使用 Android Local Tool Protocol。如果插件关闭会让该载体不可用，则必须选择 source-level upstream API、受维护 fork 或 build-time patch，并把差异固定为可审查源码，而不是恢复 minified runtime patch。

这个载体 spike 是首个纵切唯一尚未由现有真机结果回答的上游接口问题。

### 5.3 权限、Gateway 与 journal

当前 policy 只能作为原型参考，尚未实现 Phase 4 的 production 不变量：

- RPC whitelist 与 host policy ceiling。
- read-only、reversible write、destructive、critical、unsupported 的分类和决策矩阵。
- hard-confirm、审批来源与精确参数/范围绑定。
- journal 独立数据库、WAL、单写者、执行前意图记录和 interrupted 恢复。
- backup/rollback operation。
- forced-yolo 下 memory/workflow/offpeak/plugin 等副作用路径 kill switch。
- residual bypass 不可达的回归测试。

首个只读纵切仍先实现最小完整 Gateway 路径和 journal，不用“只读风险低”跳过架构边界。

### 5.4 Session 持久化

旧结论“legacy stdio 不写完整 session rows”已被 Phase 4 实测纠正。正确条件是在首次 `session/send` 前设置有效 reasoning level：create 参数、`session/setThoughtLevel` 或对象形式 `session/setModel` 均可；bridge 已采用默认 `disabled`。

迁入当前包名后必须在目标设备执行：创建会话 → 设置/自动应用 reasoning level → 真实 provider turn → 确认 ZCode SQLite rows > 0 → force-stop → `session/resume` → 验证历史与后续 turn。

## 6. 实施顺序

### M0：迁入已验证的 ZCode Host

1. 从 Phase 2/3 PoC 迁入 Node runtime、assets、`RuntimeEnv`、`NodeService`、SecureStore、ProviderConfigWriter、loopback bridge 和 CapabilityResolver。
2. 保留当前 Kotlin APK baseline 作为对照，但不再向 Kotlin Agent Core 增加功能。
3. 对 bundle、二进制、builtin config 和依赖记录版本、SHA-256、来源与许可证。
4. 所有 adb 命令显式使用 `-s DEVICE_ANDROID17`；不得对 serial `DEVICE_ANDROID15` 执行安装、授权、设置或测试命令。

验收：当前包名 APK 在 `DEVICE_ANDROID17` 上完成真实 streaming turn、取消、Activity 重连和 force-stop/session resume。

### M1：建立最小 production Gateway

1. 定义稳定的 `AndroidToolRequest/Result/Error/ArtifactRef`。
2. 实现 host RPC whitelist、policy ceiling、只读动作分类和独立 journal 单写者。
3. journal 写入失败时拒绝执行；取消贯穿 ZCode request、Gateway 和 Provider process。
4. 配置禁用未 Gateway 化的 core-internal 副作用能力，并加入不可达回归测试。

验收：无需连接模型即可经 Gateway 调用本地 Provider；每次调用有前置意图和终态记录，绕过入口被拒绝。

### M2：打通 `device_info.identity`

1. 先验证上游支持的 MCP/tool carrier；禁止 Route C runtime patch。
2. 将 tool description/schema 注册为 ZCode 模型可见工具。
3. 调用流经 host adapter → Gateway → 现有 local provider。
4. 将结构化设备信息和截断后的诊断返回 ZCode，由模型生成最终回答。

验收证据必须同时包含：ZCode session/tool 事件、Gateway journal operation、Provider request/result、目标设备 identity 和 ZCode final answer。模型必须真实选择或按任务要求调用工具，不能由宿主预填结果。

### M3：打通只读 `ui.inspect`

1. 将 Accessibility 树压缩为稳定语义结构。
2. 只注册 inspect capability；动作能力不随工具注册。
3. 记录 observation ID、窗口/包名、截断和错误分类。
4. 在标准 Android 设置页验证模型读取并概括当前 UI。

验收：ZCode final answer 与同一 observation 的真实控件树一致；界面改变后旧 observation 不能用于后续动作。

### M4：按风险顺序扩展

`workspace write + journal/backup/rollback` → `Shizuku` → `root broker`。每一阶段都复用同一 Gateway、policy、journal、取消和恢复机制，不增加旁路。

## 7. 首个纵切完成标准

必须全部满足：

- 主循环、Provider、Session、Context、Skill 和模型可见工具注册来自 ZCode。
- `device_info.identity` 和 `ui.inspect` 分别完成一次真实模型闭环。
- 所有 Android 调用经过 host adapter、Gateway 和 journal。
- ZCode Protocol 消息不带 `jsonrpc`；本地 Provider 消息保持 JSON-RPC 2.0。
- hard safety 与 host policy ceiling 不受 yolo/full access 影响。
- 未接入 Gateway 的副作用入口被禁用，回归测试证明不可达。
- force-stop 后 ZCode session 可恢复，不重复不确定副作用。
- 测试设备始终为 serial `DEVICE_ANDROID17` / model `MODEL_ANDROID17`；另一台设备无变更。
- 当前 Kotlin `AgentEngine` 没有新增职责，并列出其剩余调用点和删除计划。

## 8. 实施前仍需关闭的问题

| 问题 | 关闭方式 | 是否阻塞首个纵切 |
|---|---|---|
| ZCode bundle、Bash、builtin config 的许可证与分发边界 | 记录来源和许可证，区分自用 APK 与可分发构建 | 不阻塞本地开发，阻塞发布 |
| MCP/tool carrier 在插件 kill switch 下的可用性 | 做最小只读工具注册与重连 spike | 阻塞 `device_info.identity` ZCode 闭环 |
| ZCode tool schema、错误、取消、artifact 的精确映射 | 以实际 upstream messages 建 golden fixtures | 阻塞稳定 Adapter |
| Permission broker 的反向请求与 host decision 映射 | 对 allow/deny/confirm/unattended 建协议测试 | 阻塞 production Gateway 验收 |
| 上游最终 Web UI 资源与许可证 | 先复用 PoC transport UI，随后替换为获准上游 UI | 不阻塞 runtime/tool 闭环 |
| 16 KB page-size 启动 | 加入兼容设备或模拟器矩阵 | 不阻塞当前 4 KB 真机纵切，阻塞广泛发布 |

## 9. 证据来源

本分析按文档优先级使用以下最新材料：

- `workflow/docs/phases/phase4-adjudication.md`
- `workflow/docs/phases/phase4-runbook.md`
- `workflow/docs/phases/phase3-results.md`
- `workflow/docs/phases/phase2-results.md`
- `workflow/docs/phases/phase2-f1-session-persistence.md`
- `workflow/docs/designs/policy-journal.md`
- `workflow/docs/designs/tool-gateway.md`，仅保留实测结果；Route C production 建议已被最新裁决覆盖
- `workflow/docs/upstream-map.md`
- `workflow/docs/spike/gate-decision.md`
- `workflow/docs/spike/node-android.md`
- `workflow/docs/spike/android17-smoke.md`
- `workflow/docs/spike/failures.md`
- `workflow/spike/poc-app` 实际源码与打包内容

当前仓库差异通过源码、Gradle、Manifest、assets/jniLibs 目录和现有工具/执行/存储实现交叉检查。本文不把历史文档中的推荐文字当作高于最新裁决的依据。
