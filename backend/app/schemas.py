"""Pydantic 响应模型（API 契约）。

命名与 ``app/services/models.py`` 中的内部 dataclass 保持一致，
避免"两套真相"；这里只负责序列化与文档。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---- 枚举字面量 -------------------------------------------------------------

SimStateT = Literal["normal", "attention", "warning", "alarm", "stopped"]
RiskLevelT = Literal["low", "medium", "high", "critical"]
RiskTrendT = Literal["stable", "rising", "rising_fast", "falling"]
FusionVerdictT = Literal["normal", "attention", "warning", "alarm"]
AlarmLevelT = Literal["info", "warning", "critical"]
AlarmStatusT = Literal["pending", "processing", "resolved", "archived"]
HealthStateT = Literal["ok", "warn", "error", "offline"]
ScenarioT = Literal["normal", "attention", "warning", "alarm"]


# ---- 系统 -------------------------------------------------------------------


class StatusItem(BaseModel):
    key: str
    label: str
    state: HealthStateT
    text: str
    detail: str | None = None


class SystemStatus(BaseModel):
    ts: float
    detection_running: bool
    sim_state: SimStateT
    sim_state_text: str
    uptime_hours: float
    today_warnings: int
    devices_online: int
    devices_total: int
    statuses: list[StatusItem]


class PlatformMeta(BaseModel):
    platform_name: str
    project_name: str
    mode: Literal["simulation", "realtime"]
    mode_note: str
    conveyor_line: str
    monitor_points: int
    devices: dict[str, int]
    data_rate_hz: int


# ---- 实时数据 ---------------------------------------------------------------


class RadarReadingOut(BaseModel):
    distance: float = Field(description="当前测距 (m)，滤波值")
    baseline_distance: float = Field(description="基准距离 (m)")
    delta: float = Field(description="相对基准的变化量 (m)")
    measured: float = Field(description="测量值 (m)")
    filtered: float = Field(description="滤波值 (m)")
    sample_rate_hz: int = Field(description="本系统实际采集频率 (Hz)")
    max_refresh_hz: int = Field(description="雷达设备最高刷新能力 (Hz)，非采集频率")
    refresh_text: str
    data_fresh: bool
    online: bool


class VisionReadingOut(BaseModel):
    status: str
    label: str
    label_text: str
    confidence: float = Field(description="概率模型置信度 0~1，不代表准确率")
    coverage: float = Field(description="输送区域物料覆盖率 0~1")
    latency_ms: int
    online: bool


class EnvironmentReadingOut(BaseModel):
    temperature: float
    humidity: float
    conveyor_speed: float
    conveyor_speed_baseline: float
    equipment_load: float
    material_coverage: float


class RiskReadingOut(BaseModel):
    index: float = Field(description="风险指数 0~100")
    level: RiskLevelT
    level_text: str
    trend: RiskTrendT
    trend_text: str


class FusionReadingOut(BaseModel):
    verdict: FusionVerdictT
    verdict_text: str
    mode: Literal["fusion", "vision_only"]
    reason: str
    confidence: float


class SimSampleOut(BaseModel):
    ts: float
    label: str
    sim_state: SimStateT
    severity: float
    radar_distance: float
    radar_filtered: float
    risk_index: float
    vision_coverage: float
    vision_confidence: float
    conveyor_speed: float
    temperature: float
    humidity: float


class MonitorPointOut(BaseModel):
    id: str
    code: str
    name: str
    position: int
    device_id: str
    device_ip: str
    has_radar: bool
    online: bool
    stream: str | None


class RealtimeSnapshotOut(BaseModel):
    ts: float
    monitor_point: MonitorPointOut
    sim_state: SimStateT
    sim_state_text: str
    detection_running: bool
    stage: ScenarioT
    scenario_forced: bool
    radar: RadarReadingOut
    vision: VisionReadingOut
    environment: EnvironmentReadingOut
    risk: RiskReadingOut
    fusion: FusionReadingOut
    samples: list[SimSampleOut] = Field(description="滚动窗口内的降采样历史（60~180 点）")
    sample_interval_seconds: float = Field(
        description="历史序列的降采样间隔（秒）。内部 10 Hz 采样，对外按此间隔抽样。"
    )


# ---- 设备 -------------------------------------------------------------------


class RadarSpecOut(BaseModel):
    range: str
    accuracy: str
    max_refresh_hz: int
    protection: str


class CameraSpecOut(BaseModel):
    resolution: str
    encoding: str
    protection: str
    fps: int


class DeviceOut(BaseModel):
    id: str
    name: str
    kind: Literal["radar", "camera"]
    model: str
    vendor: str
    ip: str
    location: str
    point_id: str
    online: bool
    spec: str
    radar: RadarSpecOut | None = None
    camera: CameraSpecOut | None = None


# ---- 报警 -------------------------------------------------------------------


class TimelineEntryOut(BaseModel):
    ts: str
    stage: str
    title: str
    detail: str


class AlarmOut(BaseModel):
    id: str
    code: str
    ts: float
    device_id: str
    device_name: str
    device_ip: str
    location: str
    event_type: str
    level: AlarmLevelT
    level_text: str
    radar_value: float | None
    vision_result: str
    fusion_result: str
    status: AlarmStatusT
    status_text: str
    risk_index: float


class AiAnalysisOut(BaseModel):
    vision_label: str
    confidence: float
    coverage: float
    note: str


class AlarmDetailOut(AlarmOut):
    baseline_distance: float
    snapshot: str | None
    radar_trend: list[SimSampleOut]
    ai_analysis: AiAnalysisOut
    timeline: list[TimelineEntryOut]
    operator: str
    resolution: str


class PagedAlarms(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AlarmOut]


# ---- 智能预警 ---------------------------------------------------------------


class EvidenceOut(BaseModel):
    source: Literal["radar", "vision", "conveyor", "knowledge", "environment"]
    text: str


class SimilarEventOut(BaseModel):
    event_code: str
    similarity: float
    location: str
    event_type: str
    result: str


class CurvePointOut(BaseModel):
    label: str
    actual: float | None
    predicted: float | None


class PredictionOut(BaseModel):
    ts: float
    horizon_minutes: int
    current: dict[str, object]
    forecast: dict[str, object]
    evidence: list[EvidenceOut]
    suggestions: list[str]
    similar_events: list[SimilarEventOut]
    curve: list[CurvePointOut]


# ---- 知识库 -----------------------------------------------------------------


class KnowledgeEventOut(BaseModel):
    id: int
    event_code: str
    timestamp: str
    device_id: str
    location: str
    event_type: str
    radar_summary: str
    vision_summary: str
    environment_summary: str
    pre_event_pattern: str
    operator_review: str
    action_taken: str
    result: str
    preventive_suggestion: str


# ---- 控制类响应 -------------------------------------------------------------


class ActionResponse(BaseModel):
    ok: bool
    message: str
    sim_state: SimStateT | None = None
