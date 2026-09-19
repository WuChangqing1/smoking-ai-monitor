/**
 * 左侧导航定义与 hash 路由。
 *
 * 只有 8 个页面，引入 react-router 不划算：用 window.location.hash
 * 做路由即可满足「可分享链接 + 前进后退 + 刷新保持」的需求，零依赖。
 */

import { useCallback, useEffect, useState } from 'react'
import {
  IconAlarm,
  IconDashboard,
  IconKnowledge,
  IconPredict,
  IconRadar,
  IconSettings,
  IconTrace,
  IconVideo,
  type IconComponent,
} from '../components/icons'

export type PageId =
  | 'overview'
  | 'video'
  | 'fusion'
  | 'alarms'
  | 'trace'
  | 'prediction'
  | 'knowledge'
  | 'settings'

export interface NavItem {
  id: PageId
  label: string
  icon: IconComponent
  /** 分组标题，用于导航分区 */
  group: '实时监控' | '分析与处置' | '系统'
}

export const NAV_ITEMS: NavItem[] = [
  {
    id: 'overview',
    label: '综合监控',
    icon: IconDashboard,
    group: '实时监控',
  },
  {
    id: 'video',
    label: '视频监控',
    icon: IconVideo,
    group: '实时监控',
  },
  {
    id: 'fusion',
    label: '雷视联动',
    icon: IconRadar,
    group: '实时监控',
  },
  {
    id: 'alarms',
    label: '异常报警',
    icon: IconAlarm,
    group: '分析与处置',
  },
  {
    id: 'trace',
    label: '数据溯源',
    icon: IconTrace,
    group: '分析与处置',
  },
  {
    id: 'prediction',
    label: '智能预警',
    icon: IconPredict,
    group: '分析与处置',
  },
  {
    id: 'knowledge',
    label: '知识库',
    icon: IconKnowledge,
    group: '分析与处置',
  },
  {
    id: 'settings',
    label: '系统设置',
    icon: IconSettings,
    group: '系统',
  },
]

const DEFAULT_PAGE: PageId = 'overview'
const VALID_IDS = new Set<string>(NAV_ITEMS.map((item) => item.id))

function parseHash(): PageId {
  const raw = window.location.hash.replace(/^#\/?/, '').split('?')[0]
  return VALID_IDS.has(raw) ? (raw as PageId) : DEFAULT_PAGE
}

export function useHashRoute(): [PageId, (id: PageId) => void] {
  const [page, setPage] = useState<PageId>(() => parseHash())

  useEffect(() => {
    const onChange = () => setPage(parseHash())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])

  const navigate = useCallback((id: PageId) => {
    if (window.location.hash !== `#/${id}`) {
      window.location.hash = `#/${id}`
    }
    setPage(id)
  }, [])

  return [page, navigate]
}
