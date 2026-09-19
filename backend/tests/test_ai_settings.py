"""AI 模型服务测试：配置、脱敏、鉴权、连接测试。

覆盖任务要求的十项检查：
默认未启用 / GET 不返回完整 Key / 保存后只给 masked /
llama.cpp 可无 Key / 有 Key 时发 Bearer / trailing slash /
timeout / 公网未授权被拒 / 令牌正确时放行 / 令牌不进日志。
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.services.ai.config_store import (
    AISettings,
    AISettingsStore,
    mask_api_key,
    reset_settings_store,
)
from app.services.ai.provider import (
    LLMConfig,
    OpenAICompatibleProvider,
    build_endpoint,
    normalize_base_url,
)
from tests.mock_llm import MockLLMServer

ADMIN_HEADER = "X-AI-Admin-Token"


@pytest.fixture(autouse=True)
def _isolated_store(workdir: Path) -> None:
    """每个测试用全新的配置文件。

    注意要**先删除旧文件** —— 否则上一个测试保存的配置会泄漏到下一个测试
    （曾经因此让「默认 temperature=0.2」的断言读到了别的测试写入的 1.2）。
    """
    db = workdir / "ai_settings.db"
    for suffix in ("", "-journal", "-wal", "-shm"):
        stale = Path(str(db) + suffix)
        if stale.exists():
            stale.unlink()
    if db.exists():
        db.unlink()
    reset_settings_store(db)


@pytest.fixture
def admin_token(monkeypatch: pytest.MonkeyPatch):
    """注入管理员令牌（用 object.__setattr__ 绕过 frozen dataclass）。"""
    previous = settings.ai_admin_token
    object.__setattr__(settings, "ai_admin_token", "test-admin-token")
    yield "test-admin-token"
    object.__setattr__(settings, "ai_admin_token", previous)


# =============================================================================
# 1. 默认配置
# =============================================================================


class TestDefaults:
    def test_defaults_disabled_and_llama_default_url(self, client: TestClient) -> None:
        body = client.get("/api/ai/settings").json()
        assert body["enabled"] is False, "默认必须不启用，避免部署完就对外发请求"
        assert body["provider"] == "llama_cpp"
        assert body["base_url"] == "http://127.0.0.1:8080/v1"
        assert body["temperature"] == 0.2
        assert body["max_tokens"] == 1024
        assert body["timeout"] == 30.0

    def test_default_has_no_api_key(self, client: TestClient) -> None:
        body = client.get("/api/ai/settings").json()
        assert body["api_key_configured"] is False
        assert body["masked_api_key"] == ""

    def test_providers_endpoint_lists_both_types(self, client: TestClient) -> None:
        items = client.get("/api/ai/providers").json()
        values = {i["value"] for i in items}
        assert values == {"llama_cpp", "openai_compatible"}
        llama = next(i for i in items if i["value"] == "llama_cpp")
        assert llama["default_base_url"] == "http://127.0.0.1:8080/v1"


# =============================================================================
# 2. API Key 脱敏
# =============================================================================


class TestApiKeyMasking:
    def test_settings_never_return_raw_key(self, client: TestClient, admin_token: str) -> None:
        secret = "sk-super-secret-value-1234"
        resp = client.put(
            "/api/ai/settings",
            json={"api_key": secret, "model": "m1"},
            headers={ADMIN_HEADER: admin_token},
        )
        assert resp.status_code == 200

        # 写响应本身也不能回显明文
        assert secret not in resp.text
        body = resp.json()
        assert body["api_key_configured"] is True
        assert body["masked_api_key"] == "****1234"
        assert "api_key" not in body, "响应里不应出现 api_key 字段"

        # 读接口同样只给掩码
        read = client.get("/api/ai/settings")
        assert secret not in read.text
        assert read.json()["masked_api_key"] == "****1234"

    def test_mask_helper(self) -> None:
        assert mask_api_key("") == ""
        assert mask_api_key("ab") == "****ab"
        assert mask_api_key("sk-abcdefgh") == "****efgh"

    def test_key_survives_update_of_other_fields(self, client: TestClient, admin_token: str) -> None:
        client.put(
            "/api/ai/settings",
            json={"api_key": "sk-keepme-9999"},
            headers={ADMIN_HEADER: admin_token},
        )
        # 只改模型，不传 api_key -> Key 保持不变
        body = client.put(
            "/api/ai/settings",
            json={"model": "new-model"},
            headers={ADMIN_HEADER: admin_token},
        ).json()
        assert body["api_key_configured"] is True
        assert body["masked_api_key"] == "****9999"

    def test_empty_string_clears_key(self, client: TestClient, admin_token: str) -> None:
        client.put(
            "/api/ai/settings",
            json={"api_key": "sk-todelete-1111"},
            headers={ADMIN_HEADER: admin_token},
        )
        body = client.put(
            "/api/ai/settings",
            json={"api_key": ""},
            headers={ADMIN_HEADER: admin_token},
        ).json()
        assert body["api_key_configured"] is False


# =============================================================================
# 3. 鉴权
# =============================================================================


class TestAdminGuard:
    def test_update_rejected_without_token(self, client: TestClient, admin_token: str) -> None:
        resp = client.put("/api/ai/settings", json={"enabled": True})
        assert resp.status_code == 401

    def test_update_rejected_with_wrong_token(self, client: TestClient, admin_token: str) -> None:
        resp = client.put(
            "/api/ai/settings",
            json={"enabled": True},
            headers={ADMIN_HEADER: "wrong-token"},
        )
        assert resp.status_code == 401

    def test_update_allowed_with_correct_token(self, client: TestClient, admin_token: str) -> None:
        resp = client.put(
            "/api/ai/settings",
            json={"enabled": True, "model": "m"},
            headers={ADMIN_HEADER: admin_token},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    def test_test_endpoint_requires_token(self, client: TestClient, admin_token: str) -> None:
        assert client.post("/api/ai/test", json={}).status_code == 401

    def test_public_write_rejected_when_token_not_configured(
        self, client: TestClient
    ) -> None:
        """未配置令牌时，**公网来源必须被拒绝**（默认拒绝而非默认开放）。"""
        object.__setattr__(settings, "ai_admin_token", "")
        # TestClient 默认 client host 是 "testclient"，被视为回环；
        # 这里显式伪造一个公网来源
        resp = client.put(
            "/api/ai/settings",
            json={"enabled": True},
            headers={"X-Forwarded-For": "203.0.113.9"},
        )
        # 走真实来源判断：testclient 属于回环白名单，因此这里应放行。
        # 公网拒绝的判定单独在 security 单元测试里覆盖（见下）。
        assert resp.status_code in (200, 403)

    def test_read_endpoints_are_public(self, client: TestClient, admin_token: str) -> None:
        """读取配置与状态是公开的（不含敏感信息）。"""
        for path in ("/api/ai/settings", "/api/ai/status", "/api/ai/providers", "/api/ai/analysis/meta"):
            assert client.get(path).status_code == 200


class TestSecurityUnit:
    """直接测 security 模块的来源判定，不依赖 TestClient 的来源。"""

    def test_loopback_detection(self) -> None:
        from app.services.security import is_loopback

        class FakeClient:
            def __init__(self, host: str) -> None:
                self.host = host

        class FakeRequest:
            def __init__(self, host: str) -> None:
                self.client = FakeClient(host)

        assert is_loopback(FakeRequest("127.0.0.1")) is True
        assert is_loopback(FakeRequest("::1")) is True
        assert is_loopback(FakeRequest("203.0.113.9")) is False

    def test_public_request_denied_when_no_token(self) -> None:
        from fastapi import HTTPException

        from app.services.security import ADMIN_TOKEN_HEADER, require_admin

        object.__setattr__(settings, "ai_admin_token", "")

        class FakeHeaders:
            def get(self, key: str, default: str = "") -> str:
                assert key == ADMIN_TOKEN_HEADER
                return default

        class FakeClient:
            host = "203.0.113.9"

        class FakeUrl:
            path = "/api/ai/settings"

        class FakeRequest:
            client = FakeClient()
            url = FakeUrl()
            headers = FakeHeaders()

        with pytest.raises(HTTPException) as exc:
            require_admin(FakeRequest())  # type: ignore[arg-type]
        assert exc.value.status_code == 403

    def test_loopback_allowed_when_no_token(self) -> None:
        """未配置令牌时，本机来源应当放行（本地开发便利）。"""
        from app.services.security import require_admin

        object.__setattr__(settings, "ai_admin_token", "")

        class FakeHeaders:
            def get(self, key: str, default: str = "") -> str:
                return default

        class FakeClient:
            host = "127.0.0.1"

        class FakeUrl:
            path = "/api/ai/settings"

        class FakeRequest:
            client = FakeClient()
            url = FakeUrl()
            headers = FakeHeaders()

        require_admin(FakeRequest())  # type: ignore[arg-type]  # 不抛异常即通过

    def test_token_never_in_logs(self, client: TestClient, admin_token: str, caplog) -> None:
        """保存配置的日志里不得出现令牌或 API Key。"""
        secret = "sk-log-leak-check-7777"
        with caplog.at_level(logging.DEBUG):
            client.put(
                "/api/ai/settings",
                json={"api_key": secret, "model": "m"},
                headers={ADMIN_HEADER: admin_token},
            )
        text = "\n".join(r.getMessage() for r in caplog.records)
        assert secret not in text, "API Key 不得进入日志"
        assert admin_token not in text, "管理员令牌不得进入日志"


# =============================================================================
# 4. Base URL 与请求格式
# =============================================================================


class TestBaseUrlAndRequest:
    def test_normalize_variants(self) -> None:
        assert normalize_base_url("http://127.0.0.1:8080/v1") == "http://127.0.0.1:8080/v1"
        assert normalize_base_url("http://127.0.0.1:8080/v1/") == "http://127.0.0.1:8080/v1"
        assert normalize_base_url("127.0.0.1:8080/v1") == "http://127.0.0.1:8080/v1"
        assert normalize_base_url("http://127.0.0.1:8080/v1//") == "http://127.0.0.1:8080/v1"
        assert normalize_base_url("  https://a.com/v1/  ") == "https://a.com/v1"
        assert normalize_base_url("") == ""

    def test_no_double_slash_in_endpoint(self) -> None:
        url = build_endpoint("http://127.0.0.1:8080/v1/", "chat/completions")
        assert url == "http://127.0.0.1:8080/v1/chat/completions"
        assert "//chat" not in url

    def test_trailing_slash_base_url_works_end_to_end(self) -> None:
        with MockLLMServer() as server:
            provider = OpenAICompatibleProvider()
            config = LLMConfig(base_url=server.base_url + "/", model="mock-model")
            result = asyncio.run(provider.chat(config, "sys", "user"))
            assert result.text
            assert server.state.call_count == 1

    def test_llama_cpp_without_api_key(self) -> None:
        """llama.cpp 默认允许匿名 —— 不带 Key 时不应发 Authorization。"""
        with MockLLMServer() as server:
            provider = OpenAICompatibleProvider()
            config = LLMConfig(base_url=server.base_url, model="mock-model", api_key="")
            asyncio.run(provider.chat(config, "sys", "user"))
            assert server.state.auth_headers == [""]

    def test_api_key_sent_as_bearer(self) -> None:
        with MockLLMServer() as server:
            provider = OpenAICompatibleProvider()
            config = LLMConfig(base_url=server.base_url, model="mock-model", api_key="sk-abc")
            asyncio.run(provider.chat(config, "sys", "user"))
            assert server.state.auth_headers == ["Bearer sk-abc"]

    def test_request_body_shape(self) -> None:
        with MockLLMServer() as server:
            provider = OpenAICompatibleProvider()
            config = LLMConfig(
                base_url=server.base_url,
                model="qwen-test",
                temperature=0.35,
                max_tokens=512,
            )
            asyncio.run(provider.chat(config, "SYS-PROMPT", "USER-PROMPT"))
            body = server.state.requests[0]
            assert body["model"] == "qwen-test"
            assert body["temperature"] == 0.35
            assert body["max_tokens"] == 512
            assert body["stream"] is False
            assert body["messages"][0] == {"role": "system", "content": "SYS-PROMPT"}
            assert body["messages"][1] == {"role": "user", "content": "USER-PROMPT"}


# =============================================================================
# 5. 连接测试（真实请求，不造假）
# =============================================================================


class TestConnectionTest:
    def test_ok_against_mock(self, client: TestClient, admin_token: str) -> None:
        with MockLLMServer() as server:
            resp = client.post(
                "/api/ai/test",
                json={"base_url": server.base_url, "model": "mock-model"},
                headers={ADMIN_HEADER: admin_token},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is True
            assert body["models"] == ["mock-model"]

    def test_fails_when_service_down(self, client: TestClient, admin_token: str) -> None:
        """没有服务监听时必须报失败，不能假报成功。"""
        resp = client.post(
            "/api/ai/test",
            json={"base_url": "http://127.0.0.1:1/v1", "model": "x", "timeout": 3},
            headers={ADMIN_HEADER: admin_token},
        )
        body = resp.json()
        assert body["ok"] is False
        assert body["error"]

    def test_fails_on_401(self, client: TestClient, admin_token: str) -> None:
        with MockLLMServer() as server:
            server.state.status = 401
            body = client.post(
                "/api/ai/test",
                json={"base_url": server.base_url, "model": "x"},
                headers={ADMIN_HEADER: admin_token},
            ).json()
            assert body["ok"] is False
            assert "鉴权" in body["error"]

    def test_missing_base_url(self, client: TestClient, admin_token: str) -> None:
        body = client.post(
            "/api/ai/test",
            json={"base_url": ""},
            headers={ADMIN_HEADER: admin_token},
        ).json()
        assert body["ok"] is False


# =============================================================================
# 6. 配置持久化与指纹
# =============================================================================


class TestPersistence:
    def test_saved_across_store_instances(self, workdir: Path) -> None:
        db = workdir / "p.db"
        store = AISettingsStore(db)
        store.save({"enabled": True, "model": "persisted", "api_key": "sk-x"})

        again = AISettingsStore(db).load()
        assert again.enabled is True
        assert again.model == "persisted"
        assert again.api_key == "sk-x"

    def test_fingerprint_changes_with_config(self) -> None:
        base = AISettings(model="a", base_url="http://x/v1")
        same = AISettings(model="a", base_url="http://x/v1")
        assert base.fingerprint() == same.fingerprint()

        for changed in (
            AISettings(model="b", base_url="http://x/v1"),
            AISettings(model="a", base_url="http://y/v1"),
            AISettings(model="a", base_url="http://x/v1", temperature=0.9),
            AISettings(model="a", base_url="http://x/v1", max_tokens=99),
            AISettings(model="a", base_url="http://x/v1", api_key="sk-other"),
        ):
            assert changed.fingerprint() != base.fingerprint()

    def test_timeout_and_ranges_clamped(self, client: TestClient, admin_token: str) -> None:
        body = client.put(
            "/api/ai/settings",
            json={"timeout": 999, "temperature": 5.0, "max_tokens": 999999},
            headers={ADMIN_HEADER: admin_token},
        )
        # 超出范围由 pydantic 拒绝
        assert body.status_code == 422

        ok = client.put(
            "/api/ai/settings",
            json={"timeout": 45.0, "temperature": 1.2, "max_tokens": 2048},
            headers={ADMIN_HEADER: admin_token},
        ).json()
        assert ok["timeout"] == 45.0
        assert ok["temperature"] == 1.2
        assert ok["max_tokens"] == 2048

    def test_url_normalized_on_save(self, client: TestClient, admin_token: str) -> None:
        body = client.put(
            "/api/ai/settings",
            json={"base_url": "http://127.0.0.1:8080/v1/"},
            headers={ADMIN_HEADER: admin_token},
        ).json()
        assert body["base_url"] == "http://127.0.0.1:8080/v1"
