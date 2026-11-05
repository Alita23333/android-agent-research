# 已知问题与经验

1. typed Core tool terminal 是 outer tool.updated + payload.kind；旧 upstream transaction consumer 还判断 payload.type。Bash session-only fallback 在扩大消费前需要精确 callId 关联。
2. 网络事件实际 wire 形状与旧折叠字段不一致；WebFetch live 证据没有补齐。详见 history/docs/research/typed-event-consumer-audit-2026-10-29.md。
3. Android15 只读验收驱动没有最终 PASS，不能由截图存在或 Android17 历史 PASS 推导。
4. 原 README/部分协议说明和任务文档早于最终状态；完整历史作为资料，不按其过期指令继续执行。
5. Node ABI/Android isolatedProcess/厂商截图/API差异是真实适配成本；host 测试通过不能代替物理设备验证。
6. 未承诺无限后台保活、开机自启、任意脚本沙箱、通用 Root/Shizuku 或跨设备零配置迁移。

可复用经验：安装不授权、版本选择不等于准入、宿主 pin 覆盖不可信元数据、无 journal 不执行、动作结果需物理证据、保留首败、按实际事件字段关联、历史结果绑定精确版本。
