"""API Key 安全测试：静态加密、日志脱敏、接口不回显、Prompt 不携带。

这是**硬要求**：密钥不得出现在任何日志、接口响应、前端产物、
Prompt、异常信息或版本库中。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.services.ai.config_store import AISettingsStore, reset_settings_store
from app.services.ai.crypto import (
    ENCRYPTED_PREFIX,
    decrypt_api_key,
    encrypt_api_key,
    is_encrypted,
)
from app.services.ai.provider import LLMConfig

ADMIN_HEADER = "X-AI-Admin-Token"
SECRET_TOKEN = "admin-token-for-crypto-tests"
SECRET_KEY = "sk-dangerous-plaintext-value-9876"


@pytest.fixture
def admin_token():
    previous = settings.ai_admin_token
    object.__setattr__(settings, "ai_admin_token", SECRET_TOKEN)
    yield SECRET_TOKEN
    object.__setattr__(settings, "ai_admin_token", previous)


@pytest.fixture(autouse=True)
def _isolated_store(workdir: Path) -> None:
    db = workdir / "crypto_settings.db"
    for suffix in ("", "-journal", "-wal", "-shm"):
        stale = Path(str(db) + suffix)
        if stale.exists():
            stale.unlink()
    reset_settings_store(db)


# =============================================================================
# 1. 加密原语
# =============================================================================


class TestCrypto:
    def test_roundtrip(self) -> None:
        encrypted = encrypt_api_key(SECRET_KEY, SECRET_TOKEN)
        assert is_encrypted(encrypted)
        assert decrypt_api_key(encrypted, SECRET_TOKEN) == SECRET_KEY

    def test_plaintext_not_present_in_ciphertext(self) -> None:
        encrypted = encrypt_api_key(SECRET_KEY, SECRET_TOKEN)
        assert SECRET_KEY not in encrypted
        # 连片段也不应出现
        assert "dangerous" not in encrypted

    def test_ciphertext_is_randomized(self) -> None:
        """相同明文两次加密得到不同密文（随机 nonce）。"""
        a = encrypt_api_key(SECRET_KEY, SECRET_TOKEN)
        b = encrypt_api_key(SECRET_KEY, SECRET_TOKEN)
        assert a != b
        assert decrypt_api_key(a, SECRET_TOKEN) == decrypt_api_key(b, SECRET_TOKEN) == SECRET_KEY

    def test_wrong_secret_yields_empty(self) -> None:
        """换令牌后解不开，返回空 —— fail-safe，不回退明文。"""
        encrypted = encrypt_api_key(SECRET_KEY, SECRET_TOKEN)
        assert decrypt_api_key(encrypted, "another-token") == ""

    def test_tampered_ciphertext_rejected(self) -> None:
        encrypted = encrypt_api_key(SECRET_KEY, SECRET_TOKEN)
        tampered = encrypted[:-4] + ("AAAA" if not encrypted.endswith("AAAA") else "BBBB")
        assert decrypt_api_key(tampered, SECRET_TOKEN) == ""

    def test_empty_inputs(self) -> None:
        assert encrypt_api_key("", SECRET_TOKEN) == ""
        assert decrypt_api_key("", SECRET_TOKEN) == ""

    def test_prefix_is_versioned(self) -> None:
        assert ENCRYPTED_PREFIX == "enc:v1:"

    def test_legacy_plaintext_still_readable(self) -> None:
        """历史明文存量仍可读（并会记一条不含内容的提醒）。"""
        assert decrypt_api_key("sk-legacy-plain", SECRET_TOKEN) == "sk-legacy-plain"


# =============================================================================
# 2. 落库加密
# =============================================================================


class TestStorageEncryption:
    def test_db_stores_ciphertext(self, admin_token: str, workdir: Path) -> None:
        """数据库文件里不得出现明文密钥。"""
        db = workdir / "crypto_settings.db"
        AISettingsStore(db).save({"api_key": SECRET_KEY, "model": "m"})

        raw = db.read_bytes()
        assert SECRET_KEY.encode() not in raw, "数据库文件中出现了明文 API Key"
        assert b"dangerous" not in raw

    def test_load_returns_plaintext_for_internal_use(self, admin_token: str, workdir: Path) -> None:
        db = workdir / "crypto_settings.db"
        AISettingsStore(db).save({"api_key": SECRET_KEY})
        assert AISettingsStore(db).load().api_key == SECRET_KEY

    def test_key_unreadable_after_token_rotation(self, admin_token: str, workdir: Path) -> None:
        db = workdir / "crypto_settings.db"
        AISettingsStore(db).save({"api_key": SECRET_KEY})

        # 换令牌后旧密文解不开，按"未配置"处理
        object.__setattr__(settings, "ai_admin_token", "rotated-token")
        loaded = AISettingsStore(db).load()
        assert loaded.api_key == ""

    def test_public_view_hides_key(self, admin_token: str, workdir: Path) -> None:
        db = workdir / "crypto_settings.db"
        saved = AISettingsStore(db).save({"api_key": SECRET_KEY})
        public = saved.to_public()
        assert "api_key" not in public
        assert public["api_key_configured"] is True
        assert public["masked_api_key"] == "****9876"
        assert SECRET_KEY not in json.dumps(public, ensure_ascii=False)


# =============================================================================
# 3. repr / 日志
# =============================================================================


class TestNoLeakInRepr:
    def test_llm_config_repr_hides_key(self) -> None:
        """``LLMConfig`` 的 repr 必须排除密钥。

        否则任何 ``logger.info("cfg=%s", cfg)`` 或未捕获异常的 traceback
        都会把密钥写进日志。
        """
        config = LLMConfig(api_key=SECRET_KEY, model="m")
        assert SECRET_KEY not in repr(config)
        assert SECRET_KEY not in str(config)
        assert SECRET_KEY not in f"{config}"

    def test_settings_repr_contains_key_only_for_internal_use(self) -> None:
        """AISettings 是内部结构，但 to_public 必须干净。"""
        from app.services.ai.config_store import AISettings

        s = AISettings(api_key=SECRET_KEY)
        assert SECRET_KEY not in json.dumps(s.to_public(), ensure_ascii=False)


class TestNoLeakInLogs:
    def test_save_does_not_log_key(self, admin_token: str, workdir: Path, caplog) -> None:
        with caplog.at_level(logging.DEBUG):
            AISettingsStore(workdir / "crypto_settings.db").save(
                {"api_key": SECRET_KEY, "model": "m"}
            )
        text = "\n".join(r.getMessage() for r in caplog.records)
        assert SECRET_KEY not in text
        assert admin_token not in text

    def test_decrypt_failure_log_has_no_ciphertext(self, workdir: Path, caplog) -> None:
        encrypted = encrypt_api_key(SECRET_KEY, "some-token")
        with caplog.at_level(logging.DEBUG):
            decrypt_api_key(encrypted, "wrong-token")
        text = "\n".join(r.getMessage() for r in caplog.records)
        assert SECRET_KEY not in text
        assert encrypted not in text, "日志里不应出现密文本身"

    def test_api_call_does_not_log_key(self, client: TestClient, admin_token: str, caplog) -> None:
        with caplog.at_level(logging.DEBUG):
            client.put(
                "/api/ai/settings",
                json={"api_key": SECRET_KEY, "model": "m"},
                headers={ADMIN_HEADER: admin_token},
            )
        text = "\n".join(r.getMessage() for r in caplog.records)
        assert SECRET_KEY not in text
        assert admin_token not in text


# =============================================================================
# 4. 接口与 Prompt
# =============================================================================


class TestNoLeakInApi:
    def test_get_settings_never_returns_key(self, client: TestClient, admin_token: str) -> None:
        client.put(
            "/api/ai/settings",
            json={"api_key": SECRET_KEY, "model": "m"},
            headers={ADMIN_HEADER: admin_token},
        )
        resp = client.get("/api/ai/settings")
        assert SECRET_KEY not in resp.text
        body = resp.json()
        assert "api_key" not in body
        assert body["masked_api_key"] == "****9876"

    def test_put_response_never_echoes_key(self, client: TestClient, admin_token: str) -> None:
        resp = client.put(
            "/api/ai/settings",
            json={"api_key": SECRET_KEY, "model": "m"},
            headers={ADMIN_HEADER: admin_token},
        )
        assert SECRET_KEY not in resp.text

    def test_status_endpoint_has_no_key(self, client: TestClient, admin_token: str) -> None:
        client.put(
            "/api/ai/settings",
            json={"api_key": SECRET_KEY, "model": "m"},
            headers={ADMIN_HEADER: admin_token},
        )
        assert SECRET_KEY not in client.get("/api/ai/status").text

    def test_error_response_has_no_key(self, client: TestClient, admin_token: str) -> None:
        """即使配置非法，错误响应里也不能带出密钥。"""
        resp = client.put(
            "/api/ai/settings",
            json={"api_key": SECRET_KEY, "temperature": 99},
            headers={ADMIN_HEADER: admin_token},
        )
        assert resp.status_code == 422
        assert SECRET_KEY not in resp.text

    def test_prompt_carries_no_key(self, client: TestClient, admin_token: str) -> None:
        """发给模型的 Prompt 里不得出现 API Key 或管理员令牌。"""
        from tests.mock_llm import MockLLMServer

        with MockLLMServer() as server:
            client.put(
                "/api/ai/settings",
                json={
                    "enabled": True,
                    "provider": "openai_compatible",
                    "base_url": server.base_url,
                    "model": "mock-model",
                    "api_key": SECRET_KEY,
                },
                headers={ADMIN_HEADER: admin_token},
            )
            client.get("/api/ai/analysis/current?type=warning")

            assert server.state.call_count >= 1
            body = server.state.requests[0]
            blob = body["messages"][0]["content"] + body["messages"][1]["content"]
            assert SECRET_KEY not in blob
            assert admin_token not in blob

            # 但 Authorization 头应当带上密钥（这是唯一该出现的地方）
            assert server.state.auth_headers[0] == f"Bearer {SECRET_KEY}"
