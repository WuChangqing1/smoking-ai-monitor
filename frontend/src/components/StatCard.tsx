/**
 * 核心状态卡片。
 *
 * 首页只保留 4 张：在线设备 / 当前风险等级 / 今日预警 / 连续运行。
 * 数值全部来自后端，前端不做估算；后端未就绪时显示占位符而不是假数据。
 */

import type { ReactNode } from 'react'
import { Skeleton } from './Badge'
import type { Tone } from './Badge'
import './StatCard.css'

interface StatCardProps {
  label: string
  /** 主数值，已格式化的字符串 */
  value: ReactNode
  /** 数值后缀单位，例如「/ 18」「h」「次」 */
  suffix?: ReactNode
  tone?: Tone
  icon?: ReactNode
  /** 底部补充说明 */
  footnote?: ReactNode
  /** 数据未就绪 */
  loading?: boolean
  onClick?: () => void
}

export default function StatCard({
  label,
  value,
  suffix,
  tone = 'idle',
  icon,
  footnote,
  loading = false,
  onClick,
}: StatCardProps) {
  const interactive = Boolean(onClick)

  return (
    <div
      className={`stat-card stat-card--${tone}${interactive ? ' stat-card--clickable' : ''}`}
      onClick={onClick}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      onKeyDown={
        interactive
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onClick?.()
              }
            }
          : undefined
      }
    >
      <div className="stat-card__head">
        <span className="stat-card__label">{label}</span>
        {icon && <span className="stat-card__icon">{icon}</span>}
      </div>

      <div className="stat-card__value-row">
        {loading ? (
          <Skeleton height={30} width="70%" />
        ) : (
          <>
            <span className="stat-card__value">{value}</span>
            {suffix && <span className="stat-card__suffix">{suffix}</span>}
          </>
        )}
      </div>

      {footnote && <div className="stat-card__footnote">{footnote}</div>}
    </div>
  )
}
