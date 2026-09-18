/**
 * 视频同步上下文 —— 全站唯一的视频时间来源。
 *
 * 为什么需要它：首页与雷视联动必须基于**同一个** video.currentTime 得到
 * 同一个遥测结果，绝不能各算一套。因此：
 *
 *   MonitorVideo（播放视频并上报 currentTime）
 *        ↓ register / 读取元素
 *   VideoSyncProvider（唯一的采样循环 + 唯一的遥测解算）
 *        ↓ useVideoSync() / useSyncedTelemetry()
 *   首页 / 雷视联动 / 智能预警 / 当前报警
 *
 * 采样策略
 * --------
 * 用 `requestAnimationFrame` 读取 video.currentTime，因此：
 *   * 视频暂停 → currentTime 不变 → 数据自动冻结（不靠额外判断）；
 *   * 拖动进度 → 下一帧立即同步到新位置，不会从旧状态慢慢增长；
 *   * 切到后台标签页 → rAF 暂停，恢复后重新读取真实 currentTime，
 *     不会因为计时器累计而跑偏；
 *   * 循环回绕 → currentTime 变小 → 自动复位并开启新一轮趋势。
 *
 * 不使用 setInterval 累计时间，也不使用 Date.now()。
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import {
  VIDEO_SYNC_DURATION,
  resolveVideoTelemetry,
  samplesUpTo,
  type VideoTelemetry,
} from './videoTelemetry'
import {
  PRIMARY_DETECTION,
  resolveDetectionBoxForRisk,
  type DetectionBox,
} from './videoDetection'

export type RunMode = 'automatic' | 'video_sync'

export interface VideoSyncState {
  /** 视频当前时间（源视频秒数，0~duration） */
  currentTime: number
  /** 视频实际时长（秒） */
  duration: number
  /** 是否正在播放 */
  playing: boolean
  /** 是否已成功加载元数据（据此判断视频是否可用） */
  ready: boolean
  /** 视频源是否可用（HEAD 探测 + onError 的结果） */
  available: boolean
  /** 已完成循环次数；每 +1 表示进入了新一轮演示 */
  loopCount: number
  /** 当前运行模式 */
  runMode: RunMode
}

export interface VideoSyncContextValue extends VideoSyncState {
  /** MonitorVideo 注册其 <video> 元素，供采样循环读取 currentTime */
  register: (el: HTMLVideoElement | null) => void
  /** 标记视频源不可用（探测失败或解码失败），进入静态图回退 */
  markUnavailable: () => void
  /** 切换运行模式（仅系统设置使用） */
  setRunMode: (mode: RunMode) => void
  /** 当前时刻的遥测（video_sync 模式下有效） */
  telemetry: VideoTelemetry
  /** 本轮 0 → currentTime 的趋势序列 */
  trend: VideoTelemetry[]
  /**
   * 当前的 YOLO 风格异常检测框。
   * 由主监控点的遥测派生 —— 全站同一个框，页面不得自行解算。
   */
  detection: DetectionBox
}

const VideoSyncContext = createContext<VideoSyncContextValue | null>(null)

/** 趋势序列采样间隔（源视频秒）。0.2 s × 10 s = 最多 51 个点，图表足够平滑 */
const TREND_STEP = 0.2

interface VideoSyncProviderProps {
  /** 后端返回的运行模式；默认 video_sync */
  initialRunMode?: RunMode
  /** 视频源是否可用（由探测结果传入） */
  available?: boolean
  children: ReactNode
}

export function VideoSyncProvider({
  initialRunMode = 'video_sync',
  available = true,
  children,
}: VideoSyncProviderProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const rafRef = useRef<number | null>(null)
  const lastTimeRef = useRef(0)
  const unwrappedRef = useRef(0)

  const [runMode, setRunMode] = useState<RunMode>(initialRunMode)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(VIDEO_SYNC_DURATION)
  const [playing, setPlaying] = useState(false)
  const [ready, setReady] = useState(false)
  const [loopCount, setLoopCount] = useState(0)
  const [videoAvailable, setVideoAvailable] = useState(available)

  useEffect(() => {
    setVideoAvailable(available)
  }, [available])

  const register = useCallback((el: HTMLVideoElement | null) => {
    videoRef.current = el
    if (!el) {
      setReady(false)
      setPlaying(false)
    }
  }, [])

  const markUnavailable = useCallback(() => setVideoAvailable(false), [])

  /**
   * 采样循环：唯一的 currentTime 读取点。
   * 即使视频暂停也保持 rAF 运行，这样 seek（拖动进度条）也能被立即捕获。
   */
  useEffect(() => {
    if (!videoAvailable) return

    let stopped = false

    const tick = () => {
      if (stopped) return
      const el = videoRef.current

      if (el) {
        const t = el.currentTime
        const dur = Number.isFinite(el.duration) && el.duration > 0 ? el.duration : VIDEO_SYNC_DURATION

        // 循环检测：currentTime 明显回退即视为完成一轮
        if (t + 0.35 < lastTimeRef.current) {
          unwrappedRef.current += 1
          setLoopCount(unwrappedRef.current)
        }
        lastTimeRef.current = t

        setCurrentTime((prev) => (Math.abs(prev - t) < 0.001 ? prev : t))
        setDuration((prev) => (Math.abs(prev - dur) < 0.001 ? prev : dur))
        setPlaying((prev) => {
          const next = !el.paused && !el.ended
          return prev === next ? prev : next
        })
        setReady((prev) => (prev ? prev : el.readyState >= 1))
      }

      rafRef.current = requestAnimationFrame(tick)
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => {
      stopped = true
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
  }, [videoAvailable])

  // 遥测解算：仅依赖 currentTime / duration / loopCount，
  // 因此同一时刻的结果在整站范围内完全一致
  const telemetry = useMemo(
    () => resolveVideoTelemetry(currentTime, duration),
    [currentTime, duration],
  )

  const trend = useMemo(
    () => samplesUpTo(currentTime, TREND_STEP),
    [currentTime],
  )

  /**
   * 异常检测框：与 telemetry 同源（都由 currentTime 派生），
   * 因此首页与雷视联动拿到的是同一个框，不可能出现页面间不一致。
   */
  const detection = useMemo(
    () => resolveDetectionBoxForRisk(telemetry.risk_index, PRIMARY_DETECTION.cameraId),
    [telemetry.risk_index],
  )

  const value = useMemo<VideoSyncContextValue>(
    () => ({
      currentTime,
      duration,
      playing,
      ready,
      available: videoAvailable,
      loopCount,
      runMode,
      register,
      markUnavailable,
      setRunMode,
      telemetry,
      trend,
      detection,
    }),
    [
      currentTime,
      duration,
      playing,
      ready,
      videoAvailable,
      loopCount,
      runMode,
      register,
      markUnavailable,
      telemetry,
      trend,
      detection,
    ],
  )

  return <VideoSyncContext.Provider value={value}>{children}</VideoSyncContext.Provider>
}

/** 读取视频同步上下文；未包裹 Provider 时返回 null（页面可据此回退到后端数据） */
export function useVideoSync(): VideoSyncContextValue | null {
  return useContext(VideoSyncContext)
}

/**
 * 统一遥测入口。
 *
 * 页面只需调用本 hook，无需关心当前是哪种运行模式：
 *   * video_sync → 返回随视频同步的遥测
 *   * automatic  → 返回 null，调用方继续使用后端 /api/realtime 数据
 *
 * 这样"首页与雷视联动必须同源"就由架构保证，而不是靠各页面自觉。
 */
export function useSyncedTelemetry(): { active: boolean; telemetry: VideoTelemetry | null } {
  const ctx = useVideoSync()
  if (!ctx) return { active: false, telemetry: null }

  const active = ctx.runMode === 'video_sync' && ctx.available
  return { active, telemetry: active ? ctx.telemetry : null }
}

/**
 * 当前异常检测框（全站统一）。
 *
 * 返回 null 表示当前无框或不处于画面同步模式 —— 页面据此不渲染 overlay。
 * 与 `useSyncedTelemetry` 一样，由架构保证首页与雷视联动取到同一个框。
 */
export function useDetectionBox(): DetectionBox | null {
  const ctx = useVideoSync()
  if (!ctx) return null
  if (ctx.runMode !== 'video_sync' || !ctx.available) return null
  return ctx.detection.visible ? ctx.detection : null
}
