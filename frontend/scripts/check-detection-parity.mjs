/**
 * 前端/后端检测框对等校验（开发期工具，不参与生产构建）。
 *
 * 用途：`frontend/src/video/videoDetection.ts` 与
 * `backend/app/services/video_detection.py` 是同一套检测框规则的两份实现。
 * 本脚本用 Node 运行**前端实现**，与后端导出的期望值逐点比对。
 *
 * 用法（在 frontend 目录）：
 *   node scripts/check-detection-parity.mjs ../.parity-detection.json
 *
 * 退出码非 0 表示两边不一致，需要在提交前修好。
 */

import { readFileSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { build } from 'esbuild'

const __dirname = dirname(fileURLToPath(import.meta.url))
const expectedPath = process.argv[2] ?? resolve(__dirname, '../../.parity-detection.json')
const expected = JSON.parse(readFileSync(expectedPath, 'utf8'))

const entry = resolve(__dirname, '../src/video/videoDetection.ts')
const outDir = mkdtempSync(resolve(tmpdir(), 'detection-parity-'))
const outFile = resolve(outDir, 'videoDetection.mjs')

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

const failures = []
let checked = 0

for (const [key, want] of Object.entries(expected)) {
  const [tStr, cameraId] = key.split('|')
  const t = Number(tStr)
  const got = mod.resolveVideoDetectionBox(t, cameraId)
  checked += 1

  const pairs = [
    ['visible', got.visible, want.visible],
    ['x', got.x, want.x],
    ['y', got.y, want.y],
    ['width', got.width, want.width],
    ['height', got.height, want.height],
    ['confidence', got.confidence, want.confidence],
    ['severity', got.severity, want.severity],
    ['label', got.label, want.label],
    ['evidenceImage', got.evidenceImage, want.evidenceImage],
  ]

  for (const [name, a, b] of pairs) {
    if (a !== b) {
      failures.push(`t=${tStr} camera=${cameraId} ${name}: 前端 ${a} ≠ 后端 ${b}`)
    }
  }
}

if (failures.length > 0) {
  console.error(`✗ 前后端检测框不一致（检查 ${checked} 个组合）`)
  for (const line of failures.slice(0, 20)) console.error('  ' + line)
  if (failures.length > 20) console.error(`  … 另有 ${failures.length - 20} 处`)
  process.exit(1)
}

console.log(`✓ 前后端检测框完全一致（${checked} 个 t×camera 组合 × 9 个字段）`)
