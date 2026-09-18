/**
 * 视频遥测自检（前端）。
 *
 * 目的：前端 `videoTelemetry.ts` 与后端 `services/video_sync.py` 是同一套轨迹的
 * 两份实现。本文件用规格中给出的锚点值与整体单调性做校验，
 * 保证两边不会悄悄漂移。
 *
 * 运行方式（开发期手动调用，不进入生产构建路径）：
 *   在浏览器控制台执行
 *     const m = await import('/src/video/videoTelemetry.selftest.ts'); m.runVideoTelemetrySelfTest()
 *   或在测试接入 jest/vitest 后直接导入。
 *
 * 这些断言与 backend/tests/test_video_sync.py 的期望值一一对应：
 * 若后端改了轨迹而前端没跟上，这里会立即失败。
 */

import {
  BASELINE_DISTANCE,
  VIDEO_KEYFRAMES,
  VIDEO_SYNC_DURATION,
  clampVideoTime,
  interpolateKeyframes,
  resolveVideoTelemetry,
  samplesUpTo,
} from './videoTelemetry'

export interface SelfTestResult {
  passed: number
  failed: number
  failures: string[]
}

function approx(actual: number, expected: number, tolerance: number): boolean {
  return Math.abs(actual - expected) <= tolerance
}

/** 运行全部自检，返回通过/失败统计 */
export function runVideoTelemetrySelfTest(): SelfTestResult {
  const failures: string[] = []
  let passed = 0

  const check = (name: string, ok: boolean, detail = '') => {
    if (ok) {
      passed += 1
    } else {
      failures.push(`${name}${detail ? ` — ${detail}` : ''}`)
    }
  }

  // ---- 1. 关键帧与规格一致 ----
  const expectedKeyframes = [
    [0, 0.721, 18, 0.3, 1.0],
    [2, 0.706, 27, 0.37, 0.98],
    [4, 0.681, 43, 0.49, 0.95],
    [6, 0.651, 59, 0.61, 0.91],
    [8, 0.612, 76, 0.74, 0.86],
    [10, 0.582, 89, 0.83, 0.8],
  ]
  check('关键帧数量', VIDEO_KEYFRAMES.length === expectedKeyframes.length)
  expectedKeyframes.forEach(([t, d, r, c, s], i) => {
    const f = VIDEO_KEYFRAMES[i]
    check(
      `关键帧 ${i} (t=${t})`,
      f.t === t && f.distance === d && f.risk === r && f.coverage === c && f.speedRatio === s,
      JSON.stringify(f),
    )
  })

  // ---- 2. 状态序列必须是 normal → attention → warning → alarm ----
  const order = ['normal', 'attention', 'warning', 'alarm']
  const seen: string[] = []
  for (let i = 0; i <= 100; i += 1) {
    const state = resolveVideoTelemetry(i / 10).sim_state
    if (seen.length === 0 || seen[seen.length - 1] !== state) seen.push(state)
  }
  check('状态序列', JSON.stringify(seen) === JSON.stringify(order), seen.join(' → '))

  // ---- 3. 关键时间点 ----
  const t0 = resolveVideoTelemetry(0)
  check('t=0 normal', t0.sim_state === 'normal' && t0.vision_label === 'normal_conveying')
  check('t=0 基准距离', approx(t0.distance, BASELINE_DISTANCE, 0.01), String(t0.distance))

  const t2 = resolveVideoTelemetry(2)
  check('t=2 未进入预警', t2.risk_index < 55 && t2.distance > 0.7, String(t2.risk_index))

  const t5 = resolveVideoTelemetry(5)
  check('t=5 风险明显高于 t=2', t5.risk_index > t2.risk_index + 15)

  const t7 = resolveVideoTelemetry(7)
  check('t=7 warning', t7.sim_state === 'warning' && t7.fusion_verdict === 'warning')

  const t95 = resolveVideoTelemetry(9.5)
  check('t=9.5 alarm', t95.sim_state === 'alarm' && t95.risk_index >= 80)
  check('t=9.5 测距≈0.58', approx(t95.distance, 0.58, 0.02), String(t95.distance))

  // ---- 4. 插值锚点（与后端 interpolate_keyframes 对应）----
  const mid = interpolateKeyframes(5)
  check('t=5 距离插值', approx(mid.distance, (0.681 + 0.651) / 2, 1e-9), String(mid.distance))
  check('t=5 风险插值', approx(mid.risk, (43 + 59) / 2, 1e-9), String(mid.risk))

  // ---- 5. 整体趋势单调 ----
  const series = []
  for (let i = 0; i <= 20; i += 1) series.push(resolveVideoTelemetry(i * 0.5))

  const distances = series.map((x) => x.distance)
  const risks = series.map((x) => x.risk_index)
  const coverages = series.map((x) => x.coverage)
  const speeds = series.map((x) => x.conveyor_speed)

  check('测距整体下降', distances.every((v, i) => i === 0 || v <= distances[i - 1] + 1e-9))
  check('风险整体上升', risks.every((v, i) => i === 0 || v >= risks[i - 1] - 1e-9))
  check('覆盖率整体上升', coverages.every((v, i) => i === 0 || v >= coverages[i - 1] - 1e-9))
  check('输送速度整体下降', speeds.every((v, i) => i === 0 || v <= speeds[i - 1] + 1e-9))
  check('整段降幅 > 12cm', distances[0] - distances[distances.length - 1] > 0.12)

  // ---- 6. 无跳变 ----
  let maxStep = 0
  let prev = resolveVideoTelemetry(0)
  for (let i = 1; i <= 200; i += 1) {
    const cur = resolveVideoTelemetry(i * 0.05)
    maxStep = Math.max(maxStep, Math.abs(cur.distance - prev.distance))
    prev = cur
  }
  check('单步跳变 < 6mm', maxStep < 0.006, String(maxStep))

  // ---- 7. 微扰范围 ±3mm ----
  let maxJitter = 0
  for (let i = 0; i <= 100; i += 1) {
    const t = i / 10
    maxJitter = Math.max(
      maxJitter,
      Math.abs(resolveVideoTelemetry(t).distance - interpolateKeyframes(t).distance),
    )
  }
  check('微扰 ≤ 3mm', maxJitter <= 0.003, String(maxJitter))

  // ---- 8. 确定性：同一 t 反复解算完全一致 ----
  const repeatOk = [0, 1.7, 3.3, 5, 6.8, 8.4, 9.9, 10].every((t) => {
    const a = resolveVideoTelemetry(t)
    return (
      a.distance === resolveVideoTelemetry(t).distance &&
      a.risk_index === resolveVideoTelemetry(t).risk_index &&
      a.sim_state === resolveVideoTelemetry(t).sim_state
    )
  })
  check('同 t 结果可复现', repeatOk)

  // ---- 9. 越界 clamp ----
  check('负值 clamp', clampVideoTime(-5) === 0 && resolveVideoTelemetry(-5).t === 0)
  check('超界 clamp', clampVideoTime(999) === VIDEO_SYNC_DURATION)
  check('NaN 安全', clampVideoTime(Number.NaN) === 0 && resolveVideoTelemetry(Number.NaN).sim_state === 'normal')

  // ---- 10. 循环复位 ----
  check('终点 alarm', resolveVideoTelemetry(VIDEO_SYNC_DURATION).sim_state === 'alarm')
  check('循环回 normal', resolveVideoTelemetry(0).sim_state === 'normal')

  // ---- 11. 趋势序列只覆盖当前轮次 ----
  const longCycle = samplesUpTo(9.9)
  const afterLoop = samplesUpTo(0.4)
  check('循环后序列重置', afterLoop.length < longCycle.length / 10)
  check('序列末端等于当前值', (() => {
    const pts = samplesUpTo(5)
    const cur = resolveVideoTelemetry(5)
    return pts[pts.length - 1].distance === cur.distance && pts[pts.length - 1].risk_index === cur.risk_index
  })())

  // ---- 12. 温湿度稳定 ----
  const envOk = series.every((x) => x.temperature >= 23 && x.temperature <= 25 && x.humidity >= 51 && x.humidity <= 58)
  check('温湿度平稳', envOk)

  return { passed, failed: failures.length, failures }
}
