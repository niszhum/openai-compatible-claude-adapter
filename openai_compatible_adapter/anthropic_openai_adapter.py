"""
Standalone Anthropic Messages API facade for OpenAI-compatible chat endpoints.

The adapter is intentionally free of host project imports. Host projects only
need to provide AdapterConfig, then route /v1/messages, /v1/messages/count_tokens
and /v1/models to this module.
"""
from dataclasses import dataclass
import json
import time
import urllib.error
import urllib.request
import uuid


DEFAULT_ANTHROPIC_MODEL = "lukerclaw-openai-compatible"


class AdapterNotConfigured(RuntimeError):
    pass


@dataclass
class AdapterConfig:
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    anthropic_model: str = DEFAULT_ANTHROPIC_MODEL
    temperature: float = 0.8
    timeout: float = 120.0


def chat_endpoint(base_url):
    base = str(base_url or "").rstrip("/")
    if not base:
        return ""
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


class AnthropicOpenAIAdapter:
    def __init__(self, config):
        self.config = config

    def model_list(self):
        display_model = self.config.model or self.config.anthropic_model or DEFAULT_ANTHROPIC_MODEL
        return {
            "object": "list",
            "data": [{
                "id": self.config.anthropic_model or DEFAULT_ANTHROPIC_MODEL,
                "object": "model",
                "type": "model",
                "display_name": display_model,
                "created_at": "2026-01-01T00:00:00Z"
            }],
            "has_more": False
        }

    def count_tokens(self, body):
        text = json.dumps(body.get("system", ""), ensure_ascii=False)
        text += json.dumps(body.get("messages", []), ensure_ascii=False)
        return {"input_tokens": max(1, len(text) // 4)}

    def create_message(self, body):
        openai_payload = self.anthropic_to_openai(body)
        openai_data = self.call_openai(openai_payload)
        return self.openai_to_anthropic(body, openai_data)

    def anthropic_to_openai(self, body):
        messages = []
        system_text = content_to_text(body.get("system"))
        if system_text:
            messages.append({"role": "system", "content": system_text})

        for item in body.get("messages", []):
            role = item.get("role", "user")
            content = item.get("content", "")
            messages.extend(convert_message(role, content))

        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False
        }
        if not payload["model"]:
            raise AdapterNotConfigured("OpenAI-compatible target model is not configured")

        if body.get("temperature") is not None:
            payload["temperature"] = body.get("temperature")
        else:
            payload["temperature"] = self.config.temperature

        max_tokens = body.get("max_tokens")
        if isinstance(max_tokens, int) and max_tokens > 0:
            payload["max_tokens"] = max_tokens

        tools = convert_tools(body.get("tools"))
        if tools:
            payload["tools"] = tools
            tool_choice = convert_tool_choice(body.get("tool_choice"))
            if tool_choice:
                payload["tool_choice"] = tool_choice

        return payload

    def call_openai(self, payload):
        if not self.config.base_url or not self.config.api_key or not payload.get("model"):
            raise AdapterNotConfigured("OpenAI-compatible target is not configured")

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            chat_endpoint(self.config.base_url),
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.config.api_key
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=float(self.config.timeout or 120)) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def openai_to_anthropic(self, request_body, data):
        choice = ((data.get("choices") or [{}])[0] or {}) if isinstance(data, dict) else {}
        openai_message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        content_blocks = []
        text = openai_message.get("content") or choice.get("text") or ""
        if text:
            content_blocks.append({"type": "text", "text": str(text)})

        for call in openai_message.get("tool_calls") or []:
            function = call.get("function") if isinstance(call.get("function"), dict) else {}
            content_blocks.append({
                "type": "tool_use",
                "id": str(call.get("id") or "toolu_" + uuid.uuid4().hex),
                "name": str(function.get("name") or ""),
                "input": parse_json_object(function.get("arguments"))
            })

        finish_reason = choice.get("finish_reason")
        stop_reason = "tool_use" if any(block.get("type") == "tool_use" for block in content_blocks) else stop_reason_from_openai(finish_reason)
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return {
            "id": "msg_" + uuid.uuid4().hex,
            "type": "message",
            "role": "assistant",
            "model": request_body.get("model") or self.config.anthropic_model or DEFAULT_ANTHROPIC_MODEL,
            "content": content_blocks or [{"type": "text", "text": ""}],
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {
                "input_tokens": int(usage.get("prompt_tokens") or 0),
                "output_tokens": int(usage.get("completion_tokens") or 0)
            }
        }


def convert_message(role, content):
    if isinstance(content, str):
        return [{"role": role, "content": content}]
    if not isinstance(content, list):
        return [{"role": role, "content": str(content or "")}]

    if role == "assistant":
        text_parts = []
        tool_calls = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                text_parts.append(str(block.get("text", "")))
            elif block_type == "tool_use":
                tool_calls.append({
                    "id": str(block.get("id") or "toolu_" + uuid.uuid4().hex),
                    "type": "function",
                    "function": {
                        "name": str(block.get("name") or ""),
                        "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False)
                    }
                })
        msg = {"role": "assistant", "content": "\n".join([p for p in text_parts if p]) or None}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        return [msg]

    result = []
    text_blocks = []
    rich_blocks = []
    for block in content:
        if not isinstance(block, dict):
            text_blocks.append(str(block))
            continue
        block_type = block.get("type")
        if block_type == "text":
            text_blocks.append(str(block.get("text", "")))
        elif block_type == "image":
            image = convert_image_block(block)
            if image:
                rich_blocks.append(image)
        elif block_type == "tool_result":
            if text_blocks or rich_blocks:
                result.append(openai_user_message(text_blocks, rich_blocks))
                text_blocks, rich_blocks = [], []
            result.append({
                "role": "tool",
                "tool_call_id": str(block.get("tool_use_id") or ""),
                "content": content_to_text(block.get("content", ""))
            })
    if text_blocks or rich_blocks or not result:
        result.append(openai_user_message(text_blocks, rich_blocks))
    return result


def openai_user_message(text_blocks, rich_blocks):
    text = "\n".join([p for p in text_blocks if p])
    if rich_blocks:
        content = []
        if text:
            content.append({"type": "text", "text": text})
        content.extend(rich_blocks)
        return {"role": "user", "content": content}
    return {"role": "user", "content": text}


def convert_image_block(block):
    source = block.get("source") if isinstance(block.get("source"), dict) else {}
    if source.get("type") == "base64" and source.get("data") and source.get("media_type"):
        return {
            "type": "image_url",
            "image_url": {
                "url": "data:" + source["media_type"] + ";base64," + source["data"]
            }
        }
    return None


def convert_tools(tools):
    if not isinstance(tools, list):
        return None
    converted = []
    for tool in tools:
        if not isinstance(tool, dict) or not tool.get("name"):
            continue
        converted.append({
            "type": "function",
            "function": {
                "name": tool.get("name"),
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema") or {"type": "object", "properties": {}}
            }
        })
    return converted or None


def convert_tool_choice(tool_choice):
    if not isinstance(tool_choice, dict):
        return None
    choice_type = tool_choice.get("type")
    if choice_type == "auto":
        return "auto"
    if choice_type == "none":
        return "none"
    if choice_type == "any":
        return "required"
    if choice_type == "tool" and tool_choice.get("name"):
        return {"type": "function", "function": {"name": tool_choice["name"]}}
    return None


def stop_reason_from_openai(finish_reason):
    if finish_reason == "length":
        return "max_tokens"
    if finish_reason == "tool_calls":
        return "tool_use"
    return "end_turn"


def parse_json_object(value):
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def content_to_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                elif block.get("type") == "tool_result":
                    parts.append(content_to_text(block.get("content", "")))
            else:
                parts.append(str(block))
        return "\n".join([p for p in parts if p])
    if content is None:
        return ""
    return str(content)


def sse_events_for_message(message):
    start_message = dict(message)
    start_message["content"] = []
    start_message["stop_reason"] = None
    yield "message_start", {"type": "message_start", "message": start_message}

    for index, block in enumerate(message.get("content", [])):
        if block.get("type") == "tool_use":
            start_block = {
                "type": "tool_use",
                "id": block.get("id"),
                "name": block.get("name"),
                "input": {}
            }
            yield "content_block_start", {
                "type": "content_block_start",
                "index": index,
                "content_block": start_block
            }
            yield "content_block_delta", {
                "type": "content_block_delta",
                "index": index,
                "delta": {
                    "type": "input_json_delta",
                    "partial_json": json.dumps(block.get("input") or {}, ensure_ascii=False)
                }
            }
        else:
            yield "content_block_start", {
                "type": "content_block_start",
                "index": index,
                "content_block": {"type": "text", "text": ""}
            }
            yield "content_block_delta", {
                "type": "content_block_delta",
                "index": index,
                "delta": {"type": "text_delta", "text": block.get("text", "")}
            }
        yield "content_block_stop", {
            "type": "content_block_stop",
            "index": index
        }

    yield "message_delta", {
        "type": "message_delta",
        "delta": {
            "stop_reason": message.get("stop_reason"),
            "stop_sequence": None
        },
        "usage": {"output_tokens": message.get("usage", {}).get("output_tokens", 0)}
    }
    yield "message_stop", {"type": "message_stop"}


def sse_encode(event, data):
    payload = "event: " + event + "\n"
    payload += "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"
    return payload.encode("utf-8")


def error_payload(error_type, message):
    return {
        "type": "error",
        "error": {
            "type": error_type,
            "message": message
        }
    }


def timestamp_ms():
    return int(time.time() * 1000)
