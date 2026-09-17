"""设备台账与监控点位。

设备数量与规格**全部取自原始验收报告**：
  - 激光雷达 3 台（重邮自研）：测距 0.1–40 m、精度 ±5 cm、刷新率最高 1000 Hz、IP65
  - 网络摄像机 15 台（海康 DS-2CD2242CX8-L）：400 万像素、H.265、IP67、25 fps
  - 另含 NVR / 显示器 / PoE 交换机 / 汇聚交换机（在系统设置页以台账形式展示）

监控点位 7 个（点位1~点位7），与原始资料一致：
  - 点位 1~3 同时具备雷达与摄像头 → 联合判断
  - 点位 4~7 仅具备摄像头      → 单独判断
"""

from __future__ import annotations

#: 18 台在线设备 = 3 雷达 + 15 摄像机
TOTAL_DEVICES = 18

POINT_LOCATIONS: dict[int, str] = {
    1: "制丝线 1 号输送段",
    2: "制丝线 2 号输送段",
    3: "制丝线 3 号输送段",
    4: "叶线输送段",
    5: "叶线提升段",
    6: "加料出口段",
    7: "贮叶柜入口段",
}

#: 具备激光雷达的点位（点位 1~3）
RADAR_POINTS: tuple[int, ...] = (1, 2, 3)

#: 主监控点
PRIMARY_POINT = 2


def _radar_device(position: int, index: int) -> dict:
    # 点位 2（主监控点）对应 192.168.1.198 —— 与原始资料中的报警 IP 一致
    ip = f"192.168.1.{196 + position}"
    return {
        "id": f"RAD-{position:02d}",
        "name": f"制丝线 {position} 号工位雷达",
        "kind": "radar",
        "model": "重邮自研 ToF 激光雷达",
        "vendor": "重庆邮电大学",
        "ip": ip,
        "location": POINT_LOCATIONS[position],
        "point_id": f"P{position:02d}",
        "online": True,
        "spec": "测距 0.1–40 m · 精度 ±5 cm · 设备最高刷新率 1000 Hz · IP65",
        "radar": {
            "range": "0.1–40 m",
            "accuracy": "±5 cm",
            "max_refresh_hz": 1000,
            "protection": "IP65",
        },
        "camera": None,
    }


def _camera_device(position: int, index: int) -> dict:
    ip = f"192.168.1.{201 + index}"
    return {
        "id": f"CAM-{position:02d}",
        "name": f"制丝线 {position} 号工位摄像机" if position <= 3 else f"{POINT_LOCATIONS[position]}摄像机",
        "kind": "camera",
        "model": "DS-2CD2242CX8-L",
        "vendor": "海康威视",
        "ip": ip,
        "location": POINT_LOCATIONS[position],
        "point_id": f"P{position:02d}",
        "online": True,
        "spec": "400 万像素 · H.265 · IP67 · 25 fps · 最低照度 0.01 Lux",
        "radar": None,
        "camera": {
            "resolution": "400 万像素",
            "encoding": "H.265",
            "protection": "IP67",
            "fps": 25,
        },
    }


def build_devices() -> list[dict]:
    """构造 18 台设备的台账（3 雷达 + 15 摄像机）。"""
    devices: list[dict] = []

    # 3 台激光雷达 → 点位 1~3
    for position in RADAR_POINTS:
        devices.append(_radar_device(position, index=position))

    # 15 台摄像机：每个点位 2 台，其中点位 1 再补 1 台，合计 15 台
    camera_index = 0
    camera_plan = {1: 3, 2: 2, 3: 2, 4: 2, 5: 2, 6: 2, 7: 2}
    for position in range(1, 8):
        for _ in range(camera_plan[position]):
            camera_index += 1
            devices.append(_camera_device(position, index=camera_index))

    return devices


DEVICES: list[dict] = build_devices()


def monitor_points() -> list[dict]:
    """监控点位列表。只有主监控点具备真实画面素材，其余为待切换占位。"""
    points: list[dict] = []
    for position in range(1, 8):
        has_radar = position in RADAR_POINTS
        points.append(
            {
                "id": f"P{position:02d}",
                "code": f"Camera {position:02d}",
                "name": POINT_LOCATIONS[position],
                "position": position,
                "device_id": f"RAD-{position:02d}" if has_radar else f"CAM-{position:02d}",
                "device_ip": f"192.168.1.{196 + position}"
                if has_radar
                else f"192.168.1.{201 + position}",
                "has_radar": has_radar,
                "online": True,
                # 仅主监控点有画面；其余返回 None，前端显示"待切换"占位
                "stream": "/videos/main-monitor.mp4" if position == PRIMARY_POINT else None,
            }
        )
    return points


def primary_point() -> dict:
    return next(p for p in monitor_points() if p["position"] == PRIMARY_POINT)
