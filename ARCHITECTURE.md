# 最终架构

Android Compose/WebView 交互 → APK-owned Node Host/bootstrap → ZCode Core0.16.9。
Core 管理 Provider/Session/Context/Skill/Tool loop。不存在本轮重新启用的第二套 Kotlin Agent runtime；保留的早期类为历史/诊断源码。

模型工具 → model-visible MCP carrier → host policy/Gateway → Android Dispatcher → 本地 provider/Accessibility → structured result/artifact → Core。
ZCode JSON-RPC 与 Android Local Tool Protocol JSON-RPC2.0 分离。

宿主持有权限上限与设备能力。Provider 包存储、宿主评审、逐会话版本绑定、逐调用授权和实际执行相互区分。
Gateway journal schema3；workspace writes、备份/rollback 的现有约束保留，不发明替代 schema。
外部技能和工具自描述不扩权；root 可用不等于产品已批准 root 工具。
runtime5/Node24.18.0/Bash5.3.20 是历史固定载荷，不随本仓库再分发。

四个独立组件的引用与还原位置见 components.lock.json。runtime bootstrap、Core适配、provider准入UI、会话路由留在集成主仓库。
