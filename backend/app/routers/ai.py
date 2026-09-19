"""AI 模型服务与分析接口。

接口边界
--------
**不提供任意 Prompt 的 chat 代理。** 所有分析请求只接受系统内部定义的
业务输入（事件编号、分析类型），最终 Prompt 完全由后端生成 ——
否则平台会变成一个对公网开放的 LLM 代理。

写接口（改配置、连接测试、强制重新分析）都需要管理员令牌，
见 :mod:`app.services.security`。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.schemas import (
    AIAnalysisOut,
    AIProviderOptionOut,
    AISettingsOut,
    AISettingsUpdateIn,
    AIStatusOut,
    AITestIn,
    AITestOut,
)
from app.services.ai.analysis import (
    ANALYZABLE_STAGES,
    ANALYSIS_TYPE_TEXT,
    AIAnalysis,
    get_ai_service,
)
from app.services.ai.config_store import get_settings_store
from app.services.ai.provider import PROVIDER_PRESETS
from app.services.ai.retriever import TOP_K
from app.services.security import require_admin
from app.services.ai_context import (
    context_for_event,
    context_for_stage,
    current_stage,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------


@router.get("/providers", response_model=list[AIProviderOptionOut], summary="可选模型服务类型")
def providers() -> list[AIProviderOptionOut]:
    """服务类型与默认 Base URL，供设置页预填。"""
    return [
        AIProviderOptionOut(value=key, label=cfg["label"], default_base_url=cfg["base_url"], hint=cfg["hint"])
        for key, cfg in PROVIDER_PRESETS.items()
    ]


@router.get("/settings", response_model=AISettingsOut, summary="读取 AI 模型配置")
def read_settings() -> AISettingsOut:
    """返回脱敏配置。**不含完整 API Key**，只有 configured 与掩码。"""
    return AISettingsOut(**get_settings_store().load().to_public())


@router.put(
    "/settings",
    response_model=AISettingsOut,
    summary="更新 AI 模型配置",
    dependencies=[Depends(require_admin)],
)
def update_settings(payload: AISettingsUpdateIn) -> AISettingsOut:
    """更新配置（需管理员令牌）。

    未提供的字段保持不变；``api_key`` 传空串表示清除已保存的 Key。
    """
    saved = get_settings_store().save(payload.model_dump(exclude_unset=True))
    return AISettingsOut(**saved.to_public())


@router.post(
    "/test",
    response_model=AITestOut,
    summary="测试模型服务连接",
    dependencies=[Depends(require_admin)],
)
async def test_connection(payload: AITestIn) -> AITestOut:
    """真实请求一次模型服务（需管理员令牌）。

    **不做假测试** —— 只有服务真正响应才返回 ``ok``。
    可以带尚未保存的配置，方便「先试再存」。
    """
    result = await get_ai_service().test_connection(payload.model_dump(exclude_unset=True))
    return AITestOut(**result)


@router.get("/status", response_model=AIStatusOut, summary="AI 模型服务状态")
def status() -> AIStatusOut:
    return AIStatusOut(**get_ai_service().status())


# ---------------------------------------------------------------------------
# 分析（只读）
# ---------------------------------------------------------------------------


def _to_out(analysis: AIAnalysis) -> AIAnalysisOut:
    return AIAnalysisOut(**analysis.to_dict())


@router.get(
    "/analysis/current",
    response_model=AIAnalysisOut,
    summary="当前预警 / 报警的辅助分析",
)
async def analysis_current(
    type: str = Query("warning", pattern="^(warning|alarm)$", description="分析类型"),
    refresh: bool = Query(False, description="强制重新分析（需管理员令牌）"),
    request: Request = None,  # type: ignore[assignment]
) -> AIAnalysisOut:
    """当前阶段的 AI 辅助分析。

    只有 warning / alarm 阶段会真正调用模型；
    缓存命中时直接复用，**不会因为前端轮询而重复消耗 Token**。

    ``refresh=true`` 会绕过缓存，因此需要管理员令牌。
    """
    if refresh:
        require_admin(request)

    context = context_for_stage(type)
    if context is None:
        return _to_out(
            AIAnalysis(
                status="disabled",
                source="fallback",
                analysis_type=type,
                error_message="当前阶段不需要辅助分析",
            )
        )
    analysis = await get_ai_service().analyze(
        target=f"current:{type}",
        analysis_type=type,
        current=context,
        force=refresh,
    )
    return _to_out(analysis)


@router.get(
    "/analysis/event/{event_id}",
    response_model=AIAnalysisOut,
    summary="历史事件的辅助分析",
)
async def analysis_event(
    event_id: str,
    refresh: bool = Query(False, description="强制重新分析（需管理员令牌）"),
    request: Request = None,  # type: ignore[assignment]
) -> AIAnalysisOut:
    """针对一条历史报警做知识增强分析。

    检索历史案例时**排除该事件自身**，避免把「这次事件的处理结果」
    当成类似历史经验而自我引用。
    """
    if refresh:
        require_admin(request)

    context = context_for_event(event_id)
    if context is None:
        raise HTTPException(status_code=404, detail=f"未找到报警记录：{event_id}")

    analysis = await get_ai_service().analyze(
        target=f"event:{event_id}",
        analysis_type="event",
        current=context,
        force=refresh,
    )
    return _to_out(analysis)


@router.post(
    "/analysis/event/{event_id}/refresh",
    response_model=AIAnalysisOut,
    summary="重新分析（需管理员令牌）",
    dependencies=[Depends(require_admin)],
)
async def refresh_event_analysis(event_id: str) -> AIAnalysisOut:
    """强制重新分析一条历史事件。"""
    context = context_for_event(event_id)
    if context is None:
        raise HTTPException(status_code=404, detail=f"未找到报警记录：{event_id}")
    analysis = await get_ai_service().analyze(
        target=f"event:{event_id}",
        analysis_type="event",
        current=context,
        force=True,
    )
    return _to_out(analysis)


@router.get("/analysis/meta", summary="分析能力元信息")
def analysis_meta() -> dict:
    """阶段限制与 Top-K —— 前端据此决定是否请求分析。"""
    return {
        "analyzable_stages": list(ANALYZABLE_STAGES),
        "top_k": TOP_K,
        "analysis_type_text": dict(ANALYSIS_TYPE_TEXT),
        "stage": current_stage(),
    }
