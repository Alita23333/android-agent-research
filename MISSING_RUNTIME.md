# 未分发的运行依赖

ZCode Core zcode.cjs0.16.9、release zcode-builtin.json、personal provider config、Node/Bash二进制及依赖库、Gradle wrapper JAR、TLS测试私钥、APK均未上传。
原始runtime-manifest/payload清单为版本和来源参考，未改为匹配“删减版运行时”；原 integrity gate 保持 fail-closed。
现有交付说明将 Core/builtin 对外分发权限标为未确认。公开原始集成源码不表示已获得再分发许可。
完整 app 构建依赖隔离载荷 preparation，缺少原始匹配文件时会失败；这是本研究归档明确的复现限制。
已有 Gradle wrapper脚本有其原许可，JAR未附带；可自行使用 Gradle8.9。依赖版本参见各构建文件。
不会自动下载私有载荷、提供 mock Core 替代、关闭SELinux或移除哈希校验来制造可运行声明。
