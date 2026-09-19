"""把系统当前状态与历史报警转换为 AI 分析所需的上下文。

这一层负责**领域适配**：从既有的实时快照与报警记录里取出字段，
组装成 :class:`CurrentEventContext`。它本身不判断风险、不调用模型。

最小必要原则
------------
只取分析真正需要的监测字段。设备内网 IP（``192.168.x.x``）、设备编号、
处理人姓名、时间线这类信息**不进入上下文** ——
它们对判断异常原因没有帮助，还会造成不必要的内部信息外发。
"""

from __future__ import annotations

from app.config import settings
from app.services.ai.retriever import CurrentEventContext
from app.services.models import ALARM_LEVEL_TEXT, event_type_text
from app.services.simulation import get_engine
from app.services.video_detection import PRIMARY_DETECTION

#: 报警等级 → 是否属于"严重"
_CRITICAL_LEVEL = "critical"


def _stage_of(sim_state: str) -> str:
    """把系统状态映射成分析阶段。

    只有 warning / alarm 会被分析，其余阶段在服务层直接返回 disabled。
    """
    if sim_state in ("warning", "alarm"):
        return sim_state
    return sim_state or "normal"


def current_stage() -> str:
    """平台当前所处阶段（用于前端决定是否请求分析）。"""
    return _stage_of(get_engine().snapshot().sim_state)


def context_for_stage(stage: str) -> CurrentEventContext | None:
    """按当前实时数据构造指定阶段的分析上下文。

    只在前端请求 warning / alarm 时使用；若平台实际不处于该阶段，
    仍然按当前数据给出上下文（阶段由调用方声明），
    这样展示版在视频循环中首次进入预警时就能拿到分析。
    """
    if stage not in ("warning", "alarm"):
        return None

    snapshot = get_engine().snapshot()
    radar = snapshot.radar
    vision = snapshot.vision
    environment = snapshot.environment
    risk = snapshot.risk

    # 点位信息取设备模型，避免与报警记录口径不一致
    from app.services.devices import primary_point

    point = primary_point()

    return CurrentEventContext(
        stage=stage,
        location=point["name"],
        event_type=PRIMARY_DETECTION.label_text,
        risk_index=risk.index,
        distance=radar.distance,
        baseline_distance=radar.baseline_distance,
        coverage=vision.coverage,
        vision_label=vision.label_text,
        vision_confidence=vision.confidence,
        conveyor_speed=environment.conveyor_speed,
        temperature=environment.temperature,
        humidity=environment.humidity,
        equipment_load=environment.equipment_load,
        has_radar=bool(point.get("has_radar", True)),
    )


def context_for_event(event_id: str) -> CurrentEventContext | None:
    """按一条历史报警构造分析上下文。

    字段取自**该事件发生时记录的数据**，而不是当前实时值 ——
    分析历史事件就该用它自己的数据。
    """
    record = get_engine().alarm_by_id(event_id)
    if record is None:
        return None

    stage = "alarm" if record.alarm_level == _CRITICAL_LEVEL else "warning"

    return CurrentEventContext(
        stage=stage,
        location=record.location,
        event_type=event_type_text(record.event_type),
        risk_index=record.risk_score,
        distance=record.radar_distance,
        baseline_distance=record.baseline_distance,
        coverage=record.visual_coverage,
        vision_label=record.visual_result,
        vision_confidence=record.visual_confidence,
        # 报警记录里没有留存当时的环境读数，缺就留空，不编造
        conveyor_speed=None,
        temperature=None,
        humidity=None,
        equipment_load=None,
        has_radar=record.device_id.upper().startswith("RAD"),
        # 用于检索时排除自身，避免自我引用
        event_code=record.event_id,
    )


def alarm_level_text(level: str) -> str:
    return ALARM_LEVEL_TEXT.get(level, level)  # type: ignore[arg-type]


def is_analysis_available() -> bool:
    """现场是否已接入 —— 未接入时不建议对外展示模型分析入口。"""
    return settings.field_connected
