/**
 * 系统设置页。
 *
 * 关键约束（任务要求第二十节）：
 *   启停控制**只控制检测任务**，不控制真实生产设备。
 *   停止后数据采集与风险变化暂停，AI 状态显示「已停止」；
 *   视频仍可作为监控画面继续播放。
 *
 * 本轮次后端启停接口尚未实现，按钮会在接口不可用时给出明确提示而不是静默失败。
 */

import { useState } from 'react'
import Panel from '../components/Panel'
import { Badge, MetricList, MetricRow, SectionTitle } from '../components/Badge'
import { IconDevice, IconInfo, IconPlay, IconReset, IconSettings, IconStop } from '../components/icons'
import { api } from '../api/client'
import type { RunMode } from '../video/VideoSyncContext'
import type { PlatformMeta, SystemStatus } from '../types'
import './SettingsPage.css'

interface SettingsPageProps {
  status: SystemStatus | null
  meta: PlatformMeta | null
  onChanged: () => void
  offline: boolean
  /** 当前运行模式 */
  runMode: RunMode
  onRunModeChange: (mode: RunMode) => void
}

type ActionKey = 'start' | 'stop' | 'reset' | 'scenario' | 'clear-scenario'

interface Feedback {
  tone: 'ok' | 'error'
  text: string
}

/** 运行工况：与后端 POST /api/simulation/scenario/{scenario} 对应 */
const SCENARIOS = [
  { value: 'normal', label: '正常', tone: 'normal', desc: '距离贴近基准，风险低' },
  { value: 'attention', label: '关注', tone: 'info', desc: '物料开始堆积，出现轻微趋势' },
  { value: 'warning', label: '预警', tone: 'warning', desc: '风险明显升高，进入提前预警' },
  { value: 'alarm', label: '异常', tone: 'critical', desc: '达到报警条件，生成报警记录' },
] as const

export default function SettingsPage({
  status,
  meta,
  onChanged,
  offline,
  runMode,
  onRunModeChange,
}: SettingsPageProps) {
  const [busy, setBusy] = useState<ActionKey | null>(null)
  const [feedback, setFeedback] = useState<Feedback | null>(null)

  const running = status?.detection_running ?? false
  /** 接口缺失时的兜底提示（正常情况下后端已实现，仅用于版本不匹配的场景） */
  const notImplemented = '后端未提供该控制接口，请确认后端版本与前端一致。'

  async function run(key: ActionKey) {
    setBusy(key)
    setFeedback(null)
    try {
      const result =
        key === 'start'
          ? await api.detectionStart()
          : key === 'stop'
            ? await api.detectionStop()
            : await api.simulationReset()

      setFeedback({ tone: 'ok', text: result.message || '操作已下发' })
      onChanged()
    } catch (err) {
      const message = err instanceof Error ? err.message : '操作失败'
      const isMissing = /返回 (404|405)/.test(message)
      setFeedback({ tone: 'error', text: isMissing ? notImplemented : message })
    } finally {
      setBusy(null)
    }
  }

  async function applyScenario(scenario: (typeof SCENARIOS)[number]['value']) {
    setBusy('scenario')
    setFeedback(null)
    try {
      const result = await api.setScenario(scenario)
      setFeedback({ tone: 'ok', text: result.message })
      onChanged()
    } catch (err) {
      setFeedback({ tone: 'error', text: err instanceof Error ? err.message : '切换失败' })
    } finally {
      setBusy(null)
    }
  }

  async function clearScenario() {
    setBusy('clear-scenario')
    setFeedback(null)
    try {
      const result = await api.clearScenario()
      setFeedback({ tone: 'ok', text: result.message })
      onChanged()
    } catch (err) {
      setFeedback({ tone: 'error', text: err instanceof Error ? err.message : '恢复失败' })
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="settings">
      <div className="settings__layout">
        {/* ---- 检测任务启停 ---- */}
        <Panel
          title="检测任务控制"
          icon={<IconSettings size={14} />}
          description="仅控制检测任务，不控制真实生产设备"
          tone={running ? 'primary' : 'default'}
        >
          <div className="settings__actions">
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => void run('start')}
              disabled={busy !== null || running}
            >
              <IconPlay size={14} />
              {busy === 'start' ? '正在启动…' : '开始检测'}
            </button>

            <button
              type="button"
              className="btn btn--warning"
              onClick={() => void run('stop')}
              disabled={busy !== null || !running}
            >
              <IconStop size={14} />
              {busy === 'stop' ? '正在停止…' : '停止检测'}
            </button>

            <button
              type="button"
              className="btn"
              onClick={() => void run('reset')}
              disabled={busy !== null}
            >
              <IconReset size={14} />
              {busy === 'reset' ? '正在复位…' : '复位运行状态'}
            </button>
          </div>

          <div className="settings__state">
            <Badge tone={running ? 'normal' : 'idle'} dot>
              AI 分析：{running ? '运行中' : '已停止'}
            </Badge>
            <Badge tone="info">当前工况：{status?.sim_state_text ?? '—'}</Badge>
          </div>

          {feedback && (
            <p className={`settings__feedback settings__feedback--${feedback.tone}`}>
              <IconInfo size={13} />
              {feedback.text}
            </p>
          )}

          <ul className="settings__rules">
            <li>
              <strong>停止检测</strong>：数据采集与风险计算暂停，AI 状态显示「已停止」；
              视频仍可作为监控画面继续播放。
            </li>
            <li>
              <strong>复位运行状态</strong>：工况回到正常态并重新预热数据窗口，
              用于检修或交接班前的状态复位。
            </li>
            <li>
              页面按钮<strong>不会</strong>、也<strong>不应该</strong>被理解为可以关闭真实生产设备。
            </li>
          </ul>
        </Panel>

        {/* ---- 平台信息 ---- */}
        <Panel title="平台信息" icon={<IconInfo size={14} />}>
          {meta ? (
            <MetricList>
              <MetricRow label="平台名称" value={meta.platform_name} />
              <MetricRow label="原项目名称" value={meta.project_name} />
              <MetricRow
                label="工况来源"
                value={meta.mode === 'simulation' ? '人工设定' : '设备实时采集'}
                tone={meta.mode === 'simulation' ? 'info' : 'normal'}
              />
              <MetricRow label="监控点位" value={meta.monitor_points} unit="个" />
              <MetricRow label="在线设备" value={`${meta.devices.total}`} unit="台" />
              <MetricRow label="采集频率" value={meta.data_rate_hz} unit="Hz" />
            </MetricList>
          ) : (
            <p className="settings__muted">
              {offline ? '后端未连接，无法获取平台信息。' : '正在获取平台信息…'}
            </p>
          )}
        </Panel>
      </div>

      {/* ---- 运行模式 ---- */}
      <Panel
        title="运行模式"
        icon={<IconSettings size={14} />}
        description="平台支持两种运行方式，现场展示默认使用画面同步"
      >
        <div className="settings__modes">
          <button
            type="button"
            className={`settings__mode${runMode === 'video_sync' ? ' is-active' : ''}`}
            onClick={() => onRunModeChange('video_sync')}
          >
            <span className="settings__mode-head">
              <span className="settings__mode-name">画面同步</span>
              <Badge tone={runMode === 'video_sync' ? 'primary' : 'idle'}>
                {runMode === 'video_sync' ? '当前使用' : '可切换'}
              </Badge>
            </span>
            <span className="settings__mode-desc">
              监控画面与各项数值严格同步：画面中物料逐渐堆积时，雷达测距、物料覆盖率、
              风险指数与联合判断同步变化。
            </span>
          </button>

          <button
            type="button"
            className={`settings__mode${runMode === 'automatic' ? ' is-active' : ''}`}
            onClick={() => onRunModeChange('automatic')}
          >
            <span className="settings__mode-head">
              <span className="settings__mode-name">自动工况循环</span>
              <Badge tone={runMode === 'automatic' ? 'primary' : 'idle'}>
                {runMode === 'automatic' ? '当前使用' : '可切换'}
              </Badge>
            </span>
            <span className="settings__mode-desc">
              由平台按工业逻辑持续演化工况并自动生成预警与报警记录，
              用于系统逻辑验证、阈值调试与功能检查。切换到此模式后，
              页面数值不再跟随画面，而由平台工况循环决定。
            </span>
          </button>
        </div>
      </Panel>

      {/* ---- 工况设定（现场联调 / 应急演练时手动指定工况） ---- */}
      <Panel
        title="工况设定"
        icon={<IconSettings size={14} />}
        description="手动指定当前运行工况，用于现场联调、阈值校验与应急演练"
      >
        <div className="settings__demo">
          <p className="settings__demo-hint">
            系统默认按自动工况循环运行，<strong>大部分时间保持正常</strong>，报警不频繁。
            联调或演练需要复现特定工况时，可在此手动指定；点击「恢复自动工况」退出。
          </p>

          <div className="settings__scenarios">
            {SCENARIOS.map((item) => (
              <button
                key={item.value}
                type="button"
                className={`settings__scenario is-${item.tone}`}
                onClick={() => void applyScenario(item.value)}
                disabled={busy !== null}
              >
                <span className="settings__scenario-label">{item.label}</span>
                <span className="settings__scenario-desc">{item.desc}</span>
              </button>
            ))}
          </div>

          <div className="settings__demo-foot">
            <button
              type="button"
              className="btn"
              onClick={() => void clearScenario()}
              disabled={busy !== null}
            >
              <IconReset size={14} />
              {busy === 'clear-scenario' ? '正在恢复…' : '恢复自动工况'}
            </button>
            <span className="settings__demo-state">
              当前工况：<strong>{status?.sim_state_text ?? '—'}</strong>
            </span>
          </div>
        </div>
      </Panel>

      {/* ---- 设备台账 ---- */}
      <Panel
        title="设备台账"
        icon={<IconDevice size={14} />}
        description="硬件参数取自项目验收报告，平台数据按同一口径产生"
        flush
      >
        <div className="settings__table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>类别</th>
                <th>品牌 / 型号</th>
                <th>数量</th>
                <th>关键参数</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>激光雷达</td>
                <td>重邮自研（重庆邮电大学）</td>
                <td className="mono">3 台</td>
                <td>测距 0.1–40 m · 精度 ±5 cm · 刷新率最高 1000 Hz · IP65</td>
              </tr>
              <tr>
                <td>网络摄像机</td>
                <td>海康威视 DS-2CD2242CX8-L</td>
                <td className="mono">15 台</td>
                <td>400 万像素 · H.265 · IP67 · 25 fps · 最低照度 0.01 Lux</td>
              </tr>
              <tr>
                <td>硬盘录像机</td>
                <td>海康威视 DS-8616NI-K8-V2</td>
                <td className="mono">1 台</td>
                <td>7×8 TB · 16 路接入 · 160 Mbps · 8×SATA</td>
              </tr>
              <tr>
                <td>显示器</td>
                <td>海康威视 DS-D5242FI-1V2</td>
                <td className="mono">1 台</td>
                <td>42″ · 1920×1080 · 500 cd/m² · 对比度 4000:1</td>
              </tr>
              <tr>
                <td>PoE 交换机</td>
                <td>海康威视 DS-3E0508SP-S</td>
                <td className="mono">3 台</td>
                <td>8 口百兆 PoE · 单口 30 W · 总功率 58 W · 802.3af/at</td>
              </tr>
              <tr>
                <td>汇聚交换机</td>
                <td>海康威视 DS-3E2728T-H(B)</td>
                <td className="mono">1 台</td>
                <td>28 口千兆管理型 · VLAN/QoS/环网 · 背板 56 Gbps</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>

      {/* ---- 系统能力 ---- */}
      <Panel title="系统能力" icon={<IconInfo size={14} />}>
        <SectionTitle>已部署能力</SectionTitle>
        <div className="settings__caps">
          <div className="settings__cap">
            <Badge tone="normal" dot>
              已部署
            </Badge>
            <p className="settings__cap-title">雷视联合判断</p>
            <p className="settings__cap-desc">
              同时配备雷达与摄像头的监控点做联合判断，仅配备其一的做单独判断。
            </p>
          </div>
          <div className="settings__cap">
            <Badge tone="normal" dot>
              已部署
            </Badge>
            <p className="settings__cap-title">异常报警</p>
            <p className="settings__cap-desc">
              报警内容含设备名称、设备 IP、报警时间与距离信息，并附视觉模型生成的异常证据图。
            </p>
          </div>
          <div className="settings__cap">
            <Badge tone="normal" dot>
              已部署
            </Badge>
            <p className="settings__cap-title">数据存储与溯源</p>
            <p className="settings__cap-desc">
              按时间段与设备名称检索报警记录，并可查看异常分析窗口与当时的图像数据。
            </p>
          </div>
        </div>
      </Panel>
    </div>
  )
}
