/**
 * 监控画面组件 —— 视频优先，静态图回退。
 *
 * 关键约定（见 README 第 7 节）：
 *   固定路径 /videos/main-monitor.mp4，把最终视频放到
 *   frontend/public/videos/main-monitor.mp4 即可自动生效，**不需要改业务代码**。
 *
 * 回退策略分两层，缺一层都不够稳：
 *   1. **先探测**：对视频路径发 HEAD 请求，确认返回的确实是视频类型。
 *      这一步不能省 —— 前端开发服务器（以及部分 SPA 配置）对不存在的路径
 *      会返回 index.html 且状态码 200，光看状态码会误判成"视频存在"。
 *   2. **再兜底**：即使探测通过，播放期仍可能失败（编码不支持、文件损坏），
 *      由 <video> 的 onError 再次回退。
 *
 * 最终静默回退到静态监控画面，保证视频缺失时页面不报错、不白屏。
 */

import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import './MonitorVideo.css'

/** 固定视频路径：唯一替换约定 */
export const MONITOR_VIDEO_SRC = '/videos/main-monitor.mp4'
/** 静态回退画面（由 检测图片.png 生成） */
export const MONITOR_FALLBACK_SRC = '/images/main-monitor-fallback.png'

interface MonitorVideoProps {
  /** 画面左上角叠加的设备标识，例如 "Camera 01" */
  cameraLabel?: string
  /** 叠加的时间戳文字（通常由调用方传入当前时间） */
  timestamp?: string
  /** 是否叠加时间戳 */
  showTimestamp?: boolean
  /** 该点位是否具备独立画面；false 时直接展示占位，不请求视频 */
  hasStream?: boolean
  /** 无画面时的占位文案 */
  placeholderText?: string
  className?: string
  /** 视频之上的浮层（例如检测框说明） */
  overlay?: ReactNode
}

type Mode = 'probing' | 'video' | 'fallback' | 'none'

export default function MonitorVideo({
  cameraLabel = 'Camera 01',
  timestamp,
  showTimestamp = true,
  hasStream = true,
  placeholderText = '该监控点画面待切换',
  className = '',
  overlay,
}: MonitorVideoProps) {
  const [mode, setMode] = useState<Mode>(hasStream ? 'probing' : 'none')
  const videoRef = useRef<HTMLVideoElement | null>(null)

  // 探测视频是否真的存在（区分"404"与"SPA 回退返回的 index.html"）
  useEffect(() => {
    if (!hasStream) {
      setMode('none')
      return
    }

    let cancelled = false
    setMode('probing')

    const probe = async () => {
      try {
        const resp = await fetch(MONITOR_VIDEO_SRC, { method: 'HEAD' })
        if (cancelled) return

        const type = resp.headers.get('content-type') ?? ''
        // 只认真正的视频类型：status 200 + text/html 说明拿到的是页面而不是视频
        if (resp.ok && type.startsWith('video/')) {
          setMode('video')
        } else {
          setMode('fallback')
        }
      } catch {
        if (!cancelled) setMode('fallback')
      }
    }

    void probe()
    return () => {
      cancelled = true
    }
  }, [hasStream])

  // 某些浏览器对 autoplay 策略更严格，显式 play() 一次并捕获失败
  useEffect(() => {
    if (mode !== 'video') return
    const el = videoRef.current
    if (!el) return

    const attempt = el.play()
    if (attempt && typeof attempt.catch === 'function') {
      attempt.catch(() => {
        // 自动播放被拒不代表视频不可用，保持当前画面即可
      })
    }
  }, [mode])

  // 探测期间不显示任何画面元素，避免闪一下又切换
  const visible: Mode = mode === 'probing' ? 'none' : mode

  return (
    <div className={`monitor-video monitor-video--${visible} ${className}`.trim()}>
      {mode === 'video' && (
        <video
          ref={videoRef}
          className="monitor-video__media"
          src={MONITOR_VIDEO_SRC}
          poster={MONITOR_FALLBACK_SRC}
          autoPlay
          muted
          loop
          playsInline
          preload="auto"
          onError={() => setMode('fallback')}
        />
      )}

      {mode === 'fallback' && (
        <img
          className="monitor-video__media"
          src={MONITOR_FALLBACK_SRC}
          alt="制丝线监控画面（静态回退，等待监控视频接入）"
          onError={() => setMode('none')}
        />
      )}

      {visible === 'none' && mode !== 'probing' && (
        <div className="monitor-video__placeholder">
          <span className="monitor-video__placeholder-mark" aria-hidden="true" />
          <p className="monitor-video__placeholder-title">{placeholderText}</p>
          <p className="monitor-video__placeholder-desc">
            监控视频生成完成后，将文件放置为
            <code>public/videos/main-monitor.mp4</code> 即可自动显示。
          </p>
        </div>
      )}

      {/* 探测中：保持容器尺寸稳定，不出现布局跳动 */}
      {mode === 'probing' && <div className="monitor-video__probing" aria-hidden="true" />}

      {/* ---- 轻量叠加信息，不堆遮罩 ---- */}
      {showTimestamp && visible !== 'none' && (
        <span className="monitor-video__timestamp">{timestamp ?? '----年--月--日 --:--:--'}</span>
      )}

      {visible !== 'none' && <span className="monitor-video__camera">{cameraLabel}</span>}

      {mode === 'fallback' && (
        <span className="monitor-video__notice">静态监控画面 · 等待视频接入</span>
      )}

      {overlay}
    </div>
  )
}
