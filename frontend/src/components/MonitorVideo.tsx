/**
 * 监控画面组件 —— 视频优先，静态图回退。
 *
 * 关键约定（见 README 第 7 节）：
 *   把最终视频放到 frontend/public/videos/main-monitor.mp4 即可自动生效，
 *   **不需要改业务代码**。这里使用相对路径（不带前导斜杠），
 *   以便平台部署在根路径或子路径（如 /smoking/）下都能正确加载。
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

import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { VIDEO_PLAYBACK_RATE } from '../video/videoTelemetry'
import { useVideoSync } from '../video/VideoSyncContext'
import DetectionOverlay from './DetectionOverlay'
import './MonitorVideo.css'

/** 固定视频路径：唯一替换约定（相对路径，便于部署在任意 URL 前缀下） */
export const MONITOR_VIDEO_PATH = 'videos/main-monitor.mp4'

/**
 * 视频素材版本号 —— **替换视频文件时必须同步 +1**。
 *
 * 视频文件名固定（替换约定不变），而 HTTP 缓存无法感知内容变化：
 * 若沿用同一个 URL，浏览器会在缓存有效期内继续播放旧文件
 * （曾因此出现"服务器已是去水印的新视频、页面上仍是带水印旧视频"）。
 * 把版本号拼进查询串即可让 URL 变化，浏览器必然重新拉取。
 *
 * 查询串对 Nginx 静态文件服务无影响（只按路径匹配 $uri）。
 */
export const MONITOR_VIDEO_VERSION = 2

/** 实际请求地址：带版本参数，避免浏览器复用旧缓存 */
export const MONITOR_VIDEO_SRC = `${MONITOR_VIDEO_PATH}?v=${MONITOR_VIDEO_VERSION}`

/**
 * 其余监控点（Camera 02/03/04）的循环画面。
 *
 * 三个机位各有独立素材，按机位编号对应各自的文件。
 * 替换某个机位的素材时，换掉路径常量、并把该机位版本号 +1（理由同主监控视频）。
 * 播放速率与主监控点一致，都是 0.5×。
 */
export const CAMERA_VIDEO_PATH: Record<string, string> = {
  'Camera 02': 'videos/camera-02.mp4',
  'Camera 03': 'videos/camera-03.mp4',
  'Camera 04': 'videos/camera-04.mp4',
}

/** 各机位素材版本号，替换素材时同步 +1 */
export const CAMERA_VIDEO_VERSION: Record<string, number> = {
  'Camera 02': 1,
  'Camera 03': 1,
  'Camera 04': 1,
}

/** 取某个机位的实际请求地址（带版本参数）；未配置的机位回退到主监控视频 */
export function cameraVideoSrc(camera: string): string {
  const path = CAMERA_VIDEO_PATH[camera]
  if (!path) return MONITOR_VIDEO_SRC
  return `${path}?v=${CAMERA_VIDEO_VERSION[camera] ?? 1}`
}

/** 静态回退画面（由 检测图片.png 生成） */
export const MONITOR_FALLBACK_SRC = 'images/main-monitor-fallback.png'

interface MonitorVideoProps {
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
  /** 是否把该视频作为全站同步时间源注册到 VideoSyncContext（主监控点使用） */
  asTimeSource?: boolean
  /** 是否叠加 YOLO 风格异常检测框（主监控点使用；其他点位暂无检测配置） */
  showDetection?: boolean
  /**
   * 画面视频地址。默认使用主监控点视频；
   * 其余点位传入各自的循环画面文件即可（见 cameraVideoSrc）。
   */
  videoSrc?: string
  /**
   * 播放速率。主监控点为 0.5×（配合时间轴压缩演示）；
   * 其余点位只做画面循环展示，用默认的 1× 即可。
   */
  rate?: number
}

type Mode = 'probing' | 'video' | 'fallback' | 'none'

export default function MonitorVideo({
  timestamp,
  showTimestamp = true,
  hasStream = true,
  placeholderText = '该监控点画面待切换',
  className = '',
  overlay,
  asTimeSource = false,
  showDetection = false,
  videoSrc = MONITOR_VIDEO_SRC,
  rate = VIDEO_PLAYBACK_RATE,
}: MonitorVideoProps) {
  const [mode, setMode] = useState<Mode>(hasStream ? 'probing' : 'none')
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const sync = useVideoSync()

  /**
   * 异常检测框：直接取全站统一解算结果，组件本身不解算，
   * 保证首页与雷视联动的框完全一致。
   * 静态图回退时同样按状态显示（画面与框仍在同一 16:9 容器内，不会错位）。
   */
  const detectionBox = showDetection ? (sync?.detection ?? null) : null

  /** 视频不可用时通知上下文，使全站回退到后端数据 */
  const markUnavailable = sync?.markUnavailable
  const register = sync?.register
  const goFallback = useCallback(() => {
    setMode('fallback')
    if (asTimeSource) markUnavailable?.()
  }, [asTimeSource, markUnavailable])

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
        const resp = await fetch(videoSrc, { method: 'HEAD' })
        if (cancelled) return

        const type = resp.headers.get('content-type') ?? ''
        // 只认真正的视频类型：status 200 + text/html 说明拿到的是页面而不是视频
        if (resp.ok && type.startsWith('video/')) {
          setMode('video')
        } else {
          goFallback()
        }
      } catch {
        if (!cancelled) goFallback()
      }
    }

    void probe()
    return () => {
      cancelled = true
    }
  }, [hasStream, goFallback, videoSrc])

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

  /**
   * 播放速率。
   *
   * 主监控点与其余监控点都是 0.5×（源视频 10 s → 演示周期约 20 s）。
   *
   * 不只在初始化时设置一次 —— 部分浏览器在 load / play / seek 之后会把
   * playbackRate 重置回 1.0，因此在这几个时机都重新应用。
   */
  useEffect(() => {
    if (mode !== 'video') return
    const el = videoRef.current
    if (!el) return

    const applyRate = () => {
      if (el.playbackRate !== rate) {
        el.playbackRate = rate
      }
    }

    applyRate()
    el.addEventListener('loadedmetadata', applyRate)
    el.addEventListener('loadeddata', applyRate)
    el.addEventListener('canplay', applyRate)
    el.addEventListener('play', applyRate)
    el.addEventListener('playing', applyRate)
    el.addEventListener('seeked', applyRate)

    return () => {
      el.removeEventListener('loadedmetadata', applyRate)
      el.removeEventListener('loadeddata', applyRate)
      el.removeEventListener('canplay', applyRate)
      el.removeEventListener('play', applyRate)
      el.removeEventListener('playing', applyRate)
      el.removeEventListener('seeked', applyRate)
    }
  }, [mode, rate])

  // 把主监控视频注册为全站同步时间源
  useEffect(() => {
    if (!asTimeSource || !register) return
    register(mode === 'video' ? videoRef.current : null)
    return () => register(null)
  }, [asTimeSource, register, mode])

  // 探测期间不显示任何画面元素，避免闪一下又切换
  const visible: Mode = mode === 'probing' ? 'none' : mode

  return (
    <div className={`monitor-video monitor-video--${visible} ${className}`.trim()}>
      {mode === 'video' && (
        <video
          ref={videoRef}
          className="monitor-video__media"
          src={videoSrc}
          poster={MONITOR_FALLBACK_SRC}
          autoPlay
          muted
          loop
          playsInline
          preload="auto"
          /* 工业监控画面不显示播放器控件（进度条/音量/全屏） */
          controls={false}
          disablePictureInPicture
          onError={goFallback}
        />
      )}

      {mode === 'fallback' && (
        <img
          className="monitor-video__media"
          src={MONITOR_FALLBACK_SRC}
          alt="制丝线监控画面（静态回退）"
          onError={() => setMode('none')}
        />
      )}

      {visible === 'none' && mode !== 'probing' && (
        <div className="monitor-video__placeholder">
          <span className="monitor-video__placeholder-mark" aria-hidden="true" />
          <p className="monitor-video__placeholder-title">{placeholderText}</p>
          <p className="monitor-video__placeholder-desc">视频信号恢复后自动显示画面</p>
        </div>
      )}

      {/* 探测中：保持容器尺寸稳定，不出现布局跳动 */}
      {mode === 'probing' && <div className="monitor-video__probing" aria-hidden="true" />}

      {/* ---- YOLO 风格异常检测框：与视频内容同尺寸叠放，百分比定位 ----
           仅在 warning 及以上阶段渲染；循环回到 normal 时自然消失 */}
      {visible !== 'none' && <DetectionOverlay box={detectionBox} />}

      {/* ---- 轻量叠加信息，不堆遮罩 ----
           不再叠加机位标识文字：监控视频画面里本来就带 "Camera 01" 水印，
           再叠一层会与之重复（用户明确要求去掉）。 */}
      {showTimestamp && visible !== 'none' && (
        <span className="monitor-video__timestamp">{timestamp ?? '----年--月--日 --:--:--'}</span>
      )}

      {mode === 'fallback' && <span className="monitor-video__notice">静态监控画面</span>}

      {overlay}
    </div>
  )
}
