/**
 * 应用外壳：顶部栏 + 左侧导航 + 右侧主工作区。
 *
 * 数据来源有两条，由后端 `/api/meta` 的 `run_mode` 决定：
 *   * video_sync —— 页面数值随主监控视频的 currentTime 同步（正式演示默认）
 *   * automatic  —— 页面数值取自后端自动工况循环（开发与逻辑验证）
 *
 * 关键约束：**首页与雷视联动必须同源**。因此同步遥测只在
 * VideoSyncProvider 里解算一次，两个页面消费同一个对象，
 * 而不是各页面自己算一套。
 */

import { useCallback, useMemo, useState } from 'react'
import TopBar from '../components/TopBar'
import Sidebar from '../components/Sidebar'
import { NAV_ITEMS, useHashRoute, type PageId } from './navigation'
import { api } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { VideoSyncProvider, useVideoSync, type RunMode } from '../video/VideoSyncContext'
import {
  applyTelemetryToStatus,
  toSyncedSnapshot,
} from '../video/syncedTelemetry'
import type {
  AlarmRecord,
  Device,
  Paged,
  PlatformMeta,
  RealtimeSnapshot,
  SystemStatus,
} from '../types'
import OverviewPage from '../pages/OverviewPage'
import VideoPage from '../pages/VideoPage'
import FusionPage from '../pages/FusionPage'
import AlarmsPage from '../pages/AlarmsPage'
import TracePage from '../pages/TracePage'
import PredictionPage from '../pages/PredictionPage'
import KnowledgePage from '../pages/KnowledgePage'
import SettingsPage from '../pages/SettingsPage'
import './AppLayout.css'

/** 系统状态轮询间隔：1.5s 足够实时且压力很小 */
const STATUS_POLL_MS = 1500
/** 实时数据轮询间隔：视频同步模式下仅作低频校对与兜底 */
const REALTIME_POLL_MS = 1000
/** 趋势窗口点数：只保留最近 120 点，杜绝无限增长 */
const TREND_POINTS = 120

/** 外层只负责挂载 Provider，内层通过 hook 读取同步状态 */
export default function AppLayout() {
  const meta = useFetch<PlatformMeta>(api.meta, {})

  return (
    <VideoSyncProvider initialRunMode={meta.data?.run_mode ?? 'video_sync'}>
      <AppShell meta={meta} />
    </VideoSyncProvider>
  )
}

function AppShell({ meta }: { meta: ReturnType<typeof useFetch<PlatformMeta>> }) {
  const [page, navigate] = useHashRoute()
  const [collapsed, setCollapsed] = useState(false)

  const sync = useVideoSync()
  const syncActive = sync?.runMode === 'video_sync' && sync.available === true

  const status = useFetch<SystemStatus>(api.systemStatus, { intervalMs: STATUS_POLL_MS })
  const realtime = useFetch<RealtimeSnapshot>(() => api.realtime(TREND_POINTS), {
    intervalMs: REALTIME_POLL_MS,
  })
  const devices = useFetch<Device[]>(api.devices, {})

  /**
   * 报警记录：侧栏角标与「异常报警」页共用这一份数据。
   *
   * 之前角标取的是 `status.today_warnings`（今日发生的预警+严重报警**条数**，
   * 与是否已处置无关），而报警页的「当前报警」列的是**未处置**记录 ——
   * 两个口径不同，导致角标显示 1 但点进去是空的。
   * 现在统一为「未处置报警数」，角标与页面必然一致。
   */
  const alarms = useFetch<Paged<AlarmRecord>>(() => api.alarms({ page_size: 100 }), {
    intervalMs: STATUS_POLL_MS,
  })

  const offline = Boolean(status.error) && status.data === null && !syncActive

  /**
   * 视频同步模式下用同一份遥测替换实时快照与系统状态中的动态字段。
   * 两个页面拿到的是**同一个对象**，因此不可能出现页面间不一致。
   */
  const syncedSnapshot = useMemo(() => {
    if (!syncActive || !sync) return null
    return toSyncedSnapshot(sync.telemetry, sync.trend, {
      running: sync.playing || !sync.ready,
      sampleIntervalSeconds: sync.duration > 0 ? sync.duration / Math.max(1, sync.trend.length - 1) : 0.2,
    })
  }, [syncActive, sync])

  const effectiveRealtime = syncedSnapshot ?? realtime.data

  const effectiveStatus = useMemo(() => {
    if (!syncActive || !sync) return status.data
    return applyTelemetryToStatus(status.data, sync.telemetry, {
      running: sync.playing || !sync.ready,
      loopCount: sync.loopCount,
    })
  }, [syncActive, sync, status.data])

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

  const handleRunModeChange = useCallback(
    (mode: RunMode) => {
      sync?.setRunMode(mode)
      // 模式切换后立即刷新后端数据，避免短暂显示旧口径
      status.refresh()
      realtime.refresh()
    },
    [sync, status, realtime],
  )

  /**
   * 侧栏角标：未处置报警数。
   *
   * 口径与「异常报警 → 当前报警」列表完全一致：
   *   * 后端返回的未处置记录（pending / processing）
   *   * 加当前画面派生的临时报警（视频同步模式下进入预警/异常阶段时存在）
   * 角标为 0 时不显示 —— 避免出现「角标有数字、点进去却没有内容」的矛盾。
   */
  const liveAlarm = sync?.runMode === 'video_sync' && sync.available ? sync.currentAlarm : null

  const badges = useMemo(() => {
    const items = alarms.data?.items ?? []
    const pending =
      items.filter((a) => a.status === 'pending' || a.status === 'processing').length +
      (liveAlarm ? 1 : 0)
    return pending > 0 ? { alarms: pending } : {}
  }, [alarms.data, liveAlarm])

  const pages: Record<PageId, JSX.Element> = {
    overview: (
      <OverviewPage
        status={effectiveStatus}
        statusError={status.error}
        realtime={effectiveRealtime}
        realtimeError={realtime.error}
        devices={devices.data ?? []}
        onNavigate={handleNavigate}
        syncActive={syncActive}
      />
    ),
    video: <VideoPage meta={meta.data} />,
    fusion: (
      <FusionPage
        realtime={effectiveRealtime}
        realtimeError={realtime.error}
      />
    ),
    alarms: <AlarmsPage />,
    trace: <TracePage />,
    prediction: <PredictionPage />,
    knowledge: <KnowledgePage />,
    settings: (
      <SettingsPage
        status={effectiveStatus}
        meta={meta.data}
        onChanged={status.refresh}
        offline={offline}
        runMode={sync?.runMode ?? 'video_sync'}
        onRunModeChange={handleRunModeChange}
      />
    ),
  }

  return (
    <div className="shell">
      <TopBar
        status={effectiveStatus}
        offline={offline}
        onOpenSettings={() => handleNavigate('settings')}
      />
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
              </div>
              <div className="page__head-right">
                {effectiveStatus && (
                  <span
                    className={`page__mode${
                      effectiveStatus.detection_running ? '' : ' page__mode--idle'
                    }`}
                  >
                    {effectiveStatus.detection_running ? '检测运行中' : '检测已停止'}
                  </span>
                )}
                {effectiveStatus && (
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
