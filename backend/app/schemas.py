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
    #: 运行模式：video_sync（视频同步演示，默认） / automatic（自动工况循环）
    run_mode: Literal["automatic", "video_sync"]
    #: 视频同步模式下主监控视频的源时长（秒）
    video_duration_seconds: float
    #: 主监控视频的默认播放速率（不重新编码，浏览器侧调速）
    video_playback_rate: float


# ---- 视频同步遥测 -----------------------------------------------------------


class VideoKeyframeOut(BaseModel):
    """遥测关键帧，供前端插值使用（与后端解算结果一致）。"""

    t: float
    distance: float
    risk: float
    coverage: float
    speed_ratio: float


class VideoTelemetryOut(BaseModel):
    """按 video.currentTime 解算的一帧遥测。"""

    t: float
    sim_state: SimStateT
    sim_state_text: str
    risk_index: float
    risk_level: RiskLevelT
    risk_level_text: str
    risk_trend: RiskTrendT
    risk_trend_text: str
    distance: float
    baseline_distance: float
    delta: float
    coverage: float
    vision_label: str
    vision_label_text: str
    vision_confidence: float
    conveyor_speed: float
    conveyor_speed_baseline: float
    equipment_load: float
    temperature: float
    humidity: float
    fusion_verdict: FusionVerdictT
    fusion_verdict_text: str
    fusion_reason: str


class VideoSyncInfoOut(BaseModel):
    """视频同步模式的元信息 + 关键帧轨迹。

    前端拿关键帧做本地插值，从而在 250~500 ms 的 UI 刷新节奏下
    既不产生高频 HTTP 请求，又与后端解算结果完全一致。
    """

    run_mode: Literal["automatic", "video_sync"]
    duration_seconds: float
    playback_rate: float
    sample_rate_hz: int
    baseline_distance: float
    alarm_threshold: float
    keyframes: list[VideoKeyframeOut]


# ---- 视频异常检测框（YOLO 风格展示）-----------------------------------------


class VideoDetectionBoxOut(BaseModel):
    """按 video.currentTime 解算的异常检测框。

    ``visible`` 为 True 表示视觉模型已确认异常区域。
    位置与尺寸在同一摄像头的 warning / alarm 阶段**完全相同**，
    只有 ``severity``（决定边框颜色）与 ``confidence`` 变化。
    """

    camera_id: str
    visible: bool
    x: float = Field(description="左上角 x，相对整帧比例 0~1")
    y: float = Field(description="左上角 y，相对整帧比例 0~1")
    width: float = Field(description="宽度，相对整帧比例 0~1")
    height: float = Field(description="高度，相对整帧比例 0~1")
    label: str = Field(description="模型类别，例如 material_accumulation")
    label_text: str = Field(description="界面显示名，例如 物料堆积")
    confidence: float = Field(description="概率模型输出置信度，不是准确率")
    severity: Literal["none", "warning", "alarm"]
    evidence_image: str | None = Field(
        default=None, description="异常证据图路径（相对站点根）；无框时为 None"
    )


class VideoDetectionConfigOut(VideoDetectionBoxOut):
    """检测框配置（与 t 无关的固定部分），供前端本地解算使用。"""

    active_from_risk: float
    evidence_time: float
    evidence_confidence: float


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
    event_type_text: str = Field(description="异常类型中文描述，供界面直接展示")
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
    evidence_image: str | None = Field(
        default=None,
        description="异常证据图路径（带检测框的截图）；无证据图时为 None",
    )
    evidence_note: str | None = Field(
        default=None, description="面向现场人员的证据说明"
    )
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


# ---- AI 模型服务 ------------------------------------------------------------
#
# 注意：公开的配置视图里**没有完整 api_key**，
# 只有 api_key_configured 与 masked_api_key。

ProviderT = Literal["llama_cpp", "openai_compatible"]


class AIProviderOptionOut(BaseModel):
    """可选服务类型 + 默认 Base URL（仅用于前端预填）。"""

    value: ProviderT
    label: str
    default_base_url: str
    hint: str


class AISettingsOut(BaseModel):
    """AI 配置的脱敏视图。"""

    provider: ProviderT
    enabled: bool
    base_url: str
    model: str
    temperature: float
    max_tokens: int
    timeout: float
    #: 是否已配置 API Key（**不返回 Key 本身**）
    api_key_configured: bool
    #: 掩码形式，例如 ****abcd
    masked_api_key: str = ""
    updated_at: str = ""


class AISettingsUpdateIn(BaseModel):
    """更新配置。未提供的字段保持不变；``api_key`` 传空串表示清除。"""

    provider: ProviderT | None = None
    enabled: bool | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=64, le=8192)
    timeout: float | None = Field(default=None, ge=3.0, le=120.0)


class AITestIn(BaseModel):
    """连接测试。可带未保存的临时配置，便于"先试再存"。"""

    provider: ProviderT | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    timeout: float | None = Field(default=None, ge=3.0, le=120.0)


class AITestOut(BaseModel):
    ok: bool
    error: str | None = None
    models: list[str] = Field(default_factory=list)
    model: str = ""


class AIStatusOut(BaseModel):
    enabled: bool
    configured: bool
    provider: str
    model: str
    reachable: bool | None = None
    last_error: str | None = None
    analyzable_stages: list[str] = Field(default_factory=list)
    top_k: int = 3


class AIAnalysisOut(BaseModel):
    """AI 辅助分析结果。

    ``source`` 明确区分 ``llm``（真实模型输出）与 ``fallback``（降级），
    页面据此绝不把降级内容伪装成模型结论。
    """

    status: Literal["ok", "disabled", "unavailable"]
    source: Literal["llm", "fallback"]
    analysis_type: str
    analysis_type_text: str = ""
    provider: str = ""
    model: str = ""
    summary: str = ""
    possible_causes: list[str] = Field(default_factory=list)
    recommended_checks: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    related_cases: list[str] = Field(default_factory=list)
    evidence_basis: list[str] = Field(default_factory=list)
    #: 模型输出无法解析为 JSON 时，原样保留供纯文本展示
    fallback_text: str = ""
    structured: bool = False
    generated_at: str = ""
    cached: bool = False
    error_message: str | None = None
