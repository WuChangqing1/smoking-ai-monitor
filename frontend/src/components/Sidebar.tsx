/**
 * 左侧导航：按分组展示 8 个业务模块。
 *
 * 使用深色侧栏 + 浅色工作区形成结构分区，这是工业监控系统的常见做法，
 * 既能让「白色背景为主」的主工作区保持清爽，又能拉开导航与内容的层级。
 */

import { NAV_ITEMS, type NavItem, type PageId } from '../app/navigation'
import './Sidebar.css'

interface SidebarProps {
  current: PageId
  onNavigate: (id: PageId) => void
  collapsed: boolean
  onToggleCollapse: () => void
  /** 各页面的待处理角标，例如报警数量 */
  badges?: Partial<Record<PageId, number>>
}

const GROUPS: NavItem['group'][] = ['实时监控', '分析与处置', '系统']

export default function Sidebar({
  current,
  onNavigate,
  collapsed,
  onToggleCollapse,
  badges = {},
}: SidebarProps) {
  return (
    <aside className={`sidebar${collapsed ? ' sidebar--collapsed' : ''}`}>
      <nav className="sidebar__nav" aria-label="主导航">
        {GROUPS.map((group) => {
          const items = NAV_ITEMS.filter((item) => item.group === group)
          if (items.length === 0) return null

          return (
            <div className="sidebar__group" key={group}>
              <p className="sidebar__group-title">{collapsed ? '·' : group}</p>
              <ul className="sidebar__list">
                {items.map((item) => {
                  const Icon = item.icon
                  const active = item.id === current
                  const badge = badges[item.id]

                  return (
                    <li key={item.id}>
                      <button
                        type="button"
                        className={`sidebar__item${active ? ' sidebar__item--active' : ''}`}
                        onClick={() => onNavigate(item.id)}
                        title={collapsed ? `${item.label} · ${item.subtitle}` : item.subtitle}
                        aria-current={active ? 'page' : undefined}
                      >
                        <span className="sidebar__icon">
                          <Icon size={17} />
                        </span>
                        {!collapsed && <span className="sidebar__label">{item.label}</span>}
                        {!collapsed && badge !== undefined && badge > 0 && (
                          <span className="sidebar__badge">{badge > 99 ? '99+' : badge}</span>
                        )}
                        {collapsed && badge !== undefined && badge > 0 && (
                          <span className="sidebar__badge sidebar__badge--dot" aria-hidden="true" />
                        )}
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          )
        })}
      </nav>

      <div className="sidebar__footer">
        <button
          type="button"
          className="sidebar__collapse"
          onClick={onToggleCollapse}
          title={collapsed ? '展开导航' : '收起导航'}
        >
          <span className={`sidebar__collapse-arrow${collapsed ? ' is-collapsed' : ''}`}>‹</span>
          {!collapsed && <span>收起导航</span>}
        </button>
      </div>
    </aside>
  )
}
