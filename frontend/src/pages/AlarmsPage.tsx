/**
 * 异常报警页。
 *
 * 结构：当前报警（未处置） / 历史报警（全部，可筛选）
 * 颜色口径：提示＝蓝灰、预警＝橙、严重＝红。不做满屏红色 ——
 * 只有严重级别才使用红色实心标记。
 *
 * 报警内容口径与原始资料一致：设备名称 + 设备 IP + 报警时间 + 距离信息。
 * 点击任意一行打开报警详情，形成「发现 → 判断 → 报警 → 处理 → 归档」闭环。
 */

import { useCallback, useMemo, useState } from 'react'
import Panel from '../components/Panel'
import FilterBar, { type FilterField } from '../components/FilterBar'
import AlarmDetailModal from '../components/AlarmDetailModal'
import { Badge, EmptyState, Skeleton } from '../components/Badge'
import { IconAlarm, IconRefresh } from '../components/icons'
import { api } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import type { AlarmDetail, AlarmLevel, TraceQuery } from '../types'
import './AlarmsPage.css'

type TabKey = 'current' | 'history'

const LEVEL_TONE: Record<AlarmLevel, 'info' | 'warning' | 'critical'> = {
  info: 'info',
  warning: 'warning',
  critical: 'critical',
}

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'current', label: '当前报警' },
  { key: 'history', label: '历史报警' },
]

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false })
}

export default function AlarmsPage() {
  const [tab, setTab] = useState<TabKey>('current')
  const [level, setLevel] = useState('')
  const [status, setStatus] = useState('')
  const [eventType, setEventType] = useState('')
  const [dateFrom, setDateFrom] = useState('')

  const [detailId, setDetailId] = useState<string | null>(null)

  // 筛选选项来自后端，避免前端与数据口径脱节
  const options = useFetch(api.alarmOptions, {})

  /**
   * 列表数据。
   * 当前报警 = 未处置（pending / processing）；历史报警 = 全部。
   * 只对历史标签页做等级/状态/类型/日期筛选 —— 当前报警本就应当一览无余。
   */
  const listQuery = useMemo<TraceQuery>(() => {
    if (tab === 'current') return { page_size: 100 }
    return {
      level: (level || undefined) as AlarmLevel | undefined,
      status: (status || undefined) as TraceQuery['status'],
      event_type: eventType || undefined,
      date_from: dateFrom || undefined,
      page_size: 100,
    }
  }, [tab, level, status, eventType, dateFrom])

  const list = useFetch(() => api.alarms(listQuery), { intervalMs: 3000 })

  const allItems = list.data?.items ?? []
  const items = useMemo(
    () =>
      tab === 'current'
        ? allItems.filter((a) => a.status === 'pending' || a.status === 'processing')
        : allItems,
    [allItems, tab],
  )

  // 详情按需加载
  const detailFetcher = useCallback(
    () => (detailId ? api.alarmDetail(detailId) : Promise.resolve(null)),
    [detailId],
  )
  const detailState = useFetch<AlarmDetail | null>(detailFetcher, { enabled: detailId !== null })

  const riskLikeLevels = options.data?.levels ?? []
  const statusOptions = options.data?.statuses ?? []
  const eventTypeOptions = options.data?.event_types ?? []

  const filterFields: FilterField[] = [
    {
      key: 'level',
      label: '报警等级',
      type: 'select',
      value: level,
      options: riskLikeLevels.map((o) => ({ value: o.value, label: o.label })),
      onChange: setLevel,
    },
    {
      key: 'status',
      label: '处理状态',
      type: 'select',
      value: status,
      options: statusOptions.map((o) => ({ value: o.value, label: o.label })),
      onChange: setStatus,
    },
    {
      key: 'event_type',
      label: '异常类型',
      type: 'select',
      value: eventType,
      options: eventTypeOptions.map((o) => ({ value: o.value, label: o.label })),
      onChange: setEventType,
    },
    {
      key: 'date_from',
      label: '起始日期',
      type: 'date',
      value: dateFrom,
      onChange: setDateFrom,
    },
  ]

  const resetFilters = () => {
    setLevel('')
    setStatus('')
    setEventType('')
    setDateFrom('')
  }

  const criticalCount = allItems.filter((a) => a.level === 'critical').length
  const pendingCount = allItems.filter(
    (a) => a.status === 'pending' || a.status === 'processing',
  ).length

  return (
    <div className="alarms">
      {/* ---- 顶部：标签页 + 概览 ---- */}
      <div className="alarms__bar">
        <div className="alarms__tabs" role="tablist">
          {TABS.map((item) => (
            <button
              key={item.key}
              type="button"
              role="tab"
              aria-selected={tab === item.key}
              className={`alarms__tab${tab === item.key ? ' is-active' : ''}`}
              onClick={() => setTab(item.key)}
            >
              {item.label}
              {item.key === 'current' && pendingCount > 0 && (
                <span className="alarms__tab-badge">{pendingCount}</span>
              )}
            </button>
          ))}
        </div>

        <div className="alarms__summary">
          <span>
            共 <strong>{items.length}</strong> 条
          </span>
          {criticalCount > 0 && (
            <Badge tone="critical" dot>
              严重 {criticalCount}
            </Badge>
          )}
          <button
            type="button"
            className="alarms__refresh"
            onClick={list.refresh}
            title="立即刷新"
          >
            <IconRefresh size={13} />
            刷新
          </button>
        </div>
      </div>

      {/* ---- 筛选（仅历史报警需要） ---- */}
      {tab === 'history' && (
        <FilterBar
          fields={filterFields}
          onReset={resetFilters}
          extra={
            list.data ? (
              <>
                匹配 <strong>{list.data.total}</strong> 条
              </>
            ) : undefined
          }
        />
      )}

      {/* ---- 数据中断提示 ---- */}
      {list.error && list.data && (
        <div className="alarms__stale">
          数据更新暂时中断，当前展示为最后一次成功获取的数据。
        </div>
      )}

      {/* ---- 列表 ---- */}
      <Panel
        flush
        title={tab === 'current' ? '未处置报警' : '历史报警记录'}
        icon={<IconAlarm size={14} />}
        description="点击任意一行查看报警详情与处理闭环"
      >
        {list.loading && !list.data ? (
          <div className="alarms__loading">
            <Skeleton height={34} />
            <Skeleton height={34} />
            <Skeleton height={34} />
            <Skeleton height={34} />
          </div>
        ) : list.error && !list.data ? (
          <EmptyState
            tone="critical"
            title="报警数据不可用"
            description={list.error}
            action={
              <button type="button" className="btn" onClick={list.refresh}>
                重新加载
              </button>
            }
          />
        ) : items.length === 0 ? (
          <EmptyState
            title={tab === 'current' ? '当前没有未处置报警' : '没有符合条件的报警记录'}
            description={
              tab === 'current'
                ? '系统运行正常。报警产生后会自动出现在这里，并保留完整处理闭环。'
                : '可以调整筛选条件后重试。'
            }
          />
        ) : (
          <div className="alarms__table-wrap">
            <table className="data-table alarms__table">
              <thead>
                <tr>
                  <th>报警编号</th>
                  <th>报警时间</th>
                  <th>设备</th>
                  <th>设备 IP</th>
                  <th>位置</th>
                  <th>异常类型</th>
                  <th>等级</th>
                  <th>雷达值</th>
                  <th>视觉结果</th>
                  <th>联合结果</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {items.map((alarm) => (
                  <tr
                    key={alarm.id}
                    className={`alarms__row alarms__row--${alarm.level}`}
                    onClick={() => setDetailId(alarm.id)}
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        setDetailId(alarm.id)
                      }
                    }}
                  >
                    <td className="mono alarms__cell-code">{alarm.code}</td>
                    <td className="mono">{formatTime(alarm.ts)}</td>
                    <td>{alarm.device_name}</td>
                    <td className="mono">{alarm.device_ip}</td>
                    <td>{alarm.location}</td>
                    <td>{alarm.event_type_text}</td>
                    <td>
                      <Badge
                        tone={LEVEL_TONE[alarm.level]}
                        solid={alarm.level === 'critical'}
                        dot
                      >
                        {alarm.level_text}
                      </Badge>
                    </td>
                    <td className="mono">
                      {alarm.radar_value !== null ? `${alarm.radar_value.toFixed(3)} m` : '—'}
                    </td>
                    <td>{alarm.vision_result}</td>
                    <td>{alarm.fusion_result}</td>
                    <td>
                      <Badge tone={alarm.status === 'archived' ? 'idle' : 'primary'}>
                        {alarm.status_text}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {/* ---- 详情弹层 ---- */}
      <AlarmDetailModal
        open={detailId !== null}
        detail={detailState.data}
        loading={detailState.loading}
        error={detailState.error}
        onClose={() => setDetailId(null)}
      />
    </div>
  )
}
