/**
 * 监控画面组件 —— 视频优先，静态图回退。
 *
 * 关键约定（见 README 第 7 节）：
 *   固定路径 /videos/main-monitor.mp4，把最终视频放到
 *   frontend/public/videos/main-monitor.mp4 即可自动生效，**不需要改业务代码**。
 *
 * 视频不存在 / 编码不支持 / 播放失败时，自动回退到静态监控画面
 * /images/main-monitor-fallback.png，保证页面不报错、不白屏。
 */

import { useEffect, useRef, useState } from 'react'
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
  overlay?: React.ReactNode
}

export default function MonitorVideo({
  cameraLabel = 'Camera 01',
  timestamp,
  showTimestamp = true,
  hasStream = true,
  placeholderText = '该监控点画面待切换',
  className = '',
  overlay,
}: MonitorVideoProps) {
  /** 'video' = 视频可播放；'fallback' = 已回退静态图；'none' = 无画面 */
  const [mode, setMode] = useState<'video' | 'fallback' | 'none'>(hasStream ? 'video' : 'none')
  const videoRef = useRef<HTMLVideoElement | null>(null)

  useEffect(() => {
    setMode(hasStream ? 'video' : 'none')
  }, [hasStream])

  // 某些浏览器对 autoplay 策略更严格，显式 play() 一次并捕获失败
  useEffect(() => {
    if (mode !== 'video') return
    const el = videoRef.current
    if (!el) return

    const attempt = el.play()
    if (attempt && typeof attempt.catch === 'function') {
      attempt.catch(() => {
        // 自动播放被拒不代表视频不可用，保持画面；只有加载失败才回退
      })
    }
  }, [mode])

  return (
    <div className={`monitor-video monitor-video--${mode} ${className}`.trim()}>
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
        >
          {/* 视频源缺失时浏览器会触发 error，由 onError 统一处理 */}
        </video>
      )}

      {mode === 'fallback' && (
        <img
          className="monitor-video__media"
          src={MONITOR_FALLBACK_SRC}
          alt="制丝线监控画面（静态回退，等待监控视频接入）"
          onError={() => setMode('none')}
        />
      )}

      {mode === 'none' && (
        <div className="monitor-video__placeholder">
          <span className="monitor-video__placeholder-mark" aria-hidden="true" />
          <p className="monitor-video__placeholder-title">{placeholderText}</p>
          <p className="monitor-video__placeholder-desc">
            监控视频生成完成后，将文件放置为
            <code>public/videos/main-monitor.mp4</code> 即可自动显示。
          </p>
        </div>
      )}

      {/* ---- 轻量叠加信息，不堆遮罩 ---- */}
      {showTimestamp && mode !== 'none' && (
        <span className="monitor-video__timestamp">{timestamp ?? '----年--月--日 --:--:--'}</span>
      )}

      {mode !== 'none' && <span className="monitor-video__camera">{cameraLabel}</span>}

      {mode === 'fallback' && (
        <span className="monitor-video__notice">静态监控画面 · 等待视频接入</span>
      )}

      {overlay}
    </div>
  )
}
