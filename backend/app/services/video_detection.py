"""视频异常检测框与视觉证据图（YOLO 风格展示）。

定位
----
本模块是**展示层**的视觉异常表达，不是真实在线推理：

  * 不运行 YOLO，不加载模型权重，不引入推理依赖；
  * 检测框位置/尺寸**固定**，只随 video_sync 阶段决定是否显示；
  * "有框"即代表"视觉已确认异常区域"，无框即"尚未确认异常"。

因此同一 ``t`` 必然得到同一个框 —— 与 :mod:`app.services.video_sync`
共用同一套确定性轨迹（见前端 ``videoTelemetry.ts`` 的等价实现）。

业务含义
--------
摄像头画面 → 视觉模型检测 → 定位异常区域 → 生成带框证据图
→ 报警 → 供现场人员复核 → 处理结果进入数据溯源。

扩展性
------
按 ``camera_id`` 组织配置。当前只有主监控点（Camera 01）配置了检测框；
Camera 02~04 只需补充配置项即可，无需改动解析逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.video_sync import (
    STATE_ALARM_RISK,
    STATE_WARNING_RISK,
    resolve_video_telemetry,
    round_half_up,
)

#: 主监控点编号（与 app.services.devices 的主点位一致）
PRIMARY_CAMERA_ID = "CAM-01"

DetectionSeverity = Literal["none", "warning", "alarm"]


@dataclass(frozen=True, slots=True)
class DetectionBoxConfig:
    """一个摄像头的固定检测框配置。

    坐标全部为**相对整帧的比例**（0~1），因此与页面尺寸、CSS object-fit 无关：
    前端只要保证 overlay 与视频内容同为 16:9 并完全重合，百分比定位天然正确。
    """

    camera_id: str
    #: 固定框：x / y 为左上角，width / height 为尺寸
    x: float
    y: float
    width: float
    height: float
    #: 模型类别（内部标识）与界面显示名
    label: str
    label_text: str
    #: 从哪个风险阈值开始显示框
    active_from_risk: float
    #: 证据图路径（相对站点根，前端直接引用）
    evidence_image: str
    #: 证据图对应的视频时间点（秒），生成脚本使用同一常量
    evidence_time: float
    #: 证据图对应的置信度（与生成脚本一致，避免图片与网页数值不一致）
    evidence_confidence: float


#: 主监控点配置。
#:
#: 框位置由人工查看监控视频后确定：物料带沿画面中部由左上向右下延伸。
#: 取该区域的**左上 1/4 子区域**作为检测框 —— 这里正是物料开始增厚、
#: 堆积形态最集中的一段（1280×720 下即 430,190 → 563,363），
#: 比覆盖整条物料带更聚焦，也不包含大片空输送带与设备区域。
PRIMARY_DETECTION: DetectionBoxConfig = DetectionBoxConfig(
    camera_id=PRIMARY_CAMERA_ID,
    x=0.3359,
    y=0.2639,
    width=0.1039,
    height=0.2403,
    label="material_accumulation",
    label_text="物料堆积",
    active_from_risk=STATE_WARNING_RISK,
    evidence_image="images/evidence/main-camera-material-accumulation.jpg",
    evidence_time=8.5,
    evidence_confidence=0.92,
)

#: 摄像头 → 检测配置。Camera 02~04 接入视频时在此追加即可。
DETECTION_CONFIGS: dict[str, DetectionBoxConfig] = {
    PRIMARY_DETECTION.camera_id: PRIMARY_DETECTION,
}


def config_for(camera_id: str) -> DetectionBoxConfig | None:
    """取某摄像头的检测配置；未配置时返回 None（表示该点位暂无视觉检测框）。"""
    return DETECTION_CONFIGS.get(camera_id)


def detection_severity_for_risk(risk: float) -> DetectionSeverity:
    """风险 → 检测框等级。

    仅 warning 及以上阶段显示框：
      * < 55          → none    （normal / attention，视觉尚未确认异常区域）
      * 55 ~ 80       → warning （橙色框）
      * >= 80         → alarm   （红色框）
    """
    if risk < STATE_WARNING_RISK:
        return "none"
    if risk < STATE_ALARM_RISK:
        return "warning"
    return "alarm"


def detection_confidence_for_risk(risk: float) -> float:
    """检测框置信度：随风险在阶段区间内平滑插值。

    warning 段 0.88 → 0.93，alarm 段 0.93 → 0.96。
    确定性计算，同一 t 结果一致，不会逐帧跳动。
    注意：置信度是概率模型输出，不是准确率。
    """
    if risk < STATE_WARNING_RISK:
        return 0.0
    if risk < STATE_ALARM_RISK:
        span = STATE_ALARM_RISK - STATE_WARNING_RISK
        ratio = (risk - STATE_WARNING_RISK) / span if span > 0 else 0.0
        return round_half_up(0.88 + 0.05 * ratio, 3)
    span = 100.0 - STATE_ALARM_RISK
    ratio = min(1.0, (risk - STATE_ALARM_RISK) / span) if span > 0 else 0.0
    return round_half_up(0.93 + 0.03 * ratio, 3)


@dataclass(slots=True)
class VideoDetectionBox:
    """检测框解算结果（与前端 DetectionBox 类型字段一致）。"""

    visible: bool
    x: float
    y: float
    width: float
    height: float
    label: str
    label_text: str
    confidence: float
    severity: DetectionSeverity
    evidence_image: str | None


def resolve_video_detection_box(
    t: float,
    camera_id: str = PRIMARY_CAMERA_ID,
    duration: float | None = None,
) -> VideoDetectionBox:
    """按视频时间解算检测框状态。

    与前端 ``resolveVideoDetectionBox`` 等价：同一 ``t`` 得到同一个框。
    未配置检测的摄像头返回 ``visible=False`` 的空结果，前端不会渲染任何框。
    """
    config = config_for(camera_id)
    if config is None:
        return VideoDetectionBox(
            visible=False,
            x=0.0,
            y=0.0,
            width=0.0,
            height=0.0,
            label="",
            label_text="",
            confidence=0.0,
            severity="none",
            evidence_image=None,
        )

    telemetry = (
        resolve_video_telemetry(t, duration)
        if duration is not None
        else resolve_video_telemetry(t)
    )
    severity = detection_severity_for_risk(telemetry.risk_index)
    visible = severity != "none"

    return VideoDetectionBox(
        visible=visible,
        # 位置与尺寸固定：warning 与 alarm 使用完全相同的值
        x=config.x,
        y=config.y,
        width=config.width,
        height=config.height,
        label=config.label,
        label_text=config.label_text,
        confidence=detection_confidence_for_risk(telemetry.risk_index),
        severity=severity,
        evidence_image=config.evidence_image if visible else None,
    )


def evidence_image_for(event_type: str = "material_accumulation") -> str | None:
    """按异常类型取证据图路径（供报警详情 / 数据溯源引用）。

    当前只有主监控点的物料堆积证据图；其他类型暂无证据图，返回 None，
    调用方据此不渲染证据区块，而不是给出一个 404 的图片地址。
    """
    if event_type == PRIMARY_DETECTION.label:
        return PRIMARY_DETECTION.evidence_image
    return None
