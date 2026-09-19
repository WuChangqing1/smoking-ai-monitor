"""LLM 与知识库增强的辅助分析。

模块划分
--------
:mod:`provider`      模型服务接入（OpenAI-compatible，含本地 llama.cpp）
:mod:`config_store`  配置持久化与 API Key 脱敏
:mod:`retriever`     知识库结构化检索（Top-K）
:mod:`prompt`        Prompt 组装（后端生成，含最小必要信息）
:mod:`parser`        模型输出解析（JSON / Markdown 包裹 / 纯文本兜底）
:mod:`analysis`      编排：检索 → 调用 → 解析 → 缓存 + single-flight

设计边界
--------
模型只做**异常解释与处置建议**，不参与报警等级判定；
模型不可用时平台全部既有功能照常工作。
"""

from app.services.ai.analysis import (
    ANALYZABLE_STAGES,
    AIAnalysis,
    AIAnalysisService,
    get_ai_service,
    reset_ai_service,
)
from app.services.ai.config_store import (
    AISettings,
    get_settings_store,
    mask_api_key,
    reset_settings_store,
)
from app.services.ai.provider import (
    PROVIDER_PRESETS,
    LLMConfig,
    LLMError,
    OpenAICompatibleProvider,
    get_provider,
    normalize_base_url,
)
from app.services.ai.retriever import (
    TOP_K,
    CurrentEventContext,
    KnowledgeRetriever,
    RetrievedCase,
)

__all__ = [
    "ANALYZABLE_STAGES",
    "AIAnalysis",
    "AIAnalysisService",
    "AISettings",
    "CurrentEventContext",
    "KnowledgeRetriever",
    "LLMConfig",
    "LLMError",
    "OpenAICompatibleProvider",
    "PROVIDER_PRESETS",
    "RetrievedCase",
    "TOP_K",
    "get_ai_service",
    "get_provider",
    "get_settings_store",
    "mask_api_key",
    "normalize_base_url",
    "reset_ai_service",
    "reset_settings_store",
]
