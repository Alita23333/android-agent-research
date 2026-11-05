# provider-model1 产品包验收 — 2026-10-25

结论：**PASS_SCOPED_PRODUCT_MODEL_PROVIDER_AND_CANCELLATION**。这次从只读源码与隔离探针，推进到 Android17 实际产品包中的真实模型闭环，并修复两条取消收尾路径。结论限于经过明确准入的隔离纯数据 provider；不是整个产品所有能力的最终验收。

## 当前版本与变更

- 设备：Android17 `DEVICE_ANDROID17` / MODEL_ANDROID17；没有操作 Android15。
- 当前已安装 APK：`1FF91047068AF96339F2E451016C593DE28FDD360D3325B351D0A24B9966B8F9`。
- runtime 仍为 `0.16.9-runtime5`；Core0.16.9、Node24.18.0、Bash5.3.20。
- payload 清单 SHA-256：`c03768314ac26dca9b8e52fe08d8dbc429204aa08ffeef1a3beea159c008af84`。41 项打包载荷校验、40 项适用的安装后不可变载荷校验通过；宿主从加密设置生成的个人模型配置不当作不可变文件比较，也没有写入交接包。
- 相对原候选4CE，清单内仅 bootstrap 和 runtime manifest 的说明字段对应文件改变。Gateway、carrier-authorization、journal schema3、Core、原生运行时和 provider 协议均未改动。Kotlin 生产变更仅为 HostService 的停止顺序。
- 原已安装 C51、候选4CE、第一修复包和最终包均保存在本轮本地证据目录，未覆盖旧 APK。

`bootstrap.cjs` 原先在取消、断开和超时清除 pending 时，没有通过现有结果写入器结束对应原操作行。现在使用相同的 `CarrierAuthorization.finish`、精确工具/参数/会话、双哈希与 SQL CAS，写入失败仍返回 JOURNAL_RESULT_FAILED，不伪造成功；UI 路径继续使用其原有写入器。

`ZCodeHostService.stopRuntime()` 原先先终止 Worker/bridge。调用中停止时，进程虽然消失，bridge 来不及记录取消。现在在 bridge 尚存活时，经既有 token-gated 客户端和 `/rpc` → `session/stop` 入口请求当前会话取消，然后执行原有 Worker/进程清理。失败只记录未确认的诊断，不宣称日志或退出必然完成；不存在新的权限、journal、carrier 或注册表。

## 真实产品证据

本轮 fixture ID 为 `aa_model_1792764185483531200`。测试 instrumentation 只调用真实产品存储的 ZIP 安装器，不执行 provider，也不写评审记录；随后实际点击产品界面的检查、哈希确认和准入按钮。v1/v2 的宿主声明一致，包内容哈希不同。入口只接收显式 base64，正常计算 SHA256/长度，WAIT 输入延迟30秒供取消观察；不包含文件、网络、root 或安装钩子。

| 行为 | 实测结果与范围 |
| --- | --- |
| 真实模型发起 provider 调用 | 保留8份成功物理报告；逐份对应模型 tool part、carrier callId、Gateway 原操作行、JSON-RPC2.0 请求ID/实例、隔离 UID/PID、宿主产物字节与哈希及模型最终回答。驱动从 session/send 发起任务，没有注入 /carrier/call。 |
| v1/v2 会话绑定 | 2026-10-23 产品4CE上实际 UI 准入并更新；旧会话仍执行v1，新会话执行v2；宿主持久行保存精确 contentHash+definitionHash。最终1FF上旧会话继续返回v1，重启 Service 后的新会话返回v2。 |
| 普通调用中取消，最终包 | 已看到模型发起的 carrier call 和隔离进程，再发 session/stop；PID退出观测为141ms；原操作664写入 CANCELLED，携带callId与双哈希，没有成功产物。不是先结束后再“取消”。 |
| 产品 UI 停止 Agent，最终顺序复测 | 先观测真实调用及 bootstrap/Core/MCP/隔离进程，再点击“停止 Agent 以管理工具”；5个已确定PID均消失，观测781ms；原操作661为 CANCELLED；实际 UI 显示准入锁释放。无手动 kill/force-stop 辅助此测试。重新打开后模型又产生v2报告662。 |
| force-stop/relaunch/session resume | 最终1FF上按旧会话显式 resume、保存全量消息，force-stop后通过产品首页打开Agent、再次resume；消息JSON逐字段相等，随后模型实际调用v1并写操作663。 |
| Activity 重连 | HOME后台、重建产品界面并重新打开Agent；startedAt相同，旧会话全量消息相等。 |
| streaming | 最终重启模型任务的SSE保留357个 stream.chunk 事件，包含非空text块；不是仅凭最终文本推断流式。 |
| 配置边界 | 当前设备 memory、memory extraction、plugins 均为false；该配置下导入工具仍可被真实模型发现调用。没有启用无关插件或使用Route C。 |

逐调用 Gateway 批准由测试驱动仅对精确工具和精确输入回应；hard-confirm及其他请求不获允许，没有创建持久allow规则。这不是人工逐调用确认UI验收。provider准入和Service停止确实通过产品UI完成。系统文件选择器的ZIP导入交互未在本轮测试。

## 检查、首败与残余

- 新取消路径8项与既有双哈希结果6项：Node test runner字面14通过、0失败、0跳过；相关既有Gateway/SQLite回归字面RESULT22PASS。总计36项逻辑检查，不能称为36项手机端模型测试。
- 新鲜 JVM XML汇总134/0失败/0错误/0跳过；构建通过；lint0错误/28项既有警告。保留原始构建日志与XML。
- 独立汇总器135项离线检查通过，包含打包/安装哈希、物理报告、JSON-RPC trace、日志join、session pin与消息对比；不是135项运行测试。
- 首次构建修复包时缺ANDROID_CLANG，改为通过DevTools解析clang-android后成功。测试驱动的导航标签、Activity前台等待、旧会话先resume以及汇总器的重复输入历史匹配错误均保留失败目录和原驱动；未把它们算作生产缺陷。汇总器修正为同时匹配物理callId。
- 两个真实生产缺口的原始记录保留：操作655普通取消、658 Service停止后result为null；历史行没有被追改。新操作的取消结果已通过，不能据此宣布旧不确定记录自动消失。
- 第一修复包安装后哈希读取与一次Service测试的编排发生重叠，其状态文件也漏掉一个完成标记；原始独立结果文件保留。测试驱动已加入排他阶段锁；最终采用顺序复测的操作661/662以及随后663/664作为最终包证明，不依赖那次重叠编排。
- SSE还观察到既有Web消费端 `deliveryKind` 参数不兼容错误（最终重启任务保留12条）。它没有阻止本次真实模型/工具闭环，但本轮**没有**宣称完整Web事件订阅兼容；下一主线应定位该入口并做最小修复。
- 关闭/过期journal、进程崩溃、强制终止等条件仍可能保留“不确定”行。没有承诺所有停止路径/截止时间普遍保证，没有测试写副作用进行中崩溃恢复，不扩大到root、Shizuku或任意脚本。

## 证据与下一步

本轮2026-10-23开始，2026-10-25完成停止修复。共同run目录：
`docs/handoff/evidence/provider-model1/1792764185483531200/`。
最终独立核验：
`docs/handoff/evidence/provider-model1/acceptance-20261025-1792937892173990600/acceptance-summary.json`。

Codex接受这个版本作为provider模型闭环和已测取消路径的阶段基线。下一主线：定位Web订阅deliveryKind兼容问题，然后继续命令/Skill/独立工具组合任务；不提前扩展Root/Shizuku。

ZCode下一任务通过原ACCEPT_V1提供钉定源：Android15私有fixture中独立运行14项Node测试及22项结果回归，核对停止路径的有界源码事实；不安装本产品APK，不改已装runtime/配置/基线，不转交凭据，不重跑已经关闭的Core EOF。Android17实测不能写成Android15实测，发包也不等于对方已完成。
