# OpenAI-compatible adapter

这个目录是从 AIRP 中独立提取的 Claude/Anthropic Messages API 到 OpenAI-compatible `/chat/completions` 的适配器。

## 能力范围

- `POST /v1/messages`
- `POST /v1/messages/count_tokens`
- `GET /v1/models`
- Anthropic `tool_use` 与 OpenAI `tool_calls` 互转
- Anthropic `tool_result` 与 OpenAI `role=tool` 互转
- 文本、base64 图片块、非流式响应、SSE 流式事件

## 单独运行

```powershell
$env:AIRP_MODEL_BASE_URL="http://127.0.0.1:8317/v1"
$env:AIRP_MODEL_API_KEY="你的 OpenAI-compatible key"
$env:AIRP_MODEL_NAME="gpt-5.5"
$env:AIRP_ADAPTER_PORT="8766"
python -m openai_compatible_adapter.server
```

服务地址：

```text
http://127.0.0.1:8766/v1/messages
http://127.0.0.1:8766/v1/messages/count_tokens
http://127.0.0.1:8766/v1/models
```

## 在宿主项目中嵌入

```python
from openai_compatible_adapter import AdapterConfig, AnthropicOpenAIAdapter

adapter = AnthropicOpenAIAdapter(AdapterConfig(
    base_url="http://127.0.0.1:8317/v1",
    api_key="...",
    model="gpt-5.5",
))

message = adapter.create_message({
    "model": "airp-openai-compatible",
    "messages": [{"role": "user", "content": "Reply OK"}],
    "max_tokens": 64,
})
```

AIRP 项目内的 `skills/anthropic_openai_proxy.py` 现在只是这个独立适配器的 HTTP handler 包装层。
