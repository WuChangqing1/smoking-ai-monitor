/**
 * 视频同步遥测解析器（video_sync 模式）。
 *
 * ⚠️ 本文件是后端 `backend/app/services/video_sync.py` 的**逐行等价实现**。
 *    两边必须保持一致：后端是权威定义，前端做本地插值以避免高频 HTTP 请求。
 *    修改任一边都必须同步另一边，并运行 `backend/tests/test_video_sync.py`
 *    与 `frontend/src/video/videoTelemetry.selftest.ts` 校验。
 *
 * 设计要点
 * --------
 * 1. **唯一时间源是 video.currentTime**（源视频 0~10 s）。
 *    不使用 Date.now()、不使用"页面运行了多少秒"，
 *    因此加载延迟、卡顿、切后台、暂停、拖动进度、循环都不会造成画面与数据脱节。
 * 2. **关键帧 + 线性插值**，绝不出现分段跳变。
 * 3. **确定性微扰**：sin 关于 t 的固定函数，同一 t 每次结果一致，
 *    视频循环后数据可复现，适合录屏与答辩。
 */

import type { FusionVerdict, RiskLevel, SimState } from '../types'

/** 源视频时长（秒），与 public/videos/main-monitor.mp4 一致 */
export const VIDEO_SYNC_DURATION = 10

/** 主监控视频默认播放速率：源视频 10 s → 演示周期约 20 s */
export const VIDEO_PLAYBACK_RATE = 0.5

/** 主监控点参数（与后端、原始验收资料一致） */
export const BASELINE_DISTANCE = 0.72
export const ALARM_THRESHOLD = 0.58
export const CONVEYOR_BASE_SPEED = 1.2
const TEMP_BASE = 23.6
const HUMIDITY_BASE = 54

/** 状态/视觉结果分界，与后端 STATE_*_RISK 一致 */
const STATE_ATTENTION_RISK = 30
const STATE_WARNING_RISK = 55
const STATE_ALARM_RISK = 80

export interface VideoKeyframe {
  /** 源视频时间（秒） */
  t: number
  distance: number
  risk: number
  coverage: number
  speedRatio: number
}

/**
 * 关键帧轨迹：对应视频中物料由正常输送逐渐堆积到明显堆积的过程。
 * 终点收敛到约 0.58 m —— 取自原始验收资料中的真实报警测量值。
 */
export const VIDEO_KEYFRAMES: readonly VideoKeyframe[] = [
  { t: 0, distance: 0.721, risk: 18, coverage: 0.3, speedRatio: 1.0 },
  { t: 2, distance: 0.706, risk: 27, coverage: 0.37, speedRatio: 0.98 },
  { t: 4, distance: 0.681, risk: 43, coverage: 0.49, speedRatio: 0.95 },
  { t: 6, distance: 0.651, risk: 59, coverage: 0.61, speedRatio: 0.91 },
  { t: 8, distance: 0.612, risk: 76, coverage: 0.74, speedRatio: 0.86 },
  { t: 10, distance: 0.582, risk: 89, coverage: 0.83, speedRatio: 0.8 },
] as const

/** 解算结果：字段与后端 VideoTelemetryOut 对应 */
export interface VideoTelemetry {
  t: number
  sim_state: SimState
  sim_state_text: string
  risk_index: number
  risk_level: RiskLevel
  risk_level_text: string
  risk_trend: 'stable' | 'rising' | 'rising_fast' | 'falling'
  risk_trend_text: string
  distance: number
  baseline_distance: number
  delta: number
  coverage: number
  vision_label: string
  vision_label_text: string
  vision_confidence: number
  conveyor_speed: number
  conveyor_speed_baseline: number
  equipment_load: number
  temperature: number
  humidity: number
  fusion_verdict: FusionVerdict
  fusion_verdict_text: string
  fusion_reason: string
}

const STATE_TEXT: Record<string, string> = {
  normal: '正常',
  attention: '关注',
  warning: '预警',
  alarm: '异常',
  stopped: '已停止',
}

const RISK_LEVEL_TEXT: Record<RiskLevel, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
  critical: '严重风险',
}

const RISK_TREND_TEXT: Record<string, string> = {
  stable: '稳定',
  rising: '上升',
  rising_fast: '快速上升',
  falling: '下降',
}

const VERDICT_TEXT: Record<FusionVerdict, string> = {
  normal: '正常',
  attention: '关注',
  warning: '预警',
  alarm: '异常',
}

const VISION_LABEL_TEXT: Record<string, string> = {
  normal_conveying: '正常输送',
  material_accumulation_suspected: '疑似物料堆积',
  material_accumulation: '物料堆积',
}

/** 把任意输入安全夹到 [0, duration]；非数值按 0 处理 */
export function clampVideoTime(t: number, duration: number = VIDEO_SYNC_DURATION): number {
  const value = Number(t)
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(duration, value))
}

function lerp(a: number, b: number, ratio: number): number {
  return a + (b - a) * ratio
}

/** 按线性插值求 t 处的关键帧数值（无跳变） */
export function interpolateKeyframes(t: number): VideoKeyframe {
  const frames = VIDEO_KEYFRAMES
  if (t <= frames[0].t) return frames[0]
  if (t >= frames[frames.length - 1].t) return frames[frames.length - 1]

  for (let i = 0; i < frames.length - 1; i += 1) {
    const left = frames[i]
    const right = frames[i + 1]
    if (t >= left.t && t <= right.t) {
      const span = right.t - left.t
      const ratio = span <= 0 ? 0 : (t - left.t) / span
      return {
        t,
        distance: lerp(left.distance, right.distance, ratio),
        risk: lerp(left.risk, right.risk, ratio),
        coverage: lerp(left.coverage, right.coverage, ratio),
        speedRatio: lerp(left.speedRatio, right.speedRatio, ratio),
      }
    }
  }
  return frames[frames.length - 1]
}

function stateForRisk(risk: number): SimState {
  if (risk < STATE_ATTENTION_RISK) return 'normal'
  if (risk < STATE_WARNING_RISK) return 'attention'
  if (risk < STATE_ALARM_RISK) return 'warning'
  return 'alarm'
}

function riskLevelOf(risk: number): RiskLevel {
  if (risk < 30) return 'low'
  if (risk < 55) return 'medium'
  if (risk < 80) return 'high'
  return 'critical'
}

/**
 * 视觉模型结果：类别与置信度随风险阶段变化。
 * 置信度是概率模型输出，不是准确率。
 */
function visionForRisk(risk: number): { label: string; confidence: number } {
  if (risk < STATE_ATTENTION_RISK) return { label: 'normal_conveying', confidence: 0.97 }
  if (risk < STATE_WARNING_RISK) {
    return { label: 'material_accumulation_suspected', confidence: 0.82 }
  }
  if (risk < STATE_ALARM_RISK) return { label: 'material_accumulation', confidence: 0.9 }
  return { label: 'material_accumulation', confidence: 0.95 }
}

/** 风险变化趋势：与 window 秒前的关键帧曲线比较 */
function riskTrend(t: number, window = 1): VideoTelemetry['risk_trend'] {
  if (t <= 0) return 'rising'
  const previous = interpolateKeyframes(Math.max(0, t - window)).risk
  const current = interpolateKeyframes(t).risk
  const diff = current - previous
  if (diff >= 11) return 'rising_fast'
  if (diff >= 3.5) return 'rising'
  if (diff <= -3.5) return 'falling'
  return 'stable'
}

function fusionReason(risk: number, distance: number, coverage: number): string {
  const state = stateForRisk(risk)
  const delta = distance - BASELINE_DISTANCE
  if (state === 'normal') {
    return `雷达测距 ${distance.toFixed(3)} m 在基准附近波动，视觉未见异常形态，联合判断正常。`
  }
  if (state === 'attention') {
    return `雷达测距较基准下降 ${Math.abs(delta).toFixed(3)} m，物料覆盖率升至 ${(
      coverage * 100
    ).toFixed(1)}%，视觉识别到形态变化，联合判断为关注。`
  }
  if (state === 'warning') {
    return `雷达测距持续下降至 ${distance.toFixed(
      3,
    )} m，视觉确认物料堆积形态（覆盖率 ${(coverage * 100).toFixed(
      1,
    )}%），联合判断风险上升。`
  }
  return `雷达测距已接近报警阈值（${distance.toFixed(
    3,
  )} m），视觉确认明显堆积形态（覆盖率 ${(coverage * 100).toFixed(
    1,
  )}%），联合判断异常。`
}

/**
 * 把视频时间解算为一帧完整遥测。
 * `rawT` 会被夹到 [0, duration]，循环回绕、拖动进度、后台恢复都能安全解析。
 */
export function resolveVideoTelemetry(
  rawT: number,
  duration: number = VIDEO_SYNC_DURATION,
): VideoTelemetry {
  const safeDuration = duration && duration > 0 ? duration : VIDEO_SYNC_DURATION
  const t = clampVideoTime(rawT, safeDuration)

  // 关键帧定义在标准 10 s 轴上；实际时长不同则等比映射
  const timelineT = safeDuration === VIDEO_SYNC_DURATION ? t : t * (VIDEO_SYNC_DURATION / safeDuration)
  const frame = interpolateKeyframes(timelineT)

  // ---- 确定性微扰：±1~3 mm，同一 t 每次结果一致 ----
  const distanceJitter =
    0.001 * Math.sin(2 * Math.PI * 1.7 * timelineT + 0.6) +
    0.0006 * Math.sin(2 * Math.PI * 4.3 * timelineT + 2.1) +
    0.0004 * Math.sin(2 * Math.PI * 9.1 * timelineT + 4.2)
  const riskJitter = 0.5 * Math.sin(2 * Math.PI * 2.3 * timelineT + 1.1)

  const distance = round(frame.distance + distanceJitter, 4)
  const coverage = round(
    Math.max(0, Math.min(0.99, frame.coverage + 0.004 * Math.sin(2 * Math.PI * 2.9 * timelineT))),
    4,
  )
  const risk = Math.max(0, Math.min(100, frame.risk + riskJitter))
  const conveyorSpeed = round(CONVEYOR_BASE_SPEED * frame.speedRatio, 3)

  const severity = Math.max(0, Math.min(1, risk / 100))
  const equipmentLoad = round(Math.max(0, Math.min(100, 48 + 38 * severity)), 1)
  const temperature = round(TEMP_BASE + 1.3 * severity + 0.15 * Math.sin(0.7 * timelineT), 2)
  const humidity = round(HUMIDITY_BASE - 3 * severity + 0.4 * Math.cos(0.5 * timelineT), 1)

  const vision = visionForRisk(risk)
  const trend = riskTrend(timelineT)
  const level = riskLevelOf(risk)
  const state = stateForRisk(risk)

  return {
    t: round(t, 3),
    sim_state: state,
    sim_state_text: STATE_TEXT[state],
    risk_index: round(risk, 1),
    risk_level: level,
    risk_level_text: RISK_LEVEL_TEXT[level],
    risk_trend: trend,
    risk_trend_text: RISK_TREND_TEXT[trend],
    distance,
    baseline_distance: BASELINE_DISTANCE,
    delta: round(distance - BASELINE_DISTANCE, 4),
    coverage,
    vision_label: vision.label,
    vision_label_text: VISION_LABEL_TEXT[vision.label] ?? vision.label,
    vision_confidence: vision.confidence,
    conveyor_speed: conveyorSpeed,
    conveyor_speed_baseline: CONVEYOR_BASE_SPEED,
    equipment_load: equipmentLoad,
    temperature,
    humidity,
    fusion_verdict: state as FusionVerdict,
    fusion_verdict_text: VERDICT_TEXT[state as FusionVerdict],
    fusion_reason: fusionReason(risk, distance, coverage),
  }
}

function round(value: number, digits: number): number {
  const factor = 10 ** digits
  return Math.round(value * factor) / factor
}

/**
 * 生成 0 → t 的遥测序列（默认 0.2 s 一个点）。
 *
 * 趋势图只展示"当前这一轮已经走过的时间"，视频循环后自然从头开始，
 * 不会形成 0.72 → 0.58 → 0.72 这种无限锯齿累积。
 */
export function samplesUpTo(t: number, step = 0.2): VideoTelemetry[] {
  const clamped = clampVideoTime(t)
  const points: VideoTelemetry[] = []
  const count = Math.floor(clamped / step)
  for (let i = 0; i <= count; i += 1) {
    points.push(resolveVideoTelemetry(i * step))
  }
  // 末尾补上精确的当前时刻，保证曲线末端与当前读数一致
  if (points.length === 0 || points[points.length - 1].t < clamped) {
    points.push(resolveVideoTelemetry(clamped))
  }
  return points
}
