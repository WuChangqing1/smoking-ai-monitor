"""导出前后端对等校验的期望值（开发期工具）。

前端 `src/video/videoTelemetry.ts` / `videoDetection.ts` 与后端
`app/services/video_sync.py` / `video_detection.py` 是同一套规则的
两份实现。本脚本把后端结果导出为 JSON，供
`frontend/scripts/check-*-parity.mjs` 逐点比对。

用法（conda activate smoking）：
    python scripts/export_parity_fixtures.py
    cd frontend && node scripts/check-telemetry-parity.mjs ../.parity-telemetry.json
    cd frontend && node scripts/check-detection-parity.mjs ../.parity-detection.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from app.services.video_detection import resolve_video_detection_box  # noqa: E402
from app.services.video_sync import resolve_video_telemetry  # noqa: E402

#: 采样点：每 0.1 s 一个，覆盖整段 10 s 视频
TIMES = [round(i / 10.0, 1) for i in range(0, 101)]

#: 检测框校验覆盖的摄像头：已配置的 + 未配置的（验证空框行为）
CAMERAS = ("CAM-01", "CAM-02", "UNKNOWN")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    telemetry = {}
    for t in TIMES:
        x = resolve_video_telemetry(t)
        telemetry[f"{t:.1f}"] = [
            x.distance,
            x.risk_index,
            x.coverage,
            x.conveyor_speed,
            x.equipment_load,
            x.sim_state,
        ]

    detection = {}
    for camera in CAMERAS:
        for t in TIMES:
            b = resolve_video_detection_box(t, camera)
            detection[f"{t:.1f}|{camera}"] = {
                "visible": b.visible,
                "x": b.x,
                "y": b.y,
                "width": b.width,
                "height": b.height,
                "confidence": b.confidence,
                "severity": b.severity,
                "label": b.label,
                "evidenceImage": b.evidence_image,
            }

    tel_path = BASE_DIR / ".parity-telemetry.json"
    det_path = BASE_DIR / ".parity-detection.json"
    for path, payload, label in (
        (tel_path, telemetry, "遥测"),
        (det_path, detection, "检测框"),
    ):
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f)
        print(f"  已导出{label}期望值 {path.name}（{len(payload)} 条）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
