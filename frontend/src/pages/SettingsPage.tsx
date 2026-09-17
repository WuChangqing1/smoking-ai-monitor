/**
 * 系统设置页。
 *
 * 关键约束（任务要求第二十节）：
 *   启停控制**只控制检测任务**，不控制真实生产设备。
 *   停止后仿真数据与风险变化暂停，AI 状态显示「已停止」；
 *   视频仍可作为监控画面继续播放。
 *
 * 本轮次后端启停接口尚未实现，按钮会在接口不可用时给出明确提示而不是静默失败。
 */

import { useState } from 'react'
import Panel from '../components/Panel'
import { Badge, MetricList, MetricRow, SectionTitle } from '../components/Badge'
import { IconDevice, IconInfo, IconPlay, IconReset, IconSettings, IconStop } from '../components/icons'
import { api } from '../api/client'
import type { PlatformMeta, SystemStatus } from '../types'
import './SettingsPage.css'

interface SettingsPageProps {
  status: SystemStatus | null
  meta: PlatformMeta | null
  onChanged: () => void
  offline: boolean
}

type ActionKey = 'start' | 'stop' | 'reset'

interface Feedback {
  tone: 'ok' | 'error'
  text: string
}

export default function SettingsPage({ status, meta, onChanged, offline }: SettingsPageProps) {
  const [busy, setBusy] = useState<ActionKey | null>(null)
  const [feedback, setFeedback] = useState<Feedback | null>(null)

  const running = status?.detection_running ?? false
  /** 后端启停接口尚未实现的标记：接口返回 404/405 时提示进入下一轮次 */
  const notImplemented = '启停接口将在后端仿真引擎接入后生效（轮次 4）'

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
              {busy === 'reset' ? '正在重置…' : '重置模拟'}
            </button>
          </div>

          <div className="settings__state">
            <Badge tone={running ? 'normal' : 'idle'} dot>
              AI 分析：{running ? '运行中' : '已停止'}
            </Badge>
            <Badge tone="info">仿真状态：{status?.sim_state_text ?? '—'}</Badge>
          </div>

          {feedback && (
            <p className={`settings__feedback settings__feedback--${feedback.tone}`}>
              <IconInfo size={13} />
              {feedback.text}
            </p>
          )}

          <ul className="settings__rules">
            <li>
              <strong>停止检测</strong>：仿真数据暂停推进、风险变化暂停，AI 状态显示「已停止」；
              视频仍可作为监控画面继续播放。
            </li>
            <li>
              <strong>重置模拟</strong>：仿真状态回到初始正常态，历史缓冲清空并重新预热，
              用于演示前复位。
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
                label="运行模式"
                value={meta.mode === 'simulation' ? '仿真演示' : '实时接入'}
                tone={meta.mode === 'simulation' ? 'warning' : 'normal'}
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

      {/* ---- 设备台账 ---- */}
      <Panel
        title="设备台账"
        icon={<IconDevice size={14} />}
        description="硬件参数取自项目验收报告，仿真数据按同一口径产生"
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

      {/* ---- 技术路线与规划能力 ---- */}
      <Panel title="系统能力与技术路线" icon={<IconInfo size={14} />}>
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
            <p className="settings__cap-title">异常报警与推送</p>
            <p className="settings__cap-desc">
              报警内容含设备名称、设备 IP、报警时间与距离信息，原系统经钉钉机器人通知相关人员。
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

        <SectionTitle>规划能力</SectionTitle>
        <div className="settings__caps">
          <div className="settings__cap settings__cap--planned">
            <Badge tone="info">规划中</Badge>
            <p className="settings__cap-title">杂质检测与自动分拣</p>
            <p className="settings__cap-desc">
              待摄像头精度与算力提升后，由视觉模型识别杂质并定位，联动机械臂 / 分拣设备转移至人工复核线。
              当前为规划能力，平台不将其标注为已部署。
            </p>
          </div>
          <div className="settings__cap settings__cap--planned">
            <Badge tone="info">规划中</Badge>
            <p className="settings__cap-title">时序预测模型升级</p>
            <p className="settings__cap-desc">
              引入 LSTM 时序异常预测与多目标跟踪、场景理解算法，进一步提升提前预警的准确率。
            </p>
          </div>
          <div className="settings__cap settings__cap--planned">
            <Badge tone="info">推广方向</Badge>
            <p className="settings__cap-title">跨行业推广</p>
            <p className="settings__cap-desc">
              视觉 + 雷达融合方案可推广至食品加工、医药生产、化工原料处理等连续物料生产线。
            </p>
          </div>
        </div>
      </Panel>
    </div>
  )
}
