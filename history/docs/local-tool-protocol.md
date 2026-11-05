# 当前产品执行边界（2026-10-18）

以下 JSON-RPC1.x 协议与包格式未改变。导入 ZIP/修改 active 不自动注册或执行。
固定内置工具沿用已接受路径；新增隔离 Node provider 已具备宿主显式审核声明、不可变包哈希、
原有 Registry/Dispatcher 接线和宿主报告产物。首个 profile 只允许单一 .cjs、APK_NODE、
16KiB 内规范 base64 数据输入，声明为 data-transform/无外部副作用，输出报告32KiB 内。
这不是完整脚本沙箱保证，也不是模型端生产准入已完成。尚未启用自动注册、持久授权、
会话 pin 或通用 Gateway 结果收尾。carrier 的宿主工具快照现在携带 providerContentHash，
Dispatcher 拒绝缺失或过期哈希；它是版本围栏，不是权限凭证，不改变 JSON-RPC 本地协议。
详见 provider-binding1 验收报告和 CURRENT_STATE。

# 本地工具协议 1.0

外部工具通过逐行 JSON-RPC 2.0 与宿主通信。宿主启动 `provider.json` 中的命令，将请求写入 stdin，从 stdout 读取响应。每行必须是一个完整 JSON 对象；stdout 不能输出日志，诊断信息应写入 stderr。

本协议是 Android Agent 的本地进程边界，不等同于 MCP。以后可以由独立 `ToolProvider` 把 MCP 描述和结果转换为相同的内核类型。

## 包结构

```text
device-info/
  provider.json
  provider.sh
```

`provider.json`：

```json
{
  "id": "device_info",
  "version": "1.0.0",
  "command": ["/system/bin/sh", "${DIR}/provider.sh"]
}
```

`${DIR}` 会替换为当前版本的只读定位目录。Provider ID 必须以字母开头，只能包含字母、数字、下划线或连字符；远程工具最终 ID 为 `<provider-id>.<tool-name>`。

## 初始化

宿主启动后首先发送：

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"1.0","client":{"name":"android-agent","version":"0.1.0"}}}
```

Provider 返回协议版本和工具列表：

```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"1.0","tools":[{"name":"identity","version":"1.0.0","description":"Read device identity","inputSchema":{"type":"object","properties":{},"additionalProperties":false},"capabilities":["device-read"],"sideEffect":"NONE","supportsCancellation":false}]}}
```

主版本不是 `1` 时宿主拒绝加载。工具 ID 与已注册工具冲突时整个注册失败，不会静默覆盖。

## 调用

```json
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"identity","arguments":{},"callId":"..."}}
```

成功：

```json
{"jsonrpc":"2.0","id":2,"result":{"ok":true,"data":{"model":"example"}}}
```

工具失败可以在结果中返回结构化错误：

```json
{"jsonrpc":"2.0","id":2,"result":{"ok":false,"error":{"code":"UNAVAILABLE","message":"Service unavailable","retryable":true}}}
```

协议级错误使用 JSON-RPC `error`。首版请求和响应各限制为 1 MiB；工具包最多 200 个条目、解压后最多 20 MB。

## 权限与生命周期

工具声明的 `capabilities` 和 `sideEffect` 会交给宿主策略判断。声明不是授权，外部进程也不能绕过宿主对关键动作的确认。

可用副作用等级为 `NONE`、`REVERSIBLE`、`EXTERNAL_COMMUNICATION`、`PURCHASE`、`DESTRUCTIVE`、`SYSTEM_CRITICAL`。Provider 崩溃会变成结构化 `PROVIDER_ERROR`，Agent 内核不会随之崩溃。

当前实现按需启动 Provider 并串行化同一 Provider 的请求。`supportsCancellation` 已进入工具描述；独立的协议取消通知会在后续小版本加入。
