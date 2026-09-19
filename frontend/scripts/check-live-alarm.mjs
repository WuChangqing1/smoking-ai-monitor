/**
 * 当前报警派生自检（开发期诊断工具）。
 *
 * 验证 `buildCurrentAlarm` 在各时间点的行为：
 *   * normal / attention → 无临时报警
 *   * warning / alarm    → 生成临时报警，等级与阶段一致
 *
 * 用法（在 frontend 目录）：node scripts/check-live-alarm.mjs
 */

import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { build } from 'esbuild'

const __dirname = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(__dirname, '..')
const OUT_DIR = resolve(FRONTEND, '.live-alarm-tmp')

const ignoreCssPlugin = {
  name: 'ignore-css',
  setup(b) {
    b.onResolve({ filter: /\.css$/ }, (a) => ({ path: a.path, namespace: 'ignore-css' }))
    b.onLoad({ filter: /.*/, namespace: 'ignore-css' }, () => ({
      contents: 'export default {}',
      loader: 'js',
    }))
  },
}

mkdirSync(OUT_DIR, { recursive: true })

/* syncedTelemetry 只导入 telemetry 函数而不导出，这里建一个临时入口一起再导出 */
const entry = resolve(OUT_DIR, 'entry.ts')
writeFileSync(
  entry,
  `export { buildCurrentAlarm } from '${resolve(FRONTEND, 'src/video/syncedTelemetry').replace(/\\/g, '/')}'
export { resolveVideoTelemetry, samplesUpTo } from '${resolve(FRONTEND, 'src/video/videoTelemetry').replace(/\\/g, '/')}'
`,
)

const outFile = resolve(OUT_DIR, 'bundle.mjs')
await build({
  entryPoints: [entry],
  outfile: outFile,
  bundle: true,
  format: 'esm',
  platform: 'node',
  target: 'node18',
  plugins: [ignoreCssPlugin],
  logLevel: 'silent',
})

const { buildCurrentAlarm, resolveVideoTelemetry, samplesUpTo } = await import(
  pathToFileURL(outFile).href
)

console.log('=== 当前报警派生结果 ===')
console.log('  t(s)  阶段        临时报警   等级    编号')
console.log('  ' + '-'.repeat(58))

const failures = []
for (let i = 0; i <= 20; i += 1) {
  const t = i / 2
  const telemetry = resolveVideoTelemetry(t)
  const trend = samplesUpTo(t)
  const live = buildCurrentAlarm(telemetry, trend)
  const shouldExist = telemetry.sim_state === 'warning' || telemetry.sim_state === 'alarm'

  const exists = live !== null
  if (exists !== shouldExist) {
    failures.push(`t=${t} 阶段=${telemetry.sim_state} 期望${shouldExist ? '有' : '无'}临时报警，实际${exists ? '有' : '无'}`)
  }
  if (live) {
    const expectedLevel = telemetry.sim_state === 'alarm' ? 'critical' : 'warning'
    if (live.record.level !== expectedLevel) {
      failures.push(`t=${t} 等级应为 ${expectedLevel}，实际 ${live.record.level}`)
    }
    if (live.record.status !== 'pending') {
      failures.push(`t=${t} 状态应为 pending，实际 ${live.record.status}`)
    }
    if (!live.detail.timeline.length) {
      failures.push(`t=${t} 处理过程为空`)
    }
    if (live.detail.evidence_image === null) {
      failures.push(`t=${t} 缺证据图`)
    }
    /* 趋势数据应随 t 增长（只覆盖当前轮次） */
    if (live.detail.radar_trend.length < 2) {
      failures.push(`t=${t} 趋势点过少：${live.detail.radar_trend.length}`)
    }
  }

  console.log(
    `  ${t.toFixed(1).padStart(4)}  ${telemetry.sim_state.padEnd(10)} ` +
    `${(exists ? '有' : '—').padEnd(9)} ${(live?.record.level_text ?? '—').padEnd(6)} ` +
    `${live?.record.code ?? '—'}`,
  )
}

console.log()
if (failures.length) {
  console.error('✗ 派生异常:')
  for (const f of failures) console.error('  ' + f)
  process.exit(1)
}
console.log('✓ 当前报警派生正常（normal/attention 无、warning/alarm 有）')
console.log('  说明：该记录仅存在于内存中，不写入任何存储')
