"""异常报警：当前报警、历史报警、报警详情。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import (
    AiAnalysisOut,
    AlarmDetailOut,
    AlarmOut,
    PagedAlarms,
    TimelineEntryOut,
)
from app.services.models import (
    ALARM_LEVEL_TEXT,
    ALARM_STATUS_TEXT,
    AlarmRecordData,
    event_type_text,
)
from app.services.simulation import get_engine

router = APIRouter(prefix="/api", tags=["alarms"])


def _alarm_out(record: AlarmRecordData) -> AlarmOut:
    return AlarmOut(
        id=record.event_id,
        code=record.event_id,
        ts=record.timestamp,
        device_id=record.device_id,
        device_name=record.device_name,
        device_ip=record.device_ip,
        location=record.location,
        event_type=record.event_type,
        event_type_text=event_type_text(record.event_type),
        level=record.alarm_level,
        level_text=ALARM_LEVEL_TEXT[record.alarm_level],
        radar_value=record.radar_distance,
        vision_result=record.visual_result,
        fusion_result=record.fusion_result,
        status=record.handling_status,
        status_text=ALARM_STATUS_TEXT[record.handling_status],
        risk_index=record.risk_score,
    )


@router.get("/alarms", response_model=PagedAlarms, summary="报警列表")
def alarms(
    level: str | None = Query(None, description="按报警等级过滤：info / warning / critical"),
    status: str | None = Query(None, description="按处理状态过滤"),
    device_id: str | None = Query(None, description="按设备编号过滤"),
    event_type: str | None = Query(None, description="按异常类型过滤"),
    date_from: str | None = Query(None, description="起始日期 YYYY-MM-DD"),
    date_to: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> PagedAlarms:
    """报警列表。支持按等级 / 状态 / 设备 / 异常类型 / 日期范围筛选。"""
    from datetime import datetime, time

    records = get_engine().alarms()

    def keep(record: AlarmRecordData) -> bool:
        if level and record.alarm_level != level:
            return False
        if status and record.handling_status != status:
            return False
        if device_id and record.device_id != device_id:
            return False
        if event_type and record.event_type != event_type:
            return False

        moment = datetime.fromtimestamp(record.timestamp).date()
        if date_from:
            try:
                if moment < datetime.strptime(date_from, "%Y-%m-%d").date():
                    return False
            except ValueError:
                pass
        if date_to:
            try:
                if moment > datetime.strptime(date_to, "%Y-%m-%d").date():
                    return False
            except ValueError:
                pass
        return True

    filtered = [r for r in records if keep(r)]
    total = len(filtered)
    start = (page - 1) * page_size
    page_items = filtered[start : start + page_size]

    return PagedAlarms(
        total=total,
        page=page,
        page_size=page_size,
        items=[_alarm_out(r) for r in page_items],
    )


@router.get("/alarms/options", summary="报警筛选选项")
def alarm_options() -> dict:
    """数据溯源筛选下拉的选项来源。

    选项取自后端实际存在的数据 + 原始资料口径的异常类型，
    前端不硬编码，避免筛选值与数据不一致。

    注意：本路由必须注册在 ``/alarms/{event_id}`` 之前，否则 "options"
    会被当成 event_id 而报 404。
    """
    records = get_engine().alarms()

    device_ids = sorted({r.device_id for r in records})
    event_types = sorted({r.event_type for r in records})

    return {
        "levels": [
            {"value": "info", "label": "提示"},
            {"value": "warning", "label": "预警"},
            {"value": "critical", "label": "严重"},
        ],
        "statuses": [
            {"value": "pending", "label": "待处理"},
            {"value": "processing", "label": "处理中"},
            {"value": "resolved", "label": "已处理"},
            {"value": "archived", "label": "已归档"},
        ],
        "devices": [
            {"value": did, "label": did} for did in device_ids
        ],
        "event_types": [
            {"value": code, "label": event_type_text(code)} for code in event_types
        ],
    }


@router.get("/alarms/{event_id}", response_model=AlarmDetailOut, summary="报警详情")
def alarm_detail(event_id: str) -> AlarmDetailOut:
    """报警详情：事件基本信息 + 当时监控画面 + 雷达趋势 + AI 判断 + 处理结果。

    对应原系统的"异常分析窗口"，并补齐「发现→判断→报警→处理→归档」闭环。
    """
    engine = get_engine()
    record = engine.alarm_by_id(event_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"未找到报警记录：{event_id}")
    # 雷达趋势：取当前滚动窗口的历史作为"当时的数据走向"
    from app.routers.realtime import _sample_out

    trend = [_sample_out(s) for s in engine.history(60)]

    base = _alarm_out(record)
    return AlarmDetailOut(
        **base.model_dump(),
        baseline_distance=record.baseline_distance,
        # 当时监控画面：主监控点静态帧（视频就绪后为同一路径）
        snapshot="/images/main-monitor-fallback.png",
        radar_trend=trend,
        ai_analysis=AiAnalysisOut(
            vision_label=record.visual_result,
            confidence=record.visual_confidence,
            coverage=record.visual_coverage,
            note=(
                f"视觉模型输出为概率结果，本次置信度 {record.visual_confidence * 100:.1f}%，"
                f"物料覆盖率 {record.visual_coverage * 100:.1f}%；"
                f"测距 {record.radar_distance:.2f} m 相对基准 "
                f"{record.baseline_distance:.2f} m 变化 "
                f"{record.radar_distance - record.baseline_distance:+.2f} m。"
            ),
        ),
        timeline=[TimelineEntryOut(**entry) for entry in record.timeline],
        operator=record.operator,
        resolution=record.resolution,
    )
