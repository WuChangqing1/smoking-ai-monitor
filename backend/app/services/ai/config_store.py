"""AI 模型配置的持久化与敏感信息保护。

存储
----
复用项目已有的 SQLite（每个项目各自独立的数据目录），新增
``ai_model_settings`` 单行表。**两个项目的配置互不相通** ——
它们本来就是两套数据库。

安全
----
API Key 存进来，但**永远不通过读取接口原样返回**：
读取只给 ``api_key_configured`` 与 ``masked_api_key``。
日志、异常、Prompt 里也不出现明文 Key。
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.services.ai.crypto import decrypt_api_key, encrypt_api_key
from app.services.ai.provider import LLMConfig, normalize_base_url

logger = logging.getLogger(__name__)


def get_admin_secret() -> str:
    """静态加密用的机密 —— 取自部署时配置的管理员令牌。

    每次读取（便于测试注入）。未配置时返回空串，此时不做加密，
    但那种部署下写接口本来也只允许本机访问。
    """
    return (settings.ai_admin_token or "").strip()

#: 默认配置。**默认不启用**，避免部署完就对外发请求。
DEFAULT_PROVIDER = "llama_cpp"
DEFAULT_BASE_URL = "http://127.0.0.1:8080/v1"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TIMEOUT = 30.0

#: 可调范围（与设置页的输入约束一致）
TEMPERATURE_RANGE = (0.0, 2.0)
MAX_TOKENS_RANGE = (64, 8192)
TIMEOUT_RANGE = (3.0, 120.0)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_model_settings (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    provider    TEXT    NOT NULL,
    enabled     INTEGER NOT NULL DEFAULT 0,
    base_url    TEXT    NOT NULL DEFAULT '',
    model       TEXT    NOT NULL DEFAULT '',
    api_key     TEXT    NOT NULL DEFAULT '',
    temperature REAL    NOT NULL DEFAULT 0.2,
    max_tokens  INTEGER NOT NULL DEFAULT 1024,
    timeout     REAL    NOT NULL DEFAULT 30.0,
    updated_at  TEXT    NOT NULL DEFAULT ''
);
"""


def mask_api_key(key: str) -> str:
    """把 Key 转成可展示的掩码，只保留末 4 位。"""
    if not key:
        return ""
    tail = key[-4:] if len(key) >= 4 else key
    return f"****{tail}"


@dataclass(slots=True)
class AISettings:
    """AI 模型服务配置（含明文 Key，仅后端内部使用）。"""

    provider: str = DEFAULT_PROVIDER
    enabled: bool = False
    base_url: str = DEFAULT_BASE_URL
    model: str = ""
    api_key: str = ""
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS
    timeout: float = DEFAULT_TIMEOUT
    updated_at: str = ""

    def to_public(self) -> dict:
        """面向接口的脱敏视图：**不含完整 API Key**，只有是否已配置与掩码。"""
        return {
            "provider": self.provider,
            "enabled": self.enabled,
            "base_url": self.base_url,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "api_key_configured": bool(self.api_key),
            "masked_api_key": mask_api_key(self.api_key),
            "updated_at": self.updated_at,
        }

    def to_llm_config(self) -> LLMConfig:
        """转成调用配置。``LLMConfig.api_key`` 的 repr 已关闭，不会进日志。"""
        return LLMConfig(
            provider=self.provider,
            base_url=self.base_url,
            model=self.model,
            api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout=self.timeout,
        )

    def fingerprint(self) -> str:
        """配置指纹 —— 参与缓存 key。

        只要影响模型输出的配置变了（换模型、换端点、调温度…），
        指纹就变，旧缓存自然失效；**不需要删除旧记录**。
        含 API Key：换 Key 可能换到不同的后端账号。
        """
        raw = "|".join(
            [
                self.provider,
                normalize_base_url(self.base_url),
                self.model,
                f"{self.temperature:.3f}",
                str(self.max_tokens),
                hashlib.sha256(self.api_key.encode("utf-8")).hexdigest()[:12],
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _normalize(payload: dict, current: AISettings) -> AISettings:
    """把外部输入整理成合法配置。

    未提供的字段沿用当前值；``api_key`` 显式传空串表示「清除」，
    传 ``None`` / 不传表示「保持不变」。
    """
    provider = str(payload.get("provider") or current.provider)
    if provider not in ("llama_cpp", "openai_compatible"):
        provider = "openai_compatible"

    base_url = payload.get("base_url")
    base_url = (
        normalize_base_url(str(base_url)) if base_url is not None else current.base_url
    )

    model = payload.get("model")
    model = str(model).strip() if model is not None else current.model

    api_key = payload.get("api_key")
    if api_key is None:
        api_key = current.api_key
    else:
        api_key = str(api_key).strip()

    temperature = payload.get("temperature")
    temperature = (
        _clamp(float(temperature), *TEMPERATURE_RANGE)
        if temperature is not None
        else current.temperature
    )

    max_tokens = payload.get("max_tokens")
    max_tokens = (
        int(_clamp(int(max_tokens), *MAX_TOKENS_RANGE))
        if max_tokens is not None
        else current.max_tokens
    )

    timeout = payload.get("timeout")
    timeout = (
        _clamp(float(timeout), *TIMEOUT_RANGE) if timeout is not None else current.timeout
    )

    enabled = payload.get("enabled")
    enabled = bool(enabled) if enabled is not None else current.enabled

    return AISettings(
        provider=provider,
        enabled=enabled,
        base_url=base_url,
        model=model,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        updated_at=current.updated_at,
    )


class AISettingsStore:
    """``ai_model_settings`` 表的读写。线程安全。

    用可重入锁：``save()`` 内部要先 ``load()`` 取当前值做增量合并，
    普通 ``Lock`` 会在这里自锁死。
    """

    def __init__(self, db_path: Path | str) -> None:
        self._path = Path(db_path)
        self._lock = threading.RLock()
        self._is_memory = str(db_path) == ":memory:"
        self._memory_conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._is_memory:
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._memory_conn.row_factory = sqlite3.Row
                self._memory_conn.executescript(_SCHEMA)
            return self._memory_conn
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(_SCHEMA)
        return conn

    def load(self) -> AISettings:
        """读取配置；表中无记录时返回默认（未启用）。

        API Key 在库中是**加密存储**的，这里解密后返回给内部使用方；
        对外的脱敏视图由 :meth:`AISettings.to_public` 负责。
        """
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT * FROM ai_model_settings WHERE id = 1").fetchone()
            finally:
                if not self._is_memory:
                    conn.close()

        if row is None:
            return AISettings()
        return AISettings(
            provider=row["provider"],
            enabled=bool(row["enabled"]),
            base_url=row["base_url"],
            model=row["model"],
            api_key=decrypt_api_key(row["api_key"], get_admin_secret()),
            temperature=float(row["temperature"]),
            max_tokens=int(row["max_tokens"]),
            timeout=float(row["timeout"]),
            updated_at=row["updated_at"],
        )

    def save(self, payload: dict) -> AISettings:
        """按增量语义更新配置并落库，返回保存后的配置。

        **落库前加密 API Key** —— 数据库文件被读走也拿不到明文。
        """
        with self._lock:
            current = self.load()
            updated = _normalize(payload, current)
            updated.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO ai_model_settings
                        (id, provider, enabled, base_url, model, api_key,
                         temperature, max_tokens, timeout, updated_at)
                    VALUES (1,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                        provider    = excluded.provider,
                        enabled     = excluded.enabled,
                        base_url    = excluded.base_url,
                        model       = excluded.model,
                        api_key     = excluded.api_key,
                        temperature = excluded.temperature,
                        max_tokens  = excluded.max_tokens,
                        timeout     = excluded.timeout,
                        updated_at  = excluded.updated_at
                    """,
                    (
                        updated.provider,
                        int(updated.enabled),
                        updated.base_url,
                        updated.model,
                        # 加密后入库
                        encrypt_api_key(updated.api_key, get_admin_secret()),
                        updated.temperature,
                        updated.max_tokens,
                        updated.timeout,
                        updated.updated_at,
                    ),
                )
                conn.commit()
            finally:
                if not self._is_memory:
                    conn.close()

        # 只记录非敏感信息：不含 Key、不含密文
        logger.info(
            "AI 模型配置已更新：provider=%s enabled=%s model=%s key_configured=%s",
            updated.provider,
            updated.enabled,
            updated.model or "(未填)",
            bool(updated.api_key),
        )
        return updated


_store: AISettingsStore | None = None
_store_lock = threading.Lock()


def get_settings_store() -> AISettingsStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = AISettingsStore(settings.db_path)
    return _store


def reset_settings_store(db_path: Path | str | None = None) -> AISettingsStore:
    """重建配置存储（测试用）。"""
    global _store
    with _store_lock:
        _store = AISettingsStore(db_path if db_path is not None else settings.db_path)
    return _store
