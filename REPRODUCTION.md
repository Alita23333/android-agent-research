# 源码还原与复现范围

## 组件

从 COMPONENTS.md 选择所需仓库，checkout 固定 commit 或 archive-2026-11-05 标签，使用各自 README 的构建/测试入口。
自有源代码 MIT；第三方二进制与许可证边界见 THIRD_PARTY.md/MISSING_RUNTIME.md。

## 集成源码还原

克隆主仓库后，使用 Python3 和 Git：

```sh
python tools/restore_components.py
```

工具只获取 components.lock.json 内四个仓库的固定标签，核对 commit 和每个回填文件 SHA-256。
默认回填到当前主仓库中原来被提取的位置；已存在且内容不同即失败，不覆盖。不会下载第三方运行时、安装APK或执行模型/设备工具。
可用 `--destination <existing-empty-directory>` 在另一目录检查组件回填。
已将四个仓库克隆到同一父目录时，`--local-components <parent>` 可离线核对并还原。
SkillPackageTypes.kt 是子仓库的辅助提取文件，不覆盖主仓库原 Skills.kt。

## 可验证与不可直接运行的部分

独立组件测试见 EXPORT_VERIFICATION.md。完整 app 构建还要求原始匹配 Core/Node/Bash/库载荷；这些未随仓分发，fail-closed校验保留。
公共主仓库未宣称完整APK可以无额外依赖构建。Gradle wrapper JAR未分发，可使用 Gradle8.9。
历史 DevTools/驱动路径只是来源环境；个人home/设备serial/model已脱敏，使用自己的工具与明确核对的目标配置。
history/ 文档中链接可能指向未公开的旧交换包/二进制/原路径，作为历史引用保留；当前入口以 README 和 COMPONENTS 为准。
