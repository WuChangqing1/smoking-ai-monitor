/**
 * 视频异常检测框（YOLO 风格展示）。
 *
 * ⚠️ 本文件是后端 `backend/app/services/video_detection.py` 的**等价实现**。
 *    后端是权威定义，前端做本地解算以避免高频 HTTP 请求。
 *    修改任一边都必须同步另一边，并运行
 *    `backend/tests/test_video_detection.py` 校验。
 *
 * 定位
 * ----
 * 这是**展示层**的视觉异常表达，不是真实在线推理：
 *   * 不运行 YOLO、不加载模型权重、不引入推理依赖；
 *   * 检测框位置与尺寸**固定**，只随 video_sync 阶段决定是否显示；
 *   * 有框 = 视觉已确认异常区域，无框 = 尚未确认异常。
 *
 * 坐标全部为相对整帧的比例（0~1），因此与页面尺寸、CSS object-fit 无关 ——
 * 只要 overlay 与视频内容同为 16:9 且完全重合，百分比定位天然正确。
 */

import type { RiskLevel } from '../types'
import { VIDEO_SYNC_DURATION, resolveVideoTelemetry } from './videoTelemetry'

/** 风险分段阈值，与 backend/app/services/video_sync.py 保持一致 */
const STATE_WARNING_RISK = 55
const STATE_ALARM_RISK = 80

export type DetectionSeverity = 'none' | 'warning' | 'alarm'

export interface DetectionBox {
  visible: boolean
  /** 左上角 x，相对整帧比例 0~1 */
  x: number
  /** 左上角 y，相对整帧比例 0~1 */
  y: number
  width: number
  height: number
  /** 模型类别（内部标识） */
  label: string
  /** 界面显示名 */
  labelText: string
  /** 概率模型输出置信度，不是准确率 */
  confidence: number
  severity: DetectionSeverity
  /** 异常证据图路径；无框时为 null */
  evidenceImage: string | null
}

/** 单个摄像头的检测框配置 */
export interface DetectionConfig {
  cameraId: string
  x: number
  y: number
  width: number
  height: number
  label: string
  labelText: string
  /** 从哪个风险阈值开始显示框 */
  activeFromRisk: number
  evidenceImage: string
}

/**
 * 主监控点配置。
 *
 * 框位置由人工查看监控视频后确定：物料带沿画面中部由左上向右下延伸。
 * 取该区域的**左上 1/4 子区域**作为检测框 —— 这里正是物料开始增厚、
 * 堆积形态最集中的一段（1280×720 下即 430,190 → 563,363），
 * 比覆盖整条物料带更聚焦，也不包含大片空输送带与设备区域。
 */
export const PRIMARY_DETECTION: DetectionConfig = {
  cameraId: 'CAM-01',
  x: 0.3359,
  y: 0.2639,
  width: 0.1039,
  height: 0.2403,
  label: 'material_accumulation',
  labelText: '物料堆积',
  activeFromRisk: STATE_WARNING_RISK,
  evidenceImage: 'images/evidence/main-camera-material-accumulation.jpg',
}

/**
 * 摄像头 → 检测配置。
 * Camera 02~04 接入视频时在此追加即可，解析逻辑无需改动。
 */
export const DETECTION_CONFIGS: Record<string, DetectionConfig> = {
  [PRIMARY_DETECTION.cameraId]: PRIMARY_DETECTION,
}

export function detectionConfigFor(cameraId: string): DetectionConfig | null {
  return DETECTION_CONFIGS[cameraId] ?? null
}

/** 风险 → 检测框等级。仅 warning 及以上显示框。 */
export function detectionSeverityForRisk(risk: number): DetectionSeverity {
  if (risk < STATE_WARNING_RISK) return 'none'
  if (risk < STATE_ALARM_RISK) return 'warning'
  return 'alarm'
}

/**
 * 检测框置信度：随风险在阶段区间内平滑插值。
 * warning 段 0.88 → 0.93，alarm 段 0.93 → 0.96。
 * 确定性计算，同一 t 结果一致，不会逐帧跳动。
 */
export function detectionConfidenceForRisk(risk: number): number {
  if (risk < STATE_WARNING_RISK) return 0
  if (risk < STATE_ALARM_RISK) {
    const span = STATE_ALARM_RISK - STATE_WARNING_RISK
    const ratio = span > 0 ? (risk - STATE_WARNING_RISK) / span : 0
    return round(0.88 + 0.05 * ratio, 3)
  }
  const span = 100 - STATE_ALARM_RISK
  const ratio = span > 0 ? Math.min(1, (risk - STATE_ALARM_RISK) / span) : 0
  return round(0.93 + 0.03 * ratio, 3)
}

function round(value: number, digits: number): number {
  const factor = 10 ** digits
  return Math.round(value * factor) / factor
}

/** 空框：未配置检测的摄像头返回此结果，页面不渲染任何框 */
const EMPTY_BOX: DetectionBox = {
  visible: false,
  x: 0,
  y: 0,
  width: 0,
  height: 0,
  label: '',
  labelText: '',
  confidence: 0,
  severity: 'none',
  evidenceImage: null,
}

/**
 * 按**视频时间**解算检测框状态。
 *
 * 这是后端 `resolve_video_detection_box` 的等价实现：同一个 ``t`` 得到同一个框。
 * 内部先由 t 解算遥测风险，再据此判定是否显示框 —— 因此框与画面严格同步，
 * 循环回绕、暂停、拖动进度都能自动跟随（t 是唯一输入）。
 *
 * 位置与尺寸在 warning / alarm 阶段**完全相同**，只有边框颜色（severity）
 * 与置信度变化。
 */
export function resolveVideoDetectionBox(
  t: number,
  cameraId: string = PRIMARY_DETECTION.cameraId,
  duration: number = VIDEO_SYNC_DURATION,
): DetectionBox {
  const config = detectionConfigFor(cameraId)
  if (!config) return EMPTY_BOX

  const risk = resolveVideoTelemetry(t, duration).risk_index
  return boxForRisk(risk, config)
}

/**
 * 由风险值直接解算检测框。
 *
 * 页面侧通常已经有遥测（`sync.telemetry`），直接用它派生可以避免重复解算；
 * 与 `resolveVideoDetectionBox` 共用同一套判定，结果完全一致。
 */
export function resolveDetectionBoxForRisk(
  risk: number,
  cameraId: string = PRIMARY_DETECTION.cameraId,
): DetectionBox {
  const config = detectionConfigFor(cameraId)
  if (!config) return EMPTY_BOX
  return boxForRisk(risk, config)
}

function boxForRisk(risk: number, config: DetectionConfig): DetectionBox {
  const severity = detectionSeverityForRisk(risk)
  const visible = severity !== 'none'

  return {
    visible,
    // 位置与尺寸固定，与 t 无关
    x: config.x,
    y: config.y,
    width: config.width,
    height: config.height,
    label: config.label,
    labelText: config.labelText,
    confidence: detectionConfidenceForRisk(risk),
    severity,
    evidenceImage: visible ? config.evidenceImage : null,
  }
}

/** 检测框边框颜色：warning 橙、alarm 红（与 CSS 设计令牌同一色值） */
export function detectionColor(severity: DetectionSeverity): string {
  if (severity === 'alarm') return '#c62828'
  if (severity === 'warning') return '#d97706'
  return 'transparent'
}

/** 风险等级 → 是否应显示检测框（供少量只需布尔值的场景） */
export function isDetectionVisible(level: RiskLevel): boolean {
  return level === 'high' || level === 'critical'
}
