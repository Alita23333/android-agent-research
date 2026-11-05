# ZCode 复用与当前实现迁移决策

日期：2026-09-28  
状态：下一阶段实施基线

## 1. 结论

下一阶段采用混合架构：

```text
ZCode 0.16.9 JS/TS Agent Core + ZCode Web UI
                     │
          APK 内置 Node 24.18.0
                     │
      ZCode Protocol / Android Host Bridge
                     │
       Android Tool Gateway / CapabilityResolver
          ↙          ↓          ↘
   Accessibility   App Shell    Root/Shizuku
```

当前仓库的 Kotlin Agent Core 是已验证 Android 能力的原型，不再继续演化成与 ZCode 平行的第二套会话、模型、Skill 和工具循环。后续以 ZCode 为 Agent 运行时，保留并迁移当前仓库中已经真机验证的 Android 原生能力。

这项判断来自对参考资料和实物 PoC 的核对，不依赖参考文档中“authoritative”等措辞：

- 未修改的 `zcode.cjs` 0.16.9 已在 APK 自带 Node 24.18.0 上运行。
- Android 17 / API 37 / arm64-v8a 真机已经完成真实模型流式调用、Shell、文件工具和 Activity 重连。
- Node、Bash、共享库、Provider 配置和 Agent Core 均来自 APK，不依赖 ROM 或 Termux 安装。
- Phase 2 已实现前台服务、WebView/loopback bridge、Keystore BYOK、严格 Provider 配置生成和宿主会话索引。
- Phase 3 已实现 `CapabilityResolver` 以及 standard、Accessibility、screen、Shizuku、root Provider 骨架。

对应证据位于：

- `AGENT ON ANDROID workflow/docs/spike/gate-decision.md`
- `AGENT ON ANDROID workflow/docs/spike/node-android.md`
- `AGENT ON ANDROID workflow/docs/spike/android17-smoke.md`
- `AGENT ON ANDROID workflow/docs/spike/failures.md`
- `AGENT ON ANDROID workflow/docs/upstream-map.md`
- `AGENT ON ANDROID workflow/docs/phases/phase2-results.md`
- `AGENT ON ANDROID workflow/docs/phases/phase3-results.md`

## 2. 复用边界

### 2.1 直接复用 ZCode

| 能力 | 决策 | 原因 |
|---|---|---|
| Agent 循环 | 保留 ZCode | 已完成 Android 真机流式 turn、工具回传和取消验证 |
| 会话与消息类型 | 保留 ZCode | 避免维护第二套上下文、压缩、模型消息和工具调用格式 |
| 模型 Provider 抽象 | 保留 ZCode | 已有严格 BYOK 配置、多 API 类型和模型能力描述 |
| 工具注册和工具事件 | 保留 ZCode | Android 能力通过上游支持的工具载体与宿主 Gateway 接入，不复制循环 |
| 权限请求协议 | 保留并扩展 | 使用 `interaction/requestPermission`，Android 增加不可绕过的 critical 层 |
| ZCode Protocol | 原样保留 | NDJSON `{id,method,params}`，不能加入 `jsonrpc` 字段 |
| Web UI 与 RPC 客户端 | 优先复用 | 复用会话、流式事件、工具呈现和后续上游更新 |
| Skill/Plugin 目录约定 | 优先复用 | Android 只增加能力和平台适配元数据 |
| ZCode SQLite | 保留为会话存储 | Android SQLite 只承担操作审计和宿主索引 |
| Web search/fetch 抽象 | 保留 | Android 提供网络能力和策略边界 |

### 2.2 保留当前 Kotlin 实现并改造成 Android Host

| 当前模块 | 后续角色 | 处理方式 |
|---|---|---|
| `AgentAccessibilityService` | Accessibility capability executor | 保留控件树、快照 ID、过期检测、点击、输入、手势和截图；增加树压缩与动作后验证 |
| `DeviceToolProvider` | Android UI 工具适配器 | 工具 Schema 映射进 ZCode；实际动作仍由 Kotlin 执行 |
| `DefaultPolicyEngine` / `UiApprovalGateway` | Android hard-safety 与确认 UI | 置于 ZCode 权限引擎之外再加一层，不允许 yolo/full access 绕过 critical 操作 |
| `ProcessExecutionBackend` | Capability Provider 执行器 | 普通 app shell 暂时保留；root 后续替换为受认证 broker |
| `SqliteRunStore` | Operation Journal | 不再作为主会话数据库；记录 Provider、权限、风险、前后状态和恢复信息 |
| `FileArtifactStore` | Android Artifact Port | 保留，并与 ZCode artifact 引用互相转换 |
| `SecureSettings` | Android Keystore 密钥源 | 保留概念；输出严格 ZCode personal provider config，不再直接构造 Chat Completions 请求 |
| Skill ZIP 安全解压 | ZCode Skill 安装前置校验 | 保留路径穿越、条目数、体积和相对路径检查 |
| `JsonRpcStdioProvider` | Android 外部本地工具边界 | 保留 JSON-RPC 2.0；由 Adapter 映射成 ZCode Tool。它与 ZCode Protocol 是两个不同层次的协议 |
| Compose 设置/诊断页 | Android 设置与权限页 | 保留；主聊天与会话页面迁移到 ZCode Web UI |

### 2.3 停止扩展或逐步移除

| 当前模块 | 决策 | 替代 |
|---|---|---|
| `AgentEngine` | 冻结后移除 | ZCode Agent Core |
| `OpenAiCompatibleProvider` | 冻结后移除 | ZCode Provider layer + `ProviderConfigWriter` |
| `ContextAssembler` | 移除 | ZCode 会话上下文与 Skill 机制 |
| `SkillRuntime` 的上下文注入 | 迁移 | ZCode Skill/Plugin 系统；保留 Android 安装校验和 capability metadata |
| Compose 聊天消息状态 | 逐步移除 | ZCode Web UI/session state |
| Kotlin 工具注册表作为顶层注册表 | 降级为宿主 Gateway 注册表 | ZCode 是模型可见工具的主注册表 |

## 3. 两种协议必须明确分层

项目中需要同时存在两种协议，但不能混用。

### ZCode Protocol

用途：Web/UI/Android Host 与 ZCode Agent Core 通信。

```json
{"id":"1","method":"session/create","params":{}}
```

特点：

- NDJSON。
- 没有 `jsonrpc: "2.0"`。
- Server 可以发出 `server-N` 反向请求。
- 权限响应必须是 `{id,result:{decision}}`。
- `session/requestRuntimePreferences` 等反向请求必须响应，否则队列会阻塞。

### Android Local Tool Protocol

用途：Android Host 与用户导入的独立工具进程通信。

```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{}}
```

特点：

- JSON-RPC 2.0。
- Provider 命名空间、消息限制、取消和崩溃隔离由 Android Host 管理。
- 通过 `ZCodeToolAdapter` 转换成 ZCode 工具描述、结果、错误和产物。

## 4. 必须继承的运行时约束

这些约束已由真机失败记录验证，迁移时必须作为启动断言，而不是依靠开发者记忆：

1. Node 必须不低于 22.5；ZCode 顶层依赖 `node:sqlite`。当前验证版本为 24.18.0。
2. 可执行 ELF 必须放在 `jniLibs/arm64-v8a`，以 `lib*.so` 形式由安装器解压到只读可执行目录。不能从 `filesDir` 执行。
3. 所有 ELF 维持 16 KB LOAD alignment；当前只在 4 KB 真机启动过，16 KB 真机/模拟器仍要进入兼容矩阵。
4. `LD_LIBRARY_PATH` 必须包含 Node 和 Bash 的 APK 自带共享库目录。
5. `OPENSSL_CONF=/dev/null`，避免 Termux OpenSSL 的编译期配置路径。
6. `TMPDIR` 与 `CLAUDE_CODE_TMPDIR` 必须指向应用可写缓存目录；Android 上默认 `/tmp` 不可用。
7. `SHELL` 必须指向 APK 自带 Bash；使用 `/system/bin/sh` 会使上游解析回退到 Termux 编译路径并产生 ENOENT。
8. `PATH` 首项必须包含 `nativeLibraryDir`，因为实际 Node 文件名是 `libnode.so`。
9. 明确设置 `ZCODE_STORAGE_DIR`；不能把 `ZCODE_HOME` 当作主存储覆盖变量。
10. 必须携带真实 `zcode-builtin.json`。手写最小替代会被上游拒绝。
11. personal provider config 必须使用精确严格 Schema，写入后通过 ZCode 自身 round-trip 或 connectivity 调用验证。
12. 模型选择必须携带 `options.reasoningLevel`。
13. loopback bridge 必须只监听 `127.0.0.1`，并对 RPC、响应和状态端点验证随机 token。
14. API Key 不得通过 Intent extras 传递；部分 ROM 会将 extras 写入 logcat。

## 5. 迁移实施顺序

### M0：建立可回退集成分支

- 保留当前 APK 作为 `kotlin-baseline` 验证基线。
- 以已经通过 Phase 2/3 的 `workflow/spike/poc-app` 为 ZCode Host 来源。
- 不直接覆盖当前源码；先引入 `:zcode-runtime`、`:android-host` 或等价目录边界。
- 为 ZCode bundle、Node、共享库和 Provider 配置记录版本、哈希、来源与许可证。

验收：当前 Kotlin APK 和 ZCode Host APK 均能独立构建，迁移可逐项对照。

### M1：把 ZCode Runtime 接入当前应用壳

- 引入 `libnode.so`、Node 依赖库、`zcode.cjs`、真实 `zcode-builtin.json` 和 bootstrap。
- 引入 `RuntimeEnv`、`NodeService`、`ProviderConfigWriter` 和 loopback token。
- Compose 设置页改为生成严格 ZCode Provider 配置。
- 前台服务拥有 Node 生命周期，Activity/WebView 只负责连接。

验收：真实模型能够在当前包名 APK 中完成 streaming turn、取消和 Activity 重连。

### M2：建立 Android Tool Gateway Adapter

- 定义 `ZCodeToolAdapter`、`AndroidToolRequest`、`AndroidToolResult`。
- 通过 upstream permission broker 和上游公开的工具扩展入口接入 Android Tool Gateway；不得依赖运行时内存 patch 修改 `zcode.cjs` factory body。
- 优先验证 APK-owned MCP/tool carrier；若上游公开接口不足，采用 source-level upstream API、受维护 fork 或 build-time patch，并固定版本与回归测试。
- 每次调用依次经过 Schema、CapabilityResolver、Policy、hard-safety、Journal、Executor、验证。
- Kotlin 原有 Shell、文件、Accessibility 与本地 JSON-RPC Provider 逐个挂入 Gateway。
- 无法可靠 Gateway 化的 core-internal 副作用路径必须 fail-closed 或在配置中禁用；测试必须证明残余绕过路径不可达。

验收：不存在直接从 Skill、插件、Shell 或 root 路径绕过 Gateway 的副作用调用。

### M3：迁移 UI 自动化和 root

- 将当前无障碍树输出压缩成模型友好的语义树。
- 将 `device.observe/click/input/swipe/screenshot` 映射为 ZCode 工具。
- 先以当前 `su -c` Provider 接入统一 capability；再替换为受认证 root broker。
- root 撤销时动态降级，普通 App 能力继续可用。

验收：ZCode Agent 在 Android 17 真机上用文本模型操作标准设置页面，root/非 root 共用同一工具 ID。

### M4：迁移 Skill 与外部工具

- 使用 ZCode Skill 目录、发现和上下文机制。
- Android `android.yaml` 只表达平台、运行时、capability 与风险补充，不复制 Skill 正文协议。
- 复用当前安全 ZIP 导入与版本哈希。
- 本地 JSON-RPC Provider 通过 Adapter 暴露为 ZCode 工具。

验收：当前 `organize-downloads` Skill 和 `device_info.identity` Provider 在 ZCode Agent 中完成与 Kotlin 原型相同的闭环。

### M5：会话恢复与操作审计

- ZCode SQLite 为消息和会话内容的唯一真相源。
- Android operation journal 只记录平台副作用及恢复信息。
- 创建会话后，在首次 `session/send` 前通过 create 参数、`session/setThoughtLevel` 或对象形式 `session/setModel` 写入有效 reasoning level；Android bridge 默认应用 `disabled`，并在真机验证数据库持久化与 `session/resume`。
- 状态不明的发送、购买、删除和系统修改禁止自动重放。

验收：杀死 UI、杀死 Node 和冷启动三种场景均有定义清楚的恢复行为。

## 6. 第一批实际开发任务

下一轮不先开发 MCP、子 Agent 或 Python，而是完成一个最小迁移纵切：

1. 在当前项目加入 APK-owned Node/ZCode runtime 打包模块。
2. 启动 `zcode.cjs app-server --stdio`，保留参考 PoC 的全部启动断言。
3. 让当前模型设置生成 ZCode 严格 Provider 配置。
4. WebView 连接 token-gated loopback bridge。
5. 将当前 `device_info.identity` 本地 Provider 通过 Adapter 暴露给 ZCode。
6. 用现有测试 API 真实运行一次：ZCode 模型 → Android Adapter → JSON-RPC Provider → 真机信息 → ZCode 最终回答。
7. 将当前 Accessibility 工具迁移一个只读 `ui.inspect`，验证第二种 Android 原生能力。

完成这条纵切后再迁移文件写入、root、Skill 和审批。这样可以最早发现 ZCode Port 注入、反向请求、权限 Broker 或生命周期之间的真实接口问题。

## 7. 不直接复制的内容

- 不复制 PoC 中仅供演示的 HTML bridge 页面作为最终 UI；它只用于验证 transport。
- 不复制 yolo 自动批准逻辑到正式产品。
- 不把 `su` 是否存在写进 Agent Core 分支；必须走 CapabilityResolver。
- 不让 ZCode 的桌面 `child_process`、文件写入或插件安装绕过 Android Gateway。
- 不将 host session index 当作完整内容恢复；会话内容以正确设置 reasoning level 后写入的 ZCode SQLite 为准。
- 不将 Phase 4 Route C 的两处运行时内存 patch 作为 production architecture；其 12/12 测试只保留为研究证据。
- 不在确认许可证前发布 Bash、ZCode bundle、内置 Provider 配置或相关依赖的分发包。

## 8. 下一阶段完成定义

下一阶段完成时，应满足：

- 主 Agent 循环来自 ZCode，而不是 Kotlin `AgentEngine`。
- 模型和会话协议与 ZCode 上游兼容。
- Android 原生能力全部从统一 Gateway 进入。
- 当前已验证的 root、Accessibility、Skill、外部工具功能没有丢失。
- UI Activity 可以销毁和重建而不终止 Agent。
- Provider、Skill 和工具更新不需要修改 Agent 循环。
- 能明确列出所有仍未迁移的 Kotlin 模块及删除时间点。

这使后续 Python、MCP、子 Agent、定时任务和高级 root 工具建立在上游 Agent Runtime 与稳定 Android 能力层之上，而不是继续扩大一套需要长期独立维护的平行 Agent Core。
