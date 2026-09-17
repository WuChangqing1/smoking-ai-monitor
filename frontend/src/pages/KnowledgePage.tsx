/**
 * 知识库页 —— 历史异常处理经验库。
 *
 * 数据来自 SQLite（GET /api/knowledge），种子记录按真实生产记录格式撰写，
 * 其中 3 条直接取自原始验收资料（2025-05-19 加料堵料、2025-05-17 钉钉报警记录）。
 *
 * 页面提供：关键词全文检索、异常类型筛选、事件详情展开。
 * 详情按"异常前兆 → 人工审核 → 处理措施 → 结果 → 预防建议"组织，
 * 因为这才是经验库真正的复用价值所在。
 */

import { useEffect, useMemo, useState } from 'react'
import Panel from '../components/Panel'
import { Badge, EmptyState, Skeleton } from '../components/Badge'
import { IconKnowledge, IconSearch } from '../components/icons'
import { api } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import type { KnowledgeEvent } from '../types'
import './KnowledgePage.css'

export default function KnowledgePage() {
  const [keyword, setKeyword] = useState('')
  const [eventType, setEventType] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)

  const types = useFetch(api.knowledgeTypes, {})

  /** 关键词输入做轻量防抖，避免每敲一个字就请求一次 */
  const [debouncedKeyword, setDebouncedKeyword] = useState('')
  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedKeyword(keyword.trim()), 280)
    return () => window.clearTimeout(timer)
  }, [keyword])

  const list = useFetch(
    () =>
      api.knowledge({
        keyword: debouncedKeyword || undefined,
        event_type: eventType || undefined,
      }),
    {},
  )

  const events = list.data ?? []

  /** 按异常类型分组统计，用于筛选条展示数量 */
  const typeCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const e of events) {
      counts.set(e.event_type, (counts.get(e.event_type) ?? 0) + 1)
    }
    return counts
  }, [events])

  return (
    <div className="knowledge">
      {/* ---- 检索条 ---- */}
      <div className="knowledge__bar">
        <label className="knowledge__search">
          <IconSearch size={14} />
          <input
            type="search"
            value={keyword}
            placeholder="搜索事件编号、位置、异常描述、处理措施或预防建议…"
            onChange={(e) => setKeyword(e.target.value)}
          />
          {keyword && (
            <button
              type="button"
              className="knowledge__clear"
              onClick={() => setKeyword('')}
              aria-label="清空搜索"
            >
              ✕
            </button>
          )}
        </label>

        <div className="knowledge__types">
          <button
            type="button"
            className={`knowledge__type${eventType === '' ? ' is-active' : ''}`}
            onClick={() => setEventType('')}
          >
            全部
          </button>
          {(types.data ?? []).map((type) => (
            <button
              key={type}
              type="button"
              className={`knowledge__type${eventType === type ? ' is-active' : ''}`}
              onClick={() => setEventType(type)}
              title={`按「${type}」筛选`}
            >
              {type}
              {typeCounts.has(type) && (
                <span className="knowledge__type-count">{typeCounts.get(type)}</span>
              )}
            </button>
          ))}
        </div>

        <span className="knowledge__count">
          共 <strong>{events.length}</strong> 条经验记录
        </span>
      </div>

      {list.error && list.data && (
        <div className="knowledge__stale">
          数据更新暂时中断，当前展示为最后一次成功获取的数据。
        </div>
      )}

      {/* ---- 列表 ---- */}
      <Panel
        title="历史异常处理经验"
        icon={<IconKnowledge size={14} />}
        description="点击任意条目展开完整记录，可作为同类异常的处置参考"
      >
        {list.loading && !list.data ? (
          <div className="knowledge__loading">
            <Skeleton height={60} />
            <Skeleton height={60} />
            <Skeleton height={60} />
          </div>
        ) : list.error && !list.data ? (
          <EmptyState
            tone="critical"
            title="无法读取知识库"
            description={list.error}
            action={
              <button type="button" className="btn" onClick={list.refresh}>
                重新加载
              </button>
            }
          />
        ) : events.length === 0 ? (
          <EmptyState
            title="没有匹配的经验记录"
            description="可以尝试更换关键词，或清除异常类型筛选。"
            action={
              <button
                type="button"
                className="btn"
                onClick={() => {
                  setKeyword('')
                  setEventType('')
                }}
              >
                清除筛选
              </button>
            }
          />
        ) : (
          <ul className="knowledge__list">
            {events.map((event) => (
              <KnowledgeItem
                key={event.event_code}
                event={event}
                open={expanded === event.event_code}
                onToggle={() =>
                  setExpanded((cur) => (cur === event.event_code ? null : event.event_code))
                }
              />
            ))}
          </ul>
        )}
      </Panel>
    </div>
  )
}

/** 单条经验记录 */
function KnowledgeItem({
  event,
  open,
  onToggle,
}: {
  event: KnowledgeEvent
  open: boolean
  onToggle: () => void
}) {
  return (
    <li className={`knowledge__item${open ? ' is-open' : ''}`}>
      <button type="button" className="knowledge__head" onClick={onToggle} aria-expanded={open}>
        <span className={`knowledge__caret${open ? ' is-open' : ''}`} aria-hidden="true">
          ›
        </span>

        <span className="knowledge__head-main">
          <span className="knowledge__code">{event.event_code}</span>
          <span className="knowledge__meta">
            {event.timestamp} · {event.location} · {event.device_id}
          </span>
        </span>

        <span className="knowledge__head-right">
          <Badge
            tone={
              event.event_type === '物料堆积'
                ? 'warning'
                : event.event_type === '人员进入检测区'
                  ? 'info'
                  : 'idle'
            }
          >
            {event.event_type}
          </Badge>
        </span>
      </button>

      {open && (
        <div className="knowledge__body">
          <div className="knowledge__cols">
            <Field label="雷达记录" text={event.radar_summary} />
            <Field label="视觉记录" text={event.vision_summary} />
            <Field label="环境记录" text={event.environment_summary} />
          </div>

          <div className="knowledge__highlight">
            <span className="knowledge__highlight-label">异常前兆模式</span>
            <p className="knowledge__highlight-text">{event.pre_event_pattern}</p>
          </div>

          <div className="knowledge__cols">
            <Field label="人工审核" text={event.operator_review} />
            <Field label="处理措施" text={event.action_taken} />
            <Field label="处理结果" text={event.result} tone="normal" />
          </div>

          <div className="knowledge__preventive">
            <span className="knowledge__preventive-label">预防建议</span>
            <p className="knowledge__preventive-text">{event.preventive_suggestion}</p>
          </div>
        </div>
      )}
    </li>
  )
}

function Field({
  label,
  text,
  tone = 'default',
}: {
  label: string
  text: string
  tone?: 'default' | 'normal'
}) {
  return (
    <div className={`knowledge__field knowledge__field--${tone}`}>
      <span className="knowledge__field-label">{label}</span>
      <p className="knowledge__field-text">{text}</p>
    </div>
  )
}
