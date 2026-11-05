# 独立成果索引 / Component index

| 仓库 | 固定提交 | 复用入口 |
|---|---|---|
| [android-agent-skill-store](https://github.com/Alita23333/android-agent-skill-store) | [`96095e27708c`](https://github.com/Alita23333/android-agent-skill-store/tree/96095e27708c159ad026596a9c7cbda927b89d29) | store/：存储实现、必要数据类及10项原测试；reference/：Node会话边界参考 |
| [android-isolated-node-provider](https://github.com/Alita23333/android-isolated-node-provider) | [`48f9fa63bb73`](https://github.com/Alita23333/android-isolated-node-provider/tree/48f9fa63bb73c3cfb7d0c24904ec055eaac77645) | process/：Process facade；native/：JNI；reference/product/：需宿主 guard 的 Android 接线 |
| [agent-tool-gateway](https://github.com/Alita23333/agent-tool-gateway) | [`38e69787bc35`](https://github.com/Alita23333/agent-tool-gateway/tree/38e69787bc35499fa5802bb21204f577a55e4b1d) | runtime/：Gateway/journal/工作区写入/结算；tests/run.cjs：五组回归 |
| [android-accessibility-toolkit](https://github.com/Alita23333/android-accessibility-toolkit) | [`95ad0a16ad99`](https://github.com/Alita23333/android-accessibility-toolkit/tree/95ad0a16ad99288b714d67b686d64497fc73a852) | accessibility/：Android library；runtime/ui-tree.cjs：语义树；tests/tree-mapping.cjs：原映射断言 |

四个仓库均使用 archive-2026-11-05 标签。完整哈希、原产品回填位置和 SOURCE_MAP 身份见 components.lock.json。

各模块自己的 README/EXPORT_VERIFICATION.md 分别列出使用方法、历史设备范围与本次导出检查。
原生产接口与算法不为拆仓重新设计；构建壳、类型提取、源码布局和隐私替换属于已登记的整理变化。
