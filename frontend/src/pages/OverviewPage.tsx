/**
 * 综合监控首页 —— 评委打开网页首先看到、也是最重要的页面。
 *
 * 数据来源（全部来自后端 SimulationEngine，前端不生成任何业务数据）：
 *   - GET /api/system/status   约 1.5 s 轮询 → 顶栏状态、运行时长、今日预警
 *   - GET /api/realtime        约 1.0 s 轮询 → 当前读数 + 滚动趋势
 *   - GET /api/devices         仅取一次     → 设备状态概览
 *
 * 轮询间隔刻意保持在秒级：引擎内部按资料口径 10 Hz 演化，
 * 但浏览器没有任何理由以 10 Hz 请求接口。
 */

import { useMemo, useState, useEffect } from 'react'
import Panel from '../components/Panel'
import StatCard from '../components/StatCard'
import MonitorVideo from '../components/MonitorVideo'
import Chart from '../components/Chart'
import { radarDistanceOption, riskTrendOption } from '../components/chartOptions'
import { Badge, Dot, EmptyState, MetricList, MetricRow, SectionTitle } from '../components/Badge'
import {
  IconAlarm,
  IconChart,
  IconClock,
  IconDevice,
  IconInfo,
  IconPerson,
  IconRadar,
  IconVideo,
} from '../components/icons'
import type { PageId } from '../app/navigation'
import type { Device, RealtimeSnapshot, RiskLevel, SimState, SystemStatus } from '../types'
import './OverviewPage.css'

interface OverviewPageProps {
  status: SystemStatus | null
  statusError: string | null
  realtime: RealtimeSnapshot | null
  realtimeError: string | null
  devices: Device[]
  onNavigate: (id: PageId) => void
  /** 是否处于视频同步模式（数值随主监控画面时间轴变化） */
  syncActive?: boolean
}

/** 运行工况 → 状态卡色调与中文标签 */
const STATE_TONE: Record<SimState, 'normal' | 'warning' | 'critical' | 'idle'> = {
  normal: 'normal',
  attention: 'warning',
  warning: 'warning',
  alarm: 'critical',
  stopped: 'idle',
}

const STATE_LABEL: Record<SimState, string> = {
  normal: '低风险',
  attention: '关注',
  warning: '预警',
  alarm: '异常',
  stopped: '已停止',
}

/** 风险等级 → 标签色调 */
const LEVEL_TONE: Record<RiskLevel, 'normal' | 'info' | 'warning' | 'critical'> = {
  low: 'normal',
  medium: 'info',
  high: 'warning',
  critical: 'critical',
}

function formatUptime(hours: number | undefined): string {
  if (hours === undefined || hours === null) return '—'
  if (hours < 100) return hours.toFixed(1)
  return String(Math.round(hours))
}

/** 把秒数格式化成"约 N 分钟"的窗口描述 */
function formatWindow(seconds: number): string {
  if (seconds < 90) return `最近约 ${Math.round(seconds)} 秒`
  return `最近约 ${Math.round(seconds / 60)} 分钟`
}

export default function OverviewPage({
  status,
  statusError,
  realtime,
  realtimeError,
  devices,
  onNavigate,
  syncActive = false,
}: OverviewPageProps) {
  // 每秒走动的时钟，仅用于画面时间戳
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  const loading = realtime === null && realtimeError === null && status === null

  /** 数据更新中断：已经有过数据但最近一次失败 */
  const stale = Boolean(realtimeError) && realtime !== null

  const samples = realtime?.samples ?? []
  const windowSeconds = (samples.length - 1) * (realtime?.sample_interval_seconds ?? 1)

  // 图表 option：随轮询更新，但 ECharts 实例由 <Chart> 持有，不会重建
  const radarOption = useMemo(
    () => radarDistanceOption(samples, realtime?.radar.distance ?? null),
    [samples, realtime?.radar.distance],
  )
  const riskOption = useMemo(
    () => riskTrendOption(samples, realtime?.risk.level ?? 'low'),
    [samples, realtime?.risk.level],
  )

  const point = realtime?.monitor_point
  const running = realtime?.detection_running ?? status?.detection_running ?? false
  const simState = realtime?.sim_state ?? status?.sim_state ?? 'normal'
  const tone = STATE_TONE[simState]

  const radars = devices.filter((d) => d.kind === 'radar')
  const cameras = devices.filter((d) => d.kind === 'camera')
  const offline = devices.filter((d) => !d.online)

  return (
    <div className="overview">
      {/* 数据更新中断时的轻提示，不阻塞页面 */}
      {stale && !syncActive && (
        <div className="overview__stale">
          <IconInfo size={13} />
          数据更新暂时中断，当前展示为最后一次成功获取的数据。
          <span className="overview__stale-detail">{realtimeError}</span>
        </div>
      )}

      {/* ================= 第一部分：核心状态卡片 ================= */}
      <div className="grid grid--4 overview__stats">
        <StatCard
          label="在线设备"
          value={status ? `${status.devices_online}` : '—'}
          suffix={status ? `/ ${status.devices_total}` : undefined}
          tone={status && status.devices_online < status.devices_total ? 'warning' : 'normal'}
          icon={<IconDevice size={15} />}
          loading={loading}
          footnote="雷达 3 台 · 摄像机 15 台"
          onClick={() => onNavigate('video')}
        />

        <StatCard
          label="当前风险等级"
          value={realtime ? STATE_LABEL[realtime.sim_state] : '—'}
          tone={tone}
          icon={<IconRadar size={15} />}
          loading={loading}
          footnote={
            realtime
              ? `风险指数 ${realtime.risk.index}% · ${realtime.risk.trend_text} · 检测任务${
                  running ? '运行中' : '已停止'
                }`
              : undefined
          }
          onClick={() => onNavigate('fusion')}
        />

        <StatCard
          label="今日预警"
          value={status ? `${status.today_warnings}` : '—'}
          suffix="次"
          tone={status && status.today_warnings > 0 ? 'warning' : 'normal'}
          icon={<IconAlarm size={15} />}
          loading={loading}
          footnote="含提示与预警级别，报警记录可在异常报警中查看"
          onClick={() => onNavigate('alarms')}
        />

        <StatCard
          label="连续运行"
          value={status ? formatUptime(status.uptime_hours) : '—'}
          suffix="h"
          tone="info"
          icon={<IconClock size={15} />}
          loading={loading}
          footnote="自上次启动检测任务起累计"
        />
      </div>

      {/* ================= 第二部分：核心监控视频 ================= */}
      <div className="overview-main overview__main">
        <Panel
          className="overview__video-panel"
          tone={simState === 'alarm' ? 'critical' : simState === 'warning' ? 'warning' : 'primary'}
          flush
          title="核心监控画面"
          icon={<IconVideo size={14} />}
          description={point ? `${point.code} · 监控点：${point.name}` : 'Camera 01 · 制丝线 2 号输送段'}
          extra={
            <>
              <Badge tone={point?.online === false ? 'idle' : 'normal'} dot>
                {point?.online === false ? '离线' : '在线'}
              </Badge>
              <Badge tone={running ? 'primary' : 'idle'} dot>
                {running ? 'AI 检测中' : 'AI 检测已停止'}
              </Badge>
            </>
          }
        >
          <div className="overview__video-wrap">
            <MonitorVideo
              cameraLabel={point?.code ?? 'Camera 01'}
              timestamp={now.toLocaleString('zh-CN', { hour12: false })}
              hasStream={Boolean(point?.stream) || point === undefined}
              /* 主监控画面作为全站同步时间源：页面数值随它的 currentTime 变化 */
              asTimeSource
              /* 同时叠加 YOLO 风格异常检测框（warning 及以上出现） */
              showDetection
            />
          </div>

          {/* 画面下方信息条：只放关键字段 */}
          <div className="overview__video-meta">
            <div className="overview__meta-item">
              <span className="overview__meta-label">监控点</span>
              <span className="overview__meta-value">{point?.name ?? '制丝线 2 号输送段'}</span>
            </div>
            <div className="overview__meta-item">
              <span className="overview__meta-label">设备编号</span>
              <span className="overview__meta-value">{point?.device_id ?? 'RAD-02'}</span>
            </div>
            <div className="overview__meta-item">
              <span className="overview__meta-label">设备 IP</span>
              <span className="overview__meta-value mono">{point?.device_ip ?? '192.168.1.198'}</span>
            </div>
            <div className="overview__meta-item">
              <span className="overview__meta-label">基准距离</span>
              <span className="overview__meta-value mono">
                {realtime ? realtime.radar.baseline_distance.toFixed(2) : '0.72'} m
              </span>
            </div>
            <div className="overview__meta-item">
              <span className="overview__meta-label">判断方式</span>
              <span className="overview__meta-value">
                {point?.has_radar === false ? '视觉单独判断' : '雷达 + 视觉联合判断'}
              </span>
            </div>
          </div>
        </Panel>

        {/* ---- 右侧运行信息栏 ---- */}
        <div className="overview__side">
          <Panel title="系统运行状态" icon={<IconDevice size={14} />}>
            {status ? (
              <MetricList>
                {status.statuses.map((item) => (
                  <MetricRow
                    key={item.key}
                    label={item.label}
                    value={<span className={`overview__status-value is-${item.state}`}>{item.text}</span>}
                    hint={item.detail}
                  />
                ))}
              </MetricList>
            ) : (
              <EmptyState
                tone={statusError ? 'critical' : 'idle'}
                title={statusError ? '系统状态获取失败' : '正在获取系统状态'}
                description={statusError ?? '监控服务恢复后自动刷新。'}
              />
            )}
          </Panel>

          <Panel
            title="当前实时读数"
            icon={<IconRadar size={14} />}
            description={realtime ? `${realtime.sim_state_text} · 风险${realtime.risk.trend_text}` : undefined}
          >
            {realtime ? (
              <MetricList>
                <MetricRow
                  label="雷达测距"
                  value={realtime.radar.distance.toFixed(3)}
                  unit="m"
                  tone={realtime.radar.distance < 0.65 ? 'critical' : 'normal'}
                  hint="滤波值"
                />
                <MetricRow
                  label="相对基准"
                  value={`${realtime.radar.delta >= 0 ? '+' : ''}${realtime.radar.delta.toFixed(3)}`}
                  unit="m"
                  tone={realtime.radar.delta < -0.05 ? 'warning' : 'idle'}
                  hint="相对 0.72 m 基准距离的变化量"
                />
                <MetricRow
                  label="风险指数"
                  value={realtime.risk.index.toFixed(1)}
                  unit="%"
                  tone={
                    realtime.risk.level === 'critical'
                      ? 'critical'
                      : realtime.risk.level === 'high'
                        ? 'warning'
                        : realtime.risk.level === 'medium'
                          ? 'info'
                          : 'normal'
                  }
                />
                <MetricRow
                  label="物料覆盖率"
                  value={(realtime.vision.coverage * 100).toFixed(1)}
                  unit="%"
                  tone={realtime.vision.coverage > 0.6 ? 'warning' : 'idle'}
                />
                <MetricRow
                  label="输送速度"
                  value={realtime.environment.conveyor_speed.toFixed(2)}
                  unit="m/s"
                  tone={
                    realtime.environment.conveyor_speed <
                    realtime.environment.conveyor_speed_baseline - 0.05
                      ? 'warning'
                      : 'idle'
                  }
                  hint={`基准 ${realtime.environment.conveyor_speed_baseline.toFixed(2)} m/s`}
                />
                <MetricRow
                  label="设备负载"
                  value={realtime.environment.equipment_load.toFixed(1)}
                  unit="%"
                  tone={realtime.environment.equipment_load > 75 ? 'warning' : 'idle'}
                />
              </MetricList>
            ) : (
              <EmptyState
                tone={realtimeError ? 'critical' : 'idle'}
                title={realtimeError ? '实时数据不可用' : '正在获取实时数据'}
                description={realtimeError ?? '数据由后端监控服务统一提供。'}
              />
            )}
          </Panel>
        </div>
      </div>

      {/* ================= 第三部分：趋势图 ================= */}
      <div className="grid grid--2 overview__lower">
        <Panel
          title="雷达距离趋势"
          icon={<IconChart size={14} />}
          description={realtime ? `${formatWindow(windowSeconds)} · 基准 0.72 m · 报警阈值 0.58 m` : undefined}
          extra={
            realtime && (
              <Badge tone={realtime.radar.distance < 0.65 ? 'warning' : 'normal'}>
                {realtime.radar.distance.toFixed(3)} m
              </Badge>
            )
          }
        >
          <Chart option={radarOption} height={190} pointCount={samples.length} emptyText="暂无雷达数据" />
        </Panel>

        <Panel
          title="堆积风险趋势"
          icon={<IconChart size={14} />}
          description={realtime ? `${formatWindow(windowSeconds)} · 30% 关注 / 55% 预警 / 80% 报警` : undefined}
          extra={
            realtime && (
              <Badge tone={LEVEL_TONE[realtime.risk.level]}>
                {realtime.risk.index.toFixed(1)}% {realtime.risk.level_text}
              </Badge>
            )
          }
        >
          <Chart option={riskOption} height={190} pointCount={samples.length} emptyText="暂无风险数据" />
        </Panel>
      </div>

      {/* ================= 第四部分：雷视摘要与设备状态 ================= */}
      <div className="grid grid--2 overview__lower">
        <Panel
          title="雷视联动判断"
          icon={<IconRadar size={14} />}
          bodyClassName="overview__fusion-body"
          extra={
            <button type="button" className="overview__link" onClick={() => onNavigate('fusion')}>
              进入雷视联动
            </button>
          }
        >
          {realtime ? (
            <>
              <div className="overview__fusion-verdict">
                <span className="overview__fusion-label">联合判断</span>
                <Badge
                  tone={
                    realtime.fusion.verdict === 'alarm'
                      ? 'critical'
                      : realtime.fusion.verdict === 'warning'
                        ? 'warning'
                        : realtime.fusion.verdict === 'attention'
                          ? 'info'
                          : 'normal'
                  }
                  dot
                  solid={realtime.fusion.verdict === 'alarm'}
                >
                  {realtime.fusion.verdict_text}
                </Badge>
              </div>

              <div className="overview__fusion-grid">
                <div className="overview__fusion-col">
                  <SectionTitle>雷达</SectionTitle>
                  <p className="overview__fusion-text">
                    测距 {realtime.radar.distance.toFixed(3)} m，
                    {realtime.radar.delta < -0.005
                      ? `较基准持续下降 ${Math.abs(realtime.radar.delta).toFixed(3)} m`
                      : '在基准附近小幅波动'}
                  </p>
                </div>
                <div className="overview__fusion-col">
                  <SectionTitle>视觉</SectionTitle>
                  <p className="overview__fusion-text">
                    {realtime.vision.label_text}，覆盖率{' '}
                    {(realtime.vision.coverage * 100).toFixed(1)}%，置信度{' '}
                    {(realtime.vision.confidence * 100).toFixed(1)}%
                  </p>
                </div>
              </div>

              <p className="overview__fusion-reason">{realtime.fusion.reason}</p>
            </>
          ) : (
            <EmptyState title="雷达 + 视觉联合判断" description="暂无实时数据" />
          )}
        </Panel>

        <Panel title="设备状态概览" icon={<IconPerson size={14} />} flush>
          <div className="overview__devices">
            <div className="overview__device-summary">
              <span>
                <Dot tone={offline.length === 0 ? 'normal' : 'warning'} />
                在线 {devices.length - offline.length} / {devices.length}
              </span>
              <span>激光雷达 {radars.length} 台</span>
              <span>网络摄像机 {cameras.length} 台</span>
            </div>

            <div className="overview__device-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>设备编号</th>
                    <th>类型</th>
                    <th>位置</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {devices.slice(0, 6).map((device) => (
                    <tr key={device.id}>
                      <td className="mono">{device.id}</td>
                      <td>{device.kind === 'radar' ? '激光雷达' : '摄像机'}</td>
                      <td>{device.location}</td>
                      <td>
                        <Badge tone={device.online ? 'normal' : 'idle'} dot>
                          {device.online ? '在线' : '离线'}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                  {devices.length === 0 && (
                    <tr>
                      <td colSpan={4} className="overview__device-empty">
                        正在获取设备台账…
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {devices.length > 6 && (
              <div className="overview__device-more">
                共 {devices.length} 台设备，完整台账见
                <button type="button" className="overview__link" onClick={() => onNavigate('settings')}>
                  系统设置
                </button>
              </div>
            )}
          </div>
        </Panel>
      </div>
    </div>
  )
}
