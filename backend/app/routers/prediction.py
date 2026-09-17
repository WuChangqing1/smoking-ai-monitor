"""智能预警：未来 N 分钟风险预测。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import (
    CurvePointOut,
    EvidenceOut,
    PredictionOut,
    SimilarEventOut,
)
from app.services.simulation import get_engine

router = APIRouter(prefix="/api", tags=["prediction"])


@router.get("/prediction", response_model=PredictionOut, summary="未来 30 分钟风险预测")
def prediction(
    horizon_minutes: int = Query(30, ge=5, le=120, description="预测时长（分钟）"),
) -> PredictionOut:
    """基于雷达趋势、视觉覆盖率变化与历史相似事件计算的风险预测。

    输出刻意保持概率化措辞（"风险上升""建议关注"），
    不给出"多久之后一定堵料"这类确定性结论。
    """
    data = get_engine().prediction(horizon_minutes)

    return PredictionOut(
        ts=data.ts,
        horizon_minutes=data.horizon_minutes,
        current={
            "index": data.current_index,
            "level": data.current_level,
            "level_text": data.current_level_text,
        },
        forecast={
            "risk_index": data.forecast_index,
            "change": data.forecast_change,
            "change_text": data.forecast_change_text,
            "level": data.forecast_level,
            "level_text": data.forecast_level_text,
            "confidence": data.forecast_confidence,
        },
        evidence=[EvidenceOut(source=e.source, text=e.text) for e in data.evidence],
        suggestions=data.suggestions,
        similar_events=[
            SimilarEventOut(
                event_code=e.event_code,
                similarity=e.similarity,
                location=e.location,
                event_type=e.event_type,
                result=e.result,
            )
            for e in data.similar_events
        ],
        curve=[
            CurvePointOut(
                label=str(p["label"]),
                actual=p["actual"],  # type: ignore[arg-type]
                predicted=p["predicted"],  # type: ignore[arg-type]
            )
            for p in data.curve
        ],
    )
