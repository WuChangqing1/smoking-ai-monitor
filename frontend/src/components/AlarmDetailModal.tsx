/**
 * 报警详情弹层。
 *
 * 内容对应原系统的"异常分析窗口"：
 *   事件基本信息 + 异常证据图 + 当时监控画面 + 雷达趋势 + AI 判断 + 处理过程
 *
 * 数据来自 GET /api/alarms/{id}，弹层本身不计算任何业务结论。
 */

import { useMemo } from 'react'
import Modal from './Modal'
import Chart from './Chart'
import { radarDistanceOption } from './chartOptions'
import { Badge, EmptyState, MetricList, MetricRow, SectionTitle, Skeleton } from './Badge'
import { IconAlarm, IconInfo } from './icons'
import type { AlarmDetail, AlarmLevel } from '../types'
import './AlarmDetail.css'

interface AlarmDetailModalProps {
  open: boolean
  detail: AlarmDetail | null
  loading: boolean
  error: string | null
  onClose: () => void
}

const LEVEL_TONE: Record<AlarmLevel, 'info' | 'warning' | 'critical'> = {
  info: 'info',
  warning: 'warning',
  critical: 'critical',
}

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false })
}

export default function AlarmDetailModal({
  open,
  detail,
  loading,
  error,
  onClose,
}: AlarmDetailModalProps) {
  const radarOption = useMemo(
    () => radarDistanceOption(detail?.radar_trend ?? [], detail?.radar_value ?? null),
    [detail?.radar_trend, detail?.radar_value],
  )

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title={
        <>
          <IconAlarm size={16} />
          报警详情
          {detail && <span className="alarm-detail__code">{detail.code}</span>}
        </>
      }
      subtitle={detail ? `${detail.location} · ${formatTime(detail.ts)}` : '正在加载报警记录…'}
      footer={
        <button type="button" className="btn" onClick={onClose}>
          关闭
        </button>
      }
    >
      {loading && !detail && (
        <div className="alarm-detail__loading">
          <Skeleton height={20} width="40%" />
          <Skeleton height={64} />
          <Skeleton height={140} />
        </div>
      )}

      {!loading && error && !detail && (
        <EmptyState tone="critical" title="无法加载报警详情" description={error} />
      )}

      {detail && (
        <div className="alarm-detail">
          {/* ---------- 事件基本信息 ---------- */}
          <section className="alarm-detail__section">
            <SectionTitle
              extra={
                <span className="alarm-detail__badges">
                  <Badge tone={LEVEL_TONE[detail.level]} solid={detail.level === 'critical'} dot>
                    {detail.level_text}
                  </Badge>
                  <Badge tone={detail.status === 'archived' ? 'idle' : 'primary'}>
                    {detail.status_text}
                  </Badge>
                </span>
              }
            >
              事件基本信息
            </SectionTitle>

            <div className="alarm-detail__grid">
              <MetricList>
                <MetricRow label="报警编号" value={detail.code} />
                <MetricRow label="报警时间" value={formatTime(detail.ts)} />
                <MetricRow label="设备名称" value={detail.device_name} />
                <MetricRow label="设备编号" value={detail.device_id} />
              </MetricList>
              <MetricList>
                <MetricRow label="设备 IP" value={detail.device_ip} />
                <MetricRow label="位置" value={detail.location} />
                <MetricRow label="异常类型" value={detail.event_type_text} />
                <MetricRow
                  label="风险指数"
                  value={detail.risk_index.toFixed(1)}
                  unit="%"
                  tone={
                    detail.level === 'critical'
                      ? 'critical'
                      : detail.level === 'warning'
                        ? 'warning'
                        : 'info'
                  }
                />
              </MetricList>
            </div>
          </section>

          {/* ---------- 异常证据图 ---------- */}
          {detail.evidence_image && (
            <section className="alarm-detail__section">
              <SectionTitle
                extra={
                  <Badge tone={detail.level === 'critical' ? 'critical' : 'warning'}>
                    YOLO 检测结果
                  </Badge>
                }
              >
                异常证据图
              </SectionTitle>

              <figure className="alarm-detail__evidence-figure">
                <img
                  src={detail.evidence_image}
                  alt={`${detail.code} 视觉模型检测到${detail.event_type_text}异常区域的带框截图`}
                  loading="lazy"
                />
                <figcaption>{detail.evidence_note}</figcaption>
              </figure>
            </section>
          )}

          {/* ---------- 当时监控画面 + 雷达趋势 ---------- */}
          <section className="alarm-detail__section">
            <SectionTitle>当时监控画面与数据走向</SectionTitle>
            <div className="alarm-detail__evidence">
              <div className="alarm-detail__snapshot">
                {detail.snapshot ? (
                  <img src={detail.snapshot} alt={`${detail.code} 报警时的监控画面`} />
                ) : (
                  <div className="alarm-detail__snapshot-empty">该点位暂无图像数据</div>
                )}
                <p className="alarm-detail__snapshot-cap">
                  报警时刻监控画面（Camera 01 · 制丝线 2 号输送段）
                </p>
              </div>

              <div className="alarm-detail__trend">
                <Chart
                  option={radarOption}
                  height={188}
                  pointCount={detail.radar_trend.length}
                  emptyText="暂无雷达趋势数据"
                />
                <p className="alarm-detail__trend-cap">
                  对应原系统的异常分析窗口：数据在时间上的走向 + 图像数据
                </p>
              </div>
            </div>
          </section>

          {/* ---------- AI 判断 ---------- */}
          <section className="alarm-detail__section">
            <SectionTitle>AI 判断</SectionTitle>
            <MetricList>
              <MetricRow label="视觉结果" value={detail.ai_analysis.vision_label} />
              <MetricRow
                label="置信度"
                value={(detail.ai_analysis.confidence * 100).toFixed(1)}
                unit="%"
                hint="概率模型输出，不是准确率"
              />
              <MetricRow
                label="物料覆盖率"
                value={(detail.ai_analysis.coverage * 100).toFixed(1)}
                unit="%"
              />
              <MetricRow
                label="雷达测距"
                value={detail.radar_value !== null ? detail.radar_value.toFixed(3) : '—'}
                unit="m"
                tone="warning"
              />
              <MetricRow
                label="基准距离"
                value={detail.baseline_distance.toFixed(3)}
                unit="m"
              />
              <MetricRow label="联合结果" value={detail.fusion_result} />
            </MetricList>

            <p className="alarm-detail__note">
              <IconInfo size={12} />
              {detail.ai_analysis.note}
            </p>
          </section>

          {/* ---------- 处理过程 ---------- */}
          <section className="alarm-detail__section">
            <SectionTitle extra={<span className="alarm-detail__operator">处理人：{detail.operator}</span>}>
              处理过程
            </SectionTitle>

            <ol className="alarm-detail__timeline">
              {detail.timeline.map((entry) => (
                <li key={`${entry.stage}-${entry.ts}`} className="alarm-detail__step">
                  <div className="alarm-detail__step-body">
                    <div className="alarm-detail__step-head">
                      <span className="alarm-detail__step-stage">{entry.stage}</span>
                      <span className="alarm-detail__step-title">{entry.title}</span>
                      <span className="alarm-detail__step-ts">{entry.ts}</span>
                    </div>
                    <p className="alarm-detail__step-detail">{entry.detail}</p>
                  </div>
                </li>
              ))}
            </ol>

            {detail.resolution && (
              <div className="alarm-detail__resolution">
                <strong>处理结果：</strong>
                {detail.resolution}
              </div>
            )}
          </section>
        </div>
      )}
    </Modal>
  )
}
