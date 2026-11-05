# Codex 独立推进与 Android15 主设备接管

日期：2026-10-29（Asia/Singapore）  
依据：用户已明确要求实施《由 Codex 独立推进，并将 Android15 接管为主开发设备》。  
当前状态：**实施中；本文建立职责和接管边界，尚不宣称 Android15 已安装或验收通过。**

## 生效的项目与设备分工

Codex 统一负责产品方向、架构、实现、测试、设备调试和版本接受。ZCode Workflow 不再是日常项目推进的依赖，不再继续派单或等待其回执。产品仍沿用既定 ZCode Core、APK-owned Node/runtime、Gateway、journal schema、Skill、carrier 和本地工具协议；本次不替换内核或建立并行架构。

| 设备 | 新角色 | 验收规则 |
| --- | --- | --- |
| Android15 `DEVICE_ANDROID15` / MODEL_ANDROID15 | Codex 日常开发与主线验收 | 安装本侧产品后建立独立的 Android15 基线；每项结论绑定实际 APK／源码身份与本机实测。 |
| Android17 `DEVICE_ANDROID17` / MODEL_ANDROID17 | 按需兼容检查 | 可用时核对系统差异；不阻塞每次主线推进，不把新 Android15 PASS 自动视为 Android17 新版本通过。 |

这项用户决定覆盖 2026-10-04 分工计划和其他旧文件中“Android15 归 ZCode／Android17 必须最终接受”的规则。旧文件、包与报告保留其历史事实；不追改当时的设备、版本、失败或未测项。

## 旧协作收尾

- 接管前确认旧 ZCode 会话不再操作 Android15，之后本工作区成为唯一日常实现与验收决策源。
- 停止新的 Workflow 派单；尚未返回的旧任务记录为“不再等待”，不伪造完成、对方回执或接收侧 INTEGRATED。
- 原交换目录、READY 包、回执、上游导出和既有源码审阅资料全部保留。将来用户明确要求读取历史交付时，仍使用本侧已审阅的原 v1 工具和协议。
- 不再把 discover、封包、人工提醒或外部回执作为日常推进的必经步骤。不启用其他文件交换 skill 替代既有历史协议。

## 接管与数据边界

1. 记录 Android15 当前 APK／runtime 身份、旧应用与端口占用情况，保存回退信息。旧 `dev.zcode.nodepoc` 与本侧产品 `dev.alita.androidagent` 包名不同，可以并存。
2. 停止旧宿主运行服务以避免 bridge 端口冲突，但保留其 APK、数据、缓存 fixture 与历史证据。没有卸载、清空、升级或覆盖旧环境的默认动作。
3. 首次部署使用本侧已封存的 E36 产品制品作为候选：`E36A5B071FA052104C00618E788E66A1A4AA4C009D21C828462D407A8700F8F2`。安装前重新校验包身份，安装后重新核对适用不可变载荷；这个候选身份本身不是 Android15 通过结论。
4. Android15 建立全新产品数据。沿用已授权的模型接口配置来源，通过目标应用正常设置入口重新保存并由目标机 Keystore 加密；凭据不进入证据、文档或交接包。通知、无障碍等权限与能力在目标机重新确认。
5. 不整目录克隆 Android17 的 Keystore 密文、bridge token、活动 journal、rollback 或绝对路径 session pin。Skill／provider 包按正常导入、版本固定和准入流程重建，普通工作文件按需复制并校验。旧会话和日志先保留为来源机历史。
6. 主机测试侧使用共享 `DeviceTarget`，默认命名目标为 Android15 主设备，Android17 必须显式选择。保留执行前 serial／SDK／型号／ABI 核对；设备内 fixture 也必须验证指定 SDK／型号，不能直接删掉身份 guard。封存的历史驱动和结果不改写。

## Android15 接受记录

以下是接管退出条件，当前均为**待主线实施及回填**，不是已完成测试列表。

| 组别 | 必要判据 | 当前状态 |
| --- | --- | --- |
| 运行基础 | 产品包／载荷身份、Node／Bash／Core 启动与正常停止；实际 Android isolatedProcess provider 执行。 | 待实测 |
| 真实模型闭环 | 模型发起调用，经 carrier → Gateway → Dispatcher → 独立 provider 返回；精确 operation、pin、物理产物与最终回答关联。 | 待实测 |
| 可靠性 | 自动订阅、流式、调用中取消、产品 UI 停止 Agent、Activity 重连、force-stop 后完整消息与绑定恢复。 | 待实测 |
| 扩展与设备 | Skill 发现／激活／版本固定，独立工具导入／准入，无障碍读取与截图。搜索／视觉按实际配置单独验收，缺配置如实标待测。 | 待实测 |
| 基线交付 | Android15 独立报告、APK／源码身份、失败与限制；通过后登记为后续主线基线，Android17 新版本状态另列。 | 待回填 |

Android15 以前的 Node／SQLite／Core 协议兼容性证据可复用为诊断输入，但不能替代本侧产品隔离服务、真实模型或设备能力验收。旧 Android17 的通过结果也不能直接转成 Android15 PASS。必要修复应保持现有 Gateway、journal 和协议边界，不用放宽断言或权限来换取通过。

## 常在线与后续推进

本次“always on”仅表示 Android15 手机及 ADB 长期可用。电脑继续负责构建，设备负责实际运行与调试，按任务使用现有可见入口启动 Agent；优先沿用现有 USB 连接。本次不包括无限后台保活、开机自启、root 保活或系统限时策略修改，现有 `dataSync` 服务仍受平台后台约束。

接管通过后，由 Codex 直接在 Android15 上继续 typed 事件消费边界核查，再推进实际命令、Skill 与独立工具组合任务。无需等待 Workflow 回包，也不让用户反复负责人工查收提醒。

## 实施回填入口

主会话在实际操作与核验后补充：设备接管前身份／旧服务停用结果、产品安装与配置结果、明确运行过的测试及原始证据路径、当前 APK／源码／runtime 身份、未完成项目及接受范围。没有这些实测记录之前，不将本文件状态改为“接管通过”。
