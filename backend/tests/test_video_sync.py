"""视频同步遥测测试（video_sync 演示模式）。

覆盖任务要求的 15 项检查：
  1. t=0 返回 normal
  2. t≈2s 仍处于正常或接近 attention
  3. t≈5s 风险明显高于 t=2s
  4. t≈7s 为 warning
  5. t≈9.5s 为 alarm
  6. radar distance 随整体时间趋势下降
  7. risk 随整体趋势上升
  8. coverage 随整体趋势上升
  9. conveyor speed 随整体趋势下降
 10. 相同 t 多次解析结果一致（确定性）
 11. t 越界安全 clamp
 12. 视频 loop 后状态可恢复 normal
 13. video_sync 不新增永久报警记录
 14. automatic 模式原测试继续通过（在 test_simulation.py）
 15. start / stop 不被破坏
"""

from __future__ import annotations

import math

import pytest

from app.services.simulation import SAMPLE_RATE_HZ, SimulationEngine
from app.services.video_sync import (
    BASELINE_DISTANCE,
    STATE_ALARM_RISK,
    STATE_ATTENTION_RISK,
    STATE_WARNING_RISK,
    VIDEO_KEYFRAMES,
    VIDEO_SYNC_DURATION,
    clamp_video_time,
    interpolate_keyframes,
    resolve_video_telemetry,
    samples_up_to,
)

SEED = 20250519


def drive(engine: SimulationEngine, seconds: float) -> None:
    for _ in range(int(seconds * SAMPLE_RATE_HZ)):
        engine.tick()


# =============================================================================
# 1~5. 各时间点的状态
# =============================================================================


class TestTimelineStates:
    def test_t0_is_normal(self) -> None:
        x = resolve_video_telemetry(0.0)
        assert x.sim_state == "normal"
        assert x.fusion_verdict == "normal"
        assert x.vision_label == "normal_conveying"
        assert x.risk_index < STATE_ATTENTION_RISK
        assert x.distance == pytest.approx(BASELINE_DISTANCE, abs=0.01)

    def test_t2_still_normal_or_attention(self) -> None:
        """t≈2s 画面刚开始出现趋势，不应已经进入 warning。"""
        x = resolve_video_telemetry(2.0)
        assert x.sim_state in ("normal", "attention")
        assert x.risk_index < STATE_WARNING_RISK
        assert x.distance > 0.70

    def test_t5_risk_clearly_higher_than_t2(self) -> None:
        low = resolve_video_telemetry(2.0)
        mid = resolve_video_telemetry(5.0)
        assert mid.risk_index > low.risk_index + 15.0

    def test_t7_is_warning(self) -> None:
        x = resolve_video_telemetry(7.0)
        assert x.sim_state == "warning"
        assert x.fusion_verdict == "warning"
        assert x.vision_label == "material_accumulation"
        assert STATE_WARNING_RISK <= x.risk_index < STATE_ALARM_RISK

    def test_t9_5_is_alarm(self) -> None:
        x = resolve_video_telemetry(9.5)
        assert x.sim_state == "alarm"
        assert x.fusion_verdict == "alarm"
        assert x.risk_index >= STATE_ALARM_RISK
        # 终点收敛到资料中的真实报警测量值附近
        assert x.distance == pytest.approx(0.58, abs=0.02)

    def test_full_timeline_state_progression(self) -> None:
        """整体顺序必须是 normal → attention → warning → alarm，不跳级、不倒退。"""
        order = ["normal", "attention", "warning", "alarm"]
        seen: list[str] = []
        for i in range(0, 101):
            state = resolve_video_telemetry(i / 10.0).sim_state
            if not seen or seen[-1] != state:
                seen.append(state)

        assert seen == order, f"状态序列异常: {seen}"

    def test_vision_confidence_ranges_by_stage(self) -> None:
        """置信度按阶段落在规格区间内。"""
        normal = resolve_video_telemetry(0.5)
        attention = resolve_video_telemetry(4.0)
        warning = resolve_video_telemetry(7.0)
        alarm = resolve_video_telemetry(9.5)

        assert 0.95 <= normal.vision_confidence <= 0.99
        assert 0.76 <= attention.vision_confidence <= 0.88
        assert 0.85 <= warning.vision_confidence <= 0.95
        assert 0.90 <= alarm.vision_confidence <= 0.98

    def test_vision_label_progression(self) -> None:
        assert resolve_video_telemetry(0.5).vision_label == "normal_conveying"
        assert (
            resolve_video_telemetry(4.0).vision_label == "material_accumulation_suspected"
        )
        assert resolve_video_telemetry(7.0).vision_label == "material_accumulation"
        assert resolve_video_telemetry(9.5).vision_label == "material_accumulation"


# =============================================================================
# 6~9. 指标整体趋势
# =============================================================================


class TestMetricTrends:
    @staticmethod
    def _series(step: float = 0.5) -> list:
        n = int(VIDEO_SYNC_DURATION / step)
        return [resolve_video_telemetry(i * step) for i in range(n + 1)]

    def test_distance_decreases_overall(self) -> None:
        series = self._series()
        values = [x.distance for x in series]
        assert values == sorted(values, reverse=True), "测距应整体单调下降"
        assert values[0] - values[-1] > 0.12, "整段降幅应大于 12 cm"

    def test_risk_increases_overall(self) -> None:
        series = self._series()
        values = [x.risk_index for x in series]
        assert values == sorted(values), "风险应整体单调上升"
        assert values[-1] > 80.0

    def test_coverage_increases_overall(self) -> None:
        series = self._series()
        values = [x.coverage for x in series]
        assert values == sorted(values), "覆盖率应整体单调上升"
        assert values[-1] > 0.80

    def test_conveyor_speed_decreases_overall(self) -> None:
        series = self._series()
        values = [x.conveyor_speed for x in series]
        assert values == sorted(values, reverse=True), "输送速度应整体单调下降"
        assert values[-1] < values[0] * 0.85

    def test_equipment_load_increases_with_slowdown(self) -> None:
        series = self._series()
        values = [x.equipment_load for x in series]
        assert values == sorted(values), "设备负载应随堵料上升"
        assert 45.0 <= values[0] <= 70.0
        assert values[-1] <= 100.0

    def test_no_segment_jumps(self) -> None:
        """相邻采样点之间不得出现跳变（插值连续性）。"""
        prev = resolve_video_telemetry(0.0)
        for i in range(1, 201):
            cur = resolve_video_telemetry(i * 0.05)
            assert abs(cur.distance - prev.distance) < 0.006, (
                f"t={cur.t} 测距跳变 {prev.distance}→{cur.distance}"
            )
            assert abs(cur.risk_index - prev.risk_index) < 2.5, (
                f"t={cur.t} 风险跳变 {prev.risk_index}→{cur.risk_index}"
            )
            prev = cur

    def test_jitter_within_reasonable_range(self) -> None:
        """噪声只在 ±3 mm 内，且不改变整体趋势。"""
        for i in range(0, 101):
            t = i / 10.0
            base = interpolate_keyframes(t).distance
            assert abs(resolve_video_telemetry(t).distance - base) <= 0.003

    def test_temperature_humidity_stay_stable(self) -> None:
        """温湿度不随堵料剧烈变化。"""
        for i in range(0, 101):
            x = resolve_video_telemetry(i / 10.0)
            assert 23.0 <= x.temperature <= 25.0, x.temperature
            assert 51.0 <= x.humidity <= 58.0, x.humidity


# =============================================================================
# 10~12. 确定性、越界、循环
# =============================================================================


class TestDeterminismAndBounds:
    def test_same_t_repeated_is_identical(self) -> None:
        """同一个 t 多次解析必须完全一致 —— 视频循环后数据可复现。"""
        for t in (0.0, 1.7, 3.3, 5.0, 6.8, 8.4, 9.9, 10.0):
            first = resolve_video_telemetry(t)
            for _ in range(5):
                again = resolve_video_telemetry(t)
                assert again.distance == first.distance
                assert again.risk_index == first.risk_index
                assert again.coverage == first.coverage
                assert again.conveyor_speed == first.conveyor_speed
                assert again.sim_state == first.sim_state

    def test_key_spec_values_reproducible(self) -> None:
        """规格中给出的锚点值应稳定复现。"""
        x8 = resolve_video_telemetry(8.0)
        assert x8.distance == pytest.approx(0.612, abs=0.004)
        assert x8.risk_index == pytest.approx(76.0, abs=1.5)
        assert x8.coverage == pytest.approx(0.74, abs=0.01)

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (-5.0, 0.0),
            (-0.001, 0.0),
            (0.0, 0.0),
            (10.0, 10.0),
            (10.001, 10.0),
            (999.0, 10.0),
        ],
    )
    def test_time_is_clamped(self, raw: float, expected: float) -> None:
        assert clamp_video_time(raw) == expected
        assert resolve_video_telemetry(raw).t == expected

    def test_non_numeric_and_nan_are_safe(self) -> None:
        assert clamp_video_time(float("nan")) == 0.0
        assert clamp_video_time(float("inf")) == 0.0
        assert clamp_video_time("abc") == 0.0  # type: ignore[arg-type]
        x = resolve_video_telemetry(float("nan"))
        assert x.sim_state == "normal"

    def test_loop_returns_to_normal(self) -> None:
        """视频从头重播时状态必须复位，且与首轮完全一致。"""
        end = resolve_video_telemetry(10.0)
        assert end.sim_state == "alarm"

        restarted = resolve_video_telemetry(0.0)
        assert restarted.sim_state == "normal"
        assert restarted.distance == resolve_video_telemetry(0.0).distance

        # 第二轮同一时刻的数据与第一轮一致
        for t in (2.0, 4.0, 6.0, 8.0):
            assert resolve_video_telemetry(t).risk_index == resolve_video_telemetry(t).risk_index
            assert resolve_video_telemetry(t).sim_state == resolve_video_telemetry(t).sim_state

    def test_custom_duration_scales_timeline(self) -> None:
        """视频实际时长不同时按比例映射，终点仍为 alarm。"""
        x = resolve_video_telemetry(20.0, duration=20.0)
        assert x.sim_state == "alarm"
        assert x.distance == pytest.approx(0.58, abs=0.02)
        mid = resolve_video_telemetry(10.0, duration=20.0)
        assert mid.sim_state == "attention"


# =============================================================================
# 趋势序列（只展示当前这一轮）
# =============================================================================


class TestSampleSeries:
    def test_samples_up_to_length_and_endpoints(self) -> None:
        points = samples_up_to(5.0, step=0.2)
        assert len(points) >= 26
        assert points[0].t == 0.0
        assert points[0].sim_state == "normal"
        # 末端必须等于当前时刻的读数，保证曲线与数值卡一致
        assert points[-1].t == pytest.approx(5.0, abs=0.01)
        current = resolve_video_telemetry(5.0)
        assert points[-1].distance == current.distance
        assert points[-1].risk_index == current.risk_index

    def test_samples_do_not_accumulate_across_loops(self) -> None:
        """循环后序列重新从 0 开始，不会形成无限锯齿累积。"""
        long_cycle = samples_up_to(9.9, step=0.2)
        after_loop = samples_up_to(0.4, step=0.2)
        assert len(after_loop) < len(long_cycle) / 10
        assert after_loop[0].sim_state == "normal"

    def test_samples_empty_at_zero(self) -> None:
        points = samples_up_to(0.0, step=0.2)
        assert len(points) == 1
        assert points[0].t == 0.0


# =============================================================================
# 13~15. 不写库、不影响 automatic 模式与启停
# =============================================================================


class TestNoSideEffects:
    def test_event_recording_disabled_creates_no_alarms(self) -> None:
        """关闭事件登记后，引擎即使跑到 alarm 也不得新增报警记录。

        视频同步模式由应用启动时关闭该开关：视频每约 20 秒循环一次，
        若每轮写库，报警列表会迅速失去可信度。
        """
        engine = SimulationEngine(seed=SEED)
        engine.event_recording = False
        before = len(engine.alarms())

        engine.set_scenario("alarm")
        drive(engine, 60)

        assert engine.event_recording is False
        assert len(engine.alarms()) == before, "关闭事件登记后不应新增报警记录"

    def test_event_recording_enabled_still_records_alarms(self) -> None:
        """默认（automatic 模式）仍按原逻辑生成报警记录。"""
        engine = SimulationEngine(seed=SEED)
        assert engine.event_recording is True

        engine.reset()
        before = len(engine.alarms())
        engine.set_scenario("alarm")
        drive(engine, 60)
        assert len(engine.alarms()) > before, "automatic 模式应正常生成报警记录"

    def test_start_stop_still_work(self) -> None:
        """启停控制不被 video_sync 影响。"""
        engine = SimulationEngine(seed=SEED)
        drive(engine, 3)
        engine.stop_detection()
        frozen = engine.snapshot()

        drive(engine, 10)
        after = engine.snapshot()
        assert after.sim_state == "stopped"
        assert after.radar.distance == frozen.radar.distance
        assert after.risk.index == frozen.risk.index

        engine.start_detection()
        drive(engine, 5)
        assert engine.snapshot().sim_state != "stopped"

    def test_keyframes_match_specification(self) -> None:
        """关键帧本身必须与任务规格一致。"""
        expected = [
            (0.0, 0.721, 18.0, 0.30, 1.00),
            (2.0, 0.706, 27.0, 0.37, 0.98),
            (4.0, 0.681, 43.0, 0.49, 0.95),
            (6.0, 0.651, 59.0, 0.61, 0.91),
            (8.0, 0.612, 76.0, 0.74, 0.86),
            (10.0, 0.582, 89.0, 0.83, 0.80),
        ]
        assert len(VIDEO_KEYFRAMES) == len(expected)
        for frame, (t, d, r, c, s) in zip(VIDEO_KEYFRAMES, expected):
            assert (frame.t, frame.distance, frame.risk, frame.coverage, frame.speed_ratio) == (
                t,
                d,
                r,
                c,
                s,
            )

    def test_interpolation_is_linear_between_keyframes(self) -> None:
        """t=5 应正好落在 t=4 与 t=6 的中点。"""
        mid = interpolate_keyframes(5.0)
        assert mid.distance == pytest.approx((0.681 + 0.651) / 2, abs=1e-9)
        assert mid.risk == pytest.approx((43.0 + 59.0) / 2, abs=1e-9)
        assert mid.coverage == pytest.approx((0.49 + 0.61) / 2, abs=1e-9)
        assert mid.speed_ratio == pytest.approx((0.95 + 0.91) / 2, abs=1e-9)


def test_sin_based_jitter_is_deterministic_not_random() -> None:
    """微扰必须来自确定性函数 —— 同样的 t 反复解算不抖动。"""
    samples = [resolve_video_telemetry(3.7).distance for _ in range(20)]
    assert len(set(samples)) == 1
    assert math.isfinite(samples[0])
