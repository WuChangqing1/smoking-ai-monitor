"""视频同步遥测（video_sync 演示模式）。

用途
----
正式演示时监控画面播放最终视频，页面数值必须与画面严格同步：
画面物料逐渐堆积 ↔ 雷达测距下降、覆盖率上升、风险上升、联合判断升级。

设计要点
--------
1. **唯一事实源是 video.currentTime**（源视频 0~10 s）。
   不使用 Date.now()、不使用"网页运行了多少秒"，因此浏览器加载延迟、
   卡顿、切后台、暂停、拖动进度、循环都不会造成画面与数据脱节。
2. **关键帧 + 线性插值**，绝不出现分段跳变。
3. **确定性噪声**：扰动用 sin 关于 t 的固定函数，不用随机数。
   同一个 t 每次解析结果一致 → 视频循环后数据可复现，适合录屏与答辩。
4. **只读**：本模块不写入任何报警记录、不改动历史数据。
   视频每约 20 秒循环一次，若每轮写库会让报警列表迅速失去可信度。
5. **不改动 SimulationEngine**：automatic 模式完全保留，
   本模块是并列的第二种运行模式，由 ``settings.run_mode`` 选择。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from app.services.models import (
    RISK_LEVEL_TEXT,
    RISK_TREND_TEXT,
    STATE_TEXT,
    VERDICT_TEXT,
    VISION_LABEL_TEXT,
    risk_level_of,
)

#: 运行模式
RunMode = Literal["automatic", "video_sync"]

#: 同步演示使用的视频时长（秒）。与 public/videos/main-monitor.mp4 的源时长一致；
#: 前端会把 video.duration 上报，若实际时长不同则以实际值为准做等比缩放。
VIDEO_SYNC_DURATION = 10.0

#: 主监控点参数（与 automatic 模式、原始验收资料保持一致）
BASELINE_DISTANCE = 0.72
ALARM_THRESHOLD = 0.58
CONVEYOR_BASE_SPEED = 1.20
TEMP_BASE = 23.6
HUMIDITY_BASE = 54.0
SAMPLE_RATE_HZ = 10
RADAR_MAX_REFRESH_HZ = 1000


@dataclass(frozen=True, slots=True)
class VideoTelemetryKeyframe:
    """视频时间轴上的一个遥测关键帧。"""

    #: 源视频时间（秒）
    t: float
    #: 雷达测距 (m)
    distance: float
    #: 风险指数 0~100
    risk: float
    #: 物料覆盖率 0~1
    coverage: float
    #: 输送速度相对基线的比例（1.00 = 100%）
    speed_ratio: float


#: 关键帧轨迹：对应视频中物料由正常输送逐渐堆积到明显堆积的过程。
#: 终点收敛到约 0.58 m —— 取自原始验收资料中的真实报警测量值
#: （设备位置 2 / 测量值 0.58 / 物料变化异常警告）。
VIDEO_KEYFRAMES: tuple[VideoTelemetryKeyframe, ...] = (
    VideoTelemetryKeyframe(t=0.0, distance=0.721, risk=18.0, coverage=0.30, speed_ratio=1.00),
    VideoTelemetryKeyframe(t=2.0, distance=0.706, risk=27.0, coverage=0.37, speed_ratio=0.98),
    VideoTelemetryKeyframe(t=4.0, distance=0.681, risk=43.0, coverage=0.49, speed_ratio=0.95),
    VideoTelemetryKeyframe(t=6.0, distance=0.651, risk=59.0, coverage=0.61, speed_ratio=0.91),
    VideoTelemetryKeyframe(t=8.0, distance=0.612, risk=76.0, coverage=0.74, speed_ratio=0.86),
    VideoTelemetryKeyframe(t=10.0, distance=0.582, risk=89.0, coverage=0.83, speed_ratio=0.80),
)

# ---- 状态与视觉结果的分界（与项目既有口径一致：<30 低、<55 中、<80 高、≥80 严重）----
STATE_ATTENTION_RISK = 30.0
STATE_WARNING_RISK = 55.0
STATE_ALARM_RISK = 80.0


@dataclass(slots=True)
class VideoTelemetry:
    """一帧解算结果。字段名与 /api/realtime 快照保持一致。"""

    t: float
    sim_state: str
    sim_state_text: str
    risk_index: float
    risk_level: str
    risk_level_text: str
    risk_trend: str
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
    fusion_verdict: str
    fusion_verdict_text: str
    fusion_reason: str


def clamp_video_time(t: float, duration: float = VIDEO_SYNC_DURATION) -> float:
    """把任意输入时间安全夹到 [0, duration]；非数值按 0 处理。"""
    try:
        value = float(t)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return max(0.0, min(duration, value))


def round_half_up(value: float, digits: int) -> float:
    """四舍五入（half-up）。

    **必须显式实现**：Python 内置 ``round()`` 用的是银行家舍入（half-to-even），
    而前端 JavaScript 的 ``Math.round()`` 是 half-up。两者在恰好落在 .5 的值上
    会差一个最小单位，导致前后端遥测/置信度出现 0.001 级不一致
    （实测在 t=8.7 的检测框置信度上复现）。

    本模块所有对外数值统一走本函数，与前端保持逐位一致。
    """
    factor = 10.0**digits
    scaled = value * factor
    # 先消掉二进制表示误差（例如 0.9305*1000 = 930.4999999999999）
    nearest = round(scaled)
    if abs(scaled - nearest) < 1e-9:
        scaled = float(nearest)
    return math.floor(scaled + 0.5) / factor


def _lerp(a: float, b: float, ratio: float) -> float:
    return a + (b - a) * ratio


def interpolate_keyframes(t: float) -> VideoTelemetryKeyframe:
    """按线性插值求 t 处的关键帧数值（无跳变）。"""
    frames = VIDEO_KEYFRAMES
    if t <= frames[0].t:
        return frames[0]
    if t >= frames[-1].t:
        return frames[-1]

    for left, right in zip(frames, frames[1:]):
        if left.t <= t <= right.t:
            span = right.t - left.t
            ratio = 0.0 if span <= 0 else (t - left.t) / span
            return VideoTelemetryKeyframe(
                t=t,
                distance=_lerp(left.distance, right.distance, ratio),
                risk=_lerp(left.risk, right.risk, ratio),
                coverage=_lerp(left.coverage, right.coverage, ratio),
                speed_ratio=_lerp(left.speed_ratio, right.speed_ratio, ratio),
            )
    return frames[-1]


def _state_for_risk(risk: float) -> str:
    if risk < STATE_ATTENTION_RISK:
        return "normal"
    if risk < STATE_WARNING_RISK:
        return "attention"
    if risk < STATE_ALARM_RISK:
        return "warning"
    return "alarm"


def _vision_for_risk(risk: float) -> tuple[str, float]:
    """视觉模型结果：类别与置信度随风险阶段变化。

    置信度是概率模型输出，不是准确率。正常阶段处于高位，
    进入"疑似堆积"的过渡阶段时会下降（模型对形态判断存在不确定性），
    确认堆积后再次回升。
    """
    if risk < STATE_ATTENTION_RISK:
        return "normal_conveying", 0.970
    if risk < STATE_WARNING_RISK:
        return "material_accumulation_suspected", 0.820
    if risk < STATE_ALARM_RISK:
        return "material_accumulation", 0.900
    return "material_accumulation", 0.950


def _fusion_for_risk(risk: float) -> str:
    """联合判断结论：与状态一一对应。"""
    state = _state_for_risk(risk)
    return {"normal": "normal", "attention": "attention", "warning": "warning", "alarm": "alarm"}[
        state
    ]


def _fusion_reason(risk: float, distance: float, coverage: float) -> str:
    state = _state_for_risk(risk)
    delta = distance - BASELINE_DISTANCE
    if state == "normal":
        return (
            f"雷达测距 {distance:.3f} m 在基准附近波动，视觉未见异常形态，"
            "联合判断正常。"
        )
    if state == "attention":
        return (
            f"雷达测距较基准下降 {abs(delta):.3f} m，物料覆盖率升至 {coverage * 100:.1f}%，"
            "视觉识别到形态变化，联合判断为关注。"
        )
    if state == "warning":
        return (
            f"雷达测距持续下降至 {distance:.3f} m，视觉确认物料堆积形态"
            f"（覆盖率 {coverage * 100:.1f}%），联合判断风险上升。"
        )
    return (
        f"雷达测距已接近报警阈值（{distance:.3f} m），视觉确认明显堆积形态"
        f"（覆盖率 {coverage * 100:.1f}%），联合判断异常。"
    )


def resolve_video_telemetry(raw_t: float, duration: float = VIDEO_SYNC_DURATION) -> VideoTelemetry:
    """把视频时间解算为一帧完整遥测。

    ``raw_t`` 会被夹到 [0, duration]，因此循环回绕、拖动进度、
    后台恢复等情形都能安全解析。
    """
    duration = duration if duration and duration > 0 else VIDEO_SYNC_DURATION
    t = clamp_video_time(raw_t, duration)

    # 关键帧定义在标准 10 s 轴上；实际视频时长不同则等比映射
    timeline_t = t * (VIDEO_SYNC_DURATION / duration) if duration != VIDEO_SYNC_DURATION else t
    frame = interpolate_keyframes(timeline_t)

    # ---- 确定性微扰：±1~3 mm，同一 t 每次结果一致 ----
    # 三项不同频率叠加，避免看起来像 Excel 直线，又不会退化成随机数
    distance_jitter = (
        0.0010 * math.sin(2.0 * math.pi * 1.7 * timeline_t + 0.6)
        + 0.0006 * math.sin(2.0 * math.pi * 4.3 * timeline_t + 2.1)
        + 0.0004 * math.sin(2.0 * math.pi * 9.1 * timeline_t + 4.2)
    )
    risk_jitter = 0.5 * math.sin(2.0 * math.pi * 2.3 * timeline_t + 1.1)

    distance = round_half_up(frame.distance + distance_jitter, 4)

    # 覆盖率与风险沿用关键帧值并加极小确定性扰动
    coverage = round_half_up(max(0.0, min(0.99, frame.coverage + 0.004 * math.sin(2.0 * math.pi * 2.9 * timeline_t))), 4)
    risk = max(0.0, min(100.0, frame.risk + risk_jitter))

    conveyor_speed = round_half_up(CONVEYOR_BASE_SPEED * frame.speed_ratio, 3)
    # 设备负载：与 severity 同向。severity 由 risk 归一化得到，与 automatic 模式同一口径
    severity = max(0.0, min(1.0, risk / 100.0))
    equipment_load = round_half_up(max(0.0, min(100.0, 48.0 + 38.0 * severity)), 1)

    # 环境仅作辅助上下文：缓慢跟随，不因堵料剧烈变化
    temperature = round_half_up(TEMP_BASE + 1.3 * severity + 0.15 * math.sin(0.7 * timeline_t), 2)
    humidity = round_half_up(HUMIDITY_BASE - 3.0 * severity + 0.4 * math.cos(0.5 * timeline_t), 1)

    vision_label, vision_confidence = _vision_for_risk(risk)
    trend = _risk_trend(timeline_t)
    level = risk_level_of(risk)

    return VideoTelemetry(
        t=round_half_up(t, 3),
        sim_state=_state_for_risk(risk),
        sim_state_text=STATE_TEXT[_state_for_risk(risk)],  # type: ignore[index]
        risk_index=round_half_up(risk, 1),
        risk_level=level,
        risk_level_text=RISK_LEVEL_TEXT[level],
        risk_trend=trend,
        risk_trend_text=RISK_TREND_TEXT[trend],  # type: ignore[index]
        distance=distance,
        baseline_distance=BASELINE_DISTANCE,
        delta=round_half_up(distance - BASELINE_DISTANCE, 4),
        coverage=coverage,
        vision_label=vision_label,
        vision_label_text=VISION_LABEL_TEXT[vision_label],
        vision_confidence=vision_confidence,
        conveyor_speed=conveyor_speed,
        conveyor_speed_baseline=CONVEYOR_BASE_SPEED,
        equipment_load=equipment_load,
        temperature=temperature,
        humidity=humidity,
        fusion_verdict=_fusion_for_risk(risk),
        fusion_verdict_text=VERDICT_TEXT[_fusion_for_risk(risk)],  # type: ignore[index]
        fusion_reason=_fusion_reason(risk, distance, coverage),
    )


def _risk_trend(t: float, window: float = 1.0) -> str:
    """风险变化趋势：与 window 秒前比较。

    用关键帧曲线本身计算，因此与视频进度严格一致（循环后同样成立）。
    """
    if t <= 0.0:
        return "rising"
    previous = interpolate_keyframes(max(0.0, t - window)).risk
    current = interpolate_keyframes(t).risk
    diff = current - previous
    if diff >= 11.0:
        return "rising_fast"
    if diff >= 3.5:
        return "rising"
    if diff <= -3.5:
        return "falling"
    return "stable"


def samples_up_to(t: float, step: float = 0.2) -> list[VideoTelemetry]:
    """生成 0 → t 的遥测序列（默认 0.2 s 一个点）。

    趋势图只展示"当前这一轮已经走过的时间"，视频循环后自然从头开始，
    不会形成 0.72 → 0.58 → 0.72 这种无限锯齿累积。
    """
    t = clamp_video_time(t)
    points: list[VideoTelemetry] = []
    n = int(t / step)
    for i in range(n + 1):
        points.append(resolve_video_telemetry(i * step))
    # 末尾补上精确的当前时刻，保证曲线末端与当前读数一致
    if not points or points[-1].t < t:
        points.append(resolve_video_telemetry(t))
    return points
