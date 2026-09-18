"""检测任务启停与工况设定。

语义（严格限定）：
  - 启停控制**只控制检测任务**，不控制真实生产设备；
  - ``/api/simulation/scenario`` 用于现场联调、阈值校验与应急演练时
    手动指定运行工况，正常生产时无需使用。
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
    """停止检测任务。数据采集与风险计算暂停，历史数据仍可查询。"""
    return _response(get_engine().stop_detection())


@router.post("/simulation/reset", response_model=ActionResponse, summary="复位运行状态")
def simulation_reset() -> ActionResponse:
    """复位运行状态：工况回到 normal 并清理当前异常状态。"""
    return _response(get_engine().reset())


@router.post(
    "/simulation/scenario/{scenario}",
    response_model=ActionResponse,
    summary="设定运行工况",
)
def set_scenario(
    scenario: ScenarioT = Path(description="目标工况：normal / attention / warning / alarm"),
) -> ActionResponse:
    """手动指定当前运行工况。

    用于现场联调、阈值校验与应急演练时复现特定工况；
    不指定时引擎按自动工况循环运行，大部分时间保持正常。
    """
    if scenario not in MONITOR_STATES:
        raise HTTPException(status_code=400, detail=f"不支持的运行工况：{scenario}")
    return _response(get_engine().set_scenario(scenario))


@router.post(
    "/simulation/scenario",
    response_model=ActionResponse,
    summary="恢复自动工况",
)
def clear_scenario() -> ActionResponse:
    """恢复自动工况循环。

    刻意使用 ``/simulation/scenario``（不带路径参数）而不是 ``/scenario/clear``：
    后者会被 ``/scenario/{scenario}`` 抢先匹配，把 "clear" 当成工况名而报 422。
    """
    return _response(get_engine().clear_scenario())
