"""AI 辅助分析服务：知识检索 → Prompt → 模型 → 解析 → 缓存。

定位
----
这是 **Decision Support Layer**，不是安全判定层。
报警等级永远由既有的雷达 + 视觉 + 联合判定规则决定，
本模块只在 warning / alarm 之后提供「怎么理解和怎么处理」。

三条硬性行为
------------
1. **只有 warning / alarm 才分析。** normal / attention 不调用模型 ——
   否则 1 秒轮询会把 Token 烧光。
2. **缓存 + single-flight。** 相同 cache key 只发一次真实请求；
   并发请求共享同一次调用（展示版视频每约 20 秒循环一次，
   没有这层保护每轮都会重复计费）。
3. **失败只降级，不扩散。** 模型挂了不影响监测、预警、报警、溯源。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.services.ai import prompt as prompt_builder
from app.services.ai.config_store import AISettings, get_settings_store
from app.services.ai.parser import ParsedAnalysis, parse_analysis
from app.services.ai.provider import LLMError, get_provider
from app.services.ai.retriever import (
    TOP_K,
    CurrentEventContext,
    KnowledgeRetriever,
    RetrievedCase,
    cases_fingerprint,
)
from app.services.knowledge import get_knowledge_base

logger = logging.getLogger(__name__)

#: 允许触发模型分析的阶段。其他阶段一律不调用。
ANALYZABLE_STAGES: tuple[str, ...] = ("warning", "alarm")

#: 分析类型 → 中文名
ANALYSIS_TYPE_TEXT: dict[str, str] = {
    "warning": "预警辅助分析",
    "alarm": "报警辅助分析",
    "event": "历史事件辅助分析",
}

#: 分析结果来源
SOURCE_LLM = "llm"
SOURCE_FALLBACK = "fallback"

#: 状态
STATUS_OK = "ok"
STATUS_DISABLED = "disabled"
STATUS_UNAVAILABLE = "unavailable"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# 缓存表
# ---------------------------------------------------------------------------

_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_analysis_cache (
    cache_key     TEXT PRIMARY KEY,
    target        TEXT NOT NULL,
    analysis_type TEXT NOT NULL,
    provider      TEXT NOT NULL,
    model         TEXT NOT NULL,
    payload       TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_cache_target ON ai_analysis_cache(target, analysis_type);
"""


class AnalysisCache:
    """分析结果缓存（SQLite）。每个项目用自己的数据库。"""

    def __init__(self, db_path: Path | str) -> None:
        self._path = Path(db_path)
        self._lock = threading.Lock()
        self._is_memory = str(db_path) == ":memory:"
        self._memory_conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._is_memory:
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._memory_conn.row_factory = sqlite3.Row
                self._memory_conn.executescript(_CACHE_SCHEMA)
            return self._memory_conn
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(_CACHE_SCHEMA)
        return conn

    def get(self, cache_key: str) -> dict | None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT payload FROM ai_analysis_cache WHERE cache_key = ?",
                    (cache_key,),
                ).fetchone()
            finally:
                if not self._is_memory:
                    conn.close()
        if row is None:
            return None
        try:
            data = json.loads(row["payload"])
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def put(self, cache_key: str, target: str, analysis_type: str, payload: dict) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO ai_analysis_cache
                        (cache_key, target, analysis_type, provider, model, payload, created_at)
                    VALUES (?,?,?,?,?,?,?)
                    ON CONFLICT(cache_key) DO UPDATE SET
                        payload    = excluded.payload,
                        provider   = excluded.provider,
                        model      = excluded.model,
                        created_at = excluded.created_at
                    """,
                    (
                        cache_key,
                        target,
                        analysis_type,
                        str(payload.get("provider", "")),
                        str(payload.get("model", "")),
                        json.dumps(payload, ensure_ascii=False),
                        _now(),
                    ),
                )
                conn.commit()
            finally:
                if not self._is_memory:
                    conn.close()

    def clear(self) -> int:
        with self._lock:
            conn = self._connect()
            try:
                count = conn.execute("SELECT COUNT(*) AS c FROM ai_analysis_cache").fetchone()["c"]
                conn.execute("DELETE FROM ai_analysis_cache")
                conn.commit()
                return int(count)
            finally:
                if not self._is_memory:
                    conn.close()


_cache: AnalysisCache | None = None
_cache_lock = threading.Lock()


def get_cache() -> AnalysisCache:
    global _cache
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                _cache = AnalysisCache(settings.db_path)
    return _cache


def reset_cache(db_path: Path | str | None = None) -> AnalysisCache:
    """重建缓存（测试用）。"""
    global _cache
    with _cache_lock:
        _cache = AnalysisCache(db_path if db_path is not None else settings.db_path)
    return _cache


# ---------------------------------------------------------------------------
# Cache key
# ---------------------------------------------------------------------------


def build_cache_key(
    *,
    target: str,
    analysis_type: str,
    ai_settings: AISettings,
    knowledge_hash: str,
) -> str:
    """组装缓存 key。

    参与要素：
      * analysis target（例如 ``video_sync:camera01:warning`` 或 ``event:EVT-...``）
      * analysis type
      * **模型配置指纹** —— 换模型/换端点/调温度后旧结果不再复用
      * **知识库指纹** —— 知识库变了，旧分析失效

    旧记录不必删除：配置一变，key 自然不同。
    """
    raw = "|".join(
        [target, analysis_type, ai_settings.fingerprint(), knowledge_hash, f"k{TOP_K}"]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 结果结构
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class AIAnalysis:
    """一次分析的结果（对外结构）。"""

    status: str
    source: str
    analysis_type: str
    provider: str = ""
    model: str = ""
    summary: str = ""
    possible_causes: list[str] | None = None
    recommended_checks: list[str] | None = None
    recommended_actions: list[str] | None = None
    related_cases: list[str] | None = None
    evidence_basis: list[str] | None = None
    fallback_text: str = ""
    structured: bool = False
    generated_at: str = ""
    cached: bool = False
    error_message: str | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "source": self.source,
            "analysis_type": self.analysis_type,
            "analysis_type_text": ANALYSIS_TYPE_TEXT.get(self.analysis_type, ""),
            "provider": self.provider,
            "model": self.model,
            "summary": self.summary,
            "possible_causes": self.possible_causes or [],
            "recommended_checks": self.recommended_checks or [],
            "recommended_actions": self.recommended_actions or [],
            "related_cases": self.related_cases or [],
            "evidence_basis": self.evidence_basis or [],
            "fallback_text": self.fallback_text,
            "structured": self.structured,
            "generated_at": self.generated_at,
            "cached": self.cached,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AIAnalysis:
        return cls(
            status=str(data.get("status", STATUS_UNAVAILABLE)),
            source=str(data.get("source", SOURCE_FALLBACK)),
            analysis_type=str(data.get("analysis_type", "")),
            provider=str(data.get("provider", "")),
            model=str(data.get("model", "")),
            summary=str(data.get("summary", "")),
            possible_causes=list(data.get("possible_causes") or []),
            recommended_checks=list(data.get("recommended_checks") or []),
            recommended_actions=list(data.get("recommended_actions") or []),
            related_cases=list(data.get("related_cases") or []),
            evidence_basis=list(data.get("evidence_basis") or []),
            fallback_text=str(data.get("fallback_text", "")),
            structured=bool(data.get("structured", False)),
            generated_at=str(data.get("generated_at", "")),
            cached=True,
            error_message=data.get("error_message"),
        )


def _unavailable(analysis_type: str, error: str, *, status: str = STATUS_UNAVAILABLE) -> AIAnalysis:
    """构造降级结果 —— 页面据此显示「AI 分析暂不可用」。"""
    return AIAnalysis(
        status=status,
        source=SOURCE_FALLBACK,
        analysis_type=analysis_type,
        error_message=error,
    )


# ---------------------------------------------------------------------------
# 服务
# ---------------------------------------------------------------------------


class AIAnalysisService:
    """知识增强的 AI 辅助分析。

    每次请求都会重新检索知识库（很便宜），但**模型调用受缓存保护**。

    并发合并（single-flight）用 ``asyncio.Future`` 实现，**不能用
    ``threading.Lock``**：协程在等待网络时会让出控制权，若其他协程在
    同步锁上阻塞，就会把它们所在的事件循环线程一起卡死（实测会挂住）。
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = db_path
        #: cache_key -> 正在进行的调用。同一 key 的后来者直接等这个 future。
        self._inflight: dict[str, asyncio.Future] = {}
        # 记录实际发生的模型调用次数（测试用来断言"只调用一次"）
        self.call_count = 0

    # ---- 内部工具 -----------------------------------------------------------

    def _join_inflight(self, cache_key: str) -> asyncio.Future | None:
        """若已有同 key 的调用在进行，返回它的 future 供等待。"""
        future = self._inflight.get(cache_key)
        if future is None or future.done():
            return None
        return future

    def _begin_inflight(self, cache_key: str) -> asyncio.Future:
        """登记一次新的进行中调用。"""
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._inflight[cache_key] = future
        return future

    def _end_inflight(self, cache_key: str, future: asyncio.Future) -> None:
        if self._inflight.get(cache_key) is future:
            self._inflight.pop(cache_key, None)

    def _retriever(self) -> KnowledgeRetriever:
        return KnowledgeRetriever(get_knowledge_base())

    # ---- 对外：状态 ---------------------------------------------------------

    def status(self) -> dict:
        """模型服务状态。不含任何敏感信息。"""
        ai_settings = get_settings_store().load()
        return {
            "enabled": ai_settings.enabled,
            "configured": bool(ai_settings.base_url and ai_settings.model),
            "provider": ai_settings.provider,
            "model": ai_settings.model,
            "reachable": None,  # 由 /api/ai/test 实测，这里不主动探测
            "last_error": None,
            "analyzable_stages": list(ANALYZABLE_STAGES),
            "top_k": TOP_K,
        }

    # ---- 对外：连接测试 -----------------------------------------------------

    async def test_connection(self, override: dict | None = None) -> dict:
        """真实请求一次 ``/models`` 或 ``/chat/completions``。

        **不做假测试** —— 只有服务真正响应才返回 ok。
        """
        ai_settings = get_settings_store().load()
        if override:
            # 允许用「还没保存的」配置测试，方便用户先试再存
            merged = ai_settings.to_public()
            merged.update({k: v for k, v in override.items() if v is not None})
            if "api_key" not in override:
                merged["api_key"] = ai_settings.api_key
            from app.services.ai.config_store import _normalize

            ai_settings = _normalize(merged, ai_settings)

        if not ai_settings.base_url:
            return {"ok": False, "error": "未填写 API Base URL", "models": []}

        provider = get_provider(ai_settings.provider)
        config = ai_settings.to_llm_config()

        models = await provider.list_models(config)
        try:
            result = await provider.chat(
                config,
                "你是连接测试用的回声助手。",
                "只回复两个字：连接",
            )
        except LLMError as exc:
            logger.warning(
                "AI 连接测试失败：provider=%s kind=%s status=%s",
                ai_settings.provider,
                exc.kind,
                exc.status,
            )
            return {"ok": False, "error": exc.user_message(), "models": models}

        return {
            "ok": True,
            "error": None,
            "models": models,
            "model": result.model or ai_settings.model,
            "latency_ms": None,
        }

    # ---- 对外：分析 ---------------------------------------------------------

    async def analyze(
        self,
        *,
        target: str,
        analysis_type: str,
        current: CurrentEventContext,
        force: bool = False,
    ) -> AIAnalysis:
        """生成（或复用缓存的）辅助分析。"""
        # 只有 warning / alarm 才分析
        if current.stage not in ANALYZABLE_STAGES and analysis_type != "event":
            return _unavailable(
                analysis_type, "当前阶段不需要辅助分析", status=STATUS_DISABLED
            )

        ai_settings = get_settings_store().load()
        if not ai_settings.enabled:
            return _unavailable(analysis_type, "AI 模型服务未启用", status=STATUS_DISABLED)
        if not ai_settings.base_url or not ai_settings.model:
            return _unavailable(analysis_type, "AI 模型服务未配置完成", status=STATUS_DISABLED)

        cache = get_cache()

        # single-flight：同一个 key 的并发请求共享同一次模型调用。
        # 后来者等 future，只有创建者真正发请求。
        # 注意：cache key 依赖检索结果，所以必须先检索再算 key。
        cases: list[RetrievedCase] = self._retriever().retrieve(
            current,
            top_k=TOP_K,
            exclude_event_code=current.event_code,
        )
        cache_key = build_cache_key(
            target=target,
            analysis_type=analysis_type,
            ai_settings=ai_settings,
            knowledge_hash=cases_fingerprint(cases),
        )

        if not force:
            hit = cache.get(cache_key)
            if hit is not None:
                logger.info("AI 分析命中缓存：type=%s target=%s", analysis_type, target)
                return AIAnalysis.from_dict(hit)

            pending = self._join_inflight(cache_key)
            if pending is not None:
                logger.info("AI 分析合并到进行中的调用：type=%s", analysis_type)
                shared = await asyncio.shield(pending)
                result = AIAnalysis.from_dict(shared)
                result.cached = True
                return result

        future = self._begin_inflight(cache_key) if not force else None
        try:
            result = await self._call_model(ai_settings, analysis_type, current, cases)

            # 只有真正成功的模型结果才写缓存，失败结果不缓存 ——
            # 否则模型恢复后仍会一直返回旧的失败状态
            if result.status == STATUS_OK:
                cache.put(cache_key, target, analysis_type, result.to_dict())
                if future is not None and not future.done():
                    future.set_result(result.to_dict())
            elif future is not None and not future.done():
                # 失败也唤醒等待者，避免它们一直挂着
                future.set_result(result.to_dict())
            return result
        except Exception as exc:  # pragma: no cover - 兜底
            if future is not None and not future.done():
                future.set_exception(exc)
            raise
        finally:
            if future is not None:
                self._end_inflight(cache_key, future)

    async def _call_model(
        self,
        ai_settings: AISettings,
        analysis_type: str,
        current: CurrentEventContext,
        cases: list[RetrievedCase],
    ) -> AIAnalysis:
        """真正发起模型请求并解析结果。"""
        provider = get_provider(ai_settings.provider)
        config = ai_settings.to_llm_config()
        user_prompt = prompt_builder.build_user_prompt(current, cases)

        started = datetime.now()
        self.call_count += 1
        try:
            llm_result = await provider.chat(config, prompt_builder.BASE_SYSTEM_PROMPT, user_prompt)
        except LLMError as exc:
            elapsed = (datetime.now() - started).total_seconds()
            # 只记录非敏感信息：不含 Key、不含 Prompt 全文
            logger.warning(
                "AI 分析失败：provider=%s model=%s kind=%s status=%s 耗时=%.1fs",
                ai_settings.provider,
                ai_settings.model,
                exc.kind,
                exc.status,
                elapsed,
            )
            return _unavailable(analysis_type, exc.user_message())
        except Exception:  # pragma: no cover - 兜底，绝不向上抛
            logger.exception("AI 分析出现未预期异常")
            return _unavailable(analysis_type, "AI 分析暂不可用")

        elapsed = (datetime.now() - started).total_seconds()
        parsed: ParsedAnalysis = parse_analysis(llm_result.text)
        logger.info(
            "AI 分析完成：provider=%s model=%s type=%s 耗时=%.1fs 结构化=%s 案例=%d",
            llm_result.provider or ai_settings.provider,
            llm_result.model or ai_settings.model,
            analysis_type,
            elapsed,
            parsed.structured,
            len(cases),
        )

        return AIAnalysis(
            status=STATUS_OK,
            source=SOURCE_LLM,
            analysis_type=analysis_type,
            provider=llm_result.provider or ai_settings.provider,
            model=llm_result.model or ai_settings.model,
            summary=parsed.summary,
            possible_causes=parsed.possible_causes,
            recommended_checks=parsed.recommended_checks,
            recommended_actions=parsed.recommended_actions,
            related_cases=parsed.related_cases or [c.event_code for c in cases],
            evidence_basis=parsed.evidence_basis,
            fallback_text=parsed.fallback_text,
            structured=parsed.structured,
            generated_at=_now(),
        )


_service: AIAnalysisService | None = None
_service_lock = threading.Lock()


def get_ai_service() -> AIAnalysisService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = AIAnalysisService(settings.db_path)
    return _service


def reset_ai_service() -> AIAnalysisService:
    """重建分析服务（测试用，便于重置调用计数）。"""
    global _service
    with _service_lock:
        _service = AIAnalysisService(settings.db_path)
    return _service
