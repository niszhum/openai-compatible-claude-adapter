"""
Standalone HTTP server for the Anthropic-to-OpenAI-compatible adapter.

Environment variables:
- LUKERCLAW_MODEL_BASE_URL, AIRP_MODEL_BASE_URL, or OPENAI_BASE_URL
- LUKERCLAW_MODEL_API_KEY, AIRP_MODEL_API_KEY, or OPENAI_API_KEY
- LUKERCLAW_MODEL_NAME, AIRP_MODEL_NAME, or OPENAI_MODEL
- LUKERCLAW_MODEL_TEMPERATURE or AIRP_MODEL_TEMPERATURE
- LUKERCLAW_MODEL_TIMEOUT or AIRP_MODEL_TIMEOUT
- LUKERCLAW_ADAPTER_PORT or AIRP_ADAPTER_PORT
"""
import http.server
import json
import os
import sys
import urllib.error
import urllib.parse

from .anthropic_openai_adapter import (
    AdapterConfig,
    AdapterNotConfigured,
    AnthropicOpenAIAdapter,
    error_payload,
    sse_encode,
    sse_events_for_message,
)


def env(name, default=""):
    names = [name]
    if name.startswith("AIRP_"):
        names.insert(0, "LUKERCLAW_" + name[len("AIRP_"):])
    elif name.startswith("LUKERCLAW_"):
        names.append("AIRP_" + name[len("LUKERCLAW_"):])
    for item in names:
        if os.environ.get(item):
            return os.environ.get(item, default).strip()
    return default


def number_env(name, default):
    try:
        return float(env(name, str(default)))
    except ValueError:
        return default


def adapter_config():
    return AdapterConfig(
        base_url=env("LUKERCLAW_MODEL_BASE_URL") or env("OPENAI_BASE_URL"),
        api_key=env("LUKERCLAW_MODEL_API_KEY") or env("OPENAI_API_KEY"),
        model=env("LUKERCLAW_MODEL_NAME") or env("OPENAI_MODEL"),
        temperature=number_env("LUKERCLAW_MODEL_TEMPERATURE", 0.8),
        timeout=number_env("LUKERCLAW_MODEL_TIMEOUT", 120),
    )


def send_json(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def send_error(handler, status, error_type, message):
    send_json(handler, error_payload(error_type, message), status)


def read_json(handler):
    length = int(handler.headers.get("Content-Length", 0))
    raw = handler.rfile.read(length).decode("utf-8") if length else "{}"
    return json.loads(raw or "{}")


class AdapterHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization,x-api-key,anthropic-version")
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        adapter = AnthropicOpenAIAdapter(adapter_config())
        if path == "/health":
            config = adapter_config()
            send_json(self, {
                "ok": True,
                "configured": bool(config.base_url and config.api_key and config.model),
                "targetBaseUrl": config.base_url,
                "targetModelName": config.model,
                "apiKeySet": bool(config.api_key),
            })
            return
        if path == "/v1/models":
            send_json(self, adapter.model_list())
            return
        send_error(self, 404, "not_found_error", "not found")

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        adapter = AnthropicOpenAIAdapter(adapter_config())
        try:
            body = read_json(self)
            if path == "/v1/messages/count_tokens":
                send_json(self, adapter.count_tokens(body))
                return
            if path == "/v1/messages":
                message = adapter.create_message(body)
                if body.get("stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "close")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    for event, data in sse_events_for_message(message):
                        self.wfile.write(sse_encode(event, data))
                        self.wfile.flush()
                else:
                    send_json(self, message)
                return
            send_error(self, 404, "not_found_error", "not found")
        except AdapterNotConfigured as exc:
            send_error(self, 503, "authentication_error", str(exc))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            send_error(self, exc.code, "api_error", f"target model http {exc.code}: {detail}")
        except json.JSONDecodeError as exc:
            send_error(self, 400, "invalid_request_error", f"invalid json: {exc}")
        except Exception as exc:
            send_error(self, 500, "api_error", str(exc) or exc.__class__.__name__)


def main():
    port = int(env("LUKERCLAW_ADAPTER_PORT", "8766"))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), AdapterHandler)
    print(f"Anthropic-to-OpenAI-compatible adapter listening on http://127.0.0.1:{port}")
    print("Routes: /health, /v1/models, /v1/messages, /v1/messages/count_tokens")
    server.serve_forever()


if __name__ == "__main__":
    main()
