"""后端配置。

约束：服务器地址、SSH 信息、密码、Token 一律不得写死在仓库里，
只能通过环境变量注入（部署时用 systemd EnvironmentFile 或 .env，已被 .gitignore 忽略）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = "smoking-monitor-api"
    version: str = "0.1.0"

    host: str = os.getenv("SMOKING_HOST", "127.0.0.1")
    port: int = int(os.getenv("SMOKING_PORT", "18080"))

    # 仅本机前端开发端口，不开放通配来源
    cors_origins: list[str] = field(
        default_factory=lambda: _env_list(
            "SMOKING_CORS_ORIGINS",
            ["http://127.0.0.1:15173", "http://localhost:15173"],
        )
    )

    # 原始资料口径：雷达与摄像头采集频率 10 Hz
    data_rate_hz: int = int(os.getenv("SMOKING_DATA_RATE_HZ", "10"))

    # 仿真推进间隔（秒）。资料口径采集频率为 10 Hz，引擎内部按 100 ms 推进；
    # 该值仅控制后台 tick 线程的批量步进节奏。
    tick_seconds: float = float(os.getenv("SMOKING_TICK_SECONDS", "0.1"))

    # 仿真随机种子。固定 seed 保证数据可复现，pytest 不会因随机数偶发失败。
    simulation_seed: int = int(os.getenv("SMOKING_SIMULATION_SEED", "20250519"))

    db_path: Path = Path(os.getenv("SMOKING_DB_PATH", str(BASE_DIR / "data" / "smoking.db")))

    @property
    def is_simulation(self) -> bool:
        """当前是否仿真模式。真实设备接入后由环境变量切换。"""
        return os.getenv("SMOKING_SIMULATION", "1") == "1"


settings = Settings()
