/**
 * 前端/后端遥测一致性校验（开发期工具，不参与生产构建）。
 *
 * 用途：`frontend/src/video/videoTelemetry.ts` 与 `backend/app/services/video_sync.py`
 * 是同一套轨迹的两份实现。本脚本用 Node 直接运行**前端实现**，
 * 与后端导出的期望值逐点比对，确保两边不会漂移。
 *
 * 用法（在 frontend 目录）：
 *   python ../scripts/export_parity_fixtures.py     # 先导出后端期望值
 *   node scripts/check-telemetry-parity.mjs ../.parity-telemetry.json
 *
 * 退出码非 0 表示两边不一致，需要在提交前修好。
 */

import { readFileSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { build } from 'esbuild'

const __dirname = dirname(fileURLToPath(import.meta.url))
const expectedPath = process.argv[2] ?? resolve(__dirname, '../../.parity-telemetry.json')
const expected = JSON.parse(readFileSync(expectedPath, 'utf8'))

const entry = resolve(__dirname, '../src/video/videoTelemetry.ts')
const outDir = mkdtempSync(resolve(tmpdir(), 'telemetry-parity-'))
const outFile = resolve(outDir, 'videoTelemetry.mjs')

await build({
  entryPoints: [entry],
  outfile: outFile,
  bundle: true,
  format: 'esm',
  platform: 'neutral',
  target: 'es2020',
  logLevel: 'silent',
})

const mod = await import(pathToFileURL(outFile).href)
writeFileSync(resolve(outDir, '.built'), 'ok')

const TOLERANCE = {
  distance: 1e-6,
  risk: 1e-6,
  coverage: 1e-6,
  speed: 1e-6,
  load: 1e-6,
}

let checked = 0
const failures = []

for (const [tKey, [distance, risk, coverage, speed, load, state]] of Object.entries(expected)) {
  const t = Number(tKey)
  const actual = mod.resolveVideoTelemetry(t)
  checked += 1

  const pairs = [
    ['distance', actual.distance, distance],
    ['risk', actual.risk_index, risk],
    ['coverage', actual.coverage, coverage],
    ['speed', actual.conveyor_speed, speed],
    ['load', actual.equipment_load, load],
  ]

  for (const [name, got, want] of pairs) {
    if (Math.abs(got - want) > TOLERANCE[name]) {
      failures.push(`t=${tKey} ${name}: 前端 ${got} ≠ 后端 ${want}`)
    }
  }

  if (actual.sim_state !== state) {
    failures.push(`t=${tKey} state: 前端 ${actual.sim_state} ≠ 后端 ${state}`)
  }
}

if (failures.length > 0) {
  console.error(`✗ 前后端遥测不一致（检查 ${checked} 个时间点）`)
  for (const line of failures.slice(0, 20)) console.error('  ' + line)
  if (failures.length > 20) console.error(`  … 另有 ${failures.length - 20} 处`)
  process.exit(1)
}

console.log(`✓ 前后端遥测完全一致（${checked} 个时间点 × 6 个字段）`)
