/**
 * 数据溯源页。
 *
 * 支持按 日期范围 / 设备 / 异常类型 / 报警等级 / 处理状态 组合检索历史事件，
 * 并可下钻到具体事件的完整数据与处置记录（复用报警详情弹层）。
 *
 * 对应原始资料口径："可按时间段、设备名称对报警内容进行查询"，
 * 并在此基础上增加了异常类型、等级与状态维度。
 */

import { useCallback, useMemo, useState } from 'react'
import Panel from '../components/Panel'
import FilterBar, { type FilterField } from '../components/FilterBar'
import AlarmDetailModal from '../components/AlarmDetailModal'
import { Badge, EmptyState, MetricList, MetricRow, Skeleton } from '../components/Badge'
import { IconTrace } from '../components/icons'
import { api } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import type { AlarmDetail, AlarmLevel, TraceQuery } from '../types'
import './TracePage.css'

const LEVEL_TONE: Record<AlarmLevel, 'info' | 'warning' | 'critical'> = {
  info: 'info',
  warning: 'warning',
  critical: 'critical',
}

const PAGE_SIZE = 20

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false })
}

function formatDate(ts: number): string {
  return new Date(ts * 1000).toLocaleDateString('zh-CN')
}

export default function TracePage() {
  // 筛选条件
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [deviceId, setDeviceId] = useState('')
  const [eventType, setEventType] = useState('')
  const [level, setLevel] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)

  const [detailId, setDetailId] = useState<string | null>(null)

  const options = useFetch(api.alarmOptions, {})

  const query = useMemo<TraceQuery>(
    () => ({
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      device_id: deviceId || undefined,
      event_type: eventType || undefined,
      level: (level || undefined) as AlarmLevel | undefined,
      status: (status || undefined) as TraceQuery['status'],
      page,
      page_size: PAGE_SIZE,
    }),
    [dateFrom, dateTo, deviceId, eventType, level, status, page],
  )

  const result = useFetch(() => api.alarms(query), {})

  const detailFetcher = useCallback(
    () => (detailId ? api.alarmDetail(detailId) : Promise.resolve(null)),
    [detailId],
  )
  const detailState = useFetch<AlarmDetail | null>(detailFetcher, { enabled: detailId !== null })

  /** 任一筛选变化都要回到第一页，否则会停在空白页 */
  function updateFilter(setter: (v: string) => void) {
    return (value: string) => {
      setter(value)
      setPage(1)
    }
  }

  function resetFilters() {
    setDateFrom('')
    setDateTo('')
    setDeviceId('')
    setEventType('')
    setLevel('')
    setStatus('')
    setPage(1)
  }

  const fields: FilterField[] = [
    {
      key: 'date_from',
      label: '起始日期',
      type: 'date',
      value: dateFrom,
      onChange: updateFilter(setDateFrom),
    },
    {
      key: 'date_to',
      label: '结束日期',
      type: 'date',
      value: dateTo,
      onChange: updateFilter(setDateTo),
    },
    {
      key: 'device_id',
      label: '设备',
      type: 'select',
      value: deviceId,
      options: options.data?.devices ?? [],
      onChange: updateFilter(setDeviceId),
    },
    {
      key: 'event_type',
      label: '异常类型',
      type: 'select',
      value: eventType,
      options: options.data?.event_types ?? [],
      onChange: updateFilter(setEventType),
    },
    {
      key: 'level',
      label: '报警等级',
      type: 'select',
      value: level,
      options: options.data?.levels ?? [],
      onChange: updateFilter(setLevel),
    },
    {
      key: 'status',
      label: '处理状态',
      type: 'select',
      value: status,
      options: options.data?.statuses ?? [],
      onChange: updateFilter(setStatus),
    },
  ]

  const items = result.data?.items ?? []
  const total = result.data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  // 汇总统计（基于当前页数据，用于快速判读）
  const stats = useMemo(() => {
    const critical = items.filter((a) => a.level === 'critical').length
    const warning = items.filter((a) => a.level === 'warning').length
    const info = items.filter((a) => a.level === 'info').length
    const archived = items.filter((a) => a.status === 'archived').length
    const distances = items
      .map((a) => a.radar_value)
      .filter((v): v is number => v !== null)
    const minDistance = distances.length ? Math.min(...distances) : null
    const withDate = items.filter((a) => a.ts > 0)
    return {
      critical,
      warning,
      info,
      archived,
      minDistance,
      span:
        withDate.length > 1
          ? `${formatDate(withDate[withDate.length - 1].ts)} ~ ${formatDate(withDate[0].ts)}`
          : '—',
    }
  }, [items])

  return (
    <div className="trace">
      {/* ---- 筛选条 ---- */}
      <FilterBar
        fields={fields}
        onReset={resetFilters}
        extra={
          result.data ? (
            <>
              命中 <strong>{total}</strong> 条 · 第 <strong>{page}</strong> / {totalPages} 页
            </>
          ) : undefined
        }
      />

      {result.error && result.data && (
        <div className="trace__stale">
          数据更新暂时中断，当前展示为最后一次成功获取的数据。
        </div>
      )}

      {/* ---- 汇总 ---- */}
      <div className="grid grid--2 trace__top">
        <Panel title="检索结果汇总" icon={<IconTrace size={14} />} description={`时间跨度 ${stats.span}`}>
          <MetricList>
            <MetricRow label="命中记录" value={total} unit="条" />
            <MetricRow
              label="严重 / 预警 / 提示"
              value={`${stats.critical} / ${stats.warning} / ${stats.info}`}
              tone={stats.critical > 0 ? 'critical' : stats.warning > 0 ? 'warning' : 'normal'}
            />
            <MetricRow label="已归档" value={stats.archived} unit="条" />
            <MetricRow
              label="最低测距"
              value={stats.minDistance !== null ? stats.minDistance.toFixed(3) : '—'}
              unit="m"
              tone={stats.minDistance !== null && stats.minDistance < 0.6 ? 'critical' : 'idle'}
              hint="当前页记录中的最小雷达测距，接近 0.58 m 报警阈值即代表发生过堵料"
            />
          </MetricList>
        </Panel>
      </div>

      {/* ---- 结果表 ---- */}
      <Panel
        flush
        title="历史事件明细"
        icon={<IconTrace size={14} />}
        description="点击任意一行进入事件详情"
        extra={
          totalPages > 1 && (
            <div className="trace__pager">
              <button
                type="button"
                className="trace__pager-btn"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                上一页
              </button>
              <span className="trace__pager-info">
                {page} / {totalPages}
              </span>
              <button
                type="button"
                className="trace__pager-btn"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                下一页
              </button>
            </div>
          )
        }
      >
        {result.loading && !result.data ? (
          <div className="trace__loading">
            <Skeleton height={30} />
            <Skeleton height={30} />
            <Skeleton height={30} />
          </div>
        ) : result.error && !result.data ? (
          <EmptyState
            tone="critical"
            title="无法获取历史数据"
            description={result.error}
            action={
              <button type="button" className="btn" onClick={result.refresh}>
                重新加载
              </button>
            }
          />
        ) : items.length === 0 ? (
          <EmptyState
            title="没有符合条件的历史事件"
            description="可以放宽时间范围或清除部分筛选条件后重试。"
            action={
              <button type="button" className="btn" onClick={resetFilters}>
                重置筛选
              </button>
            }
          />
        ) : (
          <>
            <div className="trace__table-wrap">
              <table className="data-table trace__table">
                <thead>
                  <tr>
                    <th>事件编号</th>
                    <th>时间</th>
                    <th>设备</th>
                    <th>设备 IP</th>
                    <th>位置</th>
                    <th>异常类型</th>
                    <th>等级</th>
                    <th>测距</th>
                    <th>视觉</th>
                    <th>联合结果</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr
                      key={item.id}
                      className={`trace__row trace__row--${item.level}`}
                      onClick={() => setDetailId(item.id)}
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          setDetailId(item.id)
                        }
                      }}
                    >
                      <td className="mono trace__cell-code">{item.code}</td>
                      <td className="mono">{formatTime(item.ts)}</td>
                      <td>{item.device_name}</td>
                      <td className="mono">{item.device_ip}</td>
                      <td>{item.location}</td>
                      <td>{item.event_type_text}</td>
                      <td>
                        <Badge tone={LEVEL_TONE[item.level]} solid={item.level === 'critical'} dot>
                          {item.level_text}
                        </Badge>
                      </td>
                      <td className="mono">
                        {item.radar_value !== null ? `${item.radar_value.toFixed(3)} m` : '—'}
                      </td>
                      <td>{item.vision_result}</td>
                      <td>{item.fusion_result}</td>
                      <td>
                        <Badge tone={item.status === 'archived' ? 'idle' : 'primary'}>
                          {item.status_text}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="trace__foot">
              本页 {items.length} 条 / 共 {total} 条 · 数据来源于平台统一存储的历史事件记录
            </div>
          </>
        )}
      </Panel>

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
