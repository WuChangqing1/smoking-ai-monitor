/**
 * 综合监控首页 —— 评委打开网页首先看到、也是最重要的页面。
 *
 * 本页结构（自上而下）：
 *   1. 4 张核心状态卡片（在线设备 / 当前风险 / 今日预警 / 连续运行）
 *   2. 核心监控视频区（视觉中心）+ 右侧运行信息栏
 *   3. 雷视联动摘要 / 趋势图 / 设备状态
 *
 * 数据来源：全部由后端提供。轮次 3 接入 SimulationEngine 后补齐实时数值，
 * 当前对未就绪的接口显示明确占位，不使用假数据。
 */

import { useMemo } from 'react'
import Panel from '../components/Panel'
import StatCard from '../components/StatCard'
import MonitorVideo from '../components/MonitorVideo'
import { Badge, EmptyState, MetricList, MetricRow, SectionTitle } from '../components/Badge'
import {
  IconAlarm,
  IconChart,
  IconClock,
  IconDevice,
  IconPredict,
  IconRadar,
  IconVideo,
} from '../components/icons'
import type { PageId } from '../app/navigation'
import type { SystemStatus } from '../types'
import './OverviewPage.css'

interface OverviewPageProps {
  status: SystemStatus | null
  statusError: string | null
  onNavigate: (id: PageId) => void
}

/** 主监控点信息（与原系统一致：机位 2，Camera 01） */
const MAIN_POINT = {
  camera: 'Camera 01',
  point: '制丝线 2 号工位',
  position: 2,
  deviceId: 'RAD-02',
  deviceIp: '192.168.1.198',
  baseline: 0.72,
}

function formatUptime(hours: number | undefined): string {
  if (hours === undefined || hours === null) return '—'
  if (hours < 24) return hours.toFixed(1)
  const days = Math.floor(hours / 24)
  const rest = Math.round(hours - days * 24)
  return `${days * 24 + rest}`
}

export default function OverviewPage({ status, statusError, onNavigate }: OverviewPageProps) {
  const loading = status === null && statusError === null

  const riskTone = useMemo(() => {
    const state = status?.sim_state
    if (state === 'alarm') return 'critical' as const
    if (state === 'warning') return 'warning' as const
    if (state === 'stopped') return 'idle' as const
    return 'normal' as const
  }, [status?.sim_state])

  const riskText = status
    ? status.sim_state === 'stopped'
      ? '已停止'
      : status.sim_state === 'alarm'
        ? '异常'
        : status.sim_state === 'warning'
          ? '预警'
          : status.sim_state === 'attention'
            ? '关注'
            : '低风险'
    : '—'

  return (
    <div className="overview">
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
          value={riskText}
          tone={riskTone}
          icon={<IconRadar size={15} />}
          loading={loading}
          footnote={
            status
              ? `检测任务：${status.detection_running ? '运行中' : '已停止'} · ${status.sim_state_text}`
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
          footnote="含提示与预警级别，不含已归档"
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
          tone="primary"
          flush
          title="核心监控画面"
          icon={<IconVideo size={14} />}
          description={`${MAIN_POINT.camera} · 监控点：${MAIN_POINT.point}`}
          extra={
            <>
              <Badge tone="normal" dot>
                在线
              </Badge>
              <Badge tone={status?.detection_running === false ? 'idle' : 'primary'} dot>
                {status?.detection_running === false ? 'AI 已停止' : 'AI 检测中'}
              </Badge>
            </>
          }
        >
          <div className="overview__video-wrap">
            <MonitorVideo
              cameraLabel={MAIN_POINT.camera}
              timestamp={new Date().toLocaleString('zh-CN', { hour12: false })}
              hasStream
            />
          </div>

          {/* 画面下方信息条：只放关键字段，不堆砌 */}
          <div className="overview__video-meta">
            <div className="overview__meta-item">
              <span className="overview__meta-label">监控点</span>
              <span className="overview__meta-value">{MAIN_POINT.point}</span>
            </div>
            <div className="overview__meta-item">
              <span className="overview__meta-label">设备编号</span>
              <span className="overview__meta-value">{MAIN_POINT.deviceId}</span>
            </div>
            <div className="overview__meta-item">
              <span className="overview__meta-label">设备 IP</span>
              <span className="overview__meta-value mono">{MAIN_POINT.deviceIp}</span>
            </div>
            <div className="overview__meta-item">
              <span className="overview__meta-label">基准距离</span>
              <span className="overview__meta-value mono">{MAIN_POINT.baseline.toFixed(2)} m</span>
            </div>
            <div className="overview__meta-item">
              <span className="overview__meta-label">判断方式</span>
              <span className="overview__meta-value">雷达 + 视觉联合判断</span>
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
                    value={
                      <span className={`overview__status-value is-${item.state}`}>{item.text}</span>
                    }
                    hint={item.detail}
                  />
                ))}
              </MetricList>
            ) : (
              <EmptyState
                tone={statusError ? 'critical' : 'idle'}
                title={statusError ? '后端服务未连接' : '正在获取系统状态'}
                description={
                  statusError ??
                  '系统运行状态由后端 /api/system/status 提供，启动后端后自动刷新。'
                }
              />
            )}
          </Panel>

          <Panel
            title="智能预警"
            icon={<IconPredict size={14} />}
            extra={
              <button type="button" className="overview__link" onClick={() => onNavigate('prediction')}>
                查看详情
              </button>
            }
          >
            <EmptyState
              title="未来 30 分钟风险预测"
              description="预测结果由后端结合雷达趋势、视觉覆盖率与历史事件相似度计算，接入后在此展示。"
            />
          </Panel>
        </div>
      </div>

      {/* ================= 第三部分：雷视联动摘要与趋势 ================= */}
      <div className="grid grid--2 overview__lower">
        <Panel
          title="雷视联动判断"
          icon={<IconRadar size={14} />}
          extra={
            <button type="button" className="overview__link" onClick={() => onNavigate('fusion')}>
              进入雷视联动
            </button>
          }
        >
          <EmptyState
            title="雷达 + 视觉联合判断"
            description="传感器负责高频快速感知，视觉负责复杂语义判断，AI 完成融合决策。接入实时数据后在此展示联合判断结果与依据。"
          />
        </Panel>

        <Panel title="实时趋势" icon={<IconChart size={14} />} description="雷达距离与堆积风险，滚动保留最近 120 点">
          <SectionTitle extra="最近 120 秒">趋势图占位</SectionTitle>
          <EmptyState
            title="等待实时数据"
            description="雷达距离趋势与堆积风险趋势将在后端仿真引擎接入后自动绘制。"
          />
        </Panel>
      </div>
    </div>
  )
}
