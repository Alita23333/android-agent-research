# 结项记录 — 2026-11-05

停止持续功能开发；本次仅源代码拆分、脱敏、文档、导出检查与 GitHub 归档。没有操作手机、改权限、卸载或清空应用。
Codex 负责本次结项。外部 ZCode Workflow 协作已停止依赖；未返回任务（包括 codex-subscription1-20261025-r1）记“不再等待”，不伪造完成或 INTEGRATED。

## 原停止点

Android17 已接受 E36 APK：E36A5B071FA052104C00618E788E66A1A4AA4C009D21C828462D407A8700F8F2。
runtime5/Core0.16.9/Node24.18.0/Bash5.3.20，payload SHA256：4eb900732b8fa4e86b443da336fd63450bcc0237157312ddc51380eff798650a。
连续 bridge subscription 修复通过，仍非 browser replay/cursor/exactly-once 保证。

Android15 2026-10-29 接管 run1793284879529999600：E36 首次安装/正常设置配置；provider v1/v2 真模型隔离执行、Skill v1/v2、旧会话固定版本、重启恢复/取消/UI stop 分项 PASS。
完整 consolidated acceptance 未完成。两次 device-readonly 均留有 assertion failure，后一轮已有物理截图和元数据但没有最终 result.json，不登记整体 PASS。未继续修复或重跑。
本地旧 APK/失败驱动/截图/原始证据全部保留，公开和私有副本均去秘。

## 本轮证据

SOURCE_MAP.json 记录每个原始文件及公开副本哈希；设备标识/个人路径去除和类型提取/构建路径调整明确记录。
新导出测试在 EXPORT_VERIFICATION.md，不与历史真机结果混同。原工作区原件及未分发 APK/运行时保留在本地 snapshot 中。
