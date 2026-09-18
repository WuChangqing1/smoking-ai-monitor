"""核对点位与机位编号映射（开发期自检工具）。

监控画面上的 "Camera NN" 与点位号是两套编号，容易混淆。
本脚本打印后端当前的定义，便于与前端 videoDetection / syncedTelemetry 对照。

用法（conda activate smoking）：
    python scripts/check_camera_mapping.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from app.services.devices import (  # noqa: E402
    CAMERA_NUMBER,
    PRIMARY_CAMERA,
    PRIMARY_POINT,
    monitor_points,
    primary_point,
)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    print("=== 机位编号映射（点位 → Camera NN）===")
    for position in sorted(CAMERA_NUMBER):
        mark = "  ← 主监控点" if position == PRIMARY_POINT else ""
        print(f"  点位 {position} → Camera {CAMERA_NUMBER[position]:02d}{mark}")

    point = primary_point()
    print()
    print("=== 主监控点 ===")
    print(f"  PRIMARY_POINT  = {PRIMARY_POINT}")
    print(f"  PRIMARY_CAMERA = {PRIMARY_CAMERA}")
    print(f"  code / name    = {point['code']} / {point['name']}")
    print(f"  device_id / ip = {point['device_id']} / {point['device_ip']}")

    print()
    print("=== 全部监控点位 ===")
    for item in monitor_points():
        stream = item["stream"] or "—"
        print(
            f"  {item['id']}  {item['code']:<10} pos={item['position']} "
            f"radar={'是' if item['has_radar'] else '否'}  stream={stream}"
        )

    # 一致性断言：主监控点的 code 必须是 PRIMARY_CAMERA
    assert point["code"] == PRIMARY_CAMERA, "主监控点 code 与 PRIMARY_CAMERA 不一致"
    print()
    print("✓ 主监控点标识一致：", point["code"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
