/**
 * 应用外壳：顶部栏 + 左侧导航 + 右侧主工作区。
 *
 * 系统运行状态在这里统一获取（1.5s 轮询），向下传给顶栏与各页面，
 * 避免每个页面各拉一次 /api/system/status。
 */

import { useCallback, useMemo, useState } from 'react'
import TopBar from '../components/TopBar'
import Sidebar from '../components/Sidebar'
import { NAV_ITEMS, useHashRoute, type PageId } from './navigation'
import { api } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import type { Device, PlatformMeta, RealtimeSnapshot, SystemStatus } from '../types'
import OverviewPage from '../pages/OverviewPage'
import VideoPage from '../pages/VideoPage'
import FusionPage from '../pages/FusionPage'
import AlarmsPage from '../pages/AlarmsPage'
import TracePage from '../pages/TracePage'
import PredictionPage from '../pages/PredictionPage'
import KnowledgePage from '../pages/KnowledgePage'
import SettingsPage from '../pages/SettingsPage'
import './AppLayout.css'

/** 系统状态轮询间隔：比赛演示优先稳定，1.5s 足够实时且压力很小 */
const STATUS_POLL_MS = 1500
/** 实时数据轮询间隔：引擎内部 10 Hz 演化，浏览器按约 1 s 刷新 UI 即可 */
const REALTIME_POLL_MS = 1000
/** 趋势窗口点数：只保留最近 120 点，杜绝无限增长 */
const TREND_POINTS = 120

export default function AppLayout() {
  const [page, navigate] = useHashRoute()
  const [collapsed, setCollapsed] = useState(false)

  const status = useFetch<SystemStatus>(api.systemStatus, { intervalMs: STATUS_POLL_MS })
  const meta = useFetch<PlatformMeta>(api.meta, {})
  const realtime = useFetch<RealtimeSnapshot>(() => api.realtime(TREND_POINTS), {
    intervalMs: REALTIME_POLL_MS,
  })
  const devices = useFetch<Device[]>(api.devices, {})

  const offline = Boolean(status.error) && status.data === null

  const current = useMemo(
    () => NAV_ITEMS.find((item) => item.id === page) ?? NAV_ITEMS[0],
    [page],
  )

  const handleNavigate = useCallback(
    (id: PageId) => {
      navigate(id)
      // 切换页面时回到工作区顶部，避免长页面保留上一页滚动位置
      document.querySelector('.workspace')?.scrollTo({ top: 0 })
    },
    [navigate],
  )

  // 侧栏角标：当前报警数量（后端未就绪时不显示）
  const badges = useMemo(() => {
    const pending = status.data?.today_warnings
    return pending && pending > 0 ? { alarms: pending } : {}
  }, [status.data?.today_warnings])

  const pages: Record<PageId, JSX.Element> = {
    overview: (
      <OverviewPage
        status={status.data}
        statusError={status.error}
        realtime={realtime.data}
        realtimeError={realtime.error}
        devices={devices.data ?? []}
        onNavigate={handleNavigate}
      />
    ),
    video: <VideoPage meta={meta.data} />,
    fusion: <FusionPage realtime={realtime.data} realtimeError={realtime.error} />,
    alarms: <AlarmsPage />,
    trace: <TracePage />,
    prediction: <PredictionPage />,    knowledge: <KnowledgePage />,
    settings: (
      <SettingsPage
        status={status.data}
        meta={meta.data}
        onChanged={status.refresh}
        offline={offline}
      />
    ),
  }

  return (
    <div className="shell">
      <TopBar status={status.data} offline={offline} onOpenSettings={() => handleNavigate('settings')} />
      <div className="shell__body">
        <Sidebar
          current={page}
          onNavigate={handleNavigate}
          collapsed={collapsed}
          onToggleCollapse={() => setCollapsed((v) => !v)}
          badges={badges}
        />
        <main className="workspace">
          <div className="page">
            <div className="page__head">
              <div className="page__head-left">
                <h2 className="page__title">{current.label}</h2>
                <span className="page__subtitle">{current.subtitle}</span>
              </div>
              <div className="page__head-right">
                <span className={`page__mode${meta.data?.mode === 'simulation' ? ' page__mode--sim' : ''}`}>
                  {meta.data?.mode === 'simulation' ? '仿真演示环境' : '实时接入环境'}
                </span>
                {status.data && (
                  <span className="page__ts">
                    数据更新：
                    {status.updatedAt ? new Date(status.updatedAt).toLocaleTimeString('zh-CN') : '—'}
                  </span>
                )}
              </div>
            </div>
            <div className="page__body">{pages[page]}</div>
          </div>
        </main>
      </div>
    </div>
  )
}
