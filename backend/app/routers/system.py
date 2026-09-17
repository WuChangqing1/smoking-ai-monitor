"""系统状态与平台元信息。"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import PlatformMeta, StatusItem, SystemStatus
from app.services.devices import TOTAL_DEVICES
from app.services.simulation import get_engine

router = APIRouter(prefix="/api", tags=["system"])

PLATFORM_NAME = "烟厂制丝线物流智能监控与多模态预警平台"
PROJECT_NAME = "视觉识别及雷达技术在制丝线物流监视的研究与应用"


@router.get("/system/status", response_model=SystemStatus, summary="系统运行状态")
def system_status() -> SystemStatus:
    """顶栏与首页状态卡的数据源。

    所有字段都由同一个仿真引擎快照派生，因此与 /api/realtime 完全一致。
    """
    engine = get_engine()
    snapshot = engine.snapshot()

    running = snapshot.detection_running
    radar_ok = snapshot.radar.online and snapshot.radar.data_fresh
    sim_state = snapshot.sim_state

    ai_state = "ok" if running else "offline"
    ai_text = "运行中" if running else "已停止"

    statuses = [
        StatusItem(
            key="system",
            label="系统运行",
            state="ok",
            text="正常",
            detail=f"演示模式：{snapshot.sim_state_text}",
        ),
        StatusItem(
            key="ai",
            label="AI 分析",
            state=ai_state,  # type: ignore[arg-type]
            text=ai_text,
            detail=(
                f"视觉模型置信度 {snapshot.vision.confidence * 100:.1f}%，"
                f"推理耗时 {snapshot.vision.latency_ms} ms"
            ),
        ),
        StatusItem(
            key="radar",
            label="雷达数据",
            state="ok" if radar_ok else "warn",  # type: ignore[arg-type]
            text="正常" if radar_ok else "刷新异常",
            detail=(
                f"{snapshot.radar.sample_rate_hz} Hz 采集，"
                f"当前测距 {snapshot.radar.distance:.2f} m"
            ),
        ),
        StatusItem(
            key="video",
            label="视频监控",
            state="ok",
            text="在线",
            detail="Camera 01 · 制丝线 2 号输送段",
        ),
    ]

    return SystemStatus(
        ts=snapshot.ts,
        detection_running=running,
        sim_state=sim_state,
        sim_state_text=snapshot.sim_state_text,
        uptime_hours=engine.uptime_hours,
        today_warnings=engine.today_warnings,
        devices_online=TOTAL_DEVICES,
        devices_total=TOTAL_DEVICES,
        statuses=statuses,
    )


@router.get("/meta", response_model=PlatformMeta, summary="平台元信息")
def meta() -> PlatformMeta:
    from app.config import settings

    return PlatformMeta(
        platform_name=PLATFORM_NAME,
        project_name=PROJECT_NAME,
        mode="simulation" if settings.is_simulation else "realtime",
        mode_note="比赛展示 / 仿真环境，接口结构预留真实设备接入能力",
        conveyor_line="制丝线",
        monitor_points=7,
        devices={"radar": 3, "camera": 15, "total": TOTAL_DEVICES},
        data_rate_hz=settings.data_rate_hz,
    )
