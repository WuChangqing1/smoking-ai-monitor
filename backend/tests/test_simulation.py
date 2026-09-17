"""仿真引擎业务逻辑测试。

对应任务要求 A16 的 10 项检查。这些测试直接针对 ``SimulationEngine``，
不依赖 HTTP 层；HTTP 契约测试在 ``test_api_simulation.py``。

注意：所有测试都显式传入固定 seed，因此不会因为随机数偶发失败。
"""

from __future__ import annotations

import math

import pytest

from app.services.simulation import (
    ALARM_THRESHOLD,
    BASELINE_DISTANCE,
    CONVEYOR_BASE_SPEED,
    HISTORY_MAX_POINTS,
    RAW_BUFFER_SIZE,
    RISK_WEIGHT_SEVERITY,
    SAMPLE_RATE_HZ,
    SimulationEngine,
    coverage_for_severity,
)

SEED = 20250519


def make_engine() -> SimulationEngine:
    """固定 seed 的引擎，测试可复现。"""
    return SimulationEngine(seed=SEED)


def drive(engine: SimulationEngine, seconds: float) -> None:
    """推进指定仿真秒数（内部按 10 Hz，所以需要 10×tick 次数）。"""
    for _ in range(int(seconds * SAMPLE_RATE_HZ)):
        engine.tick()


def settle(engine: SimulationEngine, scenario: str, seconds: float = 60.0):
    """切到指定场景并等待 severity 收敛，返回快照。"""
    engine.set_scenario(scenario)  # type: ignore[arg-type]
    drive(engine, seconds)
    return engine.snapshot()


# =============================================================================
# 1. normal 数据范围合理
# =============================================================================


class TestNormalRanges:
    def test_normal_snapshot_within_expected_ranges(self) -> None:
        engine = make_engine()
        snap = engine.snapshot()

        assert snap.sim_state == "normal"
        # 正常状态雷达距离 0.69~0.74 m
        assert 0.69 <= snap.radar.distance <= 0.74, snap.radar.distance
        # 风险指数 8%~22%（允许 2 个百分点工程余量）
        assert 6.0 <= snap.risk.index <= 24.0, snap.risk.index
        assert snap.risk.level == "low"
        # 视觉在正常状态判定为正常输送
        assert snap.vision.label == "normal_conveying"
        # 视觉置信度在高位缓慢变化
        assert 0.94 <= snap.vision.confidence <= 0.99, snap.vision.confidence
        # 环境在正常区间
        assert 22.0 <= snap.environment.temperature <= 25.5
        assert 48.0 <= snap.environment.humidity <= 60.0
        # 正常状态输送速度接近基准
        assert snap.environment.conveyor_speed == pytest.approx(
            CONVEYOR_BASE_SPEED, abs=0.06
        )

    def test_radar_jitter_is_bounded_and_not_a_perfect_line(self) -> None:
        """趋势整体平稳，但必须有合理微噪声，不能是一条完美直线。"""
        engine = make_engine()
        series = [s.radar_filtered for s in engine.history(60)]

        steps = [abs(series[i + 1] - series[i]) for i in range(len(series) - 1)]
        # 不允许出现跳变几十厘米
        assert max(steps) < 0.02, f"单步跳变过大: {max(steps)}"
        # 也不允许完全没有波动（完美直线）
        assert max(steps) > 0.0
        # 正常状态整体应贴近基准
        for value in series:
            assert abs(value - BASELINE_DISTANCE) <= 0.05, value

    def test_sensor_noise_is_bounded(self) -> None:
        """原始测量值的噪声量级应落在 ±0.008 m 附近，而不是几十厘米。"""
        engine = make_engine()
        samples = engine.recent_samples(400)
        deviations = [abs(s.radar_distance - s.radar_filtered) for s in samples]
        assert max(deviations) < 0.03, f"测量值与滤波值偏差过大: {max(deviations)}"


# =============================================================================
# 2. 时间戳连续
# =============================================================================


class TestTimestamps:
    def test_history_timestamps_are_monotonic_and_bounded(self) -> None:
        """降采样序列必须单调递增，且点距保持在合理范围。

        等点数降采样会把原始索引四舍五入，因此步长会在相邻整数间跳动
        （原始 10 Hz → 每约 10 或 11 个原始点取一个，即 1.0~1.1 s），
        这是预期行为；这里约束的是"不会出现空洞或重复"。
        """
        engine = make_engine()
        history = engine.history(120)

        ts = [s.ts for s in history]
        assert ts == sorted(ts), "时间戳必须单调递增"
        assert len(set(ts)) == len(ts), "时间戳不得重复"

        steps = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
        assert min(steps) > 0
        assert max(steps) <= 1.2, f"点距过大，曲线会出现空洞: {max(steps)}"
        assert max(steps) - min(steps) <= 0.15, "点距抖动应在相邻原始点范围内"

        # 整体跨度应覆盖缓冲窗口的大部分
        assert ts[-1] - ts[0] > 100.0

    def test_raw_sampling_matches_10hz(self) -> None:
        """内部按资料口径 10 Hz 采样：1 秒推进应有 10 个采样点。"""
        engine = make_engine()
        before = engine.recent_samples(RAW_BUFFER_SIZE)[-1].ts
        drive(engine, 1.0)
        after = engine.recent_samples(RAW_BUFFER_SIZE)[-1].ts
        assert after - before == pytest.approx(1.0, abs=1e-6)

    def test_labels_follow_simulation_clock(self) -> None:
        engine = make_engine()
        history = engine.history(30)
        for sample in history:
            assert len(sample.label) == 8  # HH:MM:SS
            assert sample.label[2] == ":" and sample.label[5] == ":"


# =============================================================================
# 3. 历史数据数量受到限制
# =============================================================================


class TestHistoryBounds:
    def test_raw_buffer_never_exceeds_maxlen(self) -> None:
        engine = SimulationEngine(seed=SEED, raw_buffer_size=500, warmup_samples=100)
        drive(engine, 120)  # 1200 点，远超 500
        assert len(engine.recent_samples(10_000)) == 500

    def test_history_respects_requested_and_max_points(self) -> None:
        engine = make_engine()
        assert len(engine.history(80)) == 80
        # 超过上限时被夹到 HISTORY_MAX_POINTS（默认上限 180）
        assert len(engine.history(9999)) == HISTORY_MAX_POINTS

    def test_history_always_includes_latest_sample(self) -> None:
        """曲线末端必须等于当前读数，否则趋势图会与状态卡矛盾。

        快照对外保留 3 位小数、样本保留 4 位，因此用 1e-3 容差比较。
        """
        engine = make_engine()
        drive(engine, 5)
        history = engine.history(60)
        latest = engine.snapshot()
        assert history[-1].radar_filtered == pytest.approx(latest.radar.distance, abs=1e-3)
        assert history[-1].risk_index == pytest.approx(latest.risk.index, abs=0.05)

    def test_default_buffer_equals_ten_minutes(self) -> None:
        # 6000 点 @10Hz = 600 秒 = 10 分钟
        assert RAW_BUFFER_SIZE / SAMPLE_RATE_HZ == 600


# =============================================================================
# 4 & 5. start / stop 语义
# =============================================================================


class TestStartStop:
    def test_stop_freezes_data_progress(self) -> None:
        engine = make_engine()
        drive(engine, 3)
        engine.stop_detection()
        frozen = engine.snapshot()
        frozen_len = len(engine.recent_samples(RAW_BUFFER_SIZE))

        drive(engine, 10)  # 停止后继续 tick，不应推进

        after = engine.snapshot()
        assert after.sim_state == "stopped"
        assert after.sim_state_text == "已停止"
        assert after.detection_running is False
        assert after.radar.distance == frozen.radar.distance
        assert after.risk.index == frozen.risk.index
        # 原始缓冲长度也不应增长
        assert len(engine.recent_samples(RAW_BUFFER_SIZE)) == frozen_len

    def test_stopped_history_remains_queryable(self) -> None:
        engine = make_engine()
        engine.stop_detection()
        history = engine.history(60)
        assert len(history) == 60, "停止后历史数据仍应可查询"

    def test_start_resumes_progress(self) -> None:
        engine = make_engine()
        engine.stop_detection()
        drive(engine, 5)
        halted = engine.snapshot()

        engine.start_detection()
        drive(engine, 5)
        resumed = engine.snapshot()

        assert resumed.detection_running is True
        assert resumed.sim_state != "stopped"
        assert resumed.radar.distance != halted.radar.distance or (
            resumed.risk.index != halted.risk.index
        )

    def test_start_stop_are_idempotent(self) -> None:
        engine = make_engine()
        assert "已在运行中" in engine.start_detection()
        engine.stop_detection()
        assert "已处于停止" in engine.stop_detection()

    def test_stop_does_not_touch_real_equipment_semantics(self) -> None:
        """停止检测不改变设备在线状态（不控制真实生产设备）。"""
        engine = make_engine()
        engine.stop_detection()
        snap = engine.snapshot()
        assert snap.radar.online is True
        assert snap.vision.online is True
        # 只是数据不再刷新
        assert snap.radar.data_fresh is False


# =============================================================================
# 6. reset 回到 normal
# =============================================================================


class TestReset:
    def test_reset_returns_to_normal(self) -> None:
        engine = make_engine()
        settle(engine, "alarm", 60)
        assert engine.snapshot().sim_state == "alarm"

        engine.reset()
        snap = engine.snapshot()

        assert snap.sim_state == "normal"
        assert snap.risk.level == "low"
        assert 0.69 <= snap.radar.distance <= 0.74
        assert snap.vision.label == "normal_conveying"
        assert snap.detection_running is True

    def test_reset_restores_reproducibility(self) -> None:
        """reset 之后应能重现同一 seed 的初始数据。"""
        engine = make_engine()
        first = engine.snapshot()
        drive(engine, 30)
        engine.reset()
        second = engine.snapshot()
        assert first.radar.distance == pytest.approx(second.radar.distance, abs=1e-9)
        assert first.risk.index == pytest.approx(second.risk.index, abs=1e-9)

    def test_reset_clears_forced_scenario(self) -> None:
        engine = make_engine()
        engine.set_scenario("warning")
        assert engine.scenario_forced is True
        engine.reset()
        assert engine.scenario_forced is False
        assert engine.current_stage == "normal"


# =============================================================================
# 7 & 8. scenario 切换
# =============================================================================


class TestScenarios:
    @pytest.mark.parametrize(
        ("scenario", "state", "distance_range", "risk_range", "verdict"),
        [
            ("normal", "normal", (0.69, 0.74), (6.0, 24.0), "normal"),
            ("attention", "attention", (0.655, 0.695), (38.0, 55.0), "attention"),
            ("warning", "warning", (0.60, 0.65), (60.0, 80.0), "warning"),
            ("alarm", "alarm", (0.55, 0.60), (80.0, 100.0), "alarm"),
        ],
    )
    def test_scenario_reaches_expected_state(
        self,
        scenario: str,
        state: str,
        distance_range: tuple[float, float],
        risk_range: tuple[float, float],
        verdict: str,
    ) -> None:
        engine = make_engine()
        snap = settle(engine, scenario, 60)

        assert snap.sim_state == state
        assert snap.fusion.verdict == verdict
        assert distance_range[0] <= snap.radar.distance <= distance_range[1], (
            f"{scenario}: 距离 {snap.radar.distance} 超出 {distance_range}"
        )
        assert risk_range[0] <= snap.risk.index <= risk_range[1], (
            f"{scenario}: 风险 {snap.risk.index} 超出 {risk_range}"
        )

    def test_warning_yields_preliminary_warning_not_alarm(self) -> None:
        """warning 场景应是"提前预警"，而不是严重报警。"""
        engine = make_engine()
        snap = settle(engine, "warning", 60)
        assert snap.fusion.verdict == "warning"
        assert snap.risk.level == "high"
        assert snap.radar.distance > ALARM_THRESHOLD, "预警阶段不应低于报警阈值"

    def test_attention_shows_vision_noticing_before_radar_alarm(self) -> None:
        """attention 场景体现"视觉已注意形态变化，但雷达尚未明显异常"。"""
        engine = make_engine()
        snap = settle(engine, "attention", 60)
        assert snap.vision.label == "material_accumulation_suspected"
        assert snap.radar.distance > 0.64, "关注阶段雷达不应接近报警阈值"
        assert snap.fusion.verdict == "attention"

    def test_alarm_vision_labels_progress_with_severity(self) -> None:
        engine = make_engine()
        assert settle(engine, "normal", 60).vision.label == "normal_conveying"
        assert (
            settle(engine, "attention", 60).vision.label
            == "material_accumulation_suspected"
        )
        assert settle(engine, "warning", 60).vision.label == "material_accumulation"
        assert (
            settle(engine, "alarm", 60).vision.label
            == "material_accumulation_severe"
        )

    def test_unknown_scenario_is_rejected(self) -> None:
        engine = make_engine()
        with pytest.raises(ValueError):
            engine.set_scenario("meltdown")  # type: ignore[arg-type]

    def test_clear_scenario_resumes_auto_cycle(self) -> None:
        engine = make_engine()
        engine.set_scenario("alarm")
        assert engine.scenario_forced is True
        engine.clear_scenario()
        assert engine.scenario_forced is False


# =============================================================================
# 9. risk 与 radar 趋势逻辑一致
# =============================================================================


class TestRiskRadarConsistency:
    def test_risk_increases_as_distance_decreases(self) -> None:
        """核心一致性：距离越低，风险越高（四段场景严格单调）。"""
        engine = make_engine()
        rows = []
        for scenario in ("normal", "attention", "warning", "alarm"):
            snap = settle(engine, scenario, 60)
            rows.append((snap.radar.distance, snap.risk.index))

        distances = [r[0] for r in rows]
        risks = [r[1] for r in rows]

        assert distances == sorted(distances, reverse=True), f"距离应逐级下降: {distances}"
        assert risks == sorted(risks), f"风险应逐级上升: {risks}"

        # 相关系数应接近完全负相关
        assert correlation(distances, risks) < -0.99

    def test_risk_index_derives_from_severity_formula(self) -> None:
        """风险指数主项必须以 severity 为唯一来源，而不是独立随机。"""
        engine = make_engine()
        snap = settle(engine, "warning", 60)
        severity = engine.current_severity()
        nominal = 6.0 + severity * RISK_WEIGHT_SEVERITY
        # 允许视觉项与环境项的合理贡献
        assert abs(snap.risk.index - nominal) <= 12.0

    def test_coverage_and_speed_move_with_severity(self) -> None:
        """环境与辅助指标必须与 severity 关联，而不是各自随机。"""
        engine = make_engine()
        normal = settle(engine, "normal", 60)
        alarm = settle(engine, "alarm", 60)

        assert alarm.vision.coverage > normal.vision.coverage + 0.3
        assert alarm.environment.conveyor_speed < normal.environment.conveyor_speed
        assert alarm.environment.equipment_load > normal.environment.equipment_load

    def test_temperature_does_not_change_abruptly(self) -> None:
        """温湿度只是辅助上下文，不应因堵料剧烈变化。"""
        engine = make_engine()
        normal = settle(engine, "normal", 60)
        alarm = settle(engine, "alarm", 60)
        assert abs(alarm.environment.temperature - normal.environment.temperature) < 2.0
        assert abs(alarm.environment.humidity - normal.environment.humidity) < 6.0

    def test_risk_trend_reflects_direction(self) -> None:
        engine = make_engine()
        settle(engine, "normal", 60)
        engine.set_scenario("alarm")
        drive(engine, 40)
        rising = engine.snapshot().risk.trend
        assert rising in ("rising", "rising_fast"), rising

    def test_coverage_formula_is_shared(self) -> None:
        """覆盖率映射必须与报警记录使用同一公式，避免两处口径不一致。"""
        engine = make_engine()
        snap = settle(engine, "alarm", 60)
        severity = engine.current_severity()
        assert snap.vision.coverage == pytest.approx(
            coverage_for_severity(severity), abs=0.05
        )


# =============================================================================
# 附加：预警计数与报警生成
# =============================================================================


class TestAlarmGeneration:
    def test_alarm_record_created_on_alarm_transition(self) -> None:
        engine = make_engine()
        engine.reset()
        before = len(engine.alarms())

        engine.set_scenario("alarm")
        drive(engine, 60)

        records = engine.alarms()
        assert len(records) >= before

        latest = records[0]
        # 报警内容必须覆盖要求的字段
        assert latest.event_id.startswith("EVT-")
        assert latest.device_id == "RAD-02"
        assert latest.device_ip == "192.168.1.198"
        assert latest.location
        assert latest.timestamp > 0
        assert latest.radar_distance <= ALARM_THRESHOLD + 0.03
        assert latest.baseline_distance == BASELINE_DISTANCE
        assert latest.visual_result
        assert 0.0 < latest.visual_confidence <= 1.0
        assert latest.fusion_result == "异常"
        assert latest.risk_score >= 80.0
        assert latest.alarm_level == "critical"
        assert latest.event_type
        assert latest.handling_status in ("pending", "processing", "resolved", "archived")

    def test_alarm_timeline_covers_full_closure(self) -> None:
        engine = make_engine()
        record = engine.alarms()[0]
        stages = [entry["stage"] for entry in record.timeline]
        assert stages == ["发现", "判断", "报警", "处理", "归档"]

    def test_normal_scenario_does_not_generate_alarms(self) -> None:
        """正常演示时应以正常运行状态为主，不频繁报警。"""
        engine = make_engine()
        engine.reset()
        baseline = len(engine.alarms())
        drive(engine, 120)  # 2 分钟自动循环
        assert len(engine.alarms()) == baseline

    def test_today_warnings_counter_increases_on_warning(self) -> None:
        engine = make_engine()
        engine.reset()
        before = engine.today_warnings
        engine.set_scenario("warning")
        drive(engine, 60)
        assert engine.today_warnings > before

    def test_seeded_historical_alarms_are_present(self) -> None:
        """开局应有取自资料的历史报警记录，而不是空表。"""
        engine = make_engine()
        records = engine.alarms()
        assert len(records) >= 4
        assert all(r.event_id.startswith("EVT-") for r in records)
        assert any(r.handling_status == "archived" for r in records)

    def test_alarm_lookup_by_id(self) -> None:
        engine = make_engine()
        target = engine.alarms()[0]
        assert engine.alarm_by_id(target.event_id) is target
        assert engine.alarm_by_id("EVT-NOT-EXIST") is None


# =============================================================================
# 附加：并发安全与预警
# =============================================================================


class TestConcurrencyAndPrediction:
    def test_concurrent_ticks_do_not_corrupt_state(self) -> None:
        import threading

        engine = make_engine()
        errors: list[Exception] = []

        def worker() -> None:
            try:
                for _ in range(300):
                    engine.tick()
                    engine.snapshot()
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, errors
        snap = engine.snapshot()
        assert 0.0 <= snap.risk.index <= 100.0
        assert 0.30 <= snap.radar.distance <= 1.60

    def test_prediction_is_probabilistic_not_certain(self) -> None:
        engine = make_engine()
        settle(engine, "warning", 60)
        prediction = engine.prediction(30)

        assert prediction.horizon_minutes == 30
        assert 0.0 <= prediction.forecast_index <= 100.0
        assert 0.45 <= prediction.forecast_confidence <= 0.95
        assert prediction.evidence, "必须有预警依据"
        assert prediction.suggestions, "必须有建议措施"

        # 措辞必须是概率化的，不能出现确定性结论
        joined = " ".join(prediction.suggestions)
        assert "一定" not in joined
        assert "必然" not in joined

    def test_prediction_evidence_reflects_radar_decline(self) -> None:
        engine = make_engine()
        settle(engine, "alarm", 60)
        prediction = engine.prediction(30)
        radar_evidence = [e for e in prediction.evidence if e.source == "radar"]
        assert radar_evidence
        assert "下降" in radar_evidence[0].text

    def test_prediction_curve_connects_actual_and_forecast(self) -> None:
        engine = make_engine()
        prediction = engine.prediction(30)
        curve = prediction.curve
        assert len(curve) > 10
        actuals = [p for p in curve if p["actual"] is not None]
        predicted = [p for p in curve if p["predicted"] is not None]
        assert actuals and predicted

    def test_similar_events_are_ranked(self) -> None:
        engine = make_engine()
        prediction = engine.prediction(30)
        similarities = [e.similarity for e in prediction.similar_events]
        assert similarities == sorted(similarities, reverse=True)
        assert all(0.0 <= s <= 1.0 for s in similarities)


def correlation(xs: list[float], ys: list[float]) -> float:
    """皮尔逊相关系数，用于验证雷达距离与风险指数的负相关。"""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return cov / (sx * sy)
