# ZCode 任务书：Phase 9 产品修复同步、合同补齐与下一阶段边界说明

日期：2026-10-03。发给 ZCode Workflow 侧执行。Codex Android 产品主线负责接收侧集成、产品真机验收及最终基线裁决。

## 1. 本轮目标与停止点

以接收侧已经通过的 Phase 9 产品实现为实测输入，审阅并合并适合上游维护的修复，补齐实现与交付合同的差异，生成新的、可核验的同步 handoff。输出 Codex 需要的上游细节和下一阶段接入边界说明。

**本轮不启动 Phase 10 或任何新的生产能力。** 不实施 PTY、Ubuntu ToolchainProvider、Root/Shizuku/ADB 后端、虚拟显示/输入、MediaProjection、updater/watchdog。可对它们做源码定位与接入边界分析，但不得写生产实现、注册模型工具或扩大权限。

当前产品 Phase 9 PASS 保持冻结；上游同步包通过验收不等于产品自动接受新载荷。Codex 会核对新包源码、合同和差异后决定产品接收方式。

## 2. 权威基线与不可改变的架构

当前接收侧基线：

| 项目 | 当前状态 |
|---|---|
| 验收手机 | `DEVICE_ANDROID17`，型号 `MODEL_ANDROID17`，Android 17/API 37，ARM64 |
| Agent Core | ZCode `0.16.9`，原始 Core bundle 未修改 |
| Runtime | `0.16.9-runtime5`，APK-owned Node `24.18.0` / Bash `5.3.20` |
| 执行与审计 | 现有生产 Gateway、host policy ceiling、journal schema **3** |
| 生产 carrier | 模型可见 MCP stdio carrier，worker 与 INLINE 两条既有执行路径 |
| 验收 APK SHA-256 | `9AACC118DFA83372837FFB4764414CC88FF7F477AE776646C318EBE87DF03EF7` |
| 产品 runtime manifest SHA | `38735F3D4CFDA8E05D45AAA4B310473D34CD9816E9E1C67C9BF2B9C41E1B73AD` |
| 产品 payload SHA manifest SHA | `D84E42D4CE5AEF3F76B9E298EC292DD45FF3E9B0B7647F220845EF6A8180FC66` |

当前已经实际通过：运行/流式/取消/重连/崩溃重启/强制停止恢复 6 项；真实模型截图、视觉、坐标点击 3 项；真机边界与原 UI 工具 29 项；真实 identity/UI/search 3 项；真实工作区操作/回滚 5 项；JVM 30 项；手机 Node 的 WWS44/Gateway22/search57；carrier artifacts9。准确口径与限制见产品报告，不能把计数相加后当成独立覆盖率。

保持以下裁决：

- Route A：ZCode 管理 Provider/Session/Context/Skill/Tool loop；不建立第二套 Kotlin Agent Core。
- Route C minified runtime factory patch 不成为生产依赖；若需 Core 能力扩展，分析公开源级 API/维护 fork/build-time patch，不能绕回运行时 patch。
- 保持一套 Gateway、policy ceiling、journal、workspace transaction、backup 和 rollback；不建立竞争方案，不自行升级 journal schema。
- hard safety 高于 Full Access/yolo；destructive/critical 不能由 allow rule 或 benign label 绕过；无 durable journal 不执行；unattended hard-confirm 拒绝；rollback 作为新 Gateway operation。
- ZCode Protocol、MCP carrier 与 Android Local Tool Protocol JSON-RPC 2.0 是三条不同边界；不得合并协议或另造本地 Provider 协议。
- DSHA 是可选择复用的组件来源，不转向 DSHA fork；Android 宿主能力仍经过当前 Gateway。
- 不开启无关插件/workflow/off-peak 执行来使测试通过；配置关闭时用户配置的 android-host MCP 工具仍需可见。

冲突优先级：最新用户明确决策 > 最新接收侧/上游实测 > 最新 architecture/design > upstream-map > research > 早期 spike。不能依据旧文档的 locked/authoritative 字样覆盖新实测。

## 3. 输入交接与设备所有权

产品与 Workflow 是隔离工作区，**不要假定可以读取另一个仓库或宿主路径**。本任务书附带 `zcode-phase9-sync-input.zip`，用户将其复制/上传到你的工作区后，才可作为可读输入。解压包含本任务书、产品报告、最小源码快照、测试与脱敏验收材料，保持产品相对路径。

先读取包内 `INPUT_PACKAGE.md`、`SOURCE_SNAPSHOT.json`、`SHA256SUMS.txt`，校验内容，再完整读取：

1. `docs/project/CURRENT_STATE.md`。
2. `docs/handoff/zcode-integration-status.md` **顶部当前 Phase 9 节**，旧 Phase 7/8 节仅作历史证据。
3. `docs/handoff/phase9-product-acceptance.md`。
4. `docs/handoff/dsha-context-for-phase9.md`。
5. `docs/research/dsha-reuse-assessment-2026-10-03.md`。
6. `docs/handoff/evidence/phase9/README.md`、`final/release-identity.json`、最终报告与对应源码/回归测试。

输入包是审阅快照，不是完整可独立构建的产品仓库。未包含 native binaries、Core 大 bundle、凭据、数据库或 APK；它们的身份在 manifest 中。不要因缺少完整 App 依赖而重建产品架构。若包缺失或校验不符，列出缺项，先完成不依赖缺项的源码分析；不得凭记忆宣称已审阅。

`DEVICE_ANDROID17` 是 Codex 产品验收设备，**本任务不授权 ZCode 操作它**。ZCode 使用自己的已分配调试设备，并在报告中记录实际 adb serial/API/ROM/架构。历史上使用过 `DEVICE_ANDROID15`，但不能假定它当前已连接或仍被分配。不要复用接收侧脚本中的固定设备 ID 直接执行。

## 4. 工作项 A：先提交源码对照表

在改上游前，对每项修复生成一行，字段至少包括：修复 ID、接收侧文件/函数、当前上游文件/函数、旧行为、产品行为、采用方式、合同影响、对应测试、当前状态。

状态统一使用 `ADOPTED_UPSTREAM` / `PARTIALLY_ADOPTED` / `STILL_PRODUCT_DIVERGENCE` / `NOT_APPLICABLE`。只有检查实际源码并跑对应测试后才能标记采用；HANDOFF prose、单个函数同名或 cherry-pick 成功均不构成采用证明。

三个 Phase 8 修复在已消费的 Phase 9 源码中仍为 `STILL_PRODUCT_DIVERGENCE`，需优先处理：

| ID | 必须保持的行为 | 产品参考 |
|---|---|---|
| P8-GW | sparse terminal row 保留 intent 的 before hash/size；observed hash 与 verify 正确；rollback 有 executed→verified→completed，并保留原事务 backup 信息 | `gateway.cjs`、`tools/phase9/phase8-repair-regression.cjs` |
| P8-POLL | 已断开的 `/carrier/next` 清理 timer；destroyed/stopped/writableEnded 检查；旧 poll 不消耗下一条新调用 | `bootstrap.cjs`、`tools/phase8/ui-boundary-regression.cjs` |
| P8-NODE | normalized ID 对应实际 raw preorder index，包括隐藏节点和折叠 wrapper；分页保留映射；raw index 留在宿主内部；点击后返回正确 snapshot | `ui-tree.cjs`、`ZCodeCarrierWorker.kt`、同一 UI regression |

可直接复用有实测支持的源级修复。Kotlin/Compose/Keystore 等产品依赖不同的部分，应在自己的宿主层做等价适配，交付明确合同和测试，不机械替换 applicationId、生命周期或整个产品 UI。

## 5. 工作项 B：同步 Phase 9 边界修复

逐项审阅、采用或明确说明保持产品特有的理由：

| ID | 必须验证的边界 |
|---|---|
| P9-CAPTURE | 使用能可靠拒绝受保护窗口的 capture provider；产品 API34+ `takeScreenshotOfWindow` 实测拒绝 secure fixture；不以 root capture 替代拒绝。正确关闭 HardwareBuffer/Bitmap、超时晚回调不写入。 |
| P9-FRAME | 随机唯一 shot ID、JPEG ≤153600 bytes、最多2张 live frame、hash、session、≤30秒寿命、generation、rotation、真实 screen/window geometry、service observation epoch。旧 session/重绑定/重启后的帧不能重放。 |
| P9-PURGE | startup、Core exit、session change、stop/cancel/delete/dispose、host restart 清理 frame/cache/pending；中止网络；旧排队请求不能在取消后迟执行。 |
| P9-TAP | tap 前 fresh native dump；读取实际坐标下节点及祖先 label；truncated raw、超长 label、IME、越界、过期帧拒绝；真实 critical label 不能被模型 benign label 掩盖。手势发出与验证分开，无可观察变化返回 unverified，零自动重试。 |
| P9-AUTH | 外部 P9调用、tap preflight、ui_see 内部 dump/capture 均经过现有 Gateway。校验 committed exact approval arguments/session/tool，并把具体 operation ID 带到 pending/action；journal失败或关联不符不得入执行队列。 |
| P9-CONFIG | vision 显式独立配置；宿主加密存储/0600原子 materialization；可明确复制当前多模态服务，但禁止无声继承聊天 Key。批准时绑定 destination/provider/model/config hash，执行使用同一私有 snapshot。 |
| P9-EGRESS | HTTPS、公网目的地、DNS pinning、无重定向/私网绕过、IPv6边界；network intent 在 HTTP请求前；受限 image/result/response/deadline；缺Key/非法ROI/过期帧在egress前拒绝。lab例外只允许明确指定的测试origin。 |
| P9-VISION | bbox单位统一、数值严格解析、整份structured result字节预算；a11y-first ROI gate；缓存含config身份；请求次数预算不计缓存命中；达到cap仍允许已有合法cache，不发新网络。 |
| P9-CANCEL | MCP notification→carrier HTTP断开→宿主 AbortController/pending清理→原生执行前active check；取消与超时映射明确，不盲目重复可能已有副作用的动作。 |
| P9-TRACE | INLINE与worker均输出metadata-only carrier事件；保留ZCode tool事件、Gateway/network/ui记录及最终答案。Key、完整参数、图像bytes不得进入观测事件。 |

产品实际使用当前测试 API 的 `deepseek-flash` 图像输入并验收成功。主模型聊天仍按 Route A text path，图像送往显式 vision provider；这不是 Route B 改造。本输入不含 Key；需要实测凭据时，通过你工作区既有安全配置取得，不能要求在聊天中贴 Key，也不能把产品凭据文件导出。

## 6. 工作项 C：重新跑完整验证

先跑可重复的纯逻辑/故障注入测试，再在上游自己的宿主 APK/设备上跑完整 matrix。明确区分：桌面 mock、实际 runtime 源码、上游真机、真实 provider、真实 model-issued tool call。

最低必测：

1. 三项 Phase 8 修复，以及原 WWS/Gateway/search/carrier-artifacts 回归。
2. broker/config kill-switch 控制保持生效，关闭无关插件后 MCP carrier 仍模型可见；不能通过放开开关解决失败。
3. journal写入失败→零执行队列/零原生动作；network journal intent失败→零HTTP请求；approval关联失败→拒绝。
4. screenshot正常压缩预算、secure window、black frame、IME、magnification/geometry、rotation、TTL、跨session、generation碰撞与service重新绑定。
5. tap真实label critical且模型label benign仍hard-confirm；拒绝后counter不变；普通tap/long press物理变化；未观察到变化时unverified且retries=0。
6. 取消已排队调用、取消capture晚回调、取消/超时vision网络；session切换/stop/restart后无旧帧、无旧cache、无迟执行。
7. HTTP/私网/DNS/重定向/IPv6/响应超大拒绝；Key/config/model变更不串cache或变更已批准请求目的地；缓存命中不额外记网络预算。
8. real turn、streaming、cancel、Activity reconnect、runtime crash/restart、force-stop/relaunch、session/message resume。
9. 模型实际调用 screenshot、ui_see、ui_tap；同时记录ZCode工具事件、carrier事件、Gateway/operation关联、native/provider结果、物理状态及final answer。若无真实VLM凭据，将真实视觉项明确列为未测，不用mock冒充。
10. 补足产品尚未覆盖的正向长列表滚动；如果现有fixture不能证明，增加仅测试用的滚动fixture并完整复跑，不改变生产工具行为。pixel-only canvas变化/无a11y事件的staleness与验证限制需单列分析，不能声称generation覆盖所有视觉变化。

**任何修复完成后，重新跑完整的最终代码 matrix。** 不允许“全量34/1，修单项1/0”推导全量PASS。记录最终源hash、APKhash、版本、设备、测试总数、失败数、跳过数、实际命令/脚本、结果文件和重跑原因。不得删除/隐藏失败历史。

上游能力受限时，仍完成源码对照和纯测试，并分别标明 `PASS`、`PARTIAL`、`BLOCKED`。上游测试数可与产品不同，但要解释用例对应关系。不能把Codex设备上的通过结果标成自己重新通过。

## 7. 工作项 D：必须返回给 Codex 的上游细节

生成 `answers-for-codex.md`，按以下编号逐项回答。每项提供“结论 + 实际源码位置/函数或协议样例 + 测试证据 + 未知/残余”，不需要的问题也解释原因。没有源码证据时写未知，不凭印象回答。

### Q1：可维护源码与构建来源

- Core0.16.9、release builtin配置、Node24.18.0、Bash5.3.20、依赖库的确切来源、版本、源仓/commit/tag、构建步骤、补丁集、许可证/源代码提供入口是什么？哪些已经有源码，哪些只有release artifact？
- Node载荷包含哪些Termux路径/运行行为适配，例如临时目录/mkdtemp/动态库查找？哪些行为需要APK宿主设置环境，而不能视为通用Linux Node？
- 16KB对齐证据具体对应哪些ELF hash、哪个工具/命令、哪些PT_LOAD段？源级变化后怎样重复构建和验证，避免失去已验收二进制身份？

### Q2：permission broker 与残余 side-effect 路径

- 当前ZCode Core的permission reverse request、answer、tool lifecycle events的确切方法名、字段、时序、timeout/cancel语义是什么？提供脱敏完整一次时序。
- 哪些core-internal side-effect路径不经过broker？逐项列源码/配置开关/回归；plugins关闭怎样同时禁用workflow/off-peak相关路径，哪些另有开关？
- kill-switch文件写入/读取/验证失败时，是否保证不启动有残余执行能力的Core？请用源码和故障注入说明，不能只确认正常启动的配置为false。
- 宿主RPC whitelist、policy ceiling的真实入口和拒绝路径在哪里？是否存在任意命令/文件操作经其他RPC绕过Gateway？

### Q3：精确 operation 关联与重复授权

- 同一model tool经Core broker和carrier二次检查时，哪些日志是permission记录，哪些是execution/action记录？是否发生两个合法记录，如何避免错误地判为重复执行？
- 现有Gateway是否能直接返回该请求的稳定operation ID/关联句柄？产品目前校验最新durable row并绑定ID，安全上fail-closed但并发可能拒绝合法调用。请说明是否有现成接口可减少这种可用性问题。
- internal dump/capture、worker result、rollback引用原操作的session/request/toolCall/operation关联规则是什么？若需改返回metadata，提供最小兼容方案；本轮不得自行改journal schema或创设第二条审计体系。

### Q4：UI observation、截图与坐标合同

- `treeId`、normalized node ID、raw preorder、分页/隐藏节点/折叠wrapper、generation及service observation epoch的定义、生成位置和重置条件是什么？哪些字段只留宿主？
- windowId/bounds、display-pixel x/y、压缩image dimensions、rotation、system bars、overlay、IME、magnification、多窗口的转换规则是什么？提供可复算样例和检测失败条件。
- `region` 是prompt约束、筛选还是实际crop？bbox在整幅图还是ROI坐标系？为什么？请明确现有合同，不能默默改语义。
- 对protected/black/window截图错误的字段与错误码映射怎样稳定？API31–33或不同ROM不支持可靠provider时怎样fail-closed？
- 如何判断gesture完成与目标完成？Canvas无可观察tree变化时当前承诺到哪里，哪些只能unverified？未来MediaProjection/virtual display/provider怎样保留这些约束而不扩大权限？仅给边界说明。

### Q5：vision provider 能力和预算

- 原生多模态服务的image-input能力怎样检测并缓存？模型自述不算能力验证。现有主模型text path与显式vision provider是否有隐藏绑定？
- 当前支持哪些apiType/schema？Chat Completions、Responses或其他协议若不支持，返回什么错误？只说明现有能力，不扩大本轮provider实现。
- timeout层级、HTTP body/image/result预算、cache key、hour/session cap、凭据更新、DNS pinning、代理/CA/重定向路径分别在哪里执行？代理配置是否改变现有公网目的地保证？
- 网络已发出但timeout/cancel/日志写入失败时如何报告不确定结果，怎样保证不自动重试有副作用工具？

### Q6：生命周期与异常诊断

- Core/bridge/MCP child/Kotlin worker的owner、终止顺序、重启责任、orphan处理和SSE重连策略是什么？bridge ready代表子Core已可接受RPC，还是仅HTTP可访问？
- force-stop时Accessibility grant被ROM移除的检测与面向用户提示在哪里？不得用root静默恢复生产授权。
- 产品一次只读`provider/testModelConnectivity`在debug restart后出现SSE socket hang up并90秒超时，重试通过。请分析可能时序、需要增加的脱敏诊断字段及可复现测试；没有证据时不要武断归因为API或已修复。

### Q7：保持未实施的下一阶段接入点

- PTY/长命令会话的源级接入点、session/execution ID、实时输出、取消、后台断连恢复，与现有ZCode Tool loop/Gateway/local Provider的关系是什么？哪些能力已经存在，哪些确实需要新增？
- 可选Ubuntu ToolchainProvider与Android/Bionic宿主如何分工？rootfs/runtime/tool版本、依赖检测、路径映射、产物、卸载/回滚分别应由哪个现有边界负责？不把proot/chroot称为安全沙箱。
- Root、Shizuku、ADB只能作为明确执行backend，如何继承/收窄当前authorization和policy ceiling，不发生静默权限升级？分别有哪些已有可复用源码，而非仅研究建议？
- DSHA中capture/PTY/toolchain/updater/watchdog哪些可选择复用、哪些应保持正交？给源码/commit/许可证与接入点；不实施这些组件、不转移Agent Core归属。

### Q8：维护与兼容合同

- 给出“上游共同实现 / Android宿主专属 / 产品UI专属 / 测试fixture / 明确deferred”的归属表，以及后续由哪侧维护。
- 如何标识runtime5同步修订和native/Core身份？不要直接命名runtime6或改变严格manifest版本检查；若拟改版本字段，列出接收侧需要显式适配的地方。
- 新包最低支持哪些manifest/protocol版本、字段/错误码和capabilities？未知字段怎样处理、版本不兼容怎样fail-closed？
- 哪些回答与现有HANDOFF/runbook/schema/implementation冲突？列冲突并通过源码/实测裁决，不能留下两份互相矛盾的合同。

## 8. 交付包要求

在你自己的Workflow工作区生成独立导出目录，建议名称 `codex-phase9-sync-handoff/`。不得覆盖或销毁旧Phase9/runtime payload包；没有目录写权限时交付完整压缩包及索引。内容至少包括：

```text
codex-phase9-sync-handoff/
  HANDOFF.md
  adoption-matrix.md
  answers-for-codex.md
  contract-conflicts.md
  product-specific-and-deferred.md
  changes-and-source-map.md
  source/                         # 实际可采用源码及必要增量；注明适配归属
  interfaces/                    # 冻结后的请求/结果/错误/取消/坐标/事件合同
  schemas-config/                # 已有schema/config的同步版本，不另造架构
  tests/                         # 可重复fixtures、脚本、运行依赖和说明
  results/                       # 最终全量和各次失败/修复/重跑记录，脱敏
  runtime-payload/                # 若有更新，完整payload或明确引用的独立完整包
  licensing-source/              # 来源/构建/许可元数据或明确缺项
  residuals.md
  SHA256SUMS.txt
```

如果payload单独导出，HANDOFF必须明确**准确相对路径、版本、SHA manifest hash**及其与source的关系，确保Codex一次读取即可获取完整载荷；不能“请使用本地最新runtime”而不指向具体包。

SHA清单只涵盖交付内容，不混入动态`.mimosa/hook-state`等执行器状态。source、payload、manifest、native ELF证据、测试结果必须互相一致。清单生成后再次校验；记录自校验总数/成功/失败。

不得打包API Key、bridge token、个人provider配置、Keystore材料、用户数据库或真实屏幕图像。测试fixture图像如确需交付，应明确为合成fixture并标来源；不从手机私有live store提取用户内容。

## 9. 完成标准与回报格式

完成标准：源码对照明确、共同修复可采用、产品专属边界有合同、问题Q1–Q8逐项有证据或缺项、最终完整回归与payload/hash一致、残余不被PASS掩盖。

最终回报先给一句总体状态，然后列：

1. 已采用修复列表及状态；产品仍需保留的差异。
2. 完整测试结果和准确设备/版本/hash；真实provider/视觉是否实测。
3. 导出包准确路径、压缩包与SHA manifest hash。
4. Codex接收时需要适配的文件/合同；哪些可原样采用、哪些不能覆盖。
5. Q1–Q8中尚未回答的编号、原因与需要谁补充。
6. 下一阶段建议仅限边界说明；在Codex审阅并确定scope前停止生产扩展。

不要要求Codex替你完成本轮已授权的上游源码审阅或可运行回归。若被缺失凭据、设备或源码阻塞，明确指出具体缺项，继续完成独立工作后交付PARTIAL材料。不要宣称新handoff已经在Codex产品手机上验收。
