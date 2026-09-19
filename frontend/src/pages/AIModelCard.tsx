/**
 * AI 模型服务配置卡片。
 *
 * 支持两类服务，底层走同一个 OpenAI-compatible 客户端：
 *   * llama.cpp（本地，API Key 可留空）
 *   * OpenAI Compatible（通用，任何兼容 /v1/chat/completions 的服务）
 *
 * 安全约定
 * --------
 * * API Key 只提交给后端，读取时只回显示掩码；前端不做任何持久化。
 * * 管理员令牌只保留在本组件内存里，**不进 localStorage /
 *   sessionStorage / cookie**，保存后立即清空输入框。
 * * 所有模型请求都由后端发出，浏览器不直连模型服务。
 */

import { useCallback, useEffect, useState } from 'react'
import Panel from '../components/Panel'
import { Badge, MetricList, MetricRow } from '../components/Badge'
import { IconSettings } from '../components/icons'
import { api } from '../api/client'
import type { AIProvider, AIProviderOption, AISettings } from '../types'
import './AIModelCard.css'

type Tone = 'normal' | 'critical' | 'idle' | 'info' | 'warning'

interface Feedback {
  tone: 'ok' | 'error'
  text: string
}

/** 服务类型 → 默认 Base URL（后端也提供，这里兜底避免闪烁） */
const FALLBACK_PRESETS: Record<AIProvider, string> = {
  llama_cpp: 'http://127.0.0.1:8080/v1',
  openai_compatible: '',
}

export default function AIModelCard() {
  const [providers, setProviders] = useState<AIProviderOption[]>([])
  const [settings, setSettings] = useState<AISettings | null>(null)
  const [loading, setLoading] = useState(true)

  /* 表单状态 */
  const [provider, setProvider] = useState<AIProvider>('llama_cpp')
  const [enabled, setEnabled] = useState(false)
  const [baseUrl, setBaseUrl] = useState(FALLBACK_PRESETS.llama_cpp)
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [temperature, setTemperature] = useState(0.2)
  const [maxTokens, setMaxTokens] = useState(1024)
  const [timeout, setTimeoutValue] = useState(30)

  /* 管理员令牌：仅内存 */
  const [adminToken, setAdminToken] = useState('')

  const [busy, setBusy] = useState<'save' | 'test' | null>(null)
  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const [models, setModels] = useState<string[]>([])

  const applySettings = useCallback((data: AISettings) => {
    setSettings(data)
    setProvider(data.provider)
    setEnabled(data.enabled)
    setBaseUrl(data.base_url)
    setModel(data.model)
    setTemperature(data.temperature)
    setMaxTokens(data.max_tokens)
    setTimeoutValue(data.timeout)
    setApiKey('') // 不回填 Key
  }, [])

  useEffect(() => {
    let cancelled = false
    Promise.all([api.aiProviders(), api.aiSettings()])
      .then(([options, data]) => {
        if (cancelled) return
        setProviders(options)
        applySettings(data)
      })
      .catch(() => {
        if (!cancelled) setFeedback({ tone: 'error', text: '无法读取 AI 模型配置' })
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [applySettings])

  /** 切换服务类型时，若当前地址为空或还是上一个预设，就换成新预设 */
  function handleProviderChange(next: AIProvider) {
    const prevPreset = FALLBACK_PRESETS[provider]
    setProvider(next)
    if (!baseUrl || baseUrl === prevPreset) {
      const preset = providers.find((p) => p.value === next)?.default_base_url
      setBaseUrl(preset || FALLBACK_PRESETS[next] || '')
    }
  }

  /** 表单 → 请求体。api_key 为空串时表示"不修改"，由 clearKey 单独处理 */
  function buildPayload(includeKey: boolean) {
    const payload: Record<string, unknown> = {
      provider,
      enabled,
      base_url: baseUrl,
      model,
      temperature,
      max_tokens: maxTokens,
      timeout,
    }
    if (includeKey && apiKey.trim()) payload.api_key = apiKey.trim()
    return payload
  }

  async function handleSave() {
    setBusy('save')
    setFeedback(null)
    try {
      const saved = await api.aiSaveSettings(buildPayload(true), adminToken)
      applySettings(saved)
      setAdminToken('') // 用后立即清空
      setFeedback({ tone: 'ok', text: '配置已保存' })
    } catch (err) {
      const status = (err as { status?: number }).status
      setFeedback({
        tone: 'error',
        text:
          status === 401
            ? '需要管理员令牌，请填写后再保存'
            : status === 403
              ? '该配置接口未对外开放'
              : '保存失败，请检查配置内容',
      })
    } finally {
      setBusy(null)
    }
  }

  async function handleClearKey() {
    setBusy('save')
    setFeedback(null)
    try {
      const saved = await api.aiSaveSettings({ api_key: '' }, adminToken)
      applySettings(saved)
      setAdminToken('')
      setFeedback({ tone: 'ok', text: '已清除 API Key' })
    } catch {
      setFeedback({ tone: 'error', text: '清除失败，请确认管理员令牌' })
    } finally {
      setBusy(null)
    }
  }

  async function handleTest() {
    setBusy('test')
    setFeedback(null)
    setModels([])
    try {
      const result = await api.aiTest(buildPayload(true), adminToken)
      setAdminToken('')
      if (result.ok) {
        setModels(result.models)
        setFeedback({ tone: 'ok', text: `连接正常${result.model ? ` · ${result.model}` : ''}` })
      } else {
        setFeedback({ tone: 'error', text: result.error || '连接失败' })
      }
    } catch (err) {
      const status = (err as { status?: number }).status
      setFeedback({
        tone: 'error',
        text: status === 401 ? '需要管理员令牌' : '连接测试失败',
      })
    } finally {
      setBusy(null)
    }
  }

  /* 状态标签：未启用 / 已配置 / 连接正常 / 连接失败 */
  const statusBadge: { tone: Tone; text: string } = (() => {
    if (!settings?.enabled) return { tone: 'idle', text: '未启用' }
    if (!settings.base_url || !settings.model) return { tone: 'warning', text: '未配置完整' }
    if (feedback?.tone === 'ok') return { tone: 'normal', text: '连接正常' }
    if (feedback?.tone === 'error') return { tone: 'critical', text: '连接失败' }
    return { tone: 'info', text: '已配置' }
  })()

  return (
    <Panel
      title="AI 模型服务"
      icon={<IconSettings size={14} />}
      description="用于预警与报警的辅助分析，不参与报警等级判定"
      extra={
        <Badge tone={statusBadge.tone} dot>
          {statusBadge.text}
        </Badge>
      }
    >
      {loading ? (
        <p className="ai-model__hint">正在读取配置…</p>
      ) : (
        <div className="ai-model">
          <div className="ai-model__grid">
            <label className="ai-model__field">
              <span className="ai-model__label">服务类型</span>
              <select
                className="ai-model__input"
                value={provider}
                onChange={(e) => handleProviderChange(e.target.value as AIProvider)}
              >
                {providers.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="ai-model__field">
              <span className="ai-model__label">启用模型服务</span>
              <select
                className="ai-model__input"
                value={enabled ? 'on' : 'off'}
                onChange={(e) => setEnabled(e.target.value === 'on')}
              >
                <option value="off">关闭</option>
                <option value="on">开启</option>
              </select>
            </label>

            <label className="ai-model__field ai-model__field--wide">
              <span className="ai-model__label">API Base URL</span>
              <input
                className="ai-model__input"
                type="text"
                value={baseUrl}
                placeholder="http://127.0.0.1:8080/v1"
                onChange={(e) => setBaseUrl(e.target.value)}
              />
            </label>

            <label className="ai-model__field">
              <span className="ai-model__label">Model</span>
              <input
                className="ai-model__input"
                type="text"
                value={model}
                placeholder="模型名称"
                onChange={(e) => setModel(e.target.value)}
              />
            </label>

            <label className="ai-model__field">
              <span className="ai-model__label">
                API Key
                {settings?.api_key_configured && (
                  <span className="ai-model__masked">已保存 {settings.masked_api_key}</span>
                )}
              </span>
              <input
                className="ai-model__input"
                type="password"
                value={apiKey}
                autoComplete="off"
                placeholder={settings?.api_key_configured ? '留空表示不修改' : '本地服务可留空'}
                onChange={(e) => setApiKey(e.target.value)}
              />
            </label>

            <label className="ai-model__field">
              <span className="ai-model__label">Temperature</span>
              <input
                className="ai-model__input"
                type="number"
                min={0}
                max={2}
                step={0.1}
                value={temperature}
                onChange={(e) => setTemperature(Number(e.target.value))}
              />
            </label>

            <label className="ai-model__field">
              <span className="ai-model__label">最大输出 Tokens</span>
              <input
                className="ai-model__input"
                type="number"
                min={64}
                max={8192}
                step={64}
                value={maxTokens}
                onChange={(e) => setMaxTokens(Number(e.target.value))}
              />
            </label>

            <label className="ai-model__field">
              <span className="ai-model__label">请求超时（秒）</span>
              <input
                className="ai-model__input"
                type="number"
                min={3}
                max={120}
                step={1}
                value={timeout}
                onChange={(e) => setTimeoutValue(Number(e.target.value))}
              />
            </label>

            <label className="ai-model__field">
              <span className="ai-model__label">管理员口令</span>
              <input
                className="ai-model__input"
                type="password"
                value={adminToken}
                autoComplete="off"
                placeholder="修改配置时需要"
                onChange={(e) => setAdminToken(e.target.value)}
              />
            </label>
          </div>

          <div className="ai-model__actions">
            <button
              type="button"
              className="ai-model__btn ai-model__btn--primary"
              onClick={handleSave}
              disabled={busy !== null}
            >
              {busy === 'save' ? '正在保存…' : '保存配置'}
            </button>
            <button
              type="button"
              className="ai-model__btn"
              onClick={handleTest}
              disabled={busy !== null}
            >
              {busy === 'test' ? '正在测试…' : '测试连接'}
            </button>
            {settings?.api_key_configured && (
              <button
                type="button"
                className="ai-model__btn"
                onClick={handleClearKey}
                disabled={busy !== null}
              >
                清除 API Key
              </button>
            )}
          </div>

          {feedback && (
            <p className={`ai-model__feedback ai-model__feedback--${feedback.tone}`}>
              {feedback.text}
            </p>
          )}

          {models.length > 0 && (
            <MetricList>
              <MetricRow
                label="可用模型"
                value={models.length}
                unit="个"
                hint={models.slice(0, 3).join(' · ')}
              />
            </MetricList>
          )}

          <p className="ai-model__hint">
            模型请求由后端发出：本地开发填写本机推理服务地址，
            云端部署填写服务器可访问的地址。
          </p>
        </div>
      )}
    </Panel>
  )
}
