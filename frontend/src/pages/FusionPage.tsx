/**
 * 雷视联动页。
 *
 * 页面要回答的核心问题：视觉与雷达不是替代关系，而是互补。
 *   传感器（雷达）负责高频、稳定、快速的几何量测量；
 *   视觉负责复杂场景与形态语义理解；
 *   融合算法负责把两者结合，降低单一信息源的局限。
 *
 * 布局：左＝监控视频 / 中＝雷达分析 / 右＝视觉 AI + 联合判定 / 下＝时间趋势 + 技术解释。
 * 数据全部来自 GET /api/realtime（约 1 s 轮询），联合结论由后端计算，前端只呈现。
 */

import { useMemo } from 'react'
import Panel from '../components/Panel'
import MonitorVideo from '../components/MonitorVideo'
import Chart from '../components/Chart'
import { radarDistanceOption, riskTrendOption } from '../components/chartOptions'
import { Badge, EmptyState, MetricList, MetricRow, SectionTitle } from '../components/Badge'
import {
  IconChart,
  IconInfo,
  IconPerson,
  IconRadar,
  IconVideo,
} from '../components/icons'
import type { FusionVerdict, RealtimeSnapshot, RiskLevel } from '../types'
import './FusionPage.css'

interface FusionPageProps {
  realtime: RealtimeSnapshot | null
  realtimeError: string | null
}

/** 联合判断结果 → 展示色调 */
const VERDICT_TONE: Record<FusionVerdict, 'normal' | 'info' | 'warning' | 'critical'> = {
  normal: 'normal',
  attention: 'info',
  warning: 'warning',
  alarm: 'critical',
}

/** 风险等级 → 展示色调 */
const LEVEL_TONE: Record<RiskLevel, 'normal' | 'info' | 'warning' | 'critical'> = {
  low: 'normal',
  medium: 'info',
  high: 'warning',
  critical: 'critical',
}

export default function FusionPage({ realtime, realtimeError }: FusionPageProps) {
  const samples = realtime?.samples ?? []
  const windowSeconds = (samples.length - 1) * (realtime?.sample_interval_seconds ?? 1)

  const radarOption = useMemo(
    () => radarDistanceOption(samples, realtime?.radar.distance ?? null),
    [samples, realtime?.radar.distance],
  )
  const riskOption = useMemo(
    () => riskTrendOption(samples, realtime?.risk.level ?? 'low'),
    [samples, realtime?.risk.level],
  )

  if (!realtime) {
    return (
      <Panel title="雷视联动" icon={<IconRadar size={14} />}>
        <EmptyState
          tone={realtimeError ? 'critical' : 'idle'}
          title={realtimeError ? '实时数据不可用' : '正在获取实时数据'}
          description={
            realtimeError ??
            '雷达与视觉数据来自同一时刻的采样点，两路数据严格对齐。'
          }
        />
      </Panel>
    )
  }

  const { radar, vision, environment, risk, fusion, sim_state, detection_running } = realtime
  const verdictTone = VERDICT_TONE[fusion.verdict]
  const distanceLow = radar.distance < 0.65

  return (
    <div className="fusion">
      {/* ===================== 上部：视频 / 雷达 / 视觉 + 判定 ===================== */}
      <div className="fusion__top">
        {/* ---- 左：监控视频 ---- */}
        <Panel
          flush
          title="现场画面"
          icon={<IconVideo size={14} />}
          description={`${realtime.monitor_point.code} · ${realtime.monitor_point.name}`}
          extra={
            <Badge tone={detection_running ? 'primary' : 'idle'} dot>
              {detection_running ? 'AI 检测中' : '检测已停止'}
            </Badge>
          }
        >
          <div className="fusion__video">
            <MonitorVideo
              cameraLabel={realtime.monitor_point.code}
              timestamp={new Date().toLocaleString('zh-CN', { hour12: false })}
              hasStream={Boolean(realtime.monitor_point.stream)}
              /* 复用首页同一个异常检测框：位置/尺寸/标签/置信度完全一致 */
              showDetection
            />
          </div>
        </Panel>

        {/* ---- 中：雷达分析 ---- */}
        <Panel
          title="雷达分析"
          icon={<IconRadar size={14} />}
          description="激光雷达 · 高频几何量测量"
          tone={distanceLow ? 'warning' : 'default'}
          extra={
            <Badge tone={radar.online && radar.data_fresh ? 'normal' : 'idle'} dot>
              {radar.online ? (radar.data_fresh ? '在线' : '已停止刷新') : '离线'}
            </Badge>
          }
        >
          <div className="fusion__headline">
            <span className="fusion__headline-value">{radar.distance.toFixed(3)}</span>
            <span className="fusion__headline-unit">m</span>
            <span className="fusion__headline-label">当前测距（滤波值）</span>
          </div>

          <MetricList>
            <MetricRow
              label="测量值"
              value={radar.measured.toFixed(3)}
              unit="m"
              hint="雷达原始测量输出"
            />
            <MetricRow
              label="滤波值"
              value={radar.filtered.toFixed(3)}
              unit="m"
              hint="一阶低通滤波后输出，对应原系统界面上的滤波值"
            />
            <MetricRow label="基准距离" value={radar.baseline_distance.toFixed(3)} unit="m" />
            <MetricRow
              label="变化量"
              value={`${radar.delta >= 0 ? '+' : ''}${radar.delta.toFixed(3)}`}
              unit="m"
              tone={radar.delta < -0.05 ? 'warning' : radar.delta < -0.015 ? 'info' : 'normal'}
              hint="相对基准距离的变化量，负值表示料层升高"
            />
            <MetricRow
              label="变化趋势"
              value={risk.trend_text}
              tone={
                risk.trend === 'rising_fast'
                  ? 'critical'
                  : risk.trend === 'rising'
                    ? 'warning'
                    : 'idle'
              }
              hint="由风险指数近期变化率判定"
            />
            <MetricRow
              label="数据刷新"
              value={radar.refresh_text}
              tone={radar.data_fresh ? 'normal' : 'idle'}
              hint={radar.data_fresh ? '数据持续刷新中' : '检测任务已停止，数据不再推进'}
            />
          </MetricList>

          {/* 规格：明确区分"设备能力"与"系统采集频率" */}
          <div className="fusion__spec">
            <SectionTitle>传感器规格</SectionTitle>
            <dl className="fusion__spec-list">
              <div>
                <dt>测距范围</dt>
                <dd>0.1–40 m</dd>
              </div>
              <div>
                <dt>测距精度</dt>
                <dd>±5 cm</dd>
              </div>
              <div>
                <dt>设备最高刷新率</dt>
                <dd>1000 Hz</dd>
              </div>
              <div>
                <dt>本系统采集频率</dt>
                <dd className="fusion__spec-em">10 Hz</dd>
              </div>
            </dl>
            <p className="fusion__spec-note">
              <IconInfo size={12} />
              设备的最高刷新能力（1000 Hz）与本系统的实际采集频率（10 Hz）不是一回事：
              平台按 10 Hz 持续采集，已足够覆盖制丝线物料变化的节奏，也避免无谓的存储与算力开销。
            </p>
          </div>
        </Panel>

        {/* ---- 右：视觉 AI + 联合判定 ---- */}
        <div className="fusion__right">
          <Panel
            title="视觉 AI"
            icon={<IconPerson size={14} />}
            description="形态与语义判断"
            extra={
              <Badge tone={vision.online ? 'normal' : 'idle'} dot>
                {vision.online ? '在线' : '离线'}
              </Badge>
            }
          >
            <div className="fusion__vision-status">
              <span className="fusion__vision-label">{vision.label_text}</span>
              <Badge tone={vision.label === 'normal_conveying' ? 'normal' : 'warning'}>
                {vision.label}
              </Badge>
            </div>

            <MetricList>
              <MetricRow
                label="置信度"
                value={(vision.confidence * 100).toFixed(1)}
                unit="%"
                tone={vision.confidence < 0.9 ? 'warning' : 'normal'}
                hint="概率模型输出，不是准确率"
              />
              <MetricRow
                label="物料覆盖率"
                value={(vision.coverage * 100).toFixed(1)}
                unit="%"
                tone={vision.coverage > 0.6 ? 'warning' : 'idle'}
              />
              <MetricRow
                label="推理耗时"
                value={vision.latency_ms}
                unit="ms"
                hint="单帧推理耗时，视觉链路的固有延迟"
              />
              <MetricRow
                label="输送有效速度"
                value={environment.conveyor_speed.toFixed(2)}
                unit="m/s"
                tone={
                  environment.conveyor_speed < environment.conveyor_speed_baseline - 0.05
                    ? 'warning'
                    : 'idle'
                }
                hint={`基准 ${environment.conveyor_speed_baseline.toFixed(2)} m/s`}
              />
            </MetricList>

            <p className="fusion__probabilistic">
              <IconInfo size={12} />
              视觉结果属于概率模型输出，会受光照、遮挡与粉尘影响；
              它擅长判断"形态像不像堆积"，但单靠它不足以支撑报警决策。
            </p>
          </Panel>

          {/* 联合判定区：本页视觉重点 */}
          <Panel
            title="联合判定"
            icon={<IconRadar size={14} />}
            tone={verdictTone === 'critical' ? 'critical' : verdictTone === 'warning' ? 'warning' : 'primary'}
          >
            <div className="fusion__formula">
              <span className="fusion__formula-node">雷达</span>
              <span className="fusion__formula-op">+</span>
              <span className="fusion__formula-node">视觉</span>
              <span className="fusion__formula-arrow">↓</span>
              <span className={`fusion__formula-result is-${verdictTone}`}>
                {fusion.verdict_text}
              </span>
            </div>

            <ul className="fusion__basis">
              <li>
                <span className="fusion__basis-key">雷达</span>
                <span className="fusion__basis-val">
                  {radar.delta < -0.005
                    ? `距离持续下降，较基准 ${radar.delta.toFixed(3)} m`
                    : '距离在基准附近小幅波动'}
                </span>
              </li>
              <li>
                <span className="fusion__basis-key">视觉</span>
                <span className="fusion__basis-val">
                  {vision.label_text}，覆盖率 {(vision.coverage * 100).toFixed(1)}%
                </span>
              </li>
              <li>
                <span className="fusion__basis-key">联合判断</span>
                <span className="fusion__basis-val">
                  风险指数 {risk.index.toFixed(1)}%（{risk.level_text}），
                  {risk.trend_text}
                </span>
              </li>
            </ul>

            <p className="fusion__reason">{fusion.reason}</p>

            <div className="fusion__mode">
              <Badge tone="primary">
                {fusion.mode === 'fusion' ? '雷达 + 视觉 联合判断' : '视觉单独判断'}
              </Badge>
              <span className="fusion__mode-note">
                {sim_state === 'stopped'
                  ? '检测任务已停止，判断结果保持停止时的状态'
                  : `当前工况：${realtime.sim_state_text}`}
              </span>
            </div>
          </Panel>
        </div>
      </div>

      {/* ===================== 下部：时间趋势 ===================== */}
      <div className="grid grid--2">
        <Panel
          title="雷达距离趋势"
          icon={<IconChart size={14} />}
          description={`最近约 ${Math.max(1, Math.round(windowSeconds / 60))} 分钟 · 基准 0.72 m · 报警阈值 0.58 m`}
          extra={<Badge tone={distanceLow ? 'warning' : 'normal'}>{radar.distance.toFixed(3)} m</Badge>}
        >
          <Chart option={radarOption} height={200} pointCount={samples.length} emptyText="暂无雷达数据" />
        </Panel>

        <Panel
          title="堆积风险趋势"
          icon={<IconChart size={14} />}
          description="由雷达测距、视觉覆盖率与输送速度联合计算"
          extra={<Badge tone={LEVEL_TONE[risk.level]}>{risk.index.toFixed(1)}% {risk.level_text}</Badge>}
        >
          <Chart option={riskOption} height={200} pointCount={samples.length} emptyText="暂无风险数据" />
        </Panel>
      </div>

      {/* ===================== 技术解释 ===================== */}
      <Panel title="为什么需要融合" icon={<IconInfo size={14} />}>
        <div className="fusion__compare">
          <div className="fusion__compare-col">
            <SectionTitle>视觉 AI</SectionTitle>
            <p className="fusion__compare-role">负责复杂场景与形态理解</p>
            <ul className="fusion__compare-list">
              <li className="is-pro">信息丰富，可识别形态与杂质</li>
              <li className="is-pro">能做复杂语义判断</li>
              <li className="is-con">属于概率模型，输出非确定</li>
              <li className="is-con">受光照、遮挡与粉尘影响</li>
              <li className="is-con">推理延迟相对更高（当前约 {vision.latency_ms} ms）</li>
            </ul>
          </div>

          <div className="fusion__compare-col">
            <SectionTitle>雷达 / 传感器</SectionTitle>
            <p className="fusion__compare-role">负责高频、稳定、快速的几何量测量</p>
            <ul className="fusion__compare-list">
              <li className="is-pro">测量稳定，不依赖光照</li>
              <li className="is-pro">精度高（±5 cm），响应速度快</li>
              <li className="is-pro">可 10 Hz 持续高频采样</li>
              <li className="is-con">只有几何量，缺乏语义</li>
              <li className="is-con">无法区分"堆积"与"其他遮挡物"</li>
            </ul>
          </div>

          <div className="fusion__compare-col fusion__compare-col--result">
            <SectionTitle>融合判断</SectionTitle>
            <p className="fusion__compare-role">减少单一信息源的局限</p>
            <ul className="fusion__compare-list">
              <li className="is-pro">雷达先感知几何变化，响应快</li>
              <li className="is-pro">视觉再确认形态语义，避免误报</li>
              <li className="is-pro">两者一致时结论更可靠</li>
              <li className="is-pro">两者分歧时降级为「关注」并说明原因</li>
            </ul>
          </div>
        </div>
      </Panel>
    </div>
  )
}
