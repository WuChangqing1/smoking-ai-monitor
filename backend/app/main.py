"""FastAPI 应用入口 —— 烟厂制丝线物流智能监控与多模态预警平台。

架构说明
--------
* 所有实时数据来自 ``app/services/simulation.py`` 中的唯一 SimulationEngine 实例，
  由 ``app/services/ticker.py`` 的后台线程按 10 Hz（资料口径）推进；
* 前端按约 1 s 轮询 ``/api/realtime``，趋势数据由该接口一并返回的降采样序列提供；
* 数据库仅用 SQLite（标准库 ``sqlite3``），服务于知识库。

当前版本的数据由平台监控服务统一提供，接口结构已预留设备接入能力（见 README 第 11 节）。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    ai,
    alarms,
    control,
    knowledge,
    prediction,
    realtime,
    system,
    video_sync,
)
from app.services.knowledge import get_knowledge_base
from app.services.simulation import get_engine
from app.services.ticker import ticker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("smoking.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """启动/停止后台采集 tick 线程与知识库。"""
    engine = get_engine()
    # 视频同步模式下关闭事件登记：遥测由视频时间轴解算，
    # 且视频循环回放不应不断写入永久报警记录。
    engine.event_recording = not settings.is_video_sync
    logger.info(
        "监控服务已就绪：seed=%s，运行模式=%s，内部采样 10 Hz，历史接口降采样输出",
        engine.seed,
        settings.run_mode,
    )
    count = get_knowledge_base().initialize()
    logger.info("知识库已就绪：%d 条历史事件", count)

    ticker.start()
    try:
        yield
    finally:
        ticker.stop()


app = FastAPI(
    title="烟厂制丝线物流智能监控与多模态预警平台 API",
    description=(
        "视觉识别 + 激光雷达多模态融合的制丝线物流监控后端。\n\n"
        "实时数据由平台监控服务统一提供（内部 10 Hz 采集，"
        "对外输出 60~180 点降采样历史），接口结构已预留设备接入能力。\n\n"
        "启停控制仅作用于**检测任务**，不控制真实生产设备。"
    ),
    version=settings.version,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# 开发环境前端跑在 Vite (127.0.0.1:15173)，生产由 Nginx 同源反代。
# 只放开本机来源，不使用 allow_origins=["*"]。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(realtime.router)
app.include_router(control.router)
app.include_router(alarms.router)
app.include_router(prediction.router)
app.include_router(knowledge.router)
app.include_router(video_sync.router)
app.include_router(ai.router)


@app.get("/api/health", tags=["system"], summary="健康检查")
def health() -> dict:
    """部署探活与测试用。"""
    return {"status": "ok", "service": settings.app_name, "version": settings.version}
