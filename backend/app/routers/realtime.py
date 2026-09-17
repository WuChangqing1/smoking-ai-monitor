"""实时数据、历史序列与设备台账。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import (
    DeviceOut,
    EnvironmentReadingOut,
    FusionReadingOut,
    MonitorPointOut,
    RadarReadingOut,
    RealtimeSnapshotOut,
    RiskReadingOut,
    SimSampleOut,
    VisionReadingOut,
)
from app.services import devices as device_service
from app.services.simulation import HISTORY_DEFAULT_POINTS, HISTORY_MAX_POINTS, get_engine

router = APIRouter(prefix="/api", tags=["realtime"])


def _sample_out(sample) -> SimSampleOut:
    return SimSampleOut(
        ts=sample.ts,
        label=sample.label,
        sim_state=sample.sim_state,
        severity=sample.severity,
        radar_distance=sample.radar_distance,
        radar_filtered=sample.radar_filtered,
        risk_index=sample.risk_index,
        vision_coverage=sample.vision_coverage,
        vision_confidence=sample.vision_confidence,
        conveyor_speed=sample.conveyor_speed,
        temperature=sample.temperature,
        humidity=sample.humidity,
    )


@router.get("/realtime", response_model=RealtimeSnapshotOut, summary="实时快照")
def realtime(
    points: int = Query(
        HISTORY_DEFAULT_POINTS,
        ge=10,
        le=HISTORY_MAX_POINTS,
        description="随快照一并返回的历史点数（降采样后）",
    ),
) -> RealtimeSnapshotOut:
    """当前完整状态 + 滚动窗口历史。

    前端按约 1 s 轮询本接口即可：既能拿到当前读数，也能直接画趋势图，
    不需要额外再请求一次历史接口。
    """
    engine = get_engine()
    snapshot = engine.snapshot()
    samples = engine.history(points)
    point = device_service.primary_point()

    # 降采样间隔：让前端能如实标注趋势图的时间跨度，而不是靠猜
    interval = (
        round((samples[-1].ts - samples[0].ts) / (len(samples) - 1), 3)
        if len(samples) > 1
        else 0.0
    )

    return RealtimeSnapshotOut(
        ts=snapshot.ts,
        monitor_point=MonitorPointOut(**point),
        sim_state=snapshot.sim_state,
        sim_state_text=snapshot.sim_state_text,
        detection_running=snapshot.detection_running,
        stage=snapshot.stage,
        scenario_forced=snapshot.scenario_forced,
        radar=RadarReadingOut(
            distance=snapshot.radar.distance,
            baseline_distance=snapshot.radar.baseline_distance,
            delta=snapshot.radar.delta,
            measured=snapshot.radar.measured,
            filtered=snapshot.radar.filtered,
            sample_rate_hz=snapshot.radar.sample_rate_hz,
            max_refresh_hz=snapshot.radar.max_refresh_hz,
            refresh_text=snapshot.radar.refresh_text,
            data_fresh=snapshot.radar.data_fresh,
            online=snapshot.radar.online,
        ),
        vision=VisionReadingOut(
            status=snapshot.vision.status,
            label=snapshot.vision.label,
            label_text=snapshot.vision.label_text,
            confidence=snapshot.vision.confidence,
            coverage=snapshot.vision.coverage,
            latency_ms=snapshot.vision.latency_ms,
            online=snapshot.vision.online,
        ),
        environment=EnvironmentReadingOut(
            temperature=snapshot.environment.temperature,
            humidity=snapshot.environment.humidity,
            conveyor_speed=snapshot.environment.conveyor_speed,
            conveyor_speed_baseline=snapshot.environment.conveyor_speed_baseline,
            equipment_load=snapshot.environment.equipment_load,
            material_coverage=snapshot.environment.material_coverage,
        ),
        risk=RiskReadingOut(
            index=snapshot.risk.index,
            level=snapshot.risk.level,
            level_text=snapshot.risk.level_text,
            trend=snapshot.risk.trend,
            trend_text=snapshot.risk.trend_text,
        ),
        fusion=FusionReadingOut(
            verdict=snapshot.fusion.verdict,
            verdict_text=snapshot.fusion.verdict_text,
            mode=snapshot.fusion.mode,
            reason=snapshot.fusion.reason,
            confidence=snapshot.fusion.confidence,
        ),
        samples=[_sample_out(s) for s in samples],
        sample_interval_seconds=interval,
    )


@router.get(
    "/realtime/history",
    response_model=list[SimSampleOut],
    summary="实时历史序列（降采样）",
)
def realtime_history(
    limit: int = Query(
        HISTORY_DEFAULT_POINTS,
        ge=10,
        le=HISTORY_MAX_POINTS,
        description="返回的数据点数",
    ),
) -> list[SimSampleOut]:
    """趋势图专用接口。

    内部以 10 Hz 采样，但对外只返回降采样后的 60~180 个点，
    避免把数千个原始采样点丢给浏览器。
    """
    return [_sample_out(s) for s in get_engine().history(limit)]


@router.get("/devices", response_model=list[DeviceOut], summary="设备台账")
def devices() -> list[DeviceOut]:
    """18 台设备（3 雷达 + 15 摄像机），规格取自项目验收报告。"""
    return [DeviceOut(**d) for d in device_service.DEVICES]


@router.get("/monitor-points", response_model=list[MonitorPointOut], summary="监控点位")
def monitor_points() -> list[MonitorPointOut]:
    """7 个监控点位。仅主监控点具备画面素材，其余 stream 为 null。"""
    return [MonitorPointOut(**p) for p in device_service.monitor_points()]
