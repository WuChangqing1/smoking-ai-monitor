"""视频同步遥测接口（video_sync 演示模式）。

前端把监控视频的 ``currentTime`` 通过查询参数上报，后端用与
:mod:`app.services.video_sync` 相同的确定性曲线解算遥测。

为什么不做成高频轮询：
  * 曲线是**确定性**的，前端拿到关键帧后本地插值即可得到完全一致的结果；
  * 因此前端以 250~500 ms 的节奏更新 UI，只在本接口做低频校对（约 1 s），
    既不产生请求风暴，又保证与后端口径完全一致。
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.config import settings
from app.schemas import VideoKeyframeOut, VideoSyncInfoOut, VideoTelemetryOut
from app.services.video_sync import (
    ALARM_THRESHOLD,
    BASELINE_DISTANCE,
    SAMPLE_RATE_HZ,
    VIDEO_KEYFRAMES,
    VIDEO_SYNC_DURATION,
    resolve_video_telemetry,
)

router = APIRouter(prefix="/api/video-sync", tags=["video-sync"])

#: 主监控视频默认播放速率：源视频 10 s，0.5× 下演示周期约 20 s。
#: 只在前端调速，不重新编码视频，文件大小与原视频保持不变。
VIDEO_PLAYBACK_RATE = 0.5


@router.get("/info", response_model=VideoSyncInfoOut, summary="视频同步模式信息与关键帧")
def video_sync_info() -> VideoSyncInfoOut:
    """返回运行模式、视频参数与遥测关键帧轨迹。"""
    return VideoSyncInfoOut(
        run_mode="video_sync" if settings.is_video_sync else "automatic",
        duration_seconds=VIDEO_SYNC_DURATION,
        playback_rate=VIDEO_PLAYBACK_RATE,
        sample_rate_hz=SAMPLE_RATE_HZ,
        baseline_distance=BASELINE_DISTANCE,
        alarm_threshold=ALARM_THRESHOLD,
        keyframes=[
            VideoKeyframeOut(
                t=f.t,
                distance=f.distance,
                risk=f.risk,
                coverage=f.coverage,
                speed_ratio=f.speed_ratio,
            )
            for f in VIDEO_KEYFRAMES
        ],
    )


@router.get("/telemetry", response_model=VideoTelemetryOut, summary="按视频时间解算遥测")
def video_sync_telemetry(
    t: float = Query(0.0, description="视频当前时间（秒），越界会安全夹到 0~duration"),
    duration: float = Query(
        VIDEO_SYNC_DURATION, gt=0.0, le=600.0, description="视频实际时长（秒）"
    ),
) -> VideoTelemetryOut:
    """给定 ``video.currentTime`` 返回该时刻的完整遥测。

    纯读接口：不写入任何报警记录，也不改动历史数据 ——
    视频每约 20 秒循环一次，若每轮写库会让报警列表迅速失去可信度。
    """
    telemetry = resolve_video_telemetry(t, duration)
    return VideoTelemetryOut(
        t=telemetry.t,
        sim_state=telemetry.sim_state,  # type: ignore[arg-type]
        sim_state_text=telemetry.sim_state_text,
        risk_index=telemetry.risk_index,
        risk_level=telemetry.risk_level,  # type: ignore[arg-type]
        risk_level_text=telemetry.risk_level_text,
        risk_trend=telemetry.risk_trend,  # type: ignore[arg-type]
        risk_trend_text=telemetry.risk_trend_text,
        distance=telemetry.distance,
        baseline_distance=telemetry.baseline_distance,
        delta=telemetry.delta,
        coverage=telemetry.coverage,
        vision_label=telemetry.vision_label,
        vision_label_text=telemetry.vision_label_text,
        vision_confidence=telemetry.vision_confidence,
        conveyor_speed=telemetry.conveyor_speed,
        conveyor_speed_baseline=telemetry.conveyor_speed_baseline,
        equipment_load=telemetry.equipment_load,
        temperature=telemetry.temperature,
        humidity=telemetry.humidity,
        fusion_verdict=telemetry.fusion_verdict,  # type: ignore[arg-type]
        fusion_verdict_text=telemetry.fusion_verdict_text,
        fusion_reason=telemetry.fusion_reason,
    )
