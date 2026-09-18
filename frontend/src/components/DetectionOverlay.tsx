/**
 * YOLO 风格异常检测框叠加层。
 *
 * 与视频**完全同尺寸**叠放：父容器为 16:9 且 overlay 绝对定位占满，
 * 因此百分比坐标与视频内容严格对齐 —— CSS object-fit 不会造成框偏移。
 *
 * 展示纪律：
 *   * 一个框，位置与尺寸固定（不做跟踪、不缩放、不移动、不闪烁）
 *   * 只有边框颜色（warning 橙 / alarm 红）与标签置信度随阶段变化
 *   * 无框即代表视觉尚未确认异常区域
 */

import { detectionColor, type DetectionBox } from '../video/videoDetection'
import './DetectionOverlay.css'

interface DetectionOverlayProps {
  box: DetectionBox | null
  /** 是否叠加时间戳/边框等额外装饰（默认否，保持画面干净） */
  className?: string
}

export default function DetectionOverlay({ box, className = '' }: DetectionOverlayProps) {
  if (!box || !box.visible) return null

  const color = detectionColor(box.severity)
  const style = {
    left: `${box.x * 100}%`,
    top: `${box.y * 100}%`,
    width: `${box.width * 100}%`,
    height: `${box.height * 100}%`,
    borderColor: color,
  }

  return (
    <div className={`detection-overlay ${className}`.trim()} aria-hidden="true">
      <div className="detection-overlay__box" style={style}>
        <span className="detection-overlay__label" style={{ backgroundColor: color }}>
          {box.labelText} {box.confidence.toFixed(2)}
        </span>
      </div>
    </div>
  )
}

/** 证据图上的框也用同一套比例，便于页面内联展示时保持一致 */
export function detectionBoxStyle(box: DetectionBox): React.CSSProperties {
  return {
    left: `${box.x * 100}%`,
    top: `${box.y * 100}%`,
    width: `${box.width * 100}%`,
    height: `${box.height * 100}%`,
    borderColor: detectionColor(box.severity),
  }
}
