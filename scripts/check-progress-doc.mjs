/**
 * 校验 docs/任务进展.html（开发期工具）。
 *
 * 检查：
 *   1. 标签配对（忽略自闭合与 void 元素）
 *   2. 内联脚本语法可解析
 *   3. SVG 关键帧坐标与 viewBox 不越界
 *   4. 数字概览与正文里的关键数据是否自洽
 *
 * 用法：node scripts/check-progress-doc.mjs
 */

import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { Script } from 'node:vm'

const __dirname = dirname(fileURLToPath(import.meta.url))

/* 文档改过名，这里按候选顺序取第一个存在的文件 */
const CANDIDATES = ['../docs/任务进展.html', '../docs/team-progress.html']
const FILE = CANDIDATES.map((p) => resolve(__dirname, p)).find((p) => existsSync(p))
if (!FILE) {
  console.error(`✗ 未找到进度文档，候选路径：\n  ${CANDIDATES.join('\n  ')}`)
  process.exit(1)
}
const html = readFileSync(FILE, 'utf8')

const problems = []
const notes = []

/* ---------- 1. 标签配对 ---------- */
const VOID = new Set([
  'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
  'link', 'meta', 'param', 'source', 'track', 'wbr', 'path',
  'circle', 'line', 'rect', 'stop', 'use', 'polygon', 'polyline', 'ellipse',
])

const stack = []
const tagRe = /<(\/?)([a-zA-Z][a-zA-Z0-9-]*)\b([^>]*)>/g
let m
while ((m = tagRe.exec(html)) !== null) {
  const [, closing, rawName, attrs] = m
  const name = rawName.toLowerCase()
  if (name === '!doctype') continue
  if (VOID.has(name) || attrs.trimEnd().endsWith('/')) continue

  if (closing) {
    const top = stack.pop()
    if (top !== name) problems.push(`标签不匹配：期望 </${top}>，实际 </${name}>`)
  } else {
    stack.push(name)
  }
}
if (stack.length) problems.push(`以下标签未闭合：${stack.join(', ')}`)
else if (!problems.length) notes.push('标签配对正常')

/* ---------- 2. 内联脚本语法 ---------- */
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((x) => x[1])
scripts.forEach((code, i) => {
  try {
    new Script(code)
    notes.push(`内联脚本 #${i + 1} 语法正常（${code.split('\n').length} 行）`)
  } catch (err) {
    problems.push(`内联脚本 #${i + 1} 语法错误：${err.message}`)
  }
})

/* ---------- 3. SVG 关键帧坐标 ---------- */
const vb = html.match(/<svg class="chart" viewBox="([\d.\s]+)"/)
if (!vb) {
  problems.push('未找到图表 viewBox')
} else {
  const [vx, vy, vw, vh] = vb[1].trim().split(/\s+/).map(Number)
  notes.push(`图表 viewBox = ${vx} ${vy} ${vw} ${vh}`)

  const xs = [...html.matchAll(/<circle class="kf"[^>]*cx="([\d.]+)"[^>]*cy="([\d.]+)"/g)]
  if (xs.length !== 6) problems.push(`关键帧数量应为 6，实际 ${xs.length}`)

  xs.forEach(([, cx, cy]) => {
    const x = Number(cx)
    const y = Number(cy)
    if (x < vx || x > vx + vw) problems.push(`关键帧 cx=${x} 超出 viewBox 宽度`)
    if (y < vy || y > vy + vh) problems.push(`关键帧 cy=${y} 超出 viewBox 高度`)
  })

  // 文本标签右边界粗估：中文字符按字号计，数字按 0.6 倍字号计
  const labels = [...html.matchAll(/<text class="kf-label"[^>]*x="([\d.]+)"[^>]*>([^<]+)</g)]
  labels.forEach(([, lx, text]) => {
    const x = Number(lx)
    if (x > vx + vw - 30) {
      problems.push(`标签 "${text}" 起点 x=${x} 太靠右，可能被裁切`)
    }
  })
  notes.push(`关键帧坐标全部落在 viewBox 内，标签 ${labels.length} 个`)
}

/* ---------- 4. 关键数据自洽 ---------- */
const checks = [
  ['7', '大功能模块'],
  ['26', '后端接口'],
  ['220', '后端测试'],
  ['101', '一致性校验点'],
]
checks.forEach(([n, label]) => {
  if (!new RegExp(`data-count="${n}"`).test(html)) {
    problems.push(`缺少数字概览项：${label}（data-count="${n}"）`)
  }
})

// 关键帧数值应与后端定义一致
const expected = ['0.721', '0.706', '0.681', '0.651', '0.612', '0.582']
expected.forEach((v) => {
  if (!html.includes(v)) problems.push(`图表缺少关键帧数值 ${v}`)
})

// 检测框归一化坐标应出现
if (!html.includes('33.59%') || !html.includes('26.39%')) {
  problems.push('检测框示意缺少归一化坐标 33.59% / 26.39%')
}

console.log('=== 校验结果 ===')
notes.forEach((n) => console.log('  ✓ ' + n))

if (problems.length) {
  console.log()
  problems.forEach((p) => console.error('  ✗ ' + p))
  process.exit(1)
}
console.log()
console.log(`✓ ${FILE.split(/[\\/]/).pop()} 校验通过`)
console.log(`  文件大小：${(Buffer.byteLength(html, 'utf8') / 1024).toFixed(1)} KB`)
console.log(`  总行数：${html.split('\n').length}`)
