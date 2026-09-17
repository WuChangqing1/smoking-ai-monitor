"""检测任务启停与仿真控制。

语义（严格限定）：
  - 启停控制**只控制检测任务**，不控制真实生产设备；
  - ``/api/simulation/scenario/{scenario}`` 仅在演示环境使用，
    用于答辩前主动切换状态以录制演示视频，不在主界面突出展示。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from app.schemas import ActionResponse, ScenarioT
from app.services.models import MONITOR_STATES
from app.services.simulation import get_engine

router = APIRouter(prefix="/api", tags=["control"])


def _response(message: str) -> ActionResponse:
    engine = get_engine()
    return ActionResponse(ok=True, message=message, sim_state=engine.snapshot().sim_state)


@router.post("/detection/start", response_model=ActionResponse, summary="开始检测任务")
def detection_start() -> ActionResponse:
    """启动 AI 检测任务。**不是**启动输送生产线。"""
    return _response(get_engine().start_detection())


@router.post("/detection/stop", response_model=ActionResponse, summary="停止检测任务")
def detection_stop() -> ActionResponse:
    """停止检测任务。仿真数据与风险变化暂停，历史数据仍可查询。"""
    return _response(get_engine().stop_detection())


@router.post("/simulation/reset", response_model=ActionResponse, summary="重置模拟")
def simulation_reset() -> ActionResponse:
    """重置仿真：回到 normal 并清理当前异常状态，用于演示前复位。"""
    return _response(get_engine().reset())


@router.post(
    "/simulation/scenario/{scenario}",
    response_model=ActionResponse,
    summary="切换演示场景（仅演示环境）",
)
def set_scenario(
    scenario: ScenarioT = Path(description="目标场景：normal / attention / warning / alarm"),
) -> ActionResponse:
    """强制进入指定仿真状态，便于演示与录屏。

    正常演示时引擎自行循环，大部分时间保持正常；本接口只用于主动触发。
    """
    if scenario not in MONITOR_STATES:
        raise HTTPException(status_code=400, detail=f"不支持的演示场景：{scenario}")
    return _response(get_engine().set_scenario(scenario))


@router.post(
    "/simulation/scenario",
    response_model=ActionResponse,
    summary="退出演示场景",
)
def clear_scenario() -> ActionResponse:
    """恢复自动状态循环。

    刻意使用 ``/simulation/scenario``（不带路径参数）而不是 ``/scenario/clear``：
    后者会被 ``/scenario/{scenario}`` 抢先匹配，把 "clear" 当成场景名而报 422。
    """
    return _response(get_engine().clear_scenario())
