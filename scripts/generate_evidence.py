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
EVIDENCE_DIR = BASE_DIR / "frontend" / "public" / "images" / "evidence"

#: 视频来源，按优先级取第一个存在的文件。
#:
#: **必须优先使用实际接入网页的那份视频**（public/videos/main-monitor.mp4），
#: 否则证据图会来自另一份素材 —— 例如源片带水印、而网页用的是修好的版本时，
#: 证据图上就会残留水印，与页面画面对不上。
VIDEO_CANDIDATES = (
    BASE_DIR / "frontend" / "public" / "videos" / "main-monitor.mp4",
    BASE_DIR / "Video_repaired.mp4",
    BASE_DIR / "Video.mp4",
)


def resolve_video_path() -> Path:
    """返回实际用于生成证据图的视频路径。"""
    for candidate in VIDEO_CANDIDATES:
        if candidate.is_file():
            return candidate
    raise SystemExit(
        "未找到可用的源视频。请确认以下任一文件存在：\n  "
        + "\n  ".join(str(p) for p in VIDEO_CANDIDATES)
    )

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
    height: int,
    camera_label: str = "",
) -> str:
    """构造 drawbox + drawtext 滤镜串。

    包含两部分：
      * YOLO 风格检测框 + 左上角类别标签
      * 画面右下角机位标识（视频素材本身已不含水印，由这里叠加，
        与网页上的叠加层保持一致）
    """
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

        # 机位标识：右下角，半透明深色底 + 白字，与网页叠加层观感一致
        if camera_label:
            cam_size = max(18, round(width * 0.019))
            margin_x = round(width * 0.009)
            margin_y = round(height * 0.014)
            parts.append(
                "drawtext=fontfile='{font}':text='{text}':x=w-tw-{mx}:y=h-th-{my}"
                ":fontsize={size}:fontcolor=#f2f6f7:box=1"
                ":boxcolor=0x10181b@0.55:boxborderw={pad}".format(
                    font=escape_path_for_filter(font),
                    text=camera_label.replace(":", r"\:").replace("'", ""),
                    mx=margin_x,
                    my=margin_y,
                    size=cam_size,
                    pad=max(4, round(cam_size * 0.28)),
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
    frame_height: int,
    camera_label: str = "",
) -> None:
    vf = build_filter(
        x=x, y=y, w=w, h=h, color=color, label=label, font=font,
        width=frame_width, height=frame_height, camera_label=camera_label,
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

    video_path = resolve_video_path()
    ffmpeg = find_ffmpeg()
    font = find_font()
    print(f"  视频源: {video_path}")
    print(f"  ffmpeg: {ffmpeg}")
    print(f"  字体  : {font or '未找到中文字体，标签将只显示数值'}")
    print(f"  机位标识: {cfg.camera_id}（右下角）")
    print()

    for target in targets:
        confidence = target["confidence"]
        label = f"{cfg.label_text} {confidence:.2f}"
        generate_one(
            ffmpeg=ffmpeg,
            font=font,
            video=video_path,
            out_path=EVIDENCE_DIR / target["name"],
            time_s=target["time"],
            x=x, y=y, w=w, h=h,
            color=target["color"],
            label=label,
            frame_width=FRAME_W,
            frame_height=FRAME_H,
            # 与网页一致：右下角叠加机位标识
            camera_label=cfg.camera_id.replace("CAM-", "Camera "),
        )

    print()
    print(f"完成，输出目录：{EVIDENCE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
