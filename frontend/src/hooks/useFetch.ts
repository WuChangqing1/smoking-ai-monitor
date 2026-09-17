/**
 * 通用数据获取 hook：加载态 / 错误态 / 可选轮询。
 *
 * 关键约束（对应「API 失败时不会白屏」）：
 * 请求失败时保留上一次成功的数据（lastGood），只在从未成功过时展示错误，
 * 这样后端短暂抖动不会让正在展示的页面突然清空。
 */

import { useCallback, useEffect, useRef, useState } from 'react'

export interface FetchState<T> {
  data: T | null
  error: string | null
  loading: boolean
  /** 最近一次成功刷新的时间戳 */
  updatedAt: number | null
  refresh: () => void
}

export function useFetch<T>(
  fetcher: () => Promise<T>,
  options: { intervalMs?: number; enabled?: boolean } = {},
): FetchState<T> {
  const { intervalMs, enabled = true } = options

  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [updatedAt, setUpdatedAt] = useState<number | null>(null)

  // 用 ref 持有最新的 fetcher，避免调用方每次渲染传入新函数导致无限重订阅
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const aliveRef = useRef(true)
  const hasDataRef = useRef(false)

  const run = useCallback(async () => {
    try {
      const result = await fetcherRef.current()
      if (!aliveRef.current) return
      setData(result)
      hasDataRef.current = true
      setError(null)
      setUpdatedAt(Date.now())
    } catch (err) {
      if (!aliveRef.current) return
      // 已经有过成功数据时，不把界面打成错误态，只提示
      setError(err instanceof Error ? err.message : '数据获取失败')
    } finally {
      if (aliveRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    aliveRef.current = true
    return () => {
      aliveRef.current = false
    }
  }, [])

  useEffect(() => {
    if (!enabled) return
    void run()

    if (!intervalMs || intervalMs <= 0) return
    const timer = window.setInterval(() => void run(), intervalMs)
    return () => window.clearInterval(timer)
  }, [enabled, intervalMs, run])

  return { data, error, loading, updatedAt, refresh: () => void run() }
}

/** 每秒走动的时钟，用于顶栏时间显示。 */
export function useClock(intervalMs = 1000): Date {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), intervalMs)
    return () => window.clearInterval(timer)
  }, [intervalMs])

  return now
}
