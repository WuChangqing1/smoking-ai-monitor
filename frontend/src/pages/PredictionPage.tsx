/**
 * 智能预警页 —— 新平台相对原项目最重要的升级点。
 *
 * 核心表达：从「异常发生后才报警」升级为「趋势预测 + 提前预警」。
 * 因此页面刻意做到三件事：
 *   1. 明确给出预测区间（未来 30 分钟）与预测置信度；
 *   2. 把"依据"逐条摊开 —— 雷达、视觉、输送、环境、知识库各一条，
 *      让评委看到结论是怎么来的，而不是一个孤立的百分比；
 *   3. 措辞保持概率化（风险上升 / 建议关注 / 建议检查），
 *      绝不写成"30 分钟后一定堵料"。
 *
 * 数据来自 GET /api/prediction（约 3 s 轮询），所有结论由后端计算。
 */

import { useEffect, useMemo, useState } from 'react'
import Panel from '../components/Panel'
import Chart from '../components/Chart'
import AIAnalysisPanel from '../components/AIAnalysisPanel'
import { forecastOption } from '../components/chartOptions'
import { Badge, EmptyState, SectionTitle, Skeleton } from '../components/Badge'
import { IconInfo, IconKnowledge, IconPredict, IconRadar } from '../components/icons'
import { api } from '../api/client'
import { useFetch } from '../hooks/useFetch'
import { useVideoSync } from '../video/VideoSyncContext'
import { buildSyncedPrediction } from '../video/syncedTelemetry'
import type { AIAnalysis, RiskLevel } from '../types'
import './PredictionPage.css'

const LEVEL_TONE: Record<RiskLevel, 'normal' | 'info' | 'warning' | 'critical'> = {
  low: 'normal',
  medium: 'info',
  high: 'warning',
  critical: 'critical',
}

/** 预警依据来源 → 中文名 + 图标色调 */
const SOURCE_LABEL: Record<string, string> = {
  radar: '雷达测距',
  vision: '视觉识别',
  conveyor: '输送工况',
  environment: '环境参数',
  knowledge: '历史经验',
}

const TREND_TONE: Record<string, 'normal' | 'info' | 'warning' | 'critical'> = {
  stable: 'normal',
  rising: 'warning',
  rising_fast: 'critical',
  falling: 'info',
}

/** 相似度 → 展示色调 */
function similarityTone(similarity: number): 'normal' | 'info' | 'warning' {
  if (similarity >= 0.8) return 'warning'
  if (similarity >= 0.6) return 'info'
  return 'normal'
}

export default function PredictionPage() {
  const polled = useFetch(api.prediction, { intervalMs: 3000 })
  const sync = useVideoSync()

  /**
   * 视频同步模式下，预测由当前遥测与本轮轨迹派生，
   * 从而与画面阶段严格一致（normal / attention / warning / alarm 各自的结论不同）。
   */
  const syncedPrediction = useMemo(() => {
    if (!sync || sync.runMode !== 'video_sync' || !sync.available) return null
    return buildSyncedPrediction(sync.telemetry, sync.trend)
  }, [sync])

  const prediction = syncedPrediction
    ? { data: syncedPrediction, error: null, loading: false, refresh: polled.refresh }
    : polled

  const data = prediction.data

  /**
   * 当前分析阶段：由风险等级映射。
   *
   * 只有 warning / alarm 才请求 AI 分析 —— normal / attention 一律不发请求，
   * 否则前端轮询会把模型 Token 烧光。
   */
  const currentLevel = data?.forecast.level ?? 'low'
  const analyzableStage: 'warning' | 'alarm' | null =
    currentLevel === 'high' ? 'warning' : currentLevel === 'critical' ? 'alarm' : null

  const [aiAnalysis, setAiAnalysis] = useState<AIAnalysis | null>(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiError, setAiError] = useState<string | null>(null)

  useEffect(() => {
    if (!analyzableStage) {
      // 非预警阶段：清掉旧结果，不请求模型
      setAiAnalysis(null)
      setAiError(null)
      return
    }
    let cancelled = false
    setAiLoading(true)
    setAiError(null)
    api
      .aiCurrentAnalysis(analyzableStage)
      .then((result) => {
        if (!cancelled) setAiAnalysis(result)
      })
      .catch(() => {
        if (!cancelled) setAiError('AI 分析暂不可用')
      })
      .finally(() => {
        if (!cancelled) setAiLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [analyzableStage])

  const chartOption = useMemo(
    () => forecastOption(data?.curve ?? [], data?.forecast.level ?? 'low'),
    [data?.curve, data?.forecast.level],
  )

  if (!data) {
    return (
      <Panel title="智能预警" icon={<IconPredict size={14} />}>
        {prediction.error ? (
          <EmptyState
            tone="critical"
            title="预测数据不可用"
            description={prediction.error}
            action={
              <button type="button" className="btn" onClick={prediction.refresh}>
                重新加载
              </button>
            }
          />
        ) : (
          <div className="predict__loading">
            <Skeleton height={22} width="36%" />
            <Skeleton height={200} />
          </div>
        )}
      </Panel>
    )
  }

  const { current, forecast, evidence, suggestions, similar_events, curve } = data
  const rising = forecast.change === 'rising' || forecast.change === 'rising_fast'

  return (
    <div className="predict">
      {prediction.error && (
        <div className="predict__stale">
          数据更新暂时中断，当前展示为最后一次成功获取的预测结果。
        </div>
      )}

      {/* ================= 顶部：当前 vs 预测 ================= */}
      <div className="predict__hero">
        <Panel
          title="当前风险"
          icon={<IconRadar size={14} />}
        >
          <div className="predict__big">
            <span className={`predict__big-value is-${LEVEL_TONE[current.level]}`}>
              {Number(current.index).toFixed(1)}
            </span>
            <span className="predict__big-unit">%</span>
          </div>
          <div className="predict__big-tags">
            <Badge tone={LEVEL_TONE[current.level]} dot>
              {current.level_text}
            </Badge>
          </div>
        </Panel>

        <div className="predict__arrow" aria-hidden="true">
          <span className="predict__arrow-line" />
          <span className="predict__arrow-label">未来 {data.horizon_minutes} 分钟</span>
          <span className="predict__arrow-tip">→</span>
        </div>

        <Panel
          title="预测风险"
          icon={<IconPredict size={14} />}
          tone={LEVEL_TONE[forecast.level] === 'critical' ? 'critical' : 'primary'}
        >
          <div className="predict__big">
            <span className={`predict__big-value is-${LEVEL_TONE[forecast.level]}`}>
              {Number(forecast.risk_index).toFixed(1)}
            </span>
            <span className="predict__big-unit">%</span>
          </div>
          <div className="predict__big-tags">
            <Badge tone={LEVEL_TONE[forecast.level]} dot>
              {forecast.level_text}
            </Badge>
            <Badge tone={TREND_TONE[forecast.change] ?? 'info'}>
              {forecast.change_text}
            </Badge>
            <Badge tone="idle">
              置信度 {(Number(forecast.confidence) * 100).toFixed(0)}%
            </Badge>
          </div>
        </Panel>
      </div>

      {/* ================= 预测曲线 ================= */}
      <Panel
        title={`未来 ${data.horizon_minutes} 分钟风险预测`}
        icon={<IconPredict size={14} />}
        description="实线为最近实测风险，虚线为趋势外推的预测风险"
        extra={
          <Badge tone={TREND_TONE[forecast.change] ?? 'info'}>
            风险变化：{forecast.change_text}
          </Badge>
        }
      >
        <Chart option={chartOption} height={260} pointCount={curve.length} emptyText="暂无预测数据" />

        <p className="predict__disclaimer">
          <IconInfo size={12} />
          预测为概率性判断，存在不确定性
        </p>
      </Panel>

      {/* ================= 预警依据 + 相似历史 ================= */}
      <div className="grid grid--2 predict__mid">
        <Panel
          title="预警依据"
          icon={<IconInfo size={14} />}
        >
          <ul className="predict__evidence">
            {evidence.map((item, index) => (
              <li key={`${item.source}-${index}`} className="predict__evidence-item">
                <span className={`predict__evidence-src is-${item.source}`}>
                  {SOURCE_LABEL[item.source] ?? item.source}
                </span>
                <span className="predict__evidence-text">{item.text}</span>
              </li>
            ))}
          </ul>

          <SectionTitle>建议措施</SectionTitle>
          <ul className="predict__suggestions">
            {suggestions.map((text, index) => (
              <li key={index}>{text}</li>
            ))}
          </ul>
        </Panel>

        <Panel
          title="相似历史事件"
          icon={<IconKnowledge size={14} />}
          bodyClassName="predict__similar-body"
          extra={
            <button
              type="button"
              className="predict__link"
              onClick={() => {
                window.location.hash = '#/knowledge'
              }}
            >
              查看知识库
            </button>
          }
        >
          <ul className="predict__similar">
            {similar_events.map((event) => (
              <li key={event.event_code} className="predict__similar-item">
                <div className="predict__similar-head">
                  <span className="predict__similar-code">{event.event_code}</span>
                  <Badge tone={similarityTone(event.similarity)}>
                    相似度 {(event.similarity * 100).toFixed(0)}%
                  </Badge>
                </div>
                <div className="predict__similar-meta">
                  {event.location} · {event.event_type}
                </div>
                <p className="predict__similar-result">{event.result}</p>
              </li>
            ))}
          </ul>

          {rising && (
            <p className="predict__similar-hint">
              当前特征与上述历史异常的前兆模式相近，建议提前关注对应输送段。
            </p>
          )}
        </Panel>
      </div>

      {/* ================= AI 辅助分析 =================
          只在预警 / 报警阶段出现；正常与关注阶段不请求模型。
          同一阶段重复进入会复用后端缓存，不会重复消耗 Token。 */}
      {analyzableStage && (
        <Panel title="AI 辅助分析" icon={<IconInfo size={14} />}>
          <AIAnalysisPanel
            analysis={aiAnalysis}
            loading={aiLoading}
            error={aiError}
            title={analyzableStage === 'alarm' ? '报警辅助分析' : '预警辅助分析'}
          />
        </Panel>
      )}
    </div>
  )
}
