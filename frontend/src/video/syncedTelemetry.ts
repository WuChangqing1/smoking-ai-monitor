/**
 * 视频同步适配层。
 *
 * 目标：让首页 / 雷视联动等既有页面**几乎不改动**就能消费同步遥测。
 * 做法是把 VideoTelemetry 适配成页面已经在用的 RealtimeSnapshot 形状，
 * 而不是让每个页面各写一套取值逻辑。
 *
 * 同时提供预测派生（`buildSyncedPrediction`）：video_sync 是压缩回放，
 * 不能机械地把 20 秒解释成现实中的 20 秒，因此预测基于"当前趋势延续"，
 * 措辞保持概率化，并显式说明时间轴经过压缩。
 */

import type {
  FusionVerdict,
  MonitorPoint,
  Prediction,
  RealtimeSample,
  RealtimeSnapshot,
  RiskLevel,
  SimState,
  SystemStatus,
} from '../types'
import { CONVEYOR_BASE_SPEED, VIDEO_PLAYBACK_RATE, type VideoTelemetry } from './videoTelemetry'

/** 风险趋势字面量（与后端 RiskTrendT 一致） */
type RiskTrendValue = 'stable' | 'rising' | 'rising_fast' | 'falling'

/** 主监控点（与后端 devices.py 的 PRIMARY_POINT / CAMERA_NUMBER 一致） */
const PRIMARY_POINT: MonitorPoint = {
  id: 'P02',
  code: 'Camera 01',
  name: '制丝线 2 号输送段',
  position: 2,
  device_id: 'RAD-02',
  device_ip: '192.168.1.198',
  has_radar: true,
  online: true,
  stream: 'videos/main-monitor.mp4',
}

const SIM_STATE_TEXT: Record<SimState, string> = {
  normal: '正常',
  attention: '关注',
  warning: '预警',
  alarm: '异常',
  stopped: '已停止',
}

/** 报警/预测中的趋势文案 */
const RISK_TREND_TEXT: Record<RiskTrendValue, string> = {
  stable: '稳定',
  rising: '上升',
  rising_fast: '快速上升',
  falling: '下降',
}

/** 遥测样本 → 趋势图数据点 */
function toSample(x: VideoTelemetry): RealtimeSample {
  return {
    ts: String(x.t),
    label: `${x.t.toFixed(1)}s`,
    sim_state: x.sim_state,
    radar_distance: x.distance,
    radar_filtered: x.distance,
    risk_index: x.risk_index,
    vision_coverage: x.coverage,
    vision_confidence: x.vision_confidence,
    conveyor_speed: x.conveyor_speed,
    temperature: x.temperature,
    humidity: x.humidity,
  }
}

/** 把同步遥测包装成页面使用的实时快照 */
export function toSyncedSnapshot(
  telemetry: VideoTelemetry,
  trend: VideoTelemetry[],
  options: { running: boolean; sampleIntervalSeconds: number },
): RealtimeSnapshot {
  const samples = trend.map(toSample)
  if (samples.length === 0) samples.push(toSample(telemetry))

  return {
    ts: String(telemetry.t),
    monitor_point: PRIMARY_POINT,
    sim_state: telemetry.sim_state,
    sim_state_text: SIM_STATE_TEXT[telemetry.sim_state],
    // 视频暂停时视为采集暂停，页面据此显示"检测已停止"
    detection_running: options.running,
    radar: {
      distance: telemetry.distance,
      baseline_distance: telemetry.baseline_distance,
      delta: telemetry.delta,
      measured: telemetry.distance,
      filtered: telemetry.distance,
      refresh_hz: 10,
      refresh_text: options.running ? '10 Hz 正常刷新' : '数据已暂停',
      data_fresh: options.running,
      online: true,
    },
    vision: {
      status: telemetry.vision_label_text,
      label: telemetry.vision_label,
      label_text: telemetry.vision_label_text,
      confidence: telemetry.vision_confidence,
      coverage: telemetry.coverage,
      latency_ms: 62,
      online: true,
    },
    environment: {
      temperature: telemetry.temperature,
      humidity: telemetry.humidity,
      conveyor_speed: telemetry.conveyor_speed,
      conveyor_speed_baseline: telemetry.conveyor_speed_baseline,
      equipment_load: telemetry.equipment_load,
      material_coverage: telemetry.coverage,
    },
    risk: {
      index: telemetry.risk_index,
      level: telemetry.risk_level,
      level_text: telemetry.risk_level_text,
      trend: telemetry.risk_trend,
      trend_text: telemetry.risk_trend_text,
    },
    fusion: {
      verdict: telemetry.fusion_verdict,
      verdict_text: telemetry.fusion_verdict_text,
      mode: 'fusion',
      reason: telemetry.fusion_reason,
      confidence: telemetry.vision_confidence,
    },
    samples,
    sample_interval_seconds: options.sampleIntervalSeconds,
  }
}

/**
 * 用同步遥测覆盖系统状态卡。
 *
 * 只替换"随视频变化"的三项（当前风险、检测运行、工况文案），
 * 设备数量、运行时长等与视频无关的字段继续沿用后端数据 ——
 * 这样既保证画面与数据同步，又不会丢失后端提供的真实统计口径。
 */
export function applyTelemetryToStatus(
  base: SystemStatus | null,
  telemetry: VideoTelemetry,
  ctx: { running: boolean; loopCount: number },
): SystemStatus | null {
  if (!base) return base

  return {
    ...base,
    sim_state: telemetry.sim_state,
    sim_state_text: SIM_STATE_TEXT[telemetry.sim_state],
    detection_running: ctx.running,
    today_warnings: base.today_warnings,
    statuses: base.statuses.map((item) => {
      if (item.key === 'system') {
        return {
          ...item,
          state: telemetry.sim_state === 'alarm' ? 'warn' : 'ok',
          text: telemetry.sim_state === 'alarm' ? '异常' : '正常',
          detail: `当前工况：${SIM_STATE_TEXT[telemetry.sim_state]}`,
        }
      }
      if (item.key === 'ai') {
        return {
          ...item,
          state: ctx.running ? 'ok' : 'offline',
          text: ctx.running ? '运行中' : '已停止',
          detail: `视觉模型置信度 ${(telemetry.vision_confidence * 100).toFixed(1)}%`,
        }
      }
      if (item.key === 'radar') {
        return {
          ...item,
          state: ctx.running ? 'ok' : 'warn',
          text: ctx.running ? '正常' : '暂停',
          detail: `10 Hz 采集，当前测距 ${telemetry.distance.toFixed(2)} m`,
        }
      }
      return item
    }),
  }
}

/* ==========================================================================
   预测派生：基于"当前趋势延续"
   ========================================================================== */

const LEVEL_TEXT: Record<RiskLevel, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
  critical: '严重风险',
}

function levelOf(risk: number): RiskLevel {
  if (risk < 30) return 'low'
  if (risk < 55) return 'medium'
  if (risk < 80) return 'high'
  return 'critical'
}

const STATE_SUMMARY: Record<SimState, string> = {
  normal: '当前运行稳定，各项指标处于正常区间，未来风险较低。',
  attention: '雷达距离持续下降，物料覆盖率开始增加，风险存在上升趋势。',
  warning: '堵料风险明显上升，建议关注 2 号输送段。',
  alarm: '当前已达到异常判定条件，建议现场检查 2 号输送段物料堆积情况。',
  stopped: '检测任务已停止，数据与风险变化暂停。',
}

/**
 * 由同步遥测派生 30 分钟风险预测。
 *
 * ⚠️ 时间轴说明：video_sync 是**压缩场景回放**，视频约 20 秒呈现的是一段
 * 更长时间的趋势过程。因此这里的预测表达的是"在当前变化趋势持续的条件下"
 * 的风险走向，而不是"再过 20 秒就会堵料"。
 */
export function buildSyncedPrediction(
  telemetry: VideoTelemetry,
  trend: VideoTelemetry[],
): Prediction {
  const current = telemetry.risk_index

  // 用本轮已走过的轨迹估算变化率（百分点 / 视频秒），并换算为"趋势强度"
  const slope = estimateSlope(trend)

  // 压缩回放：把视频秒的趋势强度映射到一个温和的 30 分钟外推量，
  // 同样走饱和函数并封顶，避免出现 100% 这种确定性结论
  const extrapolation = saturate(slope * 9.5, 45)
  const pull =
    telemetry.risk_level === 'high' || telemetry.risk_level === 'critical'
      ? Math.min(12, (88 - current) * 0.3)
      : 0
  const forecast = clamp(current + extrapolation + Math.max(0, pull), 0, 96)

  const diff = forecast - current
  let change: RiskTrendValue = 'stable'
  if (diff >= 20) change = 'rising_fast'
  else if (diff >= 7) change = 'rising'
  else if (diff <= -7) change = 'falling'

  const trendText = RISK_TREND_TEXT

  const level = levelOf(forecast)
  const rising = change === 'rising' || change === 'rising_fast'

  // 依据：全部由当前遥测与轨迹计算
  const evidence = [
    {
      source: 'radar' as const,
      text:
        telemetry.delta < -0.005
          ? `雷达测距 ${telemetry.distance.toFixed(3)} m，较基准 ${telemetry.baseline_distance.toFixed(
              2,
            )} m 下降 ${Math.abs(telemetry.delta).toFixed(3)} m`
          : `雷达测距 ${telemetry.distance.toFixed(3)} m 在基准 ${telemetry.baseline_distance.toFixed(
              2,
            )} m 附近小幅波动`,
    },
    {
      source: 'vision' as const,
      text: `视觉模型测得物料覆盖率 ${(telemetry.coverage * 100).toFixed(1)}%，类别 ${
        telemetry.vision_label_text
      }，置信度 ${(telemetry.vision_confidence * 100).toFixed(1)}%`,
    },
    {
      source: 'conveyor' as const,
      text:
        telemetry.conveyor_speed < telemetry.conveyor_speed_baseline - 0.01
          ? `输送有效速度 ${telemetry.conveyor_speed.toFixed(2)} m/s，较基准 ${telemetry.conveyor_speed_baseline.toFixed(
              2,
            )} m/s 下降 ${(telemetry.conveyor_speed_baseline - telemetry.conveyor_speed).toFixed(2)} m/s`
          : `输送有效速度 ${telemetry.conveyor_speed.toFixed(2)} m/s，接近基准值`,
    },
    {
      source: 'environment' as const,
      text: `环境温度 ${telemetry.temperature.toFixed(1)} ℃、湿度 ${telemetry.humidity.toFixed(
        0,
      )}%，处于正常区间，未出现剧烈变化`,
    },
    {
      source: 'knowledge' as const,
      text: rising
        ? '当前物料堆积发展过程与历史异常事件 EVT-20250519-02 的前兆模式相似（测距持续下降 + 覆盖率上升 + 输送速度下降）'
        : '当前特征与历史异常事件前兆模式的相似度较低',
    },
  ]

  const suggestions: string[] = []
  if (telemetry.sim_state === 'alarm') {
    suggestions.push(
      '风险指标已达到报警区间，建议立即检查 2 号输送段物料堆积情况',
      '建议关注上游进料量与下游输送速度的匹配关系',
      '如现场确认堆料，建议降低上游进料量后观察 3~5 分钟',
    )
  } else if (rising) {
    suggestions.push(
      '堵料风险有上升趋势，建议关注 2 号输送段',
      '建议核查上游进料量是否短时升高、下游输送速度是否下降',
      '可在下一批次切换时安排一次现场巡检',
    )
  } else if (telemetry.risk_level === 'medium') {
    suggestions.push('指标出现轻微变化趋势，建议保持观察', '暂无需现场干预，风险继续上升时系统将进一步提示')
  } else {
    suggestions.push('当前各项指标处于正常区间，保持常规监控即可')
  }

  // 相似历史事件：按当前特征与历史前兆的接近程度排序
  const decline = Math.max(0, -telemetry.delta)
  const coverageRise = Math.max(0, telemetry.coverage - 0.3)
  const speedDrop = Math.max(
    0,
    (telemetry.conveyor_speed_baseline - telemetry.conveyor_speed) / telemetry.conveyor_speed_baseline,
  )
  const similarity = (dRef: number, cRef: number, sRef: number) => {
    const d = 1 - Math.min(1, Math.abs(decline - dRef) / 0.25)
    const c = 1 - Math.min(1, Math.abs(coverageRise - cRef) / 0.55)
    const s = 1 - Math.min(1, Math.abs(speedDrop - sRef) / 0.2)
    return Math.round(Math.max(0, 0.35 + 0.65 * (0.45 * d + 0.35 * c + 0.2 * s)) * 100) / 100
  }

  const similarEvents = [
    {
      event_code: 'EVT-20250519-02',
      similarity: similarity(0.14, 0.52, 0.13),
      location: '制丝线 2 号输送段',
      event_type: '物料堆积',
      result: '降低上游进料量并检查输送设备，约 4 分钟后物料恢复正常。',
    },
    {
      event_code: 'EVT-20250517-01',
      similarity: similarity(0.11, 0.44, 0.09),
      location: '制丝线 2 号输送段',
      event_type: '物料堆积',
      result: '现场清理落料口积料，调整喂料机频率后恢复。',
    },
    {
      event_code: 'EVT-20250604-03',
      similarity: similarity(0.07, 0.31, 0.06),
      location: '制丝线 1 号输送段',
      event_type: '输送速度下降',
      result: '检查变频器参数无误，判定为物料负载波动，持续观察后自行恢复。',
    },
  ].sort((a, b) => b.similarity - a.similarity)

  // 预测曲线：实测段用本轮轨迹，未来段按趋势外推（终点封顶 96%）
  const curve: Prediction['curve'] = trend.map((x) => ({
    label: `${x.t.toFixed(1)}s`,
    actual: x.risk_index,
    predicted: null,
  }))
  const steps = 6
  for (let i = 1; i <= steps; i += 1) {
    const ratio = i / steps
    curve.push({
      label: `+${Math.round(ratio * 30)}min`,
      actual: null,
      predicted: Math.round((current + (forecast - current) * ratio) * 10) / 10,
    })
  }
  if (trend.length > 0) curve[trend.length - 1].predicted = Math.round(current * 10) / 10

  return {
    ts: String(telemetry.t),
    horizon_minutes: 30,
    current: {
      index: Math.round(current * 10) / 10,
      level: telemetry.risk_level,
      level_text: telemetry.risk_level_text,
    },
    forecast: {
      risk_index: Math.round(forecast * 10) / 10,
      change,
      change_text: trendText[change],
      level,
      level_text: LEVEL_TEXT[level],
      confidence: 0.88,
    },
    evidence: [
      { source: 'radar' as const, text: STATE_SUMMARY[telemetry.sim_state] },
      ...evidence,
    ],
    suggestions: [
      ...suggestions,
      '说明：画面同步模式的时间轴经过压缩，用于呈现真实系统中可能跨越更长时间发生的趋势；预测表达的是"在当前趋势持续条件下"的风险走向。',
    ],
    similar_events: similarEvents,
    curve,
  }
}

/** 用本轮轨迹估算风险变化率（百分点 / 视频秒） */
function estimateSlope(trend: VideoTelemetry[]): number {
  if (trend.length < 2) return 0
  const first = trend[0]
  const last = trend[trend.length - 1]
  const span = last.t - first.t
  if (span <= 0) return 0
  return (last.risk_index - first.risk_index) / span
}

/** 饱和函数：渐近逼近上限而不越界，避免预测轻易顶到 100% */
function saturate(value: number, limit: number): number {
  if (value <= 0) return Math.max(-18, value * 0.4)
  const k = value / limit
  return (limit * k) / (1 + k)
}

function clamp(value: number, low: number, high: number): number {
  return Math.max(low, Math.min(high, value))
}

export { CONVEYOR_BASE_SPEED, VIDEO_PLAYBACK_RATE }

/** 导出便于测试断言 */
export type { FusionVerdict }
