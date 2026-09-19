"""测试用的 mock OpenAI-compatible 模型服务。

**测试绝不访问真实模型 API**（DeepSeek / OpenAI / Qwen / 公网）。
这里用标准库起一个本地 HTTP 服务，完整模拟：

* ``GET  /v1/models``              模型列表
* ``POST /v1/chat/completions``    对话补全
* 各种故障：401 / 429 / 500 / 超时 / 空响应 / 非法 JSON / 模型不存在

同时记录**收到的请求**，用于断言：
Bearer 头是否正确、Prompt 里有没有泄露敏感信息、模型被调用了多少次。
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

#: 一份正常的结构化输出
GOOD_JSON = json.dumps(
    {
        "summary": "测距持续下降伴随覆盖率上升，符合物料堆积的发展特征。",
        "possible_causes": ["上游进料量偏大", "下游输送速度下降"],
        "recommended_checks": ["检查落料口是否积料", "核对上游计量设备"],
        "recommended_actions": ["降低上游进料量", "清理落料口"],
        "related_cases": ["EVT-20250519-02"],
        "evidence_basis": ["雷达测距连续下降", "视觉覆盖率上升"],
    },
    ensure_ascii=False,
)

#: 被 Markdown 代码块包住的 JSON
FENCED_JSON = f"```json\n{GOOD_JSON}\n```"

#: 完全不是 JSON 的普通文本
PLAIN_TEXT = "当前测距持续下降，建议检查落料口积料情况。"


@dataclass
class MockState:
    """mock 服务的行为与记录。"""

    #: 返回体（原样写入 content 字段）
    content: str = GOOD_JSON
    #: 强制返回的 HTTP 状态码（0 表示正常 200）
    status: int = 200
    #: 是否延迟响应（用于超时测试）
    delay: float = 0.0
    #: 是否返回非法 JSON 体
    malformed: bool = False
    #: 是否返回空 content
    empty_content: bool = False
    #: /models 返回的模型列表
    models: list[str] = field(default_factory=lambda: ["mock-model"])
    #: 收到的 chat 请求（解析后的 body 与 headers）
    requests: list[dict[str, Any]] = field(default_factory=list)
    #: 收到的 Authorization 头
    auth_headers: list[str] = field(default_factory=list)

    @property
    def call_count(self) -> int:
        return len(self.requests)

    def reset(self) -> None:
        self.requests.clear()
        self.auth_headers.clear()


class MockLLMServer:
    """本地 mock 模型服务。用作上下文管理器。"""

    def __init__(self) -> None:
        self.state = MockState()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.port = 0

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def __enter__(self) -> MockLLMServer:
        state = self.state

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args: Any) -> None:  # 静默
                return

            # ---- 工具 ----
            def _send(self, status: int, payload: Any) -> None:
                body = (
                    payload
                    if isinstance(payload, bytes)
                    else json.dumps(payload, ensure_ascii=False).encode("utf-8")
                )
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            # ---- GET /v1/models ----
            def do_GET(self) -> None:
                if self.path.rstrip("/").endswith("/models"):
                    if state.status >= 400:
                        self._send(state.status, {"error": "mock error"})
                        return
                    self._send(200, {"data": [{"id": m} for m in state.models]})
                    return
                self._send(404, {"error": "not found"})

            # ---- POST /v1/chat/completions ----
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    body = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    body = {"_raw": raw.decode("utf-8", errors="replace")}

                state.requests.append(body)
                state.auth_headers.append(self.headers.get("Authorization") or "")

                if state.delay:
                    import time

                    time.sleep(state.delay)

                if state.status >= 400:
                    self._send(state.status, {"error": {"message": "mock error"}})
                    return

                if state.malformed:
                    self._send(200, b"{not json at all")
                    return

                content = "" if state.empty_content else state.content
                self._send(
                    200,
                    {
                        "id": "mock-completion",
                        "object": "chat.completion",
                        "model": body.get("model") or "mock-model",
                        "choices": [
                            {"index": 0, "message": {"role": "assistant", "content": content}}
                        ],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
                    },
                )

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=3)
