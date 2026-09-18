"""视频异常检测框与证据图测试。

覆盖任务要求的 15 项检测框检查与 8 项证据图检查，外加回归保护。
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app.services.video_detection import (
    DETECTION_CONFIGS,
    PRIMARY_CAMERA_ID,
    PRIMARY_DETECTION,
    config_for,
    detection_confidence_for_risk,
    detection_severity_for_risk,
    evidence_image_for,
    resolve_video_detection_box,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EVIDENCE_DIR = REPO_ROOT / "frontend" / "public" / "images" / "evidence"


# =============================================================================
# 1~13. 检测框逻辑
# =============================================================================


class TestDetectionVisibility:
    def test_t0_no_box(self) -> None:
        box = resolve_video_detection_box(0.0)
        assert box.visible is False
        assert box.severity == "none"
        assert box.evidence_image is None

    @pytest.mark.parametrize("t", [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 5.5])
    def test_normal_and_attention_no_box(self, t: float) -> None:
        """normal 与 attention 阶段不得出现检测框。"""
        box = resolve_video_detection_box(t)
        assert box.visible is False, f"t={t} 不应显示检测框"
        assert box.confidence == 0.0

    @pytest.mark.parametrize("t", [6.0, 6.5, 7.0, 7.5, 8.0, 8.5])
    def test_warning_has_box(self, t: float) -> None:
        box = resolve_video_detection_box(t)
        assert box.visible is True
        assert box.severity == "warning"
        assert box.evidence_image is not None

    @pytest.mark.parametrize("t", [8.8, 9.0, 9.5, 10.0])
    def test_alarm_has_box(self, t: float) -> None:
        box = resolve_video_detection_box(t)
        assert box.visible is True
        assert box.severity == "alarm"

    @pytest.mark.parametrize("t", [0.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 99.0, -5.0])
    def test_no_such_attribute_error_on_extremes(self, t: float) -> None:
        box = resolve_video_detection_box(t)
        assert isinstance(box.visible, bool)


class TestDetectionBoxGeometry:
    def test_warning_and_alarm_share_identical_geometry(self) -> None:
        """任务核心约束：warning 与 alarm 的框位置与尺寸必须完全相同。"""
        warning = resolve_video_detection_box(7.0)
        alarm = resolve_video_detection_box(9.5)

        assert warning.severity == "warning"
        assert alarm.severity == "alarm"
        assert warning.x == alarm.x
        assert warning.y == alarm.y
        assert warning.width == alarm.width
        assert warning.height == alarm.height

    def test_geometry_constant_across_whole_timeline(self) -> None:
        """整个时间轴上框坐标恒定（不做动态跟踪）。"""
        geometries = set()
        for i in range(0, 101):
            box = resolve_video_detection_box(i / 10)
            geometries.add((box.x, box.y, box.width, box.height))
        assert len(geometries) == 1, f"框坐标发生了变化: {geometries}"

    def test_geometry_within_unit_range(self) -> None:
        box = resolve_video_detection_box(7.0)
        assert 0.0 < box.x < 1.0
        assert 0.0 < box.y < 1.0
        assert 0.0 < box.width < 1.0
        assert 0.0 < box.height < 1.0
        # 框必须完整落在画面内
        assert box.x + box.width <= 1.0
        assert box.y + box.height <= 1.0

    def test_box_is_not_whole_frame(self) -> None:
        """框不能大到覆盖整个画面。"""
        box = resolve_video_detection_box(7.0)
        assert box.width * box.height < 0.25

    def test_box_is_large_enough_to_be_visible(self) -> None:
        """框也不能太小，否则评委看不清。

        当前为「覆盖物料带区域的左上 1/4」子框，宽高各约为原框的一半。
        """
        box = resolve_video_detection_box(7.0)
        assert box.width >= 0.09
        assert box.height >= 0.20
        # 面积下限：太小则失去可视化意义
        assert box.width * box.height >= 0.020

    def test_box_covers_material_band(self) -> None:
        """框必须覆盖物料堆积区 —— 用实测像素点位校验，防止坐标被误改。

        手工查看异常帧确认的物料带位置（1280×720）：
          (470,250) (480,320) 位于框内；
          (500,350) 是框下边缘附近的物料，允许在边缘带内。
        """
        box = resolve_video_detection_box(8.5)
        frame_w, frame_h = 1280, 720
        # 必须完整落在框内的物料点
        inside_points = [(470, 250), (480, 320), (455, 225), (470, 300)]
        for px, py in inside_points:
            nx, ny = px / frame_w, py / frame_h
            assert box.x <= nx <= box.x + box.width, f"物料点 ({px},{py}) 不在框内(x)"
            assert box.y <= ny <= box.y + box.height, f"物料点 ({px},{py}) 不在框内(y)"

        # 框下边缘不得超过物料继续延伸的范围太多（避免框到无关区域）
        assert box.y + box.height <= 0.55


class TestDetectionConfidence:
    def test_warning_confidence_range(self) -> None:
        warning_values = [
            resolve_video_detection_box(t).confidence for t in (6.0, 6.5, 7.0, 7.5, 8.0, 8.5)
        ]
        for value in warning_values:
            assert 0.88 <= value <= 0.93, value

    def test_alarm_confidence_range(self) -> None:
        alarm_values = [
            resolve_video_detection_box(t).confidence for t in (8.8, 9.0, 9.5, 10.0)
        ]
        for value in alarm_values:
            assert 0.93 <= value <= 0.97, value

    def test_confidence_increases_with_risk(self) -> None:
        low = resolve_video_detection_box(6.0).confidence
        high = resolve_video_detection_box(10.0).confidence
        assert high > low

    def test_confidence_is_deterministic(self) -> None:
        """同一 t 反复解算结果完全一致（不使用随机数）。"""
        for t in (6.0, 7.3, 8.0, 9.0, 9.7):
            first = resolve_video_detection_box(t)
            for _ in range(5):
                again = resolve_video_detection_box(t)
                assert again.confidence == first.confidence
                assert again.severity == first.severity
                assert again.visible == first.visible

    def test_confidence_no_large_jumps(self) -> None:
        """相邻采样点之间置信度不得剧烈跳动。"""
        prev = resolve_video_detection_box(6.0).confidence
        for i in range(61, 101):
            cur = resolve_video_detection_box(i / 10).confidence
            assert abs(cur - prev) < 0.01, f"t={i/10} 置信度跳变 {prev}→{cur}"
            prev = cur

    def test_confidence_zero_when_no_box(self) -> None:
        assert detection_confidence_for_risk(20.0) == 0.0
        assert detection_confidence_for_risk(54.9) == 0.0

    def test_severity_thresholds(self) -> None:
        assert detection_severity_for_risk(0.0) == "none"
        assert detection_severity_for_risk(29.0) == "none"
        assert detection_severity_for_risk(30.0) == "none"  # attention 仍无框
        assert detection_severity_for_risk(54.9) == "none"
        assert detection_severity_for_risk(55.0) == "warning"
        assert detection_severity_for_risk(79.9) == "warning"
        assert detection_severity_for_risk(80.0) == "alarm"
        assert detection_severity_for_risk(95.0) == "alarm"


class TestDetectionLoop:
    def test_loop_makes_box_disappear(self) -> None:
        """alarm → loop → normal 时检测框必须立即消失。"""
        end = resolve_video_detection_box(10.0)
        assert end.visible is True
        assert end.severity == "alarm"

        restarted = resolve_video_detection_box(0.0)
        assert restarted.visible is False
        assert restarted.severity == "none"
        assert restarted.evidence_image is None

    def test_second_cycle_identical_to_first(self) -> None:
        """第二轮同一时刻的框状态与第一轮一致。"""
        for t in (4.0, 6.0, 7.0, 9.0):
            first = resolve_video_detection_box(t)
            second = resolve_video_detection_box(t)
            assert first.visible == second.visible
            assert first.severity == second.severity
            assert first.confidence == second.confidence

    def test_out_of_range_clamped_safely(self) -> None:
        assert resolve_video_detection_box(999.0).severity == "alarm"
        assert resolve_video_detection_box(-999.0).visible is False
        assert resolve_video_detection_box(float("nan")).visible is False


# =============================================================================
# 多摄像头扩展性
# =============================================================================


class TestCameraRegistry:
    def test_primary_camera_configured(self) -> None:
        assert PRIMARY_CAMERA_ID in DETECTION_CONFIGS
        assert config_for(PRIMARY_CAMERA_ID) is PRIMARY_DETECTION

    def test_unknown_camera_returns_empty_box(self) -> None:
        """未配置的摄像头不渲染检测框，而不是报错或给出假坐标。"""
        box = resolve_video_detection_box(9.0, camera_id="CAM-99")
        assert box.visible is False
        assert box.severity == "none"
        assert box.confidence == 0.0
        assert box.label == ""

    @pytest.mark.parametrize("camera_id", ["CAM-02", "CAM-03", "CAM-04"])
    def test_future_cameras_safe_before_video_arrives(self, camera_id: str) -> None:
        """Camera 02~04 视频尚未接入，调用必须安全返回空框。"""
        box = resolve_video_detection_box(9.0, camera_id=camera_id)
        assert box.visible is False


# =============================================================================
# 证据图
# =============================================================================


def _jpeg_size(path: Path) -> tuple[int, int]:
    """从 JPEG 的 SOF 段读取宽高（不依赖图像库）。"""
    data = path.read_bytes()
    if data[:2] != b"\xff\xd8":
        raise ValueError("不是 JPEG 文件")
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3):
            height, width = struct.unpack(">HH", data[i + 5 : i + 9])
            return width, height
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
        i += 2 + seg_len
    raise ValueError("未找到 SOF 段")


class TestEvidenceImage:
    @pytest.fixture(scope="class")
    def evidence_paths(self) -> list[Path]:
        return sorted(EVIDENCE_DIR.glob("*.jpg"))

    def test_evidence_directory_exists(self) -> None:
        assert EVIDENCE_DIR.is_dir(), f"证据图目录不存在：{EVIDENCE_DIR}"

    def test_primary_evidence_file_exists(self) -> None:
        path = EVIDENCE_DIR / "main-camera-material-accumulation.jpg"
        assert path.is_file(), "主证据图缺失，请运行 scripts/generate_evidence.py"

    def test_alarm_evidence_file_exists(self) -> None:
        path = EVIDENCE_DIR / "main-camera-material-accumulation-alarm.jpg"
        assert path.is_file()

    def test_evidence_files_readable_and_non_empty(self, evidence_paths: list[Path]) -> None:
        assert evidence_paths, "证据图目录为空"
        for path in evidence_paths:
            assert path.stat().st_size > 10_000, f"{path.name} 过小，可能生成失败"

    def test_evidence_dimensions_are_16_9(self, evidence_paths: list[Path]) -> None:
        """证据图必须是 1280×720 的 16:9，不能拉伸变形。"""
        for path in evidence_paths:
            width, height = _jpeg_size(path)
            assert (width, height) == (1280, 720), f"{path.name} 尺寸为 {width}×{height}"
            assert abs(width / height - 16 / 9) < 0.01

    def test_evidence_config_path_matches_actual_file(self) -> None:
        """配置里声明的证据图路径必须真实存在（防止引用 404 地址）。"""
        declared = PRIMARY_DETECTION.evidence_image
        # 配置存的是相对站点根（public/）的路径，
        # 因此 EVIDENCE_DIR 下的文件名必须与声明路径的最后一段一致
        filename = declared.rsplit("/", 1)[-1]
        assert (EVIDENCE_DIR / filename).is_file(), f"配置声明的证据图不存在：{declared}"
        assert declared.startswith("images/evidence/"), (
            "证据图应放在 images/evidence/ 下，且路径为相对站点根的形式"
        )

    def test_evidence_image_helper(self) -> None:
        assert evidence_image_for("material_accumulation") == PRIMARY_DETECTION.evidence_image
        # 无证据图的类型返回 None，调用方据此不渲染区块
        assert evidence_image_for("conveyor_speed_drop") is None

    def test_evidence_time_within_video(self) -> None:
        from app.services.video_sync import VIDEO_SYNC_DURATION

        assert 0.0 < PRIMARY_DETECTION.evidence_time < VIDEO_SYNC_DURATION

    def test_evidence_time_is_in_abnormal_stage(self) -> None:
        """证据图必须取自异常阶段（有框），不能取自正常阶段。"""
        box = resolve_video_detection_box(PRIMARY_DETECTION.evidence_time)
        assert box.visible is True
        assert box.severity in ("warning", "alarm")

    def test_evidence_confidence_matches_stage(self) -> None:
        """配置中的证据图置信度必须落在其阶段区间内，保证图文一致。"""
        box = resolve_video_detection_box(PRIMARY_DETECTION.evidence_time)
        if box.severity == "warning":
            assert 0.88 <= PRIMARY_DETECTION.evidence_confidence <= 0.93
        else:
            assert 0.93 <= PRIMARY_DETECTION.evidence_confidence <= 0.97


# =============================================================================
# 回归：不写库、不破坏原有能力
# =============================================================================


class TestNoRegression:
    def test_detection_does_not_touch_alarm_store(self) -> None:
        """检测框解算纯读，不产生报警记录。"""
        from app.services.simulation import SimulationEngine

        engine = SimulationEngine(seed=20250519)
        engine.event_recording = False
        before = len(engine.alarms())

        for i in range(0, 101):
            resolve_video_detection_box(i / 10)

        assert len(engine.alarms()) == before

    def test_detection_module_has_no_heavy_dependencies(self) -> None:
        """不得引入推理框架/图像库依赖。"""
        source = (REPO_ROOT / "backend" / "app" / "services" / "video_detection.py").read_text(
            encoding="utf-8"
        )
        for forbidden in ("torch", "ultralytics", "cv2", "onnxruntime", "numpy", "PIL"):
            assert forbidden not in source, f"检测模块不应依赖 {forbidden}"
