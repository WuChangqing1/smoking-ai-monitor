/**
 * 筛选条 —— 数据溯源页使用。
 *
 * 通用的「标签 + 控件」行式布局：桌面端一行排开，窄屏自动折行。
 * 不做折叠面板，工业系统的筛选条件应当一眼可见。
 */

import type { ReactNode } from 'react'
import './FilterBar.css'

export interface FilterField {
  key: string
  label: string
  /** 文本/日期用 input，枚举用 select */
  type: 'text' | 'date' | 'select'
  value: string
  placeholder?: string
  options?: Array<{ value: string; label: string }>
  onChange: (value: string) => void
}

interface FilterBarProps {
  fields: FilterField[]
  onReset?: () => void
  /** 右侧补充信息，例如"共 N 条" */
  extra?: ReactNode
}

export default function FilterBar({ fields, onReset, extra }: FilterBarProps) {
  const hasValue = fields.some((f) => f.value !== '')

  return (
    <div className="filter-bar">
      <div className="filter-bar__fields">
        {fields.map((field) => (
          <label className="filter-bar__field" key={field.key}>
            <span className="filter-bar__label">{field.label}</span>

            {field.type === 'select' ? (
              <select
                className="filter-bar__control"
                value={field.value}
                onChange={(e) => field.onChange(e.target.value)}
              >
                <option value="">全部</option>
                {(field.options ?? []).map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                className="filter-bar__control"
                type={field.type}
                value={field.value}
                placeholder={field.placeholder}
                onChange={(e) => field.onChange(e.target.value)}
              />
            )}
          </label>
        ))}
      </div>

      <div className="filter-bar__actions">
        {extra && <span className="filter-bar__extra">{extra}</span>}
        {onReset && (
          <button
            type="button"
            className="filter-bar__reset"
            onClick={onReset}
            disabled={!hasValue}
          >
            重置筛选
          </button>
        )}
      </div>
    </div>
  )
}
