/**
 * 内联 SVG 图标集。
 *
 * 刻意不引入图标库：本平台只需要十来个线性图标，
 * 用 24x24 viewBox + currentColor 描边即可，零依赖且体积极小。
 */

import type { ReactNode } from 'react'

interface IconProps {
  size?: number
  className?: string
}

function Svg({
  size = 16,
  className,
  children,
}: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  )
}

/** 综合监控：仪表盘 */
export const IconDashboard = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3" y="3" width="7.5" height="7.5" rx="1" />
    <rect x="13.5" y="3" width="7.5" height="4.5" rx="1" />
    <rect x="13.5" y="10.5" width="7.5" height="10.5" rx="1" />
    <rect x="3" y="13.5" width="7.5" height="7.5" rx="1" />
  </Svg>
)

/** 视频监控：摄像机 */
export const IconVideo = (p: IconProps) => (
  <Svg {...p}>
    <rect x="2" y="6" width="13" height="12" rx="2" />
    <path d="M15 10.5 22 7v10l-7-3.5z" />
  </Svg>
)

/** 雷视联动：雷达波 + 目标 */
export const IconRadar = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 21a9 9 0 1 0-9-9" />
    <path d="M12 17a5 5 0 1 0-5-5" />
    <circle cx="12" cy="12" r="1.3" fill="currentColor" stroke="none" />
    <path d="M12 12 3 3" />
  </Svg>
)

/** 异常报警：警示三角 */
export const IconAlarm = (p: IconProps) => (
  <Svg {...p}>
    <path d="M10.3 3.6 1.9 18a2 2 0 0 0 1.7 3h16.8a2 2 0 0 0 1.7-3L13.7 3.6a2 2 0 0 0-3.4 0z" />
    <path d="M12 9v4.5" />
    <path d="M12 17.2h.01" />
  </Svg>
)

/** 数据溯源：时间回溯 */
export const IconTrace = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 12a9 9 0 1 0 2.6-6.4" />
    <path d="M3 4v5h5" />
    <path d="M12 8v4.5l3 1.8" />
  </Svg>
)

/** 智能预警：趋势上升 */
export const IconPredict = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 17.5 9.5 11l4 4L21 7.5" />
    <path d="M15.5 7.5H21V13" />
    <path d="M3 21h18" />
  </Svg>
)

/** 知识库：书本 */
export const IconKnowledge = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v16H6.5A2.5 2.5 0 0 0 4 20.5z" />
    <path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H20v4H6.5A2.5 2.5 0 0 1 4 20.5z" />
  </Svg>
)

/** 系统设置：齿轮 */
export const IconSettings = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2 2 2 0 1 1-4 0 1.7 1.7 0 0 0-2.9-1.2l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.7 1.7 0 0 0 3 15a2 2 0 1 1 0-4 1.7 1.7 0 0 0 1.5-2.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.7 1.7 0 0 0 10 4.6a2 2 0 1 1 4 0 1.7 1.7 0 0 0 2.9 1.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1A1.7 1.7 0 0 0 21 11a2 2 0 1 1 0 4z" />
  </Svg>
)

/** 播放 */
export const IconPlay = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6 3.8 20 12 6 20.2z" fill="currentColor" />
  </Svg>
)

/** 停止 */
export const IconStop = (p: IconProps) => (
  <Svg {...p}>
    <rect x="6" y="6" width="12" height="12" rx="1.5" fill="currentColor" stroke="none" />
  </Svg>
)

/** 重置 */
export const IconReset = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 12a9 9 0 1 0 3-6.7" />
    <path d="M3 3v6h6" />
  </Svg>
)

/** 刷新 */
export const IconRefresh = (p: IconProps) => (
  <Svg {...p}>
    <path d="M21 12a9 9 0 0 1-15.5 6.2" />
    <path d="M3 12a9 9 0 0 1 15.5-6.2" />
    <path d="M18.5 2v4.5H14" />
    <path d="M5.5 22v-4.5H10" />
  </Svg>
)

/** 折线图 */
export const IconChart = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 3v18h18" />
    <path d="M7 15l3.5-4 3 2.5L20 7" />
  </Svg>
)

/** 设备 */
export const IconDevice = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3" y="4" width="18" height="12" rx="1.8" />
    <path d="M8 20h8" />
    <path d="M12 16v4" />
  </Svg>
)

/** 时钟 */
export const IconClock = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5.3l3.4 2" />
  </Svg>
)

/** 信息 */
export const IconInfo = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5" />
    <path d="M12 7.8h.01" />
  </Svg>
)

/** 搜索 */
export const IconSearch = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.6-3.6" />
  </Svg>
)

/** 展开箭头 */
export const IconChevron = (p: IconProps) => (
  <Svg {...p}>
    <path d="m9 6 6 6-6 6" />
  </Svg>
)

/** 人员检测 */
export const IconPerson = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="8" r="3.5" />
    <path d="M5 20a7 7 0 0 1 14 0" />
  </Svg>
)

export type IconComponent = (p: IconProps) => JSX.Element
