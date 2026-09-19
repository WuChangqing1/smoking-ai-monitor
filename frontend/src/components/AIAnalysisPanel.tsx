/**
 * AI 辅助分析展示块。
 *
 * 用途：报警详情、智能预警页共用同一套呈现。
 *
 * 安全约定
 * --------
 * 模型输出属于**非可信外部文本**，这里一律用普通文本渲染，
 * 不使用 innerHTML / dangerouslySetInnerHTML —— 避免 XSS。
 *
 * 诚实约定
 * --------
 * 只有 ``source === 'llm'`` 才展示为模型结论；
 * 未启用 / 不可用时显示简短提示，**绝不伪造模型结果**。
 */

import { Badge } from './Badge'
import { IconInfo } from './icons'
import type { AIAnalysis } from '../types'
import './AIAnalysisPanel.css'

interface AIAnalysisPanelProps {
  /** 分析结果；null 表示尚未请求 */
  analysis: AIAnalysis | null
  loading?: boolean
  /** 标题，默认「AI 辅助分析」 */
  title?: string
  /** 出错时的补充说明（网络层错误，不同于模型服务不可用） */
  error?: string | null
  /** 重新分析回调；不传则不显示按钮 */
  onRefresh?: () => void
  refreshing?: boolean
}

/** 列表段落：空数组不渲染 */
function AnalysisList({ label, items }: { label: string; items: string[] }) {
  if (!items || items.length === 0) return null
  return (
    <div className="ai-analysis__group">
      <h5 className="ai-analysis__group-title">{label}</h5>
      <ul className="ai-analysis__list">
        {items.map((item, index) => (
          /* 纯文本渲染，不解析 Markdown / HTML */
          <li key={`${label}-${index}`}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

export default function AIAnalysisPanel({
  analysis,
  loading = false,
  title = 'AI 辅助分析',
  error = null,
  onRefresh,
  refreshing = false,
}: AIAnalysisPanelProps) {
  const ok = analysis?.status === 'ok' && analysis.source === 'llm'

  return (
    <div className="ai-analysis">
      <div className="ai-analysis__head">
        <h4 className="ai-analysis__title">{title}</h4>
        <div className="ai-analysis__head-right">
          {/* 只显示模型名，不显示 Base URL */}
          {ok && analysis.model && (
            <span className="ai-analysis__model">{analysis.model}</span>
          )}
          {ok && analysis.cached && <Badge tone="idle">缓存结果</Badge>}
          {onRefresh && (
            <button
              type="button"
              className="ai-analysis__refresh"
              onClick={onRefresh}
              disabled={refreshing}
            >
              {refreshing ? '分析中…' : '重新分析'}
            </button>
          )}
        </div>
      </div>

      {loading && <p className="ai-analysis__hint">正在生成分析…</p>}

      {!loading && !analysis && !error && (
        <p className="ai-analysis__hint">暂无分析</p>
      )}

      {!loading && error && <p className="ai-analysis__hint">{error}</p>}

      {!loading && analysis && !ok && (
        <p className="ai-analysis__hint">
          {analysis.error_message || 'AI 分析暂不可用'}
        </p>
      )}

      {!loading && ok && (
        <div className="ai-analysis__body">
          {analysis.summary && <p className="ai-analysis__summary">{analysis.summary}</p>}

          {/* 模型没按 JSON 输出时，按纯文本展示原文 */}
          {!analysis.structured && analysis.fallback_text && (
            <p className="ai-analysis__fallback">{analysis.fallback_text}</p>
          )}

          <AnalysisList label="可能原因" items={analysis.possible_causes} />
          <AnalysisList label="建议检查" items={analysis.recommended_checks} />
          <AnalysisList label="建议处置" items={analysis.recommended_actions} />
          <AnalysisList label="参考历史事件" items={analysis.related_cases} />
          <AnalysisList label="分析依据" items={analysis.evidence_basis} />

          {analysis.generated_at && (
            <p className="ai-analysis__meta">
              <IconInfo size={12} />
              生成于 {analysis.generated_at}
              {analysis.cached ? ' · 复用已有结果' : ''}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
