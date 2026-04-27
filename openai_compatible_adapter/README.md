# OpenAI-compatible Claude Adapter

这个适配器把 Claude/Anthropic Messages API 转成 OpenAI-compatible Chat Completions API。

用途：

- 让 Claude Code、CCB、Anthropic SDK 类工具连接 OpenAI-compatible 模型服务。
- 让 LukerClaw 的项目内 CCB agent 使用本地反代、第三方模型网关、本地模型网关。
- 转换 Anthropic 工具调用格式和 OpenAI `tool_calls` 格式。

它只做协议转换和请求转发，不提供模型能力。

## 支持接口

```text
POST /v1/messages
POST /v1/messages/count_tokens
GET  /v1/models
GET  /health
```

## 支持转换

- Anthropic `messages` -> OpenAI `messages`
- Anthropic `tools` -> OpenAI `tools`
- Anthropic `tool_use` -> OpenAI `tool_calls`
- Anthropic `tool_result` -> OpenAI `role=tool`
- OpenAI 普通文本回复 -> Anthropic `text`
- OpenAI `tool_calls` 回复 -> Anthropic `tool_use`
- 普通 JSON 响应
- SSE 流式响应
- base64 图片块转 OpenAI `image_url`

## 单独运行

```powershell
$env:LUKERCLAW_MODEL_BASE_URL="http://127.0.0.1:8317/v1"
$env:LUKERCLAW_MODEL_API_KEY="你的 OpenAI-compatible key"
$env:LUKERCLAW_MODEL_NAME="gpt-5.5"
$env:LUKERCLAW_ADAPTER_PORT="8766"

python -m openai_compatible_adapter.server
```

启动后使用：

```text
http://127.0.0.1:8766/v1/messages
http://127.0.0.1:8766/v1/messages/count_tokens
http://127.0.0.1:8766/v1/models
```

## 环境变量

```text
LUKERCLAW_MODEL_BASE_URL       OpenAI-compatible base URL，例如 http://127.0.0.1:8317/v1
LUKERCLAW_MODEL_API_KEY        OpenAI-compatible API key
LUKERCLAW_MODEL_NAME           模型名，例如 gpt-5.5
LUKERCLAW_MODEL_TEMPERATURE    可选，默认 0.8
LUKERCLAW_MODEL_TIMEOUT        可选，默认 120
LUKERCLAW_ADAPTER_PORT         可选，默认 8766
```

兼容别名：

```text
AIRP_MODEL_BASE_URL
AIRP_MODEL_API_KEY
AIRP_MODEL_NAME
AIRP_MODEL_TEMPERATURE
AIRP_MODEL_TIMEOUT
AIRP_ADAPTER_PORT
OPENAI_BASE_URL
OPENAI_API_KEY
OPENAI_MODEL
```

## Claude Code / CCB 使用方式

先启动适配器，再让 Claude Code / CCB 指向适配器：

```powershell
$env:ANTHROPIC_BASE_URL="http://127.0.0.1:8766"
$env:ANTHROPIC_API_KEY="lukerclaw-local-adapter"
$env:ANTHROPIC_AUTH_TOKEN="lukerclaw-local-adapter"
$env:ANTHROPIC_MODEL="lukerclaw-openai-compatible"
$env:ANTHROPIC_DEFAULT_OPUS_MODEL="lukerclaw-openai-compatible"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL="lukerclaw-openai-compatible"
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL="lukerclaw-openai-compatible"

ccb
```

## Python 内嵌使用

```python
from openai_compatible_adapter import AdapterConfig, AnthropicOpenAIAdapter

adapter = AnthropicOpenAIAdapter(AdapterConfig(
    base_url="http://127.0.0.1:8317/v1",
    api_key="your-key",
    model="gpt-5.5",
))

message = adapter.create_message({
    "model": "lukerclaw-openai-compatible",
    "messages": [{"role": "user", "content": "Reply exactly OK"}],
    "max_tokens": 64,
})
```

## LukerClaw 项目内用法

LukerClaw 的 `skills/anthropic_openai_proxy.py` 是这个独立适配器的 HTTP handler 包装层。项目启动 `skills/server.py` 后会暴露：

```text
http://127.0.0.1:8765/v1/messages
http://127.0.0.1:8765/v1/messages/count_tokens
http://127.0.0.1:8765/v1/models
```

运行 `start-claude-openai-compatible.bat` 可直接启动项目内桥接服务器并拉起 `ccb`。
