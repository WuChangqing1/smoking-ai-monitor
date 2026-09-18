"""生成异常证据图（YOLO 风格带框截图）。

用途
----
视频同步模式进入 warning / alarm 阶段时，视觉模型已确认物料堆积异常区域。
本脚本从监控视频中截取代表性帧，叠加与网页**完全一致**的固定检测框，
生成正式的证据图片，供报警详情与数据溯源引用。

单一事实源
----------
框坐标、类别名、置信度全部从 ``app.services.video_detection`` 读取，
**不在本脚本里重复写一份**。因此网页上的框与证据图上的框永远一致。

依赖
----
只使用 ffmpeg + Python 标准库，不安装 Pillow / OpenCV 等图像库。

用法（conda activate smoking）
----
    python scripts/generate_evidence.py
    python scripts/generate_evidence.py --check   # 只检查产物，不重新生成
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
VIDEO_PATH = BASE_DIR / "Video.mp4"
EVIDENCE_DIR = BASE_DIR / "frontend" / "public" / "images" / "evidence"

#: ffmpeg 可执行文件。优先 PATH，其次项目开发机上已验证的固定位置。
FFMPEG_CANDIDATES = (
    "ffmpeg",
    r"D:\App\Middle\TansferMP4ToMP3\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe",
)

#: 字体：标签需要显示中文，用系统中文字体
FONT_CANDIDATES = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)

#: 边框颜色：warning 橙色、alarm 红色（与网页 CSS 使用同一色值）
COLOR_WARNING = "0xD97706"
COLOR_ALARM = "0xC62828"


def find_ffmpeg() -> str:
    for candidate in FFMPEG_CANDIDATES:
        if candidate == "ffmpeg":
            if shutil.which("ffmpeg"):
                return "ffmpeg"
        elif Path(candidate).is_file():
            return candidate
    raise SystemExit(
        "未找到 ffmpeg。请安装 ffmpeg 或修改 FFMPEG_CANDIDATES 指向可执行文件。"
    )


def find_font() -> str | None:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None


def escape_path_for_filter(path: str) -> str:
    """ffmpeg filter 参数里的 Windows 路径需要转义盘符冒号。"""
    return path.replace("\\", "/").replace(":", r"\:")


def build_filter(
    *,
    x: int,
    y: int,
    w: int,
    h: int,
    color: str,
    label: str,
    font: str | None,
    width: int,
) -> str:
    """构造 drawbox + drawtext 滤镜串（YOLO 风格：粗框 + 左上角标签）。"""
    # 边框线宽按画面宽度等比，保证不同分辨率下观感一致
    thickness = max(3, round(width * 0.0025))
    # 标签字号同样等比
    font_size = max(20, round(width * 0.021))

    parts = [
        f"drawbox=x={x}:y={y}:w={w}:h={h}:color={color}@0.95:t={thickness}"
    ]

    label_y = max(4, y - round(font_size * 1.35))
    if font:
        parts.append(
            "drawtext=fontfile='{font}':text='{text}':x={x}:y={label_y}"
            ":fontsize={size}:fontcolor=white:box=1:boxcolor={color}@0.95"
            ":boxborderw={pad}".format(
                font=escape_path_for_filter(font),
                text=label.replace(":", r"\:").replace("'", ""),
                x=x,
                label_y=label_y,
                size=font_size,
                color=color,
                pad=max(4, round(font_size * 0.3)),
            )
        )
    return ",".join(parts)


def generate_one(
    *,
    ffmpeg: str,
    font: str | None,
    video: Path,
    out_path: Path,
    time_s: float,
    x: int,
    y: int,
    w: int,
    h: int,
    color: str,
    label: str,
    frame_width: int,
) -> None:
    vf = build_filter(
        x=x, y=y, w=w, h=h, color=color, label=label, font=font, width=frame_width
    )
    cmd = [
        ffmpeg,
        "-v", "error",
        "-ss", str(time_s),
        "-i", str(video),
        "-frames:v", "1",
        "-vf", vf,
        "-q:v", "2",
        str(out_path),
        "-y",
    ]
    subprocess.run(cmd, check=True)
    print(f"  已生成 {out_path.name}  ({out_path.stat().st_size // 1024} KB)  t={time_s}s  label={label}")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成异常证据图（带 YOLO 固定框）")
    parser.add_argument(
        "--check", action="store_true", help="只检查已有产物，不重新生成"
    )
    args = parser.parse_args()

    sys.path.insert(0, str(BACKEND_DIR))
    from app.services.video_detection import (  # noqa: PLC0415
        PRIMARY_DETECTION,
        detection_confidence_for_risk,
    )
    from app.services.video_sync import (  # noqa: PLC0415
        STATE_ALARM_RISK,
        STATE_WARNING_RISK,
        VIDEO_KEYFRAMES,
    )

    # 帧分辨率从关键帧常量推算（视频本身为 1280×720）
    FRAME_W, FRAME_H = 1280, 720

    cfg = PRIMARY_DETECTION
    # 归一化坐标 → 像素坐标：与网页使用同一组比例，保证位置一致
    x = round(cfg.x * FRAME_W)
    y = round(cfg.y * FRAME_H)
    w = round(cfg.width * FRAME_W)
    h = round(cfg.height * FRAME_H)

    # 异常时刻收敛到的风险值（关键帧终点），用于派生证据图置信度
    max_risk = max(f.risk for f in VIDEO_KEYFRAMES)

    targets = [
        {
            "name": cfg.evidence_image.rsplit("/", 1)[-1],
            "time": cfg.evidence_time,
            "risk": None,  # 用配置里给定的置信度
            "confidence": cfg.evidence_confidence,
            "color": COLOR_WARNING,
            "severity": "warning",
        },
        {
            "name": "main-camera-material-accumulation-alarm.jpg",
            "time": 9.5,
            "risk": None,
            "confidence": round(
                0.93 + 0.03 * min(1.0, max(0.0, (max_risk - STATE_ALARM_RISK) / (100 - STATE_ALARM_RISK))),
                3,
            ),
            "color": COLOR_ALARM,
            "severity": "alarm",
        },
    ]

    print("=== 异常证据图生成 ===")
    print(f"  固定框（归一化）: x={cfg.x} y={cfg.y} w={cfg.width} h={cfg.height}")
    print(f"  固定框（像素）  : x={x} y={y} w={w} h={h}  @ {FRAME_W}×{FRAME_H}")
    print(f"  类别            : {cfg.label} / {cfg.label_text}")
    print(f"  显示阶段        : 风险 ≥ {cfg.active_from_risk:.0f}（warning 及以上）")
    print()

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    if args.check:
        print("=== 产物检查 ===")
        ok = True
        for target in targets:
            path = EVIDENCE_DIR / target["name"]
            if path.is_file():
                print(f"  ✓ {target['name']}  ({path.stat().st_size // 1024} KB)")
            else:
                print(f"  ✗ {target['name']}  缺失")
                ok = False
        return 0 if ok else 1

    if not VIDEO_PATH.is_file():
        raise SystemExit(f"未找到源视频：{VIDEO_PATH}")

    ffmpeg = find_ffmpeg()
    font = find_font()
    print(f"  ffmpeg: {ffmpeg}")
    print(f"  字体  : {font or '未找到中文字体，标签将只显示数值'}")
    print()

    for target in targets:
        confidence = target["confidence"]
        label = f"{cfg.label_text} {confidence:.2f}"
        generate_one(
            ffmpeg=ffmpeg,
            font=font,
            video=VIDEO_PATH,
            out_path=EVIDENCE_DIR / target["name"],
            time_s=target["time"],
            x=x, y=y, w=w, h=h,
            color=target["color"],
            label=label,
            frame_width=FRAME_W,
        )

    print()
    print(f"完成，输出目录：{EVIDENCE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
