/**
 * 顶部栏：平台名称 + 当前日期时间 + 运行状态指示。
 *
 * 状态口径来自后端 /api/system/status，前端只做展示，不自行判断业务状态。
 */

import { useEffect, useState } from 'react'
import { IconClock, IconInfo } from './icons'
import type { StatusItem, SystemStatus } from '../types'
import './TopBar.css'

interface TopBarProps {
  status: SystemStatus | null
  /** 后端是否连接失败（用于顶部提示，不阻塞页面） */
  offline: boolean
  onOpenSettings: () => void
}

/** 与后端 statuses[].key 对应的顶栏展示项 */
const TOPBAR_KEYS = ['system', 'ai', 'radar', 'video'] as const

const WEEKDAYS = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']

function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n)
}

function formatDateTime(d: Date): string {
  return (
    `${d.getFullYear()}年${pad(d.getMonth() + 1)}月${pad(d.getDate())}日 ` +
    `${WEEKDAYS[d.getDay()]} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  )
}

function StatusPill({ item }: { item: StatusItem }) {
  return (
    <span className={`status-pill status-pill--${item.state}`} title={item.detail ?? item.text}>
      <i className="status-pill__dot" aria-hidden="true" />
      <span className="status-pill__label">{item.label}</span>
      <span className="status-pill__value">{item.text}</span>
    </span>
  )
}

export default function TopBar({ status, offline, onOpenSettings }: TopBarProps) {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  const byKey = new Map((status?.statuses ?? []).map((s) => [s.key, s]))
  const pills: StatusItem[] = TOPBAR_KEYS.map((key) => byKey.get(key)).filter(
    (s): s is StatusItem => Boolean(s),
  )

  return (
    <header className="topbar">
      <div className="topbar__brand">
        <span className="topbar__mark" aria-hidden="true" />
        <div className="topbar__titles">
          <h1 className="topbar__title">烟厂制丝线物流智能监控平台</h1>
          <p className="topbar__subtitle">
            视觉识别 + 激光雷达多模态融合 · 提前预警与异常溯源
          </p>
        </div>
      </div>

      <div className="topbar__status">
        {pills.length > 0 ? (
          pills.map((item) => <StatusPill key={item.key} item={item} />)
        ) : (
          <span className="status-pill status-pill--offline">
            <i className="status-pill__dot" aria-hidden="true" />
            <span className="status-pill__label">平台状态</span>
            <span className="status-pill__value">{offline ? '等待后端' : '连接中'}</span>
          </span>
        )}
      </div>

      <div className="topbar__right">
        {status?.detection_running === false && (
          <span className="topbar__tag topbar__tag--idle">检测任务已停止</span>
        )}
        {offline && (
          <button
            type="button"
            className="topbar__tag topbar__tag--warn"
            onClick={onOpenSettings}
            title="后端服务未连接，点击查看系统设置"
          >
            <IconInfo size={13} />
            后端未连接
          </button>
        )}
        <span className="topbar__clock">
          <IconClock size={14} />
          {formatDateTime(now)}
        </span>
      </div>
    </header>
  )
}
