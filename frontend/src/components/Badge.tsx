/**
 * 状态标签 / 圆点 / 通用小组件。
 *
 * 颜色语义严格统一：
 *   绿 = 正常   橙 = 预警/关注   红 = 严重报警   灰 = 停止/离线   蓝灰 = 提示
 */

import type { ReactNode } from 'react'
import './Badge.css'

export type Tone = 'normal' | 'warning' | 'critical' | 'info' | 'idle' | 'primary'

const TONE_CLASS: Record<Tone, string> = {
  normal: 'badge--normal',
  warning: 'badge--warning',
  critical: 'badge--critical',
  info: 'badge--info',
  idle: 'badge--idle',
  primary: 'badge--primary',
}

interface BadgeProps {
  tone?: Tone
  /** 带状态圆点 */
  dot?: boolean
  /** 实心填充样式 */
  solid?: boolean
  children: ReactNode
  title?: string
}

export function Badge({ tone = 'idle', dot = false, solid = false, children, title }: BadgeProps) {
  return (
    <span
      className={`badge ${TONE_CLASS[tone]}${solid ? ' badge--solid' : ''}`}
      title={title}
    >
      {dot && <i className="badge__dot" aria-hidden="true" />}
      {children}
    </span>
  )
}

/** 独立状态圆点 */
export function Dot({ tone = 'idle', pulse = false }: { tone?: Tone; pulse?: boolean }) {
  return (
    <i
      className={`dot ${TONE_CLASS[tone]}${pulse ? ' dot--pulse' : ''}`}
      aria-hidden="true"
    />
  )
}

/** 键值对行：左侧标签、右侧数值 */
export function MetricRow({
  label,
  value,
  unit,
  tone = 'idle',
  hint,
}: {
  label: ReactNode
  value: ReactNode
  unit?: string
  tone?: Tone
  hint?: string
}) {
  return (
    <div className="metric-row" title={hint}>
      <span className="metric-row__label">{label}</span>
      <span className={`metric-row__value metric-row__value--${tone}`}>
        {value}
        {unit && <em className="metric-row__unit">{unit}</em>}
      </span>
    </div>
  )
}

/** 指标列表容器。`className` 可选，便于某个页面改成横向铺开的排布。 */
export function MetricList({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return <div className={`metric-list ${className}`.trim()}>{children}</div>
}

/** 空状态 / 错误状态占位 */
export function EmptyState({
  title,
  description,
  action,
  tone = 'idle',
}: {
  title: string
  description?: string
  action?: ReactNode
  tone?: Tone
}) {
  return (
    <div className={`empty-state empty-state--${tone}`}>
      <p className="empty-state__title">{title}</p>
      {description && <p className="empty-state__desc">{description}</p>}
      {action && <div className="empty-state__action">{action}</div>}
    </div>
  )
}

/** 区块小标题 */
export function SectionTitle({
  children,
  extra,
}: {
  children: ReactNode
  extra?: ReactNode
}) {
  return (
    <div className="section-title">
      <span className="section-title__text">{children}</span>
      {extra && <span className="section-title__extra">{extra}</span>}
    </div>
  )
}

/** 加载骨架 */
export function Skeleton({ height = 16, width = '100%' }: { height?: number; width?: string }) {
  return <span className="skeleton" style={{ height, width }} aria-hidden="true" />
}
