/**
 * 与后端接口对齐的类型定义。
 *
 * 命名口径来自 docs/PROJECT_CONTEXT.md：
 *  - 运行工况 sim_state: normal / attention / warning / alarm / stopped
 *  - 风险等级 risk.level: low / medium / high / critical
 *  - 报警等级 level: info(提示) / warning(预警) / critical(严重)
 */

/** 运行工况状态机状态 */
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
  /** 运行模式：video_sync（视频同步，默认） / automatic（自动工况循环） */
  run_mode: 'automatic' | 'video_sync'
  /** 视频同步模式下主监控视频的源时长（秒） */
  video_duration_seconds: number
  /** 主监控视频的默认播放速率 */
  video_playback_rate: number
}

/** 视频同步关键帧 GET /api/video-sync/info */
export interface VideoKeyframe {
  t: number
  distance: number
  risk: number
  coverage: number
  speed_ratio: number
}

/** 视频同步模式信息 */
export interface VideoSyncInfo {
  run_mode: 'automatic' | 'video_sync'
  duration_seconds: number
  playback_rate: number
  sample_rate_hz: number
  baseline_distance: number
  alarm_threshold: number
  keyframes: VideoKeyframe[]
}

/** 按 video.currentTime 解算的一帧遥测 */
export interface VideoTelemetryPayload {
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
  /** 状态文案，例如「正常输送」「疑似物料堆积」 */
  status: string
  /** 检测类别代码，例如 normal_conveying */
  label: string
  /** 检测类别中文描述 */
  label_text: string
  /** 置信度 0~1（概率模型输出，不代表准确率） */
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
  /** 设备负载 0~100 */
  equipment_load: number
  /** 物料覆盖率 0~1（与视觉覆盖率同源） */
  material_coverage: number
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
  /** 滤波前的测量值 (m) */
  radar_distance: number
  /** 滤波后的测距 (m)，与快照上的 radar.distance 对应 */
  radar_filtered: number
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
  /** 历史序列的降采样间隔（秒）。内部 10 Hz 采样，对外按此间隔抽样。 */
  sample_interval_seconds: number
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
  /** Unix 时间戳（秒） */
  ts: number
  device_id: string
  device_name: string
  device_ip: string
  location: string
  /** 异常类型代码，例如 material_accumulation */
  event_type: string
  /** 异常类型中文描述（后端提供，前端不翻译） */
  event_type_text: string
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

/** 报警详情 GET /api/alarms/{id} */
export interface AlarmDetail extends AlarmRecord {
  /** 基准距离 (m) */
  baseline_distance: number
  /** 当时监控画面（静态图或视频帧） */
  snapshot: string | null
  /**
   * 异常证据图路径（视觉模型检测到异常区域后生成的带框截图）。
   * 无对应证据图的异常类型为 null，此时不渲染证据区块。
   */
  evidence_image: string | null
  /** 面向现场人员的证据说明 */
  evidence_note: string | null
  /** 雷达趋势（用于详情页图表） */
  radar_trend: RealtimeSample[]
  /** AI 判断说明 */
  ai_analysis: {
    vision_label: string
    confidence: number
    coverage: number
    note: string
  }
  /** 处理过程记录 */
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
  level?: AlarmLevel
  status?: AlarmStatus
  page?: number
  page_size?: number
}

/** 报警筛选选项 GET /api/alarms/options */
export interface AlarmFilterOptions {
  levels: Array<{ value: AlarmLevel; label: string }>
  statuses: Array<{ value: AlarmStatus; label: string }>
  devices: Array<{ value: string; label: string }>
  event_types: Array<{ value: string; label: string }>
}

/** 分页结果 */
export interface Paged<T> {
  total: number
  page: number
  page_size: number
  items: T[]
}

/* ==========================================================================
   AI 模型服务（辅助分析）
   ========================================================================== */

/** 服务类型：本地 llama.cpp 或任意 OpenAI 兼容端点 */
export type AIProvider = 'llama_cpp' | 'openai_compatible'

/** 可选服务类型 GET /api/ai/providers（仅用于预填 Base URL） */
export interface AIProviderOption {
  value: AIProvider
  label: string
  default_base_url: string
  hint: string
}

/**
 * AI 配置 GET /api/ai/settings
 *
 * **不含完整 API Key** —— 只有是否已配置与末 4 位掩码。
 */
export interface AISettings {
  provider: AIProvider
  enabled: boolean
  base_url: string
  model: string
  temperature: number
  max_tokens: number
  timeout: number
  api_key_configured: boolean
  masked_api_key: string
  updated_at: string
}

/** 更新 AI 配置 PUT /api/ai/settings（需管理员令牌） */
export interface AISettingsUpdate {
  provider?: AIProvider
  enabled?: boolean
  base_url?: string
  model?: string
  /** 传空串表示清除已保存的 Key；不传表示保持不变 */
  api_key?: string
  temperature?: number
  max_tokens?: number
  timeout?: number
}

/** 连接测试 POST /api/ai/test（需管理员令牌） */
export interface AITestResult {
  ok: boolean
  error: string | null
  models: string[]
  model: string
}

/** 模型服务状态 GET /api/ai/status */
export interface AIStatus {
  enabled: boolean
  configured: boolean
  provider: string
  model: string
  reachable: boolean | null
  last_error: string | null
  analyzable_stages: string[]
  top_k: number
}

/**
 * AI 辅助分析结果。
 *
 * ``source`` 明确区分 ``llm``（真实模型输出）与 ``fallback``（降级）——
 * 页面据此绝不把降级内容当作模型结论展示。
 */
export interface AIAnalysis {
  status: 'ok' | 'disabled' | 'unavailable'
  source: 'llm' | 'fallback'
  analysis_type: string
  analysis_type_text: string
  provider: string
  model: string
  summary: string
  possible_causes: string[]
  recommended_checks: string[]
  recommended_actions: string[]
  related_cases: string[]
  evidence_basis: string[]
  /** 模型输出不是合法 JSON 时，原文保留在这里按纯文本展示 */
  fallback_text: string
  structured: boolean
  generated_at: string
  cached: boolean
  error_message: string | null
}

/** 分析能力元信息 GET /api/ai/analysis/meta */
export interface AIAnalysisMeta {
  analyzable_stages: string[]
  top_k: number
  analysis_type_text: Record<string, string>
  stage: string
}
