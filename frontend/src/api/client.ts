/**
 * 后端接口客户端。
 *
 * 设计要点：
 *  - 所有请求都带超时，避免长时间挂起导致页面假死；
 *  - 失败时抛出带中文说明的错误，由调用方决定降级展示（不白屏）；
 *  - baseURL 默认走同源 /api（开发由 Vite 代理，生产由 Nginx 反代），
 *    可用 VITE_API_BASE 覆盖。
 */

import type {
  AlarmDetail,
  AlarmFilterOptions,
  AlarmRecord,
  Device,
  KnowledgeEvent,
  MonitorPoint,
  Paged,
  PlatformMeta,
  Prediction,
  RealtimeSample,
  RealtimeSnapshot,
  SystemStatus,
  TraceQuery,
} from '../types'

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? ''
const DEFAULT_TIMEOUT = 8000

/** 部署后的线上地址，用于在本地后端未启动时给出可用的替代入口 */
const DEPLOYED_URL = 'http://110.42.236.65:18082/'

/** 用 file:// 直接打开 dist/index.html 时，任何 fetch 都会失败 */
function isFileProtocol(): boolean {
  return typeof window !== 'undefined' && window.location.protocol === 'file:'
}

export class ApiError extends Error {
  readonly status: number
  /** 是否为"连不上后端"这一类错误（区别于后端返回了错误码） */
  readonly isConnectionError: boolean

  constructor(message: string, status = 0, isConnectionError = false) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.isConnectionError = isConnectionError
  }
}

/** 组装"连不上后端"时的可执行提示，而不是让使用者自己猜 */
function connectionHint(): string {
  if (isFileProtocol()) {
    return (
      '当前是用文件方式（file://）打开的页面，浏览器不允许它访问接口。' +
      '请通过服务地址访问：本地开发用 http://127.0.0.1:15173 ，' +
      `线上环境用 ${DEPLOYED_URL}`
    )
  }
  return (
    '后端服务未启动或已停止。请在项目根目录执行 scripts\\backend.bat（Windows）' +
    '或 ./scripts/dev.sh（Linux/macOS）启动后端；' +
    `若只想查看平台，可直接打开线上地址 ${DEPLOYED_URL}`
  )
}

async function request<T>(path: string, init?: RequestInit & { timeout?: number }): Promise<T> {
  const { timeout = DEFAULT_TIMEOUT, ...rest } = init ?? {}
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeout)

  try {
    const resp = await fetch(`${API_BASE}${path}`, {
      ...rest,
      signal: controller.signal,
      headers: { Accept: 'application/json', ...(rest.headers ?? {}) },
    })

    if (!resp.ok) {
      throw new ApiError(`接口 ${path} 返回 ${resp.status}`, resp.status)
    }
    return (await resp.json()) as T
  } catch (err) {
    if (err instanceof ApiError) throw err
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError(`接口 ${path} 请求超时（${timeout}ms），后端可能正在重启`, 0, true)
    }
    // 网络层失败（连接被拒 / DNS / file:// 协议）统一归为"连不上后端"
    throw new ApiError(`无法连接后端服务（${path}）。${connectionHint()}`, 0, true)
  } finally {
    window.clearTimeout(timer)
  }
}

/**
 * 把查询对象序列化为 query string。
 *
 * 形参用 object 而不是 Record<string, unknown>：这样具名的 interface
 * （例如 TraceQuery）也能直接传入，无需为它补索引签名。
 */
function toQuery(params: object): string {
  const usable = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null && v !== '',
  )
  if (usable.length === 0) return ''
  const sp = new URLSearchParams()
  for (const [k, v] of usable) sp.set(k, String(v))
  return `?${sp.toString()}`
}

export const api = {
  /** 平台元信息 */
  meta: () => request<PlatformMeta>('/api/meta'),

  /** 健康检查 */
  health: () => request<{ status: string; service: string; version: string }>('/api/health'),

  /** 系统运行状态 */
  systemStatus: () => request<SystemStatus>('/api/system/status'),

  /** 实时快照（含滚动窗口样本）。points 控制趋势窗口点数，后端限制为 10~180。 */
  realtime: (points = 120) => request<RealtimeSnapshot>(`/api/realtime${toQuery({ points })}`),

  /** 实时历史样本 */
  realtimeHistory: (limit = 120) =>
    request<RealtimeSample[]>(`/api/realtime/history${toQuery({ limit })}`),

  /** 设备列表 */
  devices: () => request<Device[]>('/api/devices'),

  /** 监控点位 */
  monitorPoints: () => request<MonitorPoint[]>('/api/monitor-points'),

  /** 报警列表 */
  alarms: (query: TraceQuery = {}) => request<Paged<AlarmRecord>>(`/api/alarms${toQuery(query)}`),

  /** 报警筛选选项（下拉数据源，避免前端硬编码） */
  alarmOptions: () => request<AlarmFilterOptions>('/api/alarms/options'),

  /** 报警详情 */
  alarmDetail: (id: string) => request<AlarmDetail>(`/api/alarms/${encodeURIComponent(id)}`),

  /** 知识库事件 */
  knowledge: (query: { keyword?: string; event_type?: string } = {}) =>
    request<KnowledgeEvent[]>(`/api/knowledge${toQuery(query)}`),

  /** 知识库异常类型列表（筛选项来源） */
  knowledgeTypes: () => request<string[]>('/api/knowledge/types'),

  /** 智能预警（未来 30 分钟风险预测） */
  prediction: () => request<Prediction>('/api/prediction'),

  /** 开始检测 */
  detectionStart: () => request<{ ok: boolean; message: string }>('/api/detection/start', { method: 'POST' }),

  /** 停止检测 */
  detectionStop: () => request<{ ok: boolean; message: string }>('/api/detection/stop', { method: 'POST' }),

  /** 重置模拟 */
  simulationReset: () => request<{ ok: boolean; message: string }>('/api/simulation/reset', { method: 'POST' }),

  /**
   * 演示模式：强制进入指定仿真状态。
   * 仅供答辩前录屏使用，刻意不放在主界面显眼位置。
   */
  setScenario: (scenario: 'normal' | 'attention' | 'warning' | 'alarm') =>
    request<{ ok: boolean; message: string; sim_state: string }>(
      `/api/simulation/scenario/${scenario}`,
      { method: 'POST' },
    ),

  /** 退出演示模式，恢复自动状态循环 */
  clearScenario: () =>
    request<{ ok: boolean; message: string; sim_state: string }>('/api/simulation/scenario', {
      method: 'POST',
    }),
}
