# 🛰 三条订阅接入路线

[首页](../README.md) · [设备适配](embodiments.md) · [验证范围](validation.md)

三家各使用本机官方客户端的登录态。先在**将要运行 harness 的同一操作系统、用户和 CLI** 里确认账号和模型，再运行实验。桌面已登录、WSL 中登录、另一个 Windows 用户登录是不同的条件。API key、Vertex 服务账号和单独付费的评审 API 属于其他认证路径。

| 客户端 | 研究系统实际采用的方式 | 本仓库的模拟入口 | 先验证什么 |
|---|---|---|---|
| 🟦 Codex | SDK 启动线程，给线程挂本地 HTTP MCP，消费 turn 事件 | `codex exec --json` + 进程级 stdio MCP 配置 | CLI 登录方式、模型 ID、终态和真实工具返回 |
| 🟪 Antigravity | `agy` 双向 stream-json，专用 agent 和 MCP，按 conversation ID 续接 | `agy` stream-json + 工程级 stdio MCP | 工具发现、图片是否可见、最终 result.status |
| 🟧 Cursor | CLI 的 ACP stdio，MCP 提供观测及动作 | ACP `session/new` 中传入 stdio server 描述 | CLI 登录、ACP 返回的模型 ID、session/prompt 停止原因 |

## 蓝 · Codex

运行 `codex login`，选择账号登录，在 `codex login status` 核实登录方式。使用客户端的模型选择器查看账户可用的 ID。模拟入口在一个新工作目录启动 `codex exec --json --skip-git-repo-check --sandbox read-only`，用 `-c mcp_servers.rail.…` 仅给该进程提供 Python 模拟器的启动参数。若服务要求确认信任，先走下面的交互式流程。

接入已有 SDK 时，给单轮线程提供 `mcp_servers.<name>.url` 和本机工具服务器地址，使用同一线程提交后续反馈。消费工具事件以及 `turn/completed` 中的成功或失败状态；需要图像时优先返回 MCP image content。[官方 MCP 指南](https://developers.openai.com/codex/mcp) · [官方 app-server 参考](https://developers.openai.com/codex/app-server)

## 紫 · Google Antigravity

启动 `agy` 完成其官方 Google 登录并在模型选择器确认可用模型。研究系统曾在同一条 Antigravity 路线上使用 Gemini 与 Claude。使用账号授权提供的模型 ID，模型名与订阅权限均可能随版本变化。

本例在工程目录创建 `.agents/mcp_config.json`。向 `agy --model MODEL_ID --input-format stream-json --output-format stream-json` 的 stdin 写一行 `{"event":"user","message":{"content":"…"}}`。stdout 以事件为单位解析，等待 `event=result` 及成功状态。工具调用成功后仍可能遇到服务断流、额度限制或终态 ERROR。原实验在多轮任务中保存 conversation ID，续接时使用同一 ID，重开实验时创建新会话。

对于 HTTP 服务，Antigravity 配置使用 `serverUrl`。研究系统在专用 agent 中收窄工具，使用文件守卫检查生成图片是否属于当前会话。公开示例沿用用户的 CLI 权限设置，适合合成场景。如果当前版本没有识别项目配置，可在该客户端的 MCP 配置界面为实验专用配置导入生成的 `rail` 条目，再在工具列表核实。[官方 MCP 配置](https://antigravity.google/docs/cli/mcp/)

## 橙 · Cursor

用 `agent login` 完成官方浏览器授权，用 `agent status` 检查 CLI 登录。模型以当前账号提供的选择为准。研究系统通过 Cursor 访问 Grok；可选模型还受账号、地区和客户端版本影响。

参考客户端启动 `agent --model MODEL_ID --workspace DIR acp`，通过 stdin/stdout 逐行交换 JSON-RPC。顺序为 `initialize → authenticate(cursor_login) → session/new → session/prompt`。请求与 `session/update` 通知可能交错，依据请求 ID 配对。客户端传入 `fs=false` 对应的读写能力和 `terminal=false`，记录模型返回的 currentModelId（如有）。本例只传一个 rail MCP。遇到额外权限请求会取消该请求，可在交互式流程中检查并批准这三个模拟工具。

视觉实验先检查初始化返回的 `agentCapabilities.promptCapabilities.image`；为真时可在 prompt 中传 `{type:"image", mimeType:"image/png", data:"<base64>"}`。MCP 工具也能返回图像。不要把内置工具的 thought 更新写入公开实验日志。[官方 ACP 协议示例](https://cursor.com/docs/cli/acp) · [官方 CLI 使用指南](https://cursor.com/docs/cli/using)

## 交互式运行与排错

```sh
python pilot.py init codex runs/manual-codex
cd runs/manual-codex
codex
```

其他客户端分别将第一行的 provider 改为 `antigravity` 或 `cursor`，打开新目录，运行 `agy` 或 `agent`。选择自己的模型，查看 MCP 工具清单，确认 `rail` 的 `observe`、`act`、`finish` 都在，再粘贴 `TASK.txt`。退出后在仓库根目录执行 `python pilot.py check runs/manual-codex`（换成实际目录）。

- **找不到 CLI**。用 `--binary` 指向该官方 CLI 的可执行文件。Windows 下的 WSL 和原生 Python 应使用各自环境能访问的二进制和绝对路径。
- **工具发现失败**。在客户端实际打开生成的目录。核对该版本支持的项目级 MCP 配置与工作区信任设置；本例只需要批准本地 rail 服务。每次新实验用一个新目录。
- **账号看起来相同，调用却异常**。对照 CLI 与桌面的操作系统用户、代理与模型选择。用一次合成任务验证端到端行为。服务额度和响应时间从客户端记录取证。
- **付费边界**。本示例使用官方客户端正常登录与工具接口。运行前检查当前订阅包含的模型、额度和额外计费设置；研究系统另配评审服务时单独核算。
