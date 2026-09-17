/**
 * Panel —— 工业风卡片容器。
 *
 * 平台所有内容块都放在 Panel 里，统一标题、右侧操作区与内容留白，
 * 避免各页面各写一套卡片样式导致视觉不一致。
 */

import type { ReactNode } from 'react'
import './Panel.css'

interface PanelProps {
  title?: ReactNode
  /** 标题左侧的小图标 */
  icon?: ReactNode
  /** 标题右侧操作区（按钮、筛选器等） */
  extra?: ReactNode
  /** 标题下方的补充说明 */
  description?: ReactNode
  /** 去掉内容区默认内边距（表格、视频等需要贴边时使用） */
  flush?: boolean
  /** 高亮边框：用于报警等需要强调的卡片 */
  tone?: 'default' | 'primary' | 'warning' | 'critical'
  className?: string
  bodyClassName?: string
  children: ReactNode
}

export default function Panel({
  title,
  icon,
  extra,
  description,
  flush = false,
  tone = 'default',
  className = '',
  bodyClassName = '',
  children,
}: PanelProps) {
  return (
    <section className={`panel panel--${tone} ${className}`.trim()}>
      {(title || extra) && (
        <header className="panel__head">
          <div className="panel__head-left">
            {icon && <span className="panel__icon">{icon}</span>}
            <div>
              {title && <h2 className="panel__title">{title}</h2>}
              {description && <p className="panel__desc">{description}</p>}
            </div>
          </div>
          {extra && <div className="panel__extra">{extra}</div>}
        </header>
      )}
      <div className={`panel__body${flush ? ' panel__body--flush' : ''} ${bodyClassName}`.trim()}>
        {children}
      </div>
    </section>
  )
}
