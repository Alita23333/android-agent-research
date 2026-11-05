# Skill 格式

应用导入一个 ZIP，ZIP 内必须只包含一个 `SKILL.md`。`SKILL.md` 可以位于压缩包根目录或单一顶层目录中。

```text
organize-downloads/
  SKILL.md
  android.yaml
  scripts/
    preview.sh
  references/
    rules.md
  assets/
```

## SKILL.md

支持常见 YAML front matter 的顶层标量字段；未知字段会保留。正文是给模型的操作说明，只有 Skill 被激活后才进入任务上下文。

```markdown
---
id: organize-downloads
name: 整理下载目录
description: 按扩展名预览并整理下载目录，移动前要求确认。
version: 1.0.0
---

# 操作步骤

先读取 `scripts/preview.sh`，仅预览分类；向用户展示计划并获得确认后再移动文件。
```

## android.yaml

这是可选的 Android 适配声明。首版读取 `tools` 列表并与当前工具注册表比对：

```yaml
runtime: android-shell
tools:
  - shell.root
  - skills.read_resource
permissions:
  - root
```

缺少所需工具时，Skill 状态为 `MISSING_DEPENDENCY`，激活会被拒绝并列出缺项。声明不会自动授予 root 或任何关键操作权限。

## 加载规则

1. 发现时只读取名称、描述、版本、来源、内容哈希和依赖状态。
2. `skills.inspect` 展示元信息和资源路径，不注入完整正文。
3. `skills.activate` 为当前任务固定一个内容快照并注入正文。
4. `skills.read_resource` 只允许已激活 Skill，且只读取 Skill 目录内的相对路径。

任务运行期间重新导入同 ID 的 Skill 会创建新内容版本并切换活动版本。已经激活的任务继续使用内存中的旧快照；新任务使用新版本。

## 打包与导入

不要把顶层父目录之外的文件加入 ZIP。应用会拒绝路径穿越、超过 500 个条目和解压后超过 20 MB 的包。

```powershell
Compress-Archive -Path .\organize-downloads\* -DestinationPath .\organize-downloads.skill.zip
```

在应用“技能”页选择 ZIP。导入后可以启用、停用或删除。
