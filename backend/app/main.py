# FastAPI 应用入口 —— 烟厂制丝线物流智能监控与多模态预警平台
#
# 轮次 1：仅健康检查与只读元信息，用于确认工程可启动。
# 轮次 4：接入 SimulationEngine，补齐 /api/realtime 等实时数据接口。

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app = FastAPI(
    title="烟厂制丝线物流智能监控与多模态预警平台 API",
    description=(
        "视觉识别 + 激光雷达多模态融合的制丝线物流监控后端。\n\n"
        "当前为比赛展示 / 仿真环境：数据由统一仿真引擎产生，"
        "接口结构已预留真实设备接入能力。"
    ),
    version=settings.version,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

# 开发环境前端跑在 Vite (127.0.0.1:15173)，生产由 Nginx 同源反代。
# 只放开本机来源，不设置 allow_origins=["*"]。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["system"], summary="健康检查")
def health() -> dict:
    """部署探活与测试用。"""
    return {"status": "ok", "service": settings.app_name, "version": settings.version}


@app.get("/api/meta", tags=["system"], summary="平台元信息")
def meta() -> dict:
    """返回平台基础口径，便于前端在接口未就绪时也能渲染静态文案。"""
    return {
        "platform_name": "烟厂制丝线物流智能监控与多模态预警平台",
        "project_name": "视觉识别及雷达技术在制丝线物流监视的研究与应用",
        "mode": "simulation",
        "mode_note": "比赛展示 / 仿真环境，接口结构预留真实设备接入能力",
        "conveyor_line": "制丝线",
        "monitor_points": 7,
        "devices": {"radar": 3, "camera": 15, "total": 18},
        "data_rate_hz": settings.data_rate_hz,
    }
