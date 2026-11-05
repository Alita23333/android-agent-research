---
id: organize-downloads
name: 整理下载目录
description: 先预览 Android 下载目录中的文件分类，确认后再按类型移动。
version: 1.0.0
---

# 整理下载目录

用于整理 `/sdcard/Download`，遵循以下顺序：

1. 激活后读取 `scripts/preview.sh`，使用 `shell.root` 执行脚本内容，只生成预览。
2. 汇总每个分类的文件数量、将创建的目录和可能的同名冲突。
3. 在用户明确同意前不要移动、改名或删除任何文件。
4. 确认后用 `shell.root` 逐类创建目录并移动文件。目标已存在时跳过，不能覆盖。
5. 再次列出来源和目标，验证每个移动结果；把失败项单独报告。

分类规则记录在 `references/rules.md`。不认识的扩展名放在 `Other` 计划中，但执行前要单独说明。
