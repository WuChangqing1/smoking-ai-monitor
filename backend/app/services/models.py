"""仿真引擎的数据结构。

这些 dataclass 是后端内部的唯一数据口径，Pydantic 响应模型在
``app/schemas.py`` 中定义，两边字段名保持一致，避免"两套真相"。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SimState = Literal["normal", "attention", "warning", "alarm", "stopped"]
RiskLevel = Literal["low", "medium", "high", "critical"]
RiskTrend = Literal["stable", "rising", "rising_fast", "falling"]
FusionVerdict = Literal["normal", "attention", "warning", "alarm"]
AlarmLevel = Literal["info", "warning", "critical"]
AlarmStatus = Literal["pending", "processing", "resolved", "archived"]

# 状态机中可被"演示场景"直接指定的状态（stopped 由启停控制管理，不在此列）
ScenarioName = Literal["normal", "attention", "warning", "alarm"]

#: 状态顺序，用于判断状态是"升级"还是"恢复"
STATE_ORDER: tuple[SimState, ...] = ("normal", "attention", "warning", "alarm")

MONITOR_STATES: tuple[ScenarioName, ...] = ("normal", "attention", "warning", "alarm")

STATE_TEXT: dict[SimState, str] = {
    "normal": "正常",
    "attention": "关注",
    "warning": "预警",
    "alarm": "异常",
    "stopped": "已停止",
}

#: 风险指数 → 风险等级（全站统一口径）
RISK_THRESHOLDS: tuple[tuple[float, RiskLevel], ...] = (
    (30.0, "low"),
    (55.0, "medium"),
    (80.0, "high"),
    (100.0, "critical"),
)

RISK_LEVEL_TEXT: dict[RiskLevel, str] = {
    "low": "低风险",
    "medium": "中风险",
    "high": "高风险",
    "critical": "严重风险",
}

RISK_TREND_TEXT: dict[RiskTrend, str] = {
    "stable": "稳定",
    "rising": "上升",
    "rising_fast": "快速上升",
    "falling": "下降",
}

VERDICT_TEXT: dict[FusionVerdict, str] = {
    "normal": "正常",
    "attention": "关注",
    "warning": "预警",
    "alarm": "异常",
}

#: 联合判断结果 → 风险等级（用于报警记录定级）
VERDICT_TO_LEVEL: dict[FusionVerdict, RiskLevel] = {
    "normal": "low",
    "attention": "medium",
    "warning": "high",
    "alarm": "critical",
}

#: 联合判断结果 → 报警等级（提示 / 预警 / 严重）
VERDICT_TO_ALARM_LEVEL: dict[FusionVerdict, AlarmLevel] = {
    "normal": "info",
    "attention": "info",
    "warning": "warning",
    "alarm": "critical",
}

ALARM_LEVEL_TEXT: dict[AlarmLevel, str] = {
    "info": "提示",
    "warning": "预警",
    "critical": "严重",
}

ALARM_STATUS_TEXT: dict[AlarmStatus, str] = {
    "pending": "待处理",
    "processing": "处理中",
    "resolved": "已处理",
    "archived": "已归档",
}

#: 视觉模型类别 → 中文描述。类别名沿用资料中的模型命名风格。
VISION_LABEL_TEXT: dict[str, str] = {
    "normal_conveying": "正常输送",
    "material_accumulation_suspected": "疑似物料堆积",
    "material_accumulation": "物料堆积",
    "material_accumulation_severe": "物料堆积（严重）",
}


def risk_level_of(index: float) -> RiskLevel:
    """风险指数 → 风险等级。"""
    for upper, level in RISK_THRESHOLDS:
        if index < upper:
            return level
    return "critical"


def state_order_index(state: SimState) -> int:
    """状态在状态机中的序位；stopped 视为与 normal 同级（不参与升级判断）。"""
    if state == "stopped":
        return 0
    return STATE_ORDER.index(state)


@dataclass(slots=True)
class RadarReading:
    """雷达读数。测量值与滤波值分开，对应原系统界面上的「测量值 / 滤波值」。"""

    distance: float
    baseline_distance: float
    delta: float
    measured: float
    filtered: float
    #: 本系统实际采集频率（资料口径 10 Hz）
    sample_rate_hz: int
    #: 设备最高刷新能力（资料口径最高 1000 Hz）—— 与采集频率不是一回事
    max_refresh_hz: int
    refresh_text: str
    data_fresh: bool
    online: bool


@dataclass(slots=True)
class VisionReading:
    """视觉 AI 读数。属于概率模型输出，置信度不是"准确率"。"""

    status: str
    label: str
    label_text: str
    confidence: float
    coverage: float
    latency_ms: int
    online: bool


@dataclass(slots=True)
class EnvironmentReading:
    """环境与输送辅助数据。与堵料程度弱关联，不剧烈跳变。"""

    temperature: float
    humidity: float
    conveyor_speed: float
    conveyor_speed_baseline: float
    equipment_load: float
    material_coverage: float


@dataclass(slots=True)
class RiskReading:
    index: float
    level: RiskLevel
    level_text: str
    trend: RiskTrend
    trend_text: str


@dataclass(slots=True)
class FusionReading:
    verdict: FusionVerdict
    verdict_text: str
    mode: Literal["fusion", "vision_only"]
    reason: str
    confidence: float


@dataclass(slots=True)
class SimSample:
    """一个采样点。内部 10 Hz 产生，对外输出的历史序列经过降采样。"""

    ts: float
    label: str
    sim_state: SimState
    severity: float
    radar_distance: float
    radar_filtered: float
    risk_index: float
    vision_coverage: float
    vision_confidence: float
    conveyor_speed: float
    temperature: float
    humidity: float


@dataclass(slots=True)
class Snapshot:
    """GET /api/realtime 的完整快照。"""

    ts: float
    sim_state: SimState
    sim_state_text: str
    detection_running: bool
    stage: ScenarioName
    scenario_forced: bool
    radar: RadarReading
    vision: VisionReading
    environment: EnvironmentReading
    risk: RiskReading
    fusion: FusionReading


@dataclass(slots=True)
class AlarmRecordData:
    """异常报警记录。

    字段依据任务要求 A8，并覆盖原系统报警内容口径
    （设备名称 + 设备 IP + 报警时间 + 距离信息）。
    """

    event_id: str
    device_id: str
    device_name: str
    device_ip: str
    location: str
    timestamp: float
    radar_distance: float
    baseline_distance: float
    visual_result: str
    visual_confidence: float
    #: 报警发生时的物料覆盖率（视觉模型输出，0~1）
    visual_coverage: float
    fusion_result: str
    risk_score: float
    alarm_level: AlarmLevel
    event_type: str
    handling_status: AlarmStatus
    operator: str = "—"
    resolution: str = ""
    #: 处理闭环时间线：发现 → 判断 → 报警 → 处理 → 归档
    timeline: list[dict[str, str]] = field(default_factory=list)


@dataclass(slots=True)
class Evidence:
    """预警依据。source 用于前端区分图标，text 是面向用户的说明。"""

    source: Literal["radar", "vision", "conveyor", "knowledge", "environment"]
    text: str


@dataclass(slots=True)
class SimilarEvent:
    event_code: str
    similarity: float
    location: str
    event_type: str
    result: str


@dataclass(slots=True)
class PredictionData:
    """未来 30 分钟风险预测。措辞必须保持概率化，不给确定性结论。"""

    ts: float
    horizon_minutes: int
    current_index: float
    current_level: RiskLevel
    current_level_text: str
    forecast_index: float
    forecast_change: RiskTrend
    forecast_change_text: str
    forecast_level: RiskLevel
    forecast_level_text: str
    forecast_confidence: float
    evidence: list[Evidence]
    suggestions: list[str]
    similar_events: list[SimilarEvent]
    curve: list[dict[str, object]]
