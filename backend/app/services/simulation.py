"""统一监控数据引擎。

设计原则（对应任务要求 A1~A16）
-------------------------------
1. **唯一数据源**：整个系统只有这一个持续存在的运行状态。所有 API（realtime /
   history / system status / prediction / alarms）都从同一个引擎读取，
   因此首页、雷视联动、趋势图、报警在任何时刻都互相自洽。
2. **状态机驱动**：severity（堵料严重度 0~1）由状态机推进；
   雷达距离、视觉覆盖率、输送速度、设备负载、风险指数全部由 severity 派生，
   所以指标之间存在真实关联，而不是各自随机。
3. **真实采样口径**：资料标明采集频率 10 Hz，因此内部按 100 ms 推进一个采样点；
   对外的历史接口降采样到 60~180 点，浏览器按约 1 s 刷新 UI。
4. **不做完美直线**：所有传感器信号 = 趋势项 + 慢漂移 + 带限高频噪声 + 平滑滤波，
   整体趋势单调下降，但存在合理微小幅度的抖动（雷达正常噪声约 ±5 mm）。
5. **可复现**：随机数来自固定 seed 的 ``random.Random`` 实例，测试用固定 seed，
   pytest 不会因为随机数偶发失败。
6. **内存有界**：原始采样用 ``deque(maxlen=...)``，永不无限增长。
7. **并发安全**：所有读写都在 ``threading.Lock`` 内完成（tick 由后台线程驱动，
   API 由 FastAPI 线程池处理）。
"""

from __future__ import annotations

import math
import random
import threading
import time
from collections import deque
from datetime import datetime, timedelta

from app.services.models import (
    ALARM_LEVEL_TEXT,
    ALARM_STATUS_TEXT,
    MONITOR_STATES,
    RISK_LEVEL_TEXT,
    RISK_TREND_TEXT,
    STATE_TEXT,
    VERDICT_TEXT,
    VERDICT_TO_ALARM_LEVEL,
    VERDICT_TO_LEVEL,
    VISION_LABEL_TEXT,
    AlarmRecordData,
    EnvironmentReading,
    Evidence,
    FusionReading,
    FusionVerdict,
    PredictionData,
    RadarReading,
    RiskReading,
    RiskTrend,
    ScenarioName,
    SimSample,
    SimilarEvent,
    SimState,
    Snapshot,
    VisionReading,
    risk_level_of,
)

# =============================================================================
# 常量：全部取自原始验收资料，不得随意改动
# =============================================================================

#: 主监控点（机位 2 / Camera 01）
PRIMARY_DEVICE_ID = "RAD-02"
PRIMARY_DEVICE_NAME = "制丝线 2 号工位雷达"
PRIMARY_DEVICE_IP = "192.168.1.198"
PRIMARY_LOCATION = "制丝线 2 号输送段"
PRIMARY_POSITION = 2

#: 基准距离 0.72 m
BASELINE_DISTANCE = 0.72
#: 报警阈值：资料中真实报警测量值为 0.58 m
ALARM_THRESHOLD = 0.58

#: 系统实际采集频率（资料口径 10 Hz）
SAMPLE_RATE_HZ = 10
#: 雷达设备最高刷新能力（资料口径最高 1000 Hz）—— 与采集频率不是一回事
RADAR_MAX_REFRESH_HZ = 1000
#: 雷达测距范围与精度（资料口径）
RADAR_RANGE = "0.1–40 m"
RADAR_ACCURACY = "±5 cm"

#: 单次 tick 的时间步长（10 Hz）
TICK_SECONDS = 1.0 / SAMPLE_RATE_HZ

#: 内部原始采样保留量：6000 点 = 10 分钟 @10Hz
RAW_BUFFER_SIZE = 6000
#: 启动时预热的样本数：1200 点 = 2 分钟，保证趋势图开局即有内容
WARMUP_SAMPLES = 1200
#: 历史接口默认/最大返回点数（浏览器只需要 60~180 个点）
HISTORY_DEFAULT_POINTS = 120
HISTORY_MAX_POINTS = 180

#: 输送速度基准值
CONVEYOR_BASE_SPEED = 1.20
#: 环境基准值
TEMP_BASE = 23.6
HUMIDITY_BASE = 54.0

#: 状态机驻留时长（秒）。大部分时间保持正常，报警不频繁 —— 对应要求 A9。
STAGE_DWELL: dict[ScenarioName, float] = {
    "normal": 180.0,
    "attention": 60.0,
    "warning": 45.0,
    "alarm": 40.0,
}
#: 恢复阶段（alarm → normal 的回落过程）时长
RECOVERY_DWELL = 50.0

#: 自动循环进入 warning / alarm 的概率。刻意压低，避免"每几十秒报警一次"的假象。
PROB_ENTER_WARNING = 0.32
PROB_ENTER_ALARM = 0.14

#: 各状态的目标 severity（堵料严重度 0~1）
STAGE_SEVERITY_TARGET: dict[ScenarioName, float] = {
    "normal": 0.20,
    "attention": 0.45,
    "warning": 0.72,
    "alarm": 0.93,
}
#: 状态切换后 severity 迁移到目标值所需时间（秒）
SEVERITY_TRANSITION_SECONDS = 45.0

#: severity → 雷达距离：基准 0.72 m（severity 0.20），报警阈值 0.58 m（severity 0.93）
SEVERITY_ANCHOR_LOW = (0.20, BASELINE_DISTANCE)
SEVERITY_ANCHOR_HIGH = (0.93, ALARM_THRESHOLD)

#: 风险指数 = 主项 severity 映射 + 视觉项 + 辅助环境项
RISK_WEIGHT_SEVERITY = 88.0
RISK_WEIGHT_VISION = 7.0
RISK_WEIGHT_AUX = 5.0
#: 风险指数低端截断，正常状态不会掉到 0
RISK_FLOOR = 6.0

#: 预测的斜率外推上限（百分点）与预测封顶值。
#: 概率预测不应该给出 100% 这种确定性结论，因此封顶在 96%。
FORECAST_MAX_EXTRAPOLATION = 45.0
FORECAST_MAX_PULL = 12.0
FORECAST_CEILING = 96.0

#: 物料覆盖率映射：severity 0 → 18%，severity 1 → 86%
COVERAGE_BASE = 0.18
COVERAGE_SPAN = 0.68
#: 输送有效速度的最大降幅比例（severity=1 时下降 12%）
CONVEYOR_SPEED_MAX_DROP = 0.12


def coverage_for_severity(severity: float) -> float:
    """severity → 输送区域物料覆盖率。"""
    return COVERAGE_BASE + COVERAGE_SPAN * severity


class SimulationEngine:
    """制丝线物流监控的统一数据引擎。"""

    def __init__(
        self,
        *,
        seed: int = 20250519,
        warmup_samples: int = WARMUP_SAMPLES,
        raw_buffer_size: int = RAW_BUFFER_SIZE,
    ) -> None:
        self._seed = seed
        self._lock = threading.RLock()

        # 内部 10 Hz 原始采样缓冲，容量固定，永不无限增长
        self._raw: deque[SimSample] = deque(maxlen=raw_buffer_size)

        # 检测任务是否运行（对应启停控制；只控制检测任务，不控制真实设备）
        self._running = True
        # 运行工况状态机当前阶段
        self._stage: ScenarioName = "normal"
        # 是否处于"工况手动设定"状态（此时暂停自动循环）
        self._scenario_forced = False
        # 当前阶段已经驻留的运行秒数
        self._stage_elapsed = 0.0
        # 上一阶段（用于恢复路径判定）
        self._previous_stage: ScenarioName = "normal"
        # 恢复阶段剩余秒数；>0 时表示正在回落
        self._recover_remaining = 0.0

        # 本次自动循环内是否已经报过警（防止重复报警刷屏）
        self._alarm_this_cycle = False

        # 连续运行统计（只在检测运行时累加）
        self._uptime_seconds = 0.0
        # 今日预警计数
        self._today_warnings = 0
        # 预警/报警记录
        self._alarms: deque[AlarmRecordData] = deque(maxlen=300)
        self._alarm_seq = 0
        #: 是否登记预警/报警事件。视频同步模式下由应用启动时关闭，
        #: 避免演示视频循环回放不断写入永久报警记录。
        self._event_recording = True

        # 当前堵料严重度（0~1）。None 表示尚未初始化，首个 tick 直接落到目标值。
        self._severity: float | None = None

        # 传感器状态（带平滑，避免噪声直接暴露在对外读数上）
        self._radar_ema: float | None = None
        self._coverage_ema: float | None = None
        self._temp_ema = TEMP_BASE
        self._humidity_ema = HUMIDITY_BASE
        self._conveyor_ema = CONVEYOR_BASE_SPEED

        # 上一阶段的联合判断结果，用于边沿检测（生成报警 / 计数预警）
        self._last_verdict: FusionVerdict = "normal"

        # 运行时钟（单调递增，与真实时间同速）
        self._sim_start = time.time()
        self._sim_time = 0.0

        self._rng = random.Random(seed)

        # 启动即预热，保证趋势图与统计口径开局就有内容
        self._warmup(warmup_samples)
        self._seed_historical_alarms()

    # =========================================================================
    # 时间与状态推进
    # =========================================================================

    def _warmup(self, samples: int) -> None:
        """用同一套逻辑回放一段时间，让历史缓冲与统计量开局即合理。"""
        # 预热期间不产生报警记录，只累积历史曲线
        original_running = self._running
        self._running = True
        for _ in range(samples):
            self._advance(record_events=False)
        self._running = original_running

    def _seed_historical_alarms(self) -> None:
        """预置若干条历史报警记录。

        数据取自原始验收资料中的真实事件（2025-05-19 加料堵料、
        2025-05-17 物料堆积报警），并覆盖多个点位与异常类型，
        使"设备 / 异常类型 / 等级"等溯源维度都有真实可筛的数据，
        而不是全部堆在同一台设备上。
        """
        from app.services.devices import POINT_LOCATIONS, RADAR_POINTS, device_of_position

        now = datetime.now()
        # (时间偏移, 点位, 测距, 异常类型, 联合结果, 视觉置信度, 处理说明)
        samples: list[tuple[timedelta, int, float, str, str, float, str]] = [
            (
                timedelta(hours=2, minutes=14),
                2,
                ALARM_THRESHOLD,
                "material_accumulation",
                "alarm",
                0.94,
                "现场确认进料量短时间升高，同时下游输送速度降低；降低上游进料量并检查输送设备，约 4 分钟后物料恢复正常。",
            ),
            (
                timedelta(days=1, hours=5),
                2,
                0.61,
                "material_accumulation",
                "warning",
                0.86,
                "物料覆盖率短时上升，巡检确认输送带无堵料，属进料波动，持续观察后自行恢复。",
            ),
            (
                timedelta(days=3, hours=1, minutes=26),
                1,
                0.59,
                "material_accumulation",
                "alarm",
                0.91,
                "清理 1 号输送段落料口积料，调整上游喂料机频率后恢复。",
            ),
            (
                timedelta(days=6, hours=8),
                3,
                0.63,
                "conveyor_speed_drop",
                "warning",
                0.79,
                "输送速度短时下降约 8%，检查变频器参数无误，判定为物料负载波动。",
            ),
            (
                timedelta(days=8, hours=3, minutes=12),
                1,
                0.66,
                "material_flow_fluctuation",
                "warning",
                0.82,
                "测距呈周期性波动，与上游喂料机给料节拍一致；调整给料频率后波动收窄。",
            ),
            (
                timedelta(days=11, hours=6),
                3,
                0.68,
                "radar_refresh_abnormal",
                "warning",
                0.90,
                "雷达数据刷新短时中断约 4 秒，重启采集服务后恢复，期间未影响生产。",
            ),
        ]

        for offset, position, distance, event_type, verdict, confidence, resolution in samples:
            # 雷达点位之外的异常（例如仅摄像头的点位）归到最近的雷达台账上，
            # 保证 device_id 始终是真实存在的设备编号
            if position not in RADAR_POINTS:
                position = RADAR_POINTS[0]

            device_id, device_name, device_ip, location = device_of_position(position)
            self._alarm_seq += 1
            record = self._build_alarm(
                ts=(now - offset).timestamp(),
                severity=self._severity_for_distance(distance),
                distance=distance,
                event_type=event_type,
                verdict=verdict,  # type: ignore[arg-type]
                confidence=confidence,
                resolution=resolution,
                device_id=device_id,
                device_name=device_name,
                device_ip=device_ip,
                location=location,
            )
            record.handling_status = "archived"
            record.operator = "制丝车间值班员"
            self._alarms.append(record)

        # 今日预警计数：统计今天已经发生的记录
        today = now.date()
        self._today_warnings = sum(
            1
            for a in self._alarms
            if datetime.fromtimestamp(a.timestamp).date() == today
            and a.alarm_level in ("warning", "critical")
        )

    def tick(self) -> None:
        """推进一个采样周期（100 ms）。由后台线程按 10 Hz 调用。"""
        with self._lock:
            if not self._running:
                # 停止检测后数据不再推进，但状态与历史保持可查询
                return
            self._advance(record_events=True)

    def _advance(self, *, record_events: bool) -> None:
        """推进一个内部采样周期。调用方必须已持有锁。"""
        self._sim_time += TICK_SECONDS
        self._uptime_seconds += TICK_SECONDS

        self._advance_stage()
        severity = self._current_severity()
        sample = self._sample(severity)
        self._raw.append(sample)

        if record_events:
            self._evaluate_events(sample)

    # ---- 状态机 -------------------------------------------------------------

    def _advance_stage(self) -> None:
        """推进状态机。阶段驻留时间到点后按规则迁移。"""
        self._stage_elapsed += TICK_SECONDS

        # 恢复阶段：时间到点后回到 normal
        if self._recover_remaining > 0.0:
            self._recover_remaining -= TICK_SECONDS
            if self._recover_remaining <= 0.0:
                self._recover_remaining = 0.0
                self._enter_stage("normal")
            return

        # 工况手动设定期间不自动迁移
        if self._scenario_forced:
            return

        if self._stage_elapsed < STAGE_DWELL[self._stage]:
            return

        # 驻留时间到点 → 决定下一个阶段
        if self._stage == "normal":
            self._enter_stage("attention")
        elif self._stage == "attention":
            # 只有一定概率继续恶化，否则回到正常 —— 避免频繁报警
            if self._rng.random() < PROB_ENTER_WARNING:
                self._enter_stage("warning")
            else:
                self._enter_stage("normal")
                self._alarm_this_cycle = False
        elif self._stage == "warning":
            if not self._alarm_this_cycle and self._rng.random() < PROB_ENTER_ALARM:
                self._enter_stage("alarm")
            else:
                self._begin_recovery()
        else:  # alarm
            self._begin_recovery()

    def _enter_stage(self, stage: ScenarioName) -> None:
        if stage != self._stage:
            self._previous_stage = self._stage
        self._stage = stage
        self._stage_elapsed = 0.0
        if stage == "normal":
            self._alarm_this_cycle = False

    def _begin_recovery(self) -> None:
        """进入回落过程：severity 平滑下降到正常水平。"""
        self._previous_stage = self._stage
        self._stage = "attention"
        self._stage_elapsed = 0.0
        self._recover_remaining = RECOVERY_DWELL
        self._alarm_this_cycle = False

    def _current_severity(self) -> float:
        """当前堵料严重度：按固定斜率向目标值迁移，保证时间序列连续。"""
        target = STAGE_SEVERITY_TARGET[self._stage]
        if self._severity is None:
            self._severity = target
            return target

        # 每秒最多迁移 1/SEVERITY_TRANSITION_SECONDS 的幅度
        max_step = TICK_SECONDS / SEVERITY_TRANSITION_SECONDS
        diff = target - self._severity
        if abs(diff) <= max_step:
            self._severity = target
        else:
            self._severity += math.copysign(max_step, diff)
        return self._severity

    # ---- 传感器信号 ---------------------------------------------------------

    def _noise(self, sigma: float) -> float:
        """高斯噪声。幅度可控，不会出现跳变几十厘米的异常值。"""
        return self._rng.gauss(0.0, sigma)

    def _resonance(self, freq: float, amp: float) -> float:
        """带限机械振动项。比纯随机更接近真实设备的周期性抖动。"""
        return amp * math.sin(2.0 * math.pi * freq * self._sim_time)

    def _sample(self, severity: float) -> SimSample:
        """由 severity 派生一整组互相自洽的传感器读数。"""
        # ---- 雷达距离：趋势项 + 慢漂移 + 振动 + 测量噪声 ----
        trend = self._distance_for_severity(severity)
        drift = 0.0025 * math.sin(2.0 * math.pi * self._sim_time / 47.0)
        vibration = self._resonance(2.1, 0.0016) + self._resonance(6.7, 0.0009)
        # 测量噪声随 severity 略增（物料表面越不平整，回波越不稳定）
        sigma = 0.0025 + 0.0020 * severity
        measured = trend + drift + vibration + self._noise(sigma)
        measured = max(0.30, min(1.60, measured))

        # 滤波值：一阶低通，对应原系统界面上的「滤波值」
        if self._radar_ema is None:
            self._radar_ema = measured
        else:
            self._radar_ema += 0.12 * (measured - self._radar_ema)

        # ---- 视觉覆盖率：与 severity 同向，略滞后并带噪声 ----
        coverage_target = coverage_for_severity(severity)
        coverage_raw = coverage_target + self._noise(0.012) + self._resonance(0.7, 0.006)
        coverage_raw = max(0.05, min(0.99, coverage_raw))
        if self._coverage_ema is None:
            self._coverage_ema = coverage_raw
        else:
            self._coverage_ema += 0.10 * (coverage_raw - self._coverage_ema)
        coverage = self._coverage_ema

        # ---- 输送有效速度：堵料时轻微下降 ----
        speed_target = CONVEYOR_BASE_SPEED * (1.0 - CONVEYOR_SPEED_MAX_DROP * severity)
        speed = speed_target + self._noise(0.008) + self._resonance(0.35, 0.004)
        speed = max(0.70, speed)
        self._conveyor_ema += 0.06 * (speed - self._conveyor_ema)
        conveyor = self._conveyor_ema

        # ---- 环境：辅助上下文，不因堵料剧烈变化 ----
        temp_target = TEMP_BASE + 1.3 * severity + self._noise(0.05)
        self._temp_ema += 0.02 * (temp_target - self._temp_ema)
        humid_target = HUMIDITY_BASE - 3.0 * severity + self._noise(0.25)
        self._humidity_ema += 0.02 * (humid_target - self._humidity_ema)

        # ---- 风险指数：以 severity 为主项，视觉与环境为辅助项 ----
        vision_term = abs(coverage - coverage_for_severity(severity)) * 40.0
        aux_term = (CONVEYOR_BASE_SPEED - conveyor) / CONVEYOR_BASE_SPEED * 60.0
        risk = (
            RISK_FLOOR
            + severity * RISK_WEIGHT_SEVERITY
            + vision_term * (RISK_WEIGHT_VISION / 40.0)
            + aux_term * (RISK_WEIGHT_AUX / 60.0)
            + self._noise(0.35)
        )
        risk = max(0.0, min(100.0, risk))

        return SimSample(
            ts=self._sim_time,
            label=self._label_at(self._sim_time),
            sim_state=self._public_state(),
            severity=severity,
            radar_distance=round(measured, 4),
            radar_filtered=round(self._radar_ema, 4),
            risk_index=round(risk, 2),
            vision_coverage=round(coverage, 4),
            vision_confidence=round(self._confidence_for(severity, coverage), 4),
            conveyor_speed=round(conveyor, 4),
            temperature=round(self._temp_ema, 2),
            humidity=round(self._humidity_ema, 2),
        )

    @staticmethod
    def _distance_for_severity(severity: float) -> float:
        """severity → 雷达距离（线性锚点插值，保证 risk↔distance 单调一致）。"""
        (s0, d0), (s1, d1) = SEVERITY_ANCHOR_LOW, SEVERITY_ANCHOR_HIGH
        ratio = (severity - s0) / (s1 - s0)
        if ratio < 0.0:
            ratio = 0.0
        return d0 + (d1 - d0) * ratio

    @staticmethod
    def _severity_for_distance(distance: float) -> float:
        """雷达距离 → severity（_distance_for_severity 的逆运算）。"""
        (s0, d0), (s1, d1) = SEVERITY_ANCHOR_LOW, SEVERITY_ANCHOR_HIGH
        return s0 + (distance - d0) * (s1 - s0) / (d1 - d0)

    def _confidence_for(self, severity: float, coverage: float) -> float:
        """视觉置信度。

        正常时在高位（0.94~0.99）缓慢变化；越接近异常，模型输出越"犹豫"，
        置信度区间下移到 0.82~0.94（对应要求 A7）。
        注意：这是概率模型输出，不代表准确率。
        """
        if severity < 0.36:
            center, spread = 0.965, 0.010
        elif severity < 0.60:
            center, spread = 0.905, 0.020
        elif severity < 0.86:
            center, spread = 0.880, 0.025
        else:
            center, spread = 0.925, 0.020
        value = center + self._noise(spread) + 0.35 * (coverage - 0.5) * 0.05
        return max(0.70, min(0.995, value))

    # ---- 判断逻辑 -----------------------------------------------------------

    def _public_state(self) -> SimState:
        if not self._running:
            return "stopped"
        return self._stage

    def _vision_label(self, severity: float) -> str:
        if severity < 0.38:
            return "normal_conveying"
        if severity < 0.62:
            return "material_accumulation_suspected"
        if severity < 0.86:
            return "material_accumulation"
        return "material_accumulation_severe"

    def _radar_verdict(self, distance: float) -> FusionVerdict:
        """雷达单独判断：以距离阈值与趋势为依据。"""
        delta = distance - BASELINE_DISTANCE
        if distance <= ALARM_THRESHOLD + 0.015:
            return "alarm"
        if delta <= -0.085:
            return "warning"
        if delta <= -0.035:
            return "attention"
        return "normal"

    def _vision_verdict(self, severity: float) -> FusionVerdict:
        """视觉单独判断：以形态类别为依据。"""
        if severity >= 0.86:
            return "alarm"
        if severity >= 0.62:
            return "warning"
        if severity >= 0.38:
            return "attention"
        return "normal"

    @staticmethod
    def _verdict_rank(verdict: FusionVerdict) -> int:
        return ("normal", "attention", "warning", "alarm").index(verdict)

    def _fuse(
        self, distance: float, severity: float, confidence: float
    ) -> tuple[FusionVerdict, str]:
        """联合判断：雷达与视觉互补，取较高风险一方作为基础结论。

        互补性体现在：
        - 雷达反映"几何量"（料层高度/距离变化），响应快、精度高；
        - 视觉反映"形态语义"（是否为堆积形态），抗干扰但属概率输出。
        两者一致时给出确定性更高的结论；仅一方异常时降级为"关注"并说明原因。
        """
        radar_v = self._radar_verdict(distance)
        vision_v = self._vision_verdict(severity)

        if radar_v == vision_v:
            verdict = radar_v
            reason = {
                "normal": "雷达测距稳定在基准范围内，视觉未见异常形态，联合判断正常。",
                "attention": "雷达测距出现小幅下移，视觉识别到形态轻微变化，联合判断为关注。",
                "warning": "雷达测距持续下降且视觉确认物料堆积形态，联合判断风险上升。",
                "alarm": "雷达测距已接近报警阈值，视觉确认明显堆积形态，联合判断异常。",
            }[verdict]
            return verdict, reason

        high = radar_v if self._verdict_rank(radar_v) > self._verdict_rank(vision_v) else vision_v
        low = vision_v if high is radar_v else radar_v

        if self._verdict_rank(high) >= 2 and self._verdict_rank(low) <= 1:
            # 一方明显异常、另一方仍未确认 —— 降一级并说明分歧
            verdict: FusionVerdict = "attention" if self._verdict_rank(high) == 2 else "warning"
            which = "雷达" if high is radar_v else "视觉"
            other = "视觉" if high is radar_v else "雷达"
            reason = (
                f"{which}已出现异常特征，但{other}尚未确认，"
                f"视觉置信度 {confidence * 100:.1f}%，联合判断暂定为{VERDICT_TEXT[verdict]}，建议持续观察。"
            )
            return verdict, reason

        verdict = high
        which = "雷达" if high is radar_v else "视觉"
        reason = f"以{which}的判断为主（另一方结果较轻微），联合判断为{VERDICT_TEXT[verdict]}。"
        return verdict, reason

    def _risk_trend(self, window_seconds: float = 30.0) -> RiskTrend:
        """风险变化趋势：与 30 秒前的风险指数比较。"""
        if len(self._raw) < 2:
            return "stable"
        current = self._raw[-1].risk_index
        reference = None
        # 从缓冲尾部向前找第一个时间差达到 window_seconds 的点
        for sample in reversed(self._raw):
            if self._raw[-1].ts - sample.ts >= window_seconds:
                reference = sample.risk_index
                break
        if reference is None:
            reference = self._raw[0].risk_index

        diff = current - reference
        if diff >= 18.0:
            return "rising_fast"
        if diff >= 6.0:
            return "rising"
        if diff <= -6.0:
            return "falling"
        return "stable"

    # ---- 事件（预警计数 / 报警生成）------------------------------------------

    def _classify_event(self, sample: SimSample) -> str:
        """按主导特征判定异常类型，而不是一律记成"物料堆积"。

        判断顺序体现的是排查优先级：
          1. 测距已明显低于基准 → 物料堆积（几何量证据最直接）
          2. 测距正常但输送速度明显下降 → 输送速度下降
          3. 测距正常、速度正常，仅覆盖率偏高 → 物料流量波动
        """
        delta = sample.radar_filtered - BASELINE_DISTANCE
        speed_drop = (CONVEYOR_BASE_SPEED - sample.conveyor_speed) / CONVEYOR_BASE_SPEED

        if delta <= -0.06:
            return "material_accumulation"
        if speed_drop >= 0.07:
            return "conveyor_speed_drop"
        return "material_flow_fluctuation"

    def _evaluate_events(self, sample: SimSample) -> None:
        """升级到 warning / alarm 时登记事件。

        ``event_recording`` 为 False 时直接返回。视频同步模式下由应用启动时
        关闭该开关：该模式的遥测完全由视频时间轴解算
        （见 :mod:`app.services.video_sync`），引擎的自动演化结果不参与展示，
        若仍在此写库，视频每约 20 秒循环一次就会不断新增报警记录，
        几分钟后报警列表将完全失去可信度。
        """
        if not self._event_recording:
            return

        distance = sample.radar_filtered
        fusion, _ = self._fuse(distance, sample.severity, sample.vision_confidence)
        previous = self._last_verdict
        self._last_verdict = fusion

        prev_rank = self._verdict_rank(previous)
        curr_rank = self._verdict_rank(fusion)

        # 升级到 warning：计入今日预警（不生成报警记录）
        if curr_rank == 2 and prev_rank < 2:
            self._today_warnings += 1

        # 升级到 alarm：生成报警记录
        if curr_rank == 3 and prev_rank < 3:
            self._alarm_this_cycle = True
            self._today_warnings += 1
            self._alarm_seq += 1
            self._alarms.append(
                self._build_alarm(
                    ts=datetime.now().timestamp(),
                    severity=sample.severity,
                    distance=distance,
                    event_type=self._classify_event(sample),
                    verdict=fusion,
                    confidence=sample.vision_confidence,
                    resolution="",
                    coverage=sample.vision_coverage,
                )
            )

    def _build_alarm(
        self,
        *,
        ts: float,
        severity: float,
        distance: float,
        event_type: str,
        verdict: FusionVerdict,
        confidence: float,
        resolution: str,
        coverage: float | None = None,
        device_id: str | None = None,
        device_name: str | None = None,
        device_ip: str | None = None,
        location: str | None = None,
    ) -> AlarmRecordData:
        moment = datetime.fromtimestamp(ts)
        event_id = f"EVT-{moment.strftime('%Y%m%d')}-{self._alarm_seq:02d}"
        level = VERDICT_TO_ALARM_LEVEL[verdict]
        label = self._vision_label(severity)

        timeline = [
            {
                "ts": (moment - timedelta(seconds=95)).strftime("%Y-%m-%d %H:%M:%S"),
                "stage": "发现",
                "title": "雷达测距开始连续下降",
                "detail": (
                    f"雷达测距均值由 {BASELINE_DISTANCE:.2f} m 逐步下降至 {distance:.2f} m，"
                    "下降过程连续无跳变。"
                ),
            },
            {
                "ts": (moment - timedelta(seconds=58)).strftime("%Y-%m-%d %H:%M:%S"),
                "stage": "判断",
                "title": "视觉模型检出堆积形态",
                "detail": (
                    f"视觉模型识别到输送区域物料覆盖率持续增加，"
                    f"类别 {VISION_LABEL_TEXT.get(label, label)}，置信度 {confidence * 100:.1f}%。"
                ),
            },
            {
                "ts": moment.strftime("%Y-%m-%d %H:%M:%S"),
                "stage": "报警",
                "title": "联合风险指数达到报警条件",
                "detail": (
                    f"联合判断为{VERDICT_TEXT[verdict]}，风险指数 "
                    f"{self._risk_from_severity(severity):.0f}%，"
                    f"测距 {distance:.2f} m 已接近报警阈值 {ALARM_THRESHOLD:.2f} m。"
                ),
            },
            {
                "ts": (moment + timedelta(seconds=35)).strftime("%Y-%m-%d %H:%M:%S"),
                "stage": "处理",
                "title": "值班人员确认并处置",
                "detail": resolution
                or "值班人员确认进料量短时间升高，下游输送速度降低；降低上游进料量并检查输送设备。",
            },
            {
                "ts": (moment + timedelta(minutes=4)).strftime("%Y-%m-%d %H:%M:%S"),
                "stage": "归档",
                "title": "物料恢复正常，事件归档",
                "detail": "测距回到基准范围，风险指数回落至低风险区间，事件处理经验写入知识库。",
            },
        ]

        return AlarmRecordData(
            event_id=event_id,
            device_id=device_id or PRIMARY_DEVICE_ID,
            device_name=device_name or PRIMARY_DEVICE_NAME,
            device_ip=device_ip or PRIMARY_DEVICE_IP,
            location=location or PRIMARY_LOCATION,
            timestamp=ts,
            radar_distance=round(distance, 3),
            baseline_distance=BASELINE_DISTANCE,
            visual_result=VISION_LABEL_TEXT.get(label, label),
            visual_confidence=round(confidence, 4),
            visual_coverage=round(
                coverage if coverage is not None else coverage_for_severity(severity), 4
            ),
            fusion_result=VERDICT_TEXT[verdict],
            risk_score=round(self._risk_from_severity(severity), 1),
            alarm_level=level,
            event_type=event_type,
            handling_status="pending" if level == "critical" else "resolved",
            operator="制丝车间值班员" if level != "critical" else "—",
            resolution=resolution,
            timeline=timeline,
        )

    @staticmethod
    def _risk_from_severity(severity: float) -> float:
        return SimulationEngine._clamp(
            RISK_FLOOR + severity * RISK_WEIGHT_SEVERITY, 0.0, 100.0
        )

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    # ---- 时间标签 -----------------------------------------------------------

    def _label_at(self, sim_time: float) -> str:
        """运行时间 → 时钟标签，基于真实启动时刻，保证与页面时间一致。"""
        moment = datetime.fromtimestamp(self._sim_start + sim_time)
        return moment.strftime("%H:%M:%S")

    def _timestamp_at(self, sim_time: float) -> float:
        return self._sim_start + sim_time

    # =========================================================================
    # 对外只读接口
    # =========================================================================

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def event_recording(self) -> bool:
        """是否登记新的预警/报警事件。"""
        with self._lock:
            return self._event_recording

    @event_recording.setter
    def event_recording(self, enabled: bool) -> None:
        with self._lock:
            self._event_recording = bool(enabled)

    @property
    def seed(self) -> int:
        return self._seed

    def snapshot(self) -> Snapshot:
        """当前完整快照。所有字段来自同一个采样点。"""
        with self._lock:
            sample = self._raw[-1]
            distance = sample.radar_filtered
            fusion, reason = self._fuse(distance, sample.severity, sample.vision_confidence)
            trend = self._risk_trend()
            level = risk_level_of(sample.risk_index)
            label = self._vision_label(sample.severity)

            radar = RadarReading(
                distance=round(distance, 3),
                baseline_distance=BASELINE_DISTANCE,
                delta=round(distance - BASELINE_DISTANCE, 3),
                measured=sample.radar_distance,
                filtered=round(distance, 3),
                sample_rate_hz=SAMPLE_RATE_HZ,
                max_refresh_hz=RADAR_MAX_REFRESH_HZ,
                refresh_text=f"{SAMPLE_RATE_HZ} Hz 正常刷新",
                data_fresh=self._running,
                online=True,
            )

            vision = VisionReading(
                status=VISION_LABEL_TEXT.get(label, label),
                label=label,
                label_text=VISION_LABEL_TEXT.get(label, label),
                confidence=round(sample.vision_confidence, 4),
                coverage=round(sample.vision_coverage, 4),
                latency_ms=int(42 + 26 * sample.severity + abs(self._noise(3.0))),
                online=True,
            )

            environment = EnvironmentReading(
                temperature=round(sample.temperature, 2),
                humidity=round(sample.humidity, 1),
                conveyor_speed=round(sample.conveyor_speed, 3),
                conveyor_speed_baseline=CONVEYOR_BASE_SPEED,
                equipment_load=round(
                    SimulationEngine._clamp(
                        48.0 + 38.0 * sample.severity + self._noise(0.8), 0.0, 100.0
                    ),
                    1,
                ),
                material_coverage=round(sample.vision_coverage, 4),
            )

            risk = RiskReading(
                index=round(sample.risk_index, 1),
                level=level,
                level_text=RISK_LEVEL_TEXT[level],
                trend=trend,
                trend_text=RISK_TREND_TEXT[trend],
            )

            reading = FusionReading(
                verdict=fusion,
                verdict_text=VERDICT_TEXT[fusion],
                mode="fusion",
                reason=reason,
                confidence=round(sample.vision_confidence, 4),
            )

            return Snapshot(
                ts=self._timestamp_at(sample.ts),
                sim_state=self._public_state(),
                sim_state_text=STATE_TEXT[self._public_state()],
                detection_running=self._running,
                stage=self._stage,
                scenario_forced=self._scenario_forced,
                radar=radar,
                vision=vision,
                environment=environment,
                risk=risk,
                fusion=reading,
            )

    def history(self, points: int = HISTORY_DEFAULT_POINTS) -> list[SimSample]:
        """返回降采样后的历史序列。

        浏览器只画 60~180 个点，因此这里把 10 Hz 原始采样等间隔抽样，
        而不是把几千个点全量返回。
        """
        with self._lock:
            return self._downsample(points)

    def _downsample(self, points: int) -> list[SimSample]:
        points = max(10, min(HISTORY_MAX_POINTS, int(points)))
        total = len(self._raw)
        if total <= points:
            return list(self._raw)

        # 等间隔抽样，并始终包含最后一个点（保证曲线末端与当前读数一致）
        step = (total - 1) / (points - 1)
        picked: list[SimSample] = []
        for i in range(points):
            picked.append(self._raw[int(round(i * step))])
        picked[-1] = self._raw[-1]
        return picked

    def recent_samples(self, count: int) -> list[SimSample]:
        """最近 count 个原始采样点（供趋势/预测内部使用）。"""
        with self._lock:
            total = len(self._raw)
            if total <= count:
                return list(self._raw)
            return list(self._raw)[-count:]

    @property
    def uptime_hours(self) -> float:
        with self._lock:
            return round(self._uptime_seconds / 3600.0, 1)

    @property
    def today_warnings(self) -> int:
        with self._lock:
            return self._today_warnings

    @property
    def stage_elapsed(self) -> float:
        with self._lock:
            return self._stage_elapsed

    @property
    def scenario_forced(self) -> bool:
        with self._lock:
            return self._scenario_forced

    @property
    def current_stage(self) -> ScenarioName:
        with self._lock:
            return self._stage

    def current_severity(self) -> float:
        """当前堵料严重度（0~1）。风险指数与各传感器读数都由它派生。"""
        with self._lock:
            return self._severity if self._severity is not None else 0.0

    def alarms(self) -> list[AlarmRecordData]:
        """报警记录，按时间倒序（最新在前）。"""
        with self._lock:
            return sorted(self._alarms, key=lambda a: a.timestamp, reverse=True)

    def alarm_by_id(self, event_id: str) -> AlarmRecordData | None:
        with self._lock:
            for record in self._alarms:
                if record.event_id == event_id:
                    return record
            return None

    # =========================================================================
    # 控制接口（启停 / 复位 / 工况设定）
    # =========================================================================

    def start_detection(self) -> str:
        """开始检测任务。只启动检测，不涉及任何真实生产设备。"""
        with self._lock:
            if self._running:
                return "检测任务已在运行中"
            self._running = True
            return "检测任务已启动"
        
    def stop_detection(self) -> str:
        """停止检测任务。数据采集与风险计算随之暂停，历史仍可查询。"""
        with self._lock:
            if not self._running:
                return "检测任务已处于停止状态"
            self._running = False
            return "检测任务已停止，数据采集暂停"

    def reset(self) -> str:
        """复位运行状态：回到 normal 并清理当前异常状态。

        同时清空实时历史缓冲并重新预热，使状态回到干净的初始值。
        历史报警记录保留（它们属于"已发生的事实"）。
        """
        with self._lock:
            self._rng = random.Random(self._seed)
            self._raw.clear()
            self._stage = "normal"
            self._previous_stage = "normal"
            self._stage_elapsed = 0.0
            self._recover_remaining = 0.0
            self._scenario_forced = False
            self._alarm_this_cycle = False
            self._severity = None
            self._radar_ema = None
            self._coverage_ema = None
            self._temp_ema = TEMP_BASE
            self._humidity_ema = HUMIDITY_BASE
            self._conveyor_ema = CONVEYOR_BASE_SPEED
            self._last_verdict = "normal"
            self._uptime_seconds = 0.0
            self._sim_start = time.time()
            self._sim_time = 0.0
            self._running = True

            self._warmup(WARMUP_SAMPLES)
            return "运行状态已复位，当前工况为正常"

    def set_scenario(self, scenario: ScenarioName) -> str:
        """工况设定：手动指定当前运行工况。

        用于现场联调、阈值校验与应急演练时复现特定工况；
        不指定时引擎按自动工况循环运行。
        """
        with self._lock:
            if scenario not in MONITOR_STATES:
                raise ValueError(f"不支持的运行工况：{scenario}")
            self._stage = scenario
            self._stage_elapsed = 0.0
            self._recover_remaining = 0.0
            self._scenario_forced = True
            self._alarm_this_cycle = scenario == "alarm"
            self._running = True
            return f"运行工况已设定为：{STATE_TEXT[scenario]}"

    def clear_scenario(self) -> str:
        """恢复自动工况循环。"""
        with self._lock:
            self._scenario_forced = False
            self._stage_elapsed = 0.0
            return "已恢复自动工况循环"

    # =========================================================================
    # 智能预警
    # =========================================================================

    def prediction(self, horizon_minutes: int = 30) -> PredictionData:
        """未来 N 分钟风险预测。

        实现方式：用最近 5 分钟的风险斜率做线性外推，并叠加"状态机趋势"权重，
        最后给出概率化措辞与依据列表。不外推为确定性结论。

        为防止把短期扰动放大成"必然爆表"，做了三重约束：
          1. 斜率取 5 分钟窗口，短期抖动会被摊平；
          2. 斜率外推走饱和函数（渐近逼近上限），而不是线性无限外推；
          3. 只有在趋势确实向上（rising / rising_fast）时才叠加状态机牵引，且牵引量有上限；
          4. 整体预测封顶 96% —— 概率预测不给出 100% 的确定性结论。
        """
        with self._lock:
            sample = self._raw[-1]
            current = sample.risk_index
            slope = self._risk_slope_per_minute()
            trend = self._risk_trend()

            # 饱和式外推：斜率越大越接近上限，但永远不会越过它
            raw_extrapolation = slope * horizon_minutes * 0.55
            if raw_extrapolation > 0.0:
                k = raw_extrapolation / FORECAST_MAX_EXTRAPOLATION
                extrapolation = FORECAST_MAX_EXTRAPOLATION * k / (1.0 + k)
            else:
                k = raw_extrapolation / FORECAST_MAX_EXTRAPOLATION
                extrapolation = FORECAST_MAX_EXTRAPOLATION * k / (1.0 - k) if k > -1.0 else -18.0
                extrapolation = max(extrapolation, -18.0)

            # 趋势确实向上时，才叠加"当前阶段目标"的牵引
            target = self._risk_from_severity(STAGE_SEVERITY_TARGET[self._stage])
            if target > current and trend in ("rising", "rising_fast"):
                pull = min((target - current) * 0.45, FORECAST_MAX_PULL)
            else:
                pull = 0.0

            forecast = self._clamp(
                current + extrapolation + pull, 0.0, FORECAST_CEILING
            )

            diff = forecast - current
            if diff >= 20.0:
                change: RiskTrend = "rising_fast"
            elif diff >= 7.0:
                change = "rising"
            elif diff <= -7.0:
                change = "falling"
            else:
                change = "stable"

            level = risk_level_of(forecast)
            evidence = self._evidence(sample, slope)
            suggestions = self._suggestions(level, change)
            similar = self._similar_events(sample, level)

            return PredictionData(
                ts=self._timestamp_at(sample.ts),
                horizon_minutes=horizon_minutes,
                current_index=round(current, 1),
                current_level=risk_level_of(current),
                current_level_text=RISK_LEVEL_TEXT[risk_level_of(current)],
                forecast_index=round(forecast, 1),
                forecast_change=change,
                forecast_change_text=RISK_TREND_TEXT[change],
                forecast_level=level,
                forecast_level_text=RISK_LEVEL_TEXT[level],
                forecast_confidence=round(self._forecast_confidence(slope), 2),
                evidence=evidence,
                suggestions=suggestions,
                similar_events=similar,
                curve=self._forecast_curve(current, forecast, horizon_minutes),
            )

    def _risk_slope_per_minute(self) -> float:
        """最近 5 分钟的风险变化率（百分点/分钟）。

        窗口取 5 分钟而不是更短：制丝线的物料变化是分钟级的连续过程，
        窗口太短会把正常波动误判为"快速上升"。
        """
        window = 300.0
        latest = self._raw[-1]
        reference = None
        for s in reversed(self._raw):
            if latest.ts - s.ts >= window:
                reference = s
                break
        if reference is None:
            reference = self._raw[0]
        elapsed = latest.ts - reference.ts
        if elapsed <= 0.0:
            return 0.0
        return (latest.risk_index - reference.risk_index) / (elapsed / 60.0)

    #: 判定"持续下降"所需的最小累计降幅 (m)。
    #: 取 5 mm：小于此幅度的波动属于传感器噪声与物料自然起伏，不构成趋势。
    RADAR_DECLINE_MIN_DROP = 0.005

    def _radar_decline_minutes(self) -> float:
        """雷达测距连续下降的时长（分钟）。

        两个约束缺一不可：
          1. 逐点回溯时允许 ±3 mm 的噪声容差；
          2. 起点到当前点的**累计降幅**必须达到 RADAR_DECLINE_MIN_DROP。
        否则正常状态下围绕基准的微小抖动会被误报成"持续下降"，
        出现"已持续下降 2 分钟，变化 -0.00 m"这种自相矛盾的依据。
        """
        samples = list(self._raw)
        if len(samples) < 2:
            return 0.0

        end = samples[-1]
        start_index = len(samples) - 1
        previous = end.radar_filtered

        for i in range(len(samples) - 2, -1, -1):
            if samples[i].radar_filtered <= previous + 0.003:
                start_index = i
                previous = samples[i].radar_filtered
            else:
                break

        # 累计降幅不足 → 不认为存在下降趋势
        if end.radar_filtered - samples[start_index].radar_filtered > -self.RADAR_DECLINE_MIN_DROP:
            return 0.0

        return round((end.ts - samples[start_index].ts) / 60.0, 1)

    def _coverage_delta(self) -> float:
        """视觉覆盖率相对 3 分钟前的变化量。"""
        return self._window_delta("vision_coverage", 180.0)

    def _window_delta(self, field: str, window: float) -> float:
        """某个字段相对 window 秒前的变化量。

        刚切换场景（或刚重置）时历史窗口不足，此时差值不具备趋势含义，
        调用方应据此避免给出"近 3 分钟变化 +0.0"这类容易被误读的表述。
        """
        latest = self._raw[-1]
        for s in reversed(self._raw):
            if latest.ts - s.ts >= window:
                return round(getattr(latest, field) - getattr(s, field), 4)
        # 窗口不足：返回 0，并由 has_full_window 告知调用方
        return 0.0

    def _has_full_window(self, window: float) -> bool:
        """历史缓冲是否覆盖了完整的观察窗口。"""
        if len(self._raw) < 2:
            return False
        return (self._raw[-1].ts - self._raw[0].ts) >= window

    def _evidence(self, sample: SimSample, slope: float) -> list[Evidence]:
        """预警依据：全部由真实计算得到，不是写死的文案。"""
        evidence: list[Evidence] = []

        decline = self._radar_decline_minutes()
        # 下降一直追溯到缓冲起点时，说明观测窗口不足，实际下降时长可能更长
        buffered = (self._raw[-1].ts - self._raw[0].ts) / 60.0
        window_limited = buffered > 0 and decline >= buffered - 0.05

        if decline >= 0.5:
            duration = (
                f"已持续下降至少 {decline:.0f} 分钟"
                if window_limited
                else f"连续下降 {decline:.0f} 分钟"
            )
            evidence.append(
                Evidence(
                    source="radar",
                    text=(
                        f"雷达测距{duration}，"
                        f"由基准 {BASELINE_DISTANCE:.2f} m 降至 {sample.radar_filtered:.2f} m"
                        f"（变化 {sample.radar_filtered - BASELINE_DISTANCE:+.2f} m）"
                    ),
                )
            )
        else:
            evidence.append(
                Evidence(
                    source="radar",
                    text=(
                        f"雷达测距 {sample.radar_filtered:.2f} m 在基准 "
                        f"{BASELINE_DISTANCE:.2f} m 附近小幅波动，未见持续单向变化"
                    ),
                )
            )

        coverage_delta = self._coverage_delta()
        window_ready = self._has_full_window(180.0)
        if window_ready:
            coverage_trend = f"近 3 分钟变化 {coverage_delta * 100:+.1f} 个百分点"
        else:
            coverage_trend = "历史窗口不足 3 分钟，暂无法给出覆盖率变化趋势"
        evidence.append(
            Evidence(
                source="vision",
                text=(
                    f"视觉模型测得输送区域物料覆盖率 {sample.vision_coverage * 100:.1f}%，"
                    f"{coverage_trend}，置信度 {sample.vision_confidence * 100:.1f}%"
                ),
            )
        )

        speed_delta = sample.conveyor_speed - CONVEYOR_BASE_SPEED
        if speed_delta <= -0.01:
            evidence.append(
                Evidence(
                    source="conveyor",
                    text=(
                        f"输送有效速度 {sample.conveyor_speed:.2f} m/s，"
                        f"较基准 {CONVEYOR_BASE_SPEED:.2f} m/s 下降 {abs(speed_delta):.2f} m/s"
                    ),
                )
            )
        else:
            evidence.append(
                Evidence(
                    source="conveyor",
                    text=f"输送有效速度 {sample.conveyor_speed:.2f} m/s，接近基准值，未见明显下降",
                )
            )

        evidence.append(
            Evidence(
                source="environment",
                text=(
                    f"环境温度 {sample.temperature:.1f} ℃、湿度 {sample.humidity:.0f}%，"
                    "处于正常区间，未出现剧烈变化"
                ),
            )
        )

        if slope >= 1.0:
            evidence.append(
                Evidence(
                    source="knowledge",
                    text=(
                        f"当前风险变化率为 {slope:+.1f} 百分点/分钟，"
                        "与历史异常事件前兆模式相似度较高"
                    ),
                )
            )

        return evidence

    def _suggestions(self, level: str, change: RiskTrend) -> list[str]:
        """建议措施。措辞保持概率化，不给确定性结论。"""
        if level == "critical":
            return [
                "风险指标已达到报警区间，建议立即检查 2 号输送段物料堆积情况",
                "建议关注上游进料量与下游输送速度的匹配关系",
                "如现场确认堆料，建议降低上游进料量后观察 3~5 分钟",
            ]
        if level == "high" or change in ("rising", "rising_fast"):
            return [
                "堵料风险有上升趋势，建议关注 2 号输送段",
                "建议核查上游进料量是否短时升高、下游输送速度是否下降",
                "可在下一批次切换时安排一次现场巡检",
            ]
        if level == "medium":
            return [
                "指标出现轻微变化趋势，建议保持观察",
                "暂无需现场干预，若风险继续上升系统将进一步提示",
            ]
        return ["当前各项指标处于正常区间，保持常规监控即可"]

    def _forecast_confidence(self, slope: float) -> float:
        """预测置信度：数据越平稳、越有明确趋势，置信度越高。"""
        values = [s.risk_index for s in self.recent_samples(300)]
        if len(values) < 10:
            return 0.60
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        volatility = math.sqrt(variance)
        base = 0.88 - min(0.28, volatility / 100.0)
        if abs(slope) > 2.0:
            base += 0.04
        return SimulationEngine._clamp(base, 0.45, 0.95)

    def _similar_events(self, sample: SimSample, level: str) -> list[SimilarEvent]:
        """相似历史事件匹配。相似度按当前特征与历史前兆模式的接近程度计算。"""
        # 历史前兆模式（来自知识库样例）：测距下降 + 覆盖率上升 + 输送速度下降
        decline = BASELINE_DISTANCE - sample.radar_filtered
        coverage_rise = sample.vision_coverage - coverage_for_severity(0.20)
        speed_drop = (CONVEYOR_BASE_SPEED - sample.conveyor_speed) / CONVEYOR_BASE_SPEED

        def similarity(d_ref: float, c_ref: float, s_ref: float) -> float:
            d = 1.0 - min(1.0, abs(decline - d_ref) / 0.25)
            c = 1.0 - min(1.0, abs(coverage_rise - c_ref) / 0.55)
            s = 1.0 - min(1.0, abs(speed_drop - s_ref) / 0.20)
            return round(max(0.0, 0.35 + 0.65 * (0.45 * d + 0.35 * c + 0.20 * s)), 2)

        catalogue = [
            ("EVT-20250519-02", 0.14, 0.52, 0.13, "制丝线 2 号输送段", "物料堆积",
             "降低上游进料量并检查输送设备，约 4 分钟后物料恢复正常。"),
            ("EVT-20250517-01", 0.11, 0.44, 0.09, "制丝线 2 号输送段", "物料堆积",
             "现场清理落料口积料，调整喂料机频率后恢复。"),
            ("EVT-20250604-03", 0.07, 0.31, 0.06, "制丝线 1 号输送段", "输送速度下降",
             "检查变频器参数无误，判定为物料负载波动，持续观察后自行恢复。"),
        ]

        events = [
            SimilarEvent(
                event_code=code,
                similarity=similarity(d_ref, c_ref, s_ref),
                location=loc,
                event_type=etype,
                result=result,
            )
            for code, d_ref, c_ref, s_ref, loc, etype, result in catalogue
        ]
        events.sort(key=lambda e: e.similarity, reverse=True)
        return events[:3]

    def _forecast_curve(
        self, current: float, forecast: float, horizon_minutes: int
    ) -> list[dict[str, object]]:
        """预测曲线：最近 10 分钟实测 + 未来 30 分钟预测（线性插值）。"""
        curve: list[dict[str, object]] = []

        # 实测段：取最近约 10 分钟，降采样到 20 个点
        history = self._downsample(20)
        for s in history:
            curve.append(
                {"label": self._label_at(s.ts), "actual": round(s.risk_index, 1), "predicted": None}
            )

        # 预测段：从当前点出发，分 6 段到 horizon
        steps = 6
        for i in range(1, steps + 1):
            ratio = i / steps
            value = current + (forecast - current) * ratio
            future_label = self._label_at(self._sim_time + horizon_minutes * 60.0 * ratio)
            curve.append(
                {
                    "label": future_label,
                    "actual": None,
                    "predicted": round(value, 1),
                }
            )

        # 让两条线在"当前"处相接
        if history:
            curve[len(history) - 1]["predicted"] = round(current, 1)

        return curve


# =============================================================================
# 进程级单例
# =============================================================================

_engine: SimulationEngine | None = None
_engine_lock = threading.Lock()


def get_engine() -> SimulationEngine:
    """获取进程内唯一的监控数据引擎实例。"""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from app.config import settings

                _engine = SimulationEngine(seed=settings.simulation_seed)
    return _engine


def reset_engine(seed: int | None = None) -> SimulationEngine:
    """重建引擎（测试用）。"""
    global _engine
    with _engine_lock:
        from app.config import settings

        _engine = SimulationEngine(seed=settings.simulation_seed if seed is None else seed)
    return _engine
