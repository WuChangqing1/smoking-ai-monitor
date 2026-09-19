"""LLM 模型服务接入层（OpenAI-compatible）。

设计要点
--------
**统一抽象，不按厂商复制代码。** 目前实际实现只有一个
:class:`OpenAICompatibleProvider` —— llama.cpp server、DeepSeek、Qwen、
OpenAI 以及任何提供 ``/v1/chat/completions`` 的服务都用它。
厂商差异只体现在默认 Base URL 上（见 :data:`PROVIDER_PRESETS`）。

**请求由后端发出。** Base URL 的含义是「从后端所在机器能访问的地址」，
API Key 不下发前端、不进日志、不由浏览器直连模型服务。

**依赖只用标准库。** 一个 POST 请求不值得引入 OpenAI SDK / LangChain，
这里用 ``urllib.request``，并用 ``asyncio.to_thread`` 避免阻塞事件循环。

**模型不可用不能影响业务。** 所有失败都转换成 :class:`LLMError`，
由上层降级为 fallback，绝不向上抛裸异常。
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)

#: 连接测试与模型列表的超时（秒），比正式请求短
PROBE_TIMEOUT_SECONDS = 10.0

#: 服务类型 → 展示名与默认 Base URL。
#:
#: 全部走同一个 OpenAICompatibleProvider；这里只是帮用户预填地址，
#: **不包含任何厂商专属请求逻辑**。
PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "llama_cpp": {
        "label": "llama.cpp（本地）",
        "base_url": "http://127.0.0.1:8080/v1",
        "hint": "本地推理服务，API Key 可留空",
    },
    "openai_compatible": {
        "label": "OpenAI Compatible（通用）",
        "base_url": "",
        "hint": "任何提供 OpenAI 兼容接口的服务，填写其 Base URL 即可",
    },
}

#: 常见的兼容服务端点，仅用于帮用户预填 Base URL
BASE_URL_PRESETS: dict[str, str] = {
    "deepseek": "https://api.deepseek.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "openai": "https://api.openai.com/v1",
}


class LLMError(RuntimeError):
    """模型调用失败。

    ``kind`` 用于上层区分错误类型并向用户给出可理解的提示，
    不会把 Python traceback 暴露到接口响应里。
    """

    #: 错误类别 → 面向用户的说明
    KIND_TEXT: dict[str, str] = {
        "not_configured": "AI 模型服务未配置",
        "disabled": "AI 模型服务未启用",
        "connection": "无法连接 AI 模型服务",
        "timeout": "AI 模型服务响应超时",
        "unauthorized": "AI 模型服务鉴权失败",
        "forbidden": "AI 模型服务拒绝访问",
        "not_found": "AI 模型服务地址或模型不存在",
        "rate_limited": "AI 模型服务请求过于频繁",
        "server_error": "AI 模型服务内部错误",
        "bad_response": "AI 模型服务返回内容无法解析",
        "http_error": "AI 模型服务返回异常",
    }

    def __init__(self, kind: str, *, status: int | None = None, detail: str = "") -> None:
        self.kind = kind
        self.status = status
        self.detail = detail
        super().__init__(self.user_message())

    def user_message(self) -> str:
        base = self.KIND_TEXT.get(self.kind, "AI 模型服务调用失败")
        if self.status:
            return f"{base}（HTTP {self.status}）"
        return base


@dataclass(slots=True)
class LLMConfig:
    """一次调用所需的模型配置。

    ``api_key`` 用 ``repr=False`` 排除在 ``__repr__`` 之外 ——
    否则任何一次 ``logger.info("config=%s", config)`` 或未捕获异常的
    traceback 都会把密钥打进日志。**密钥不进日志是硬要求。**
    """

    provider: str = "llama_cpp"
    base_url: str = "http://127.0.0.1:8080/v1"
    model: str = ""
    api_key: str = field(default="", repr=False)
    temperature: float = 0.2
    max_tokens: int = 1024
    timeout: float = 30.0


@dataclass(slots=True)
class LLMResult:
    """模型返回的原始结果。"""

    text: str
    model: str = ""
    provider: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    """模型服务统一接口。

    以后要接入非 OpenAI 协议的厂商（Anthropic / Gemini 原生协议），
    实现这个 Protocol 即可，上层分析与缓存逻辑无需改动。
    """

    name: str

    async def chat(self, config: LLMConfig, system: str, user: str) -> LLMResult:
        """发起一次对话补全。失败时抛 :class:`LLMError`。"""
        ...

    async def list_models(self, config: LLMConfig) -> list[str]:
        """尽力获取模型列表（服务不支持时返回空列表，不算失败）。"""
        ...


# ---------------------------------------------------------------------------
# Base URL 规范化
# ---------------------------------------------------------------------------


def normalize_base_url(raw: str) -> str:
    """规范化 Base URL。

    只做必要处理：去空白、补协议、去重复斜杠、去尾部斜杠。
    必须保证后续拼接不会产生 ``/v1//chat/completions``。
    """
    url = (raw or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    # 折叠路径里的重复斜杠（保留协议部分的 //）
    scheme, sep, rest = url.partition("://")
    rest = "/".join(part for part in rest.split("/") if part != "")
    url = f"{scheme}{sep}{rest}"
    return url.rstrip("/")


def build_endpoint(base_url: str, path: str) -> str:
    """拼接接口地址，避免 ``/v1//chat/completions`` 这类重复斜杠。"""
    base = normalize_base_url(base_url)
    return f"{base}/{path.lstrip('/')}"


# ---------------------------------------------------------------------------
# OpenAI-compatible Provider
# ---------------------------------------------------------------------------


class OpenAICompatibleProvider:
    """OpenAI 兼容 Chat Completions 客户端。

    覆盖 llama.cpp server、DeepSeek、Qwen（DashScope 兼容模式）、OpenAI
    以及任何自建兼容端点。API Key 为空时不发 ``Authorization`` 头
    （llama.cpp 默认允许匿名）。
    """

    name = "openai_compatible"

    async def chat(self, config: LLMConfig, system: str, user: str) -> LLMResult:
        payload: dict[str, Any] = {
            "model": config.model or "default",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "stream": False,
        }
        data = await self._post(config, "chat/completions", payload, timeout=config.timeout)

        choices = data.get("choices") or []
        if not choices:
            raise LLMError("bad_response", detail="响应中没有 choices")
        message = choices[0].get("message") or {}
        text = message.get("content")
        if not isinstance(text, str) or not text.strip():
            raise LLMError("bad_response", detail="响应内容为空")

        return LLMResult(
            text=text,
            model=str(data.get("model") or config.model or ""),
            provider=self.name,
            usage=data.get("usage") or {},
        )

    async def list_models(self, config: LLMConfig) -> list[str]:
        """尝试读取 ``/models``。不支持时返回空列表（不视为错误）。"""
        try:
            data = await self._request(
                config, "GET", "models", None, timeout=PROBE_TIMEOUT_SECONDS
            )
        except LLMError:
            return []
        items = data.get("data")
        if not isinstance(items, list):
            return []
        result: list[str] = []
        for item in items:
            if isinstance(item, dict) and item.get("id"):
                result.append(str(item["id"]))
        return result

    # ---- HTTP ---------------------------------------------------------------

    async def _post(
        self,
        config: LLMConfig,
        path: str,
        payload: dict[str, Any],
        *,
        timeout: float,
    ) -> dict[str, Any]:
        return await self._request(config, "POST", path, payload, timeout=timeout)

    async def _request(
        self,
        config: LLMConfig,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        *,
        timeout: float,
    ) -> dict[str, Any]:
        url = build_endpoint(config.base_url, path)
        body = json.dumps(payload).encode("utf-8") if payload is not None else None

        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"

        # 阻塞的 urllib 放到线程里，避免卡住事件循环
        return await asyncio.to_thread(
            self._send, url, method, body, headers, max(1.0, float(timeout))
        )

    @staticmethod
    def _send(
        url: str,
        method: str,
        body: bytes | None,
        headers: dict[str, str],
        timeout: float,
    ) -> dict[str, Any]:
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            raise _http_error(exc.code) from exc
        except TimeoutError as exc:
            raise LLMError("timeout", detail=str(exc)) from exc
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, TimeoutError):
                raise LLMError("timeout", detail=str(reason)) from exc
            raise LLMError("connection", detail=str(reason)) from exc
        except OSError as exc:
            raise LLMError("connection", detail=str(exc)) from exc

        if not raw:
            raise LLMError("bad_response", detail="响应体为空")
        try:
            data = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise LLMError("bad_response", detail="响应不是合法 JSON") from exc
        if not isinstance(data, dict):
            raise LLMError("bad_response", detail="响应结构不是对象")
        return data


def _http_error(status: int) -> LLMError:
    """把 HTTP 状态码映射成错误类别。"""
    if status in (401,):
        return LLMError("unauthorized", status=status)
    if status in (403,):
        return LLMError("forbidden", status=status)
    if status in (404,):
        return LLMError("not_found", status=status)
    if status in (429,):
        return LLMError("rate_limited", status=status)
    if status >= 500:
        return LLMError("server_error", status=status)
    return LLMError("http_error", status=status)


#: 当前实际实现的 Provider（按服务类型取用；目前都指向同一个实现）
_PROVIDERS: dict[str, LLMProvider] = {
    "llama_cpp": OpenAICompatibleProvider(),
    "openai_compatible": OpenAICompatibleProvider(),
}


def get_provider(provider: str) -> LLMProvider:
    """按服务类型取 Provider；未知类型回退到通用兼容实现。"""
    return _PROVIDERS.get(provider, _PROVIDERS["openai_compatible"])
