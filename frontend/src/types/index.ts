/**
 * 与后端接口对齐的类型定义。
 *
 * 命名口径来自 docs/PROJECT_CONTEXT.md：
 *  - 仿真状态 sim_state: normal / attention / warning / alarm / stopped
 *  - 风险等级 risk.level: low / medium / high / critical
 *  - 报警等级 level: info(提示) / warning(预警) / critical(严重)
 */

/** 仿真状态机状态 */
export type SimState = 'normal' | 'attention' | 'warning' | 'alarm' | 'stopped'

/** 风险等级 */
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'

/** 报警等级 */
export type AlarmLevel = 'info' | 'warning' | 'critical'

/** 报警处理状态 */
export type AlarmStatus = 'pending' | 'processing' | 'resolved' | 'archived'

/** 联合判断结果 */
export type FusionVerdict = 'normal' | 'attention' | 'warning' | 'alarm'

/** 单项健康状态 */
export type HealthState = 'ok' | 'warn' | 'error' | 'offline'

/** 设备类型 */
export type DeviceKind = 'radar' | 'camera'

/** 判断模式：联合判断 / 单独判断（依据原始资料） */
export type FusionMode = 'fusion' | 'vision_only'

/** 平台元信息 GET /api/meta */
export interface PlatformMeta {
  platform_name: string
  project_name: string
  mode: 'simulation' | 'realtime'
  mode_note: string
  conveyor_line: string
  monitor_points: number
  devices: { radar: number; camera: number; total: number }
  data_rate_hz: number
}

/** 运行状态项 GET /api/system/status */
export interface StatusItem {
  key: string
  label: string
  state: HealthState
  /** 面向用户的中文状态词，例如「正常」「运行中」「在线」「已停止」 */
  text: string
  detail?: string
}

/** 系统运行状态 GET /api/system/status */
export interface SystemStatus {
  ts: string
  /** 检测任务是否在运行（对应启停控制） */
  detection_running: boolean
  sim_state: SimState
  sim_state_text: string
  /** 连续运行时长（小时，保留 1 位小数） */
  uptime_hours: number
  statuses: StatusItem[]
  /** 今日预警次数 */
  today_warnings: number
  /** 在线设备数 / 总数 */
  devices_online: number
  devices_total: number
}

/** 雷达实时数据 */
export interface RadarReading {
  /** 当前距离 (m) */
  distance: number
  /** 基准距离 (m)，主监控点为 0.72 */
  baseline_distance: number
  /** 变化量 (m)，= distance - baseline */
  delta: number
  /** 数据刷新状态描述，例如「10 Hz 正常刷新」 */
  refresh_text: string
  refresh_hz: number
  /** 采样本周期内是否新鲜 */
  data_fresh: boolean
  /** 雷达是否在线 */
  online: boolean
  /** 滤波值（对应原系统「滤波值:0.58」） */
  filtered: number
  /** 测量值（对应原系统「测量值:0.58」） */
  measured: number
}

/** 视觉 AI 实时数据 */
export interface VisionReading {
  /** 状态文案，例如「正常」「疑似物料堆积」 */
  status: string
  /** 检测类别 */
  label: string
  /** 置信度 0~1 */
  confidence: number
  /** 输送区域物料覆盖率 0~1 */
  coverage: number
  /** 推理耗时 (ms) */
  latency_ms: number
  online: boolean
}

/** 环境与输送辅助数据 */
export interface EnvironmentReading {
  temperature: number
  humidity: number
  conveyor_speed: number
  /** 输送速度基准值 (m/s) */
  conveyor_speed_baseline: number
}

/** 风险指数 */
export interface RiskReading {
  /** 0~100 */
  index: number
  level: RiskLevel
  level_text: string
  /** 趋势：stable / rising / rising_fast / falling */
  trend: 'stable' | 'rising' | 'rising_fast' | 'falling'
  trend_text: string
}

/** 联合判断结果 */
export interface FusionReading {
  verdict: FusionVerdict
  verdict_text: string
  /** 判断模式 */
  mode: FusionMode
  /** 判断依据文字说明（后端产生） */
  reason: string
  /** 置信度 0~1 */
  confidence: number
}

/** 单条实时样本（趋势图数据点） */
export interface RealtimeSample {
  ts: string
  /** 相对时间标签，例如 13:34:16 */
  label: string
  sim_state: SimState
  radar_distance: number
  risk_index: number
  vision_coverage: number
  vision_confidence: number
  conveyor_speed: number
  temperature: number
  humidity: number
}

/** 实时快照 GET /api/realtime */
export interface RealtimeSnapshot {
  ts: string
  monitor_point: MonitorPoint
  sim_state: SimState
  sim_state_text: string
  detection_running: boolean
  radar: RadarReading
  vision: VisionReading
  environment: EnvironmentReading
  risk: RiskReading
  fusion: FusionReading
  /** 滚动窗口内的最近样本（后端限制长度，避免无限增长） */
  samples: RealtimeSample[]
}

/** 监控点 */
export interface MonitorPoint {
  id: string
  code: string
  name: string
  /** 设备位置编号，例如 2 */
  position: number
  device_id: string
  device_ip: string
  /** 是否具备雷达 */
  has_radar: boolean
  online: boolean
  /** 监控画面资源；null 表示该点位暂无画面（前端显示占位） */
  stream: string | null
}

/** 设备 GET /api/devices */
export interface Device {
  id: string
  name: string
  kind: DeviceKind
  model: string
  vendor: string
  ip: string
  location: string
  point_id: string
  online: boolean
  /** 关键规格摘要，来自原始验收资料 */
  spec: string
  /** 雷达专属 */
  radar?: {
    range: string
    accuracy: string
    max_refresh_hz: number
    protection: string
  }
  /** 摄像头专属 */
  camera?: {
    resolution: string
    encoding: string
    protection: string
    fps: number
  }
}

/** 报警记录 */
export interface AlarmRecord {
  id: string
  /** 报警编号，例如 ALM-20250519-1334 */
  code: string
  ts: string
  device_id: string
  device_name: string
  device_ip: string
  location: string
  /** 异常类型，例如 物料堆积 */
  event_type: string
  level: AlarmLevel
  level_text: string
  radar_value: number | null
  vision_result: string
  fusion_result: string
  status: AlarmStatus
  status_text: string
  /** 风险指数 */
  risk_index: number
}

/** 报警详情 GET /api/alarms/{id} —— 发现→判断→报警→处理→归档 闭环 */
export interface AlarmDetail extends AlarmRecord {
  /** 当时监控画面（静态图或视频帧） */
  snapshot: string | null
  /** 雷达趋势（用于详情页图表） */
  radar_trend: RealtimeSample[]
  /** AI 判断说明 */
  ai_analysis: {
    vision_label: string
    confidence: number
    coverage: number
    note: string
  }
  /** 处理闭环时间线 */
  timeline: Array<{
    ts: string
    stage: string
    title: string
    detail: string
  }>
  operator: string
  resolution: string
}

/** 知识库事件 */
export interface KnowledgeEvent {
  id: number
  event_code: string
  timestamp: string
  device_id: string
  location: string
  event_type: string
  radar_summary: string
  vision_summary: string
  environment_summary: string
  pre_event_pattern: string
  operator_review: string
  action_taken: string
  result: string
  preventive_suggestion: string
}

/** 智能预警 GET /api/prediction */
export interface Prediction {
  ts: string
  horizon_minutes: number
  current: { index: number; level: RiskLevel; level_text: string }
  forecast: {
    /** 预测风险 0~100 */
    risk_index: number
    /** 变化趋势 */
    change: 'stable' | 'rising' | 'rising_fast' | 'falling'
    change_text: string
    /** 风险等级（预测） */
    level: RiskLevel
    level_text: string
    /** 预测置信度 0~1 */
    confidence: number
  }
  /** 预警依据列表（后端依据实际数据产生） */
  evidence: Array<{
    source: 'radar' | 'vision' | 'conveyor' | 'knowledge' | 'environment'
    text: string
  }>
  /** 建议措施，措辞为概率化建议，不下确定性结论 */
  suggestions: string[]
  /** 相似历史事件 */
  similar_events: Array<{
    event_code: string
    similarity: number
    location: string
    event_type: string
    result: string
  }>
  /** 用于展示的预测曲线 */
  curve: Array<{ label: string; actual: number | null; predicted: number | null }>
}

/** 数据溯源查询条件 */
export interface TraceQuery {
  date_from?: string
  date_to?: string
  device_id?: string
  event_type?: string
  level?: RiskLevel
  status?: AlarmStatus
  page?: number
  page_size?: number
}

/** 分页结果 */
export interface Paged<T> {
  total: number
  page: number
  page_size: number
  items: T[]
}
