/**
 * ECharts 封装。
 *
 * 为什么要封装：
 *  - 统一工业风主题（细网格、克制的配色、等宽数字），避免每个页面各写一份 option；
 *  - 统一处理自适应：窗口尺寸变化时 resize；
 *  - 统一处理空数据：没有数据点时显示占位而不是空白坐标系；
 *  - 图表数据由调用方控制长度（只保留最近 60~120 点），杜绝无限增长。
 */

import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsCoreOption } from 'echarts/core'
import { EmptyState } from './Badge'
import './Chart.css'

echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  MarkAreaComponent,
  TitleComponent,
  CanvasRenderer,
])

export interface ChartProps {
  option: EChartsCoreOption
  height?: number | string
  /** 数据点数量，为 0 时展示空状态 */
  pointCount?: number
  emptyText?: string
  className?: string
}

export default function Chart({
  option,
  height = 200,
  pointCount,
  emptyText = '暂无数据',
  className = '',
}: ChartProps) {
  const hostRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  // 初始化与销毁
  useEffect(() => {
    const host = hostRef.current
    if (!host) return

    const instance = echarts.init(host, undefined, { renderer: 'canvas' })
    chartRef.current = instance

    const onResize = () => instance.resize()
    window.addEventListener('resize', onResize)

    // 侧栏折叠等布局变化不会触发 window.resize，用 ResizeObserver 兜住
    const observer = new ResizeObserver(() => instance.resize())
    observer.observe(host)

    return () => {
      window.removeEventListener('resize', onResize)
      observer.disconnect()
      instance.dispose()
      chartRef.current = null
    }
  }, [])

  // 更新配置
  useEffect(() => {
    const instance = chartRef.current
    if (!instance) return
    // notMerge=true：避免旧 series 残留（例如通道数变化时）
    instance.setOption(option, true)
  }, [option])

  const isEmpty = pointCount !== undefined && pointCount === 0

  return (
    <div className={`chart ${className}`.trim()} style={{ height }}>
      {isEmpty ? (
        <div className="chart__empty">
          <EmptyState title={emptyText} description="等待后端实时数据接入后自动绘制。" />
        </div>
      ) : (
        <div ref={hostRef} className="chart__canvas" />
      )}
    </div>
  )
}

/* ==========================================================================
   工业风图表主题工具
   ========================================================================== */

/** 平台统一色板（与 tokens.css 语义一致） */
export const CHART_COLORS = {
  primary: '#0f8a4d',
  normal: '#1a9c5b',
  warning: '#d97706',
  critical: '#c62828',
  info: '#4a6b8a',
  axis: '#8a949e',
  split: '#eef1f3',
  text: '#232a30',
  textSub: '#5b666f',
} as const

/** 统一的网格与坐标轴配置 */
export function baseGrid(overrides: Record<string, unknown> = {}) {
  return {
    left: 8,
    right: 12,
    top: 18,
    bottom: 4,
    containLabel: true,
    ...overrides,
  }
}

export function baseXAxis(overrides: Record<string, unknown> = {}) {
  return {
    type: 'category' as const,
    boundaryGap: false,
    axisLine: { lineStyle: { color: '#dfe4e8' } },
    axisTick: { show: false },
    axisLabel: {
      color: CHART_COLORS.axis,
      fontSize: 10,
      hideOverlap: true,
      margin: 8,
    },
    splitLine: { show: false },
    ...overrides,
  }
}

export function baseYAxis(overrides: Record<string, unknown> = {}) {
  return {
    type: 'value' as const,
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: CHART_COLORS.axis, fontSize: 10, margin: 6 },
    splitLine: { lineStyle: { color: CHART_COLORS.split, type: 'solid' as const } },
    ...overrides,
  }
}

export function baseTooltip(overrides: Record<string, unknown> = {}) {
  return {
    trigger: 'axis' as const,
    confine: true,
    backgroundColor: 'rgba(255,255,255,0.97)',
    borderColor: '#c6ced6',
    borderWidth: 1,
    padding: [7, 10],
    textStyle: { color: CHART_COLORS.text, fontSize: 12 },
    axisPointer: {
      type: 'line' as const,
      lineStyle: { color: '#c6ced6', type: 'dashed' as const },
    },
    ...overrides,
  }
}

/** 面积渐变：用于风险趋势这类需要强调"量"的曲线 */
export function areaGradient(color: string, topOpacity = 0.22) {
  return new echarts.graphic.LinearGradient(0, 0, 0, 1, [
    { offset: 0, color: hexToRgba(color, topOpacity) },
    { offset: 1, color: hexToRgba(color, 0.01) },
  ])
}

function hexToRgba(hex: string, alpha: number): string {
  const value = hex.replace('#', '')
  const r = parseInt(value.slice(0, 2), 16)
  const g = parseInt(value.slice(2, 4), 16)
  const b = parseInt(value.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}
