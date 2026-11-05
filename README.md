# Android Agent Research Archive

**已结项，停止维护 / Archived research, no longer maintained — 2026-11-05**

这个项目探索在 Android 手机上独立运行的可扩展 Agent：ZCode Core 负责模型、会话、上下文、Skill 与工具循环；Android Host 负责设备能力、隔离 provider、权限上限、journal 和产物。

项目停止持续开发。个人项目的维护成本、运行时/平台适配与现成工具的使用便利性，使继续维护完整产品的收益不足。现有实现、验证方法和失败经验整理公开，供研究与复用。

## 独立成果索引

| 模块 | 仓库 | 已完成的范围 |
|---|---|---|
| 不可变 Skill 包存储 | [android-agent-skill-store](https://github.com/Alita23333/android-agent-skill-store) | ZIP/哈希/版本 pin/依赖/完整性；不是独立 Agent Skill 引擎 |
| Android 隔离 Node provider | [android-isolated-node-provider](https://github.com/Alita23333/android-isolated-node-provider) | isolated UID/FD/stdio/Process 生命周期；ABI 与运行时条件明确 |
| Gateway / journal / rollback | [agent-tool-gateway](https://github.com/Alita23333/agent-tool-gateway) | 现有工具边界、受限写入与结果结算；已知 residual 公开 |
| 无障碍与语义 UI 树 | [android-accessibility-toolkit](https://github.com/Alita23333/android-accessibility-toolkit) | Android service、规范化映射、动作验证和截图基础 |

固定提交、原集成位置与 SHA-256 见 components.lock.json；各仓库保存 SOURCE_MAP.json。
主仓库保留集成代码、模型/carrier 接线、测试驱动、研究与历史验收。提取组件按锁定提交恢复，见 REPRODUCTION.md。

## 实际成果

- 模型真实发起 MCP tool，经 carrier → Gateway → Android Dispatcher → 独立本地 JSON-RPC provider → 物理产物 → 最终回答。
- Skill/provider 不可变版本和逐会话 pin、导入与显式准入分离。
- 逐调用授权、journal 结算、取消、产品界面停止、Activity 重连与 force-stop 后消息/绑定恢复的受限实测。
- Android17 历史产品验收，以及 Android15 接管过程中多个真实模型、Skill 与可靠性分项通过。

这些是限定 APK/源码/设备的证据；不是全功能产品完成声明。Android15 最终接管汇总未完成，只读设备测试最后两次驱动断言失败；不补造整体 PASS。

## 从哪里读

- [结项与验收边界](CLOSEOUT.md)
- [源码组织与还原](REPRODUCTION.md)
- [最终架构](ARCHITECTURE.md)
- [已知问题和可复用经验](KNOWN_ISSUES.md)
- history/docs/：原研究/设计/验收文档，历史命令与状态不构成新执行指示。
- evidence/：经检查脱敏的原始结构化摘要，保留原测试范围与失败记录。

## 运行和许可

自有代码 MIT，第三方依赖保留各自条款。ZCode Core、内置供应商配置和第三方二进制未分发；完整 APK 暂不发布。
公开仓库不是开箱可运行的 APK 分发源。缺失载荷清单见 MISSING_RUNTIME.md；不绕过原 fail-closed 校验，不下载或合成替代 Core。
设备驱动中的序列号/型号已脱敏，绝不能不经身份核对直接用于手机。
本项目没有发行承诺、维护计划或用户支持承诺。未来可 fork 研究；原项目停在此记录点。
