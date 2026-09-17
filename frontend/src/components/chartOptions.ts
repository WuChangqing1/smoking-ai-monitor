/**
 * 趋势图配置构造器。
 *
 * 图表 option 由这些纯函数生成，页面只负责把实时数据窗口传进来。
 * ECharts 实例本身由 <Chart> 组件持有，配置变化只调用 setOption，
 * 不会 destroy / recreate，因此滚动更新是平滑的。
 *
 * 数据窗口长度由调用方控制（只保留最近 60~180 点），杜绝无限增长。
 */

import type { EChartsCoreOption } from 'echarts/core'
import type { RealtimeSample } from '../types'
import { CHART_COLORS, areaGradient, baseGrid, baseTooltip, baseXAxis, baseYAxis } from './Chart'

/** 主监控点基准距离 (m)，与后端一致 */
export const BASELINE_DISTANCE = 0.72
/** 报警阈值 (m)，取自原始资料中的真实报警值 */
export const ALARM_THRESHOLD = 0.58

/**
 * 雷达距离趋势图。
 *
 * 标注：当前值、基准值（虚线）、报警阈值（红色虚线）。
 * 刻意朴素：不做渐变彩虹，只用一个主色 + 两条参考线。
 */
export function radarDistanceOption(
  samples: RealtimeSample[],
  current: number | null,
): EChartsCoreOption {
  const labels = samples.map((s) => s.label)
  const values = samples.map((s) => s.radar_filtered)

  return {
    grid: baseGrid({ top: 16, bottom: 2, left: 2, right: 10 }),
    tooltip: baseTooltip({
      valueFormatter: (v: unknown) => (typeof v === 'number' ? `${v.toFixed(3)} m` : '—'),
    }),
    xAxis: baseXAxis({ data: labels }),
    yAxis: baseYAxis({
      min: 0.5,
      max: 0.8,
      // 距离越小风险越高，Y 轴刻度保留 2 位小数
      axisLabel: { color: CHART_COLORS.axis, fontSize: 10, formatter: (v: number) => v.toFixed(2) },
    }),
    series: [
      {
        name: '雷达测距',
        type: 'line',
        data: values,
        smooth: 0.2,
        showSymbol: false,
        lineStyle: { width: 1.8, color: CHART_COLORS.primary },
        itemStyle: { color: CHART_COLORS.primary },
        areaStyle: { color: areaGradient(CHART_COLORS.primary, 0.16) },
        markLine: {
          silent: true,
          symbol: 'none',
          label: {
            position: 'insideEndTop',
            fontSize: 10,
            color: CHART_COLORS.textSub,
            formatter: (p: { name?: string }) => p.name ?? '',
          },
          data: [
            {
              name: `基准 ${BASELINE_DISTANCE.toFixed(2)}`,
              yAxis: BASELINE_DISTANCE,
              lineStyle: { color: CHART_COLORS.info, type: 'dashed', width: 1 },
            },
            {
              name: `报警 ${ALARM_THRESHOLD.toFixed(2)}`,
              yAxis: ALARM_THRESHOLD,
              lineStyle: { color: CHART_COLORS.critical, type: 'dashed', width: 1 },
              label: { color: CHART_COLORS.critical },
            },
          ],
        },
        // 当前值用最后一个点标记出来，和状态卡上的读数对应
        markPoint:
          current !== null && values.length > 0
            ? {
                symbol: 'circle',
                symbolSize: 7,
                data: [{ coord: [labels.length - 1, values[values.length - 1]], value: current }],
                itemStyle: { color: CHART_COLORS.primary, borderColor: '#fff', borderWidth: 1.5 },
                label: { show: false },
              }
            : undefined,
      },
    ],
  }
}

/** 风险等级 → 曲线颜色。颜色跟随等级变化，而不是彩虹渐变。 */
function riskColor(level: string): string {
  switch (level) {
    case 'critical':
      return CHART_COLORS.critical
    case 'high':
      return CHART_COLORS.warning
    case 'medium':
      return CHART_COLORS.info
    default:
      return CHART_COLORS.normal
  }
}

/**
 * 堆积风险趋势图。Y 轴固定 0~100%。
 *
 * 颜色按当前风险等级变化，用来直观传达严重程度；
 * 参考线标注 30/55/80 三个等级分界。
 */
export function riskTrendOption(
  samples: RealtimeSample[],
  level: string,
): EChartsCoreOption {
  const labels = samples.map((s) => s.label)
  const values = samples.map((s) => s.risk_index)
  const color = riskColor(level)

  return {
    grid: baseGrid({ top: 16, bottom: 2, left: 2, right: 10 }),
    tooltip: baseTooltip({
      valueFormatter: (v: unknown) => (typeof v === 'number' ? `${v.toFixed(1)}%` : '—'),
    }),
    xAxis: baseXAxis({ data: labels }),
    yAxis: baseYAxis({
      min: 0,
      max: 100,
      axisLabel: { color: CHART_COLORS.axis, fontSize: 10, formatter: '{value}%' },
    }),
    series: [
      {
        name: '堆积风险',
        type: 'line',
        data: values,
        smooth: 0.25,
        showSymbol: false,
        lineStyle: { width: 1.8, color },
        itemStyle: { color },
        areaStyle: { color: areaGradient(color, 0.2) },
        markLine: {
          silent: true,
          symbol: 'none',
          label: { show: false },
          data: [
            { yAxis: 30, lineStyle: { color: '#dfe4e8', type: 'dashed', width: 1 } },
            { yAxis: 55, lineStyle: { color: '#ecd9bd', type: 'dashed', width: 1 } },
            { yAxis: 80, lineStyle: { color: '#e8b4b4', type: 'dashed', width: 1 } },
          ],
        },
      },
    ],
  }
}

/**
 * 预测曲线：实测段（实线）+ 预测段（虚线）。
 *
 * 用于智能预警页；两段共用一个 X 轴标签序列，保证在"当前"处首尾相接。
 */
export function forecastOption(
  curve: Array<{ label: string; actual: number | null; predicted: number | null }>,
  level: string,
): EChartsCoreOption {
  const labels = curve.map((p) => p.label)
  const color = riskColor(level)

  return {
    grid: baseGrid({ top: 20, bottom: 2, left: 2, right: 12 }),
    tooltip: baseTooltip({
      valueFormatter: (v: unknown) => (typeof v === 'number' ? `${v.toFixed(1)}%` : '—'),
    }),
    legend: {
      right: 0,
      top: 0,
      itemWidth: 12,
      itemHeight: 8,
      textStyle: { color: CHART_COLORS.textSub, fontSize: 11 },
      data: ['实测风险', '预测风险'],
    },
    xAxis: baseXAxis({ data: labels, boundaryGap: false }),
    yAxis: baseYAxis({
      min: 0,
      max: 100,
      axisLabel: { color: CHART_COLORS.axis, fontSize: 10, formatter: '{value}%' },
    }),
    series: [
      {
        name: '实测风险',
        type: 'line',
        data: curve.map((p) => p.actual),
        smooth: 0.25,
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.8, color },
        itemStyle: { color },
        areaStyle: { color: areaGradient(color, 0.16) },
      },
      {
        name: '预测风险',
        type: 'line',
        data: curve.map((p) => p.predicted),
        smooth: 0.25,
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.8, color, type: 'dashed' },
        itemStyle: { color },
      },
    ],
  }
}
