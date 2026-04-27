# OpenAI-compatible Claude Adapter

这是一个把 Claude/Anthropic Messages API 转成 OpenAI-compatible Chat Completions API 的本地适配器。

用途：

- 让只支持 Anthropic `/v1/messages` 的工具连接 OpenAI-compatible 模型服务。
- 让 Claude Code、CCB 或类似 agent 工具使用本地反代、第三方模型网关、本地模型网关。
- 把 Anthropic 工具调用格式和 OpenAI `tool_calls` 格式互相转换。

它不是模型服务。它只负责协议转换和请求转发。

## 支持的接口

```text
POST /v1/messages
POST /v1/messages/count_tokens
GET  /v1/models
GET  /health
```

## 支持的转换

- Anthropic `messages` -> OpenAI `messages`
- Anthropic `tools` -> OpenAI `tools`
- Anthropic `tool_use` -> OpenAI `tool_calls`
- Anthropic `tool_result` -> OpenAI `role=tool`
- OpenAI 普通文本回复 -> Anthropic `text`
- OpenAI `tool_calls` 回复 -> Anthropic `tool_use`
- 普通 JSON 响应
- SSE 流式响应
- base64 图片块转 OpenAI `image_url`

## 运行

```powershell
$env:AIRP_MODEL_BASE_URL="http://127.0.0.1:8317/v1"
$env:AIRP_MODEL_API_KEY="你的 OpenAI-compatible key"
$env:AIRP_MODEL_NAME="gpt-5.5"
$env:AIRP_ADAPTER_PORT="8766"

python -m openai_compatible_adapter.server
```

启动后使用：

```text
http://127.0.0.1:8766/v1/messages
```

## 环境变量

```text
AIRP_MODEL_BASE_URL       OpenAI-compatible base URL，例如 http://127.0.0.1:8317/v1
AIRP_MODEL_API_KEY        OpenAI-compatible API key
AIRP_MODEL_NAME           模型名，例如 gpt-5.5
AIRP_MODEL_TEMPERATURE    可选，默认 0.8
AIRP_MODEL_TIMEOUT        可选，默认 120
AIRP_ADAPTER_PORT         可选，默认 8766
```

也支持这些别名：

```text
OPENAI_BASE_URL
OPENAI_API_KEY
OPENAI_MODEL
```

## Claude Code / CCB 使用方式

先启动适配器，再让 Claude Code / CCB 指向适配器：

```powershell
$env:ANTHROPIC_BASE_URL="http://127.0.0.1:8766"
$env:ANTHROPIC_API_KEY="local-adapter"
$env:ANTHROPIC_AUTH_TOKEN="local-adapter"
$env:ANTHROPIC_MODEL="airp-openai-compatible"
$env:ANTHROPIC_DEFAULT_OPUS_MODEL="airp-openai-compatible"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL="airp-openai-compatible"
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL="airp-openai-compatible"

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
    "model": "airp-openai-compatible",
    "messages": [{"role": "user", "content": "Reply exactly OK"}],
    "max_tokens": 64,
})
```

## 适用场景

- 本地 OpenAI-compatible 反代
- 第三方 OpenAI-compatible 网关
- 本地模型服务
- Claude Code / CCB 需要接入非 Anthropic 官方接口
- Agent 工具需要保留工具调用能力
