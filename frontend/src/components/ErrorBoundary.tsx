/**
 * 顶层错误边界。
 *
 * 比赛现场最怕白屏：任何渲染期异常都被这里兜住，展示可读的提示与恢复按钮，
 * 而不是让评委看到一片空白。
 */

import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // 保留控制台信息便于排查；不向外上报，避免引入额外依赖
    console.error('[监控平台] 页面渲染异常：', error, info.componentStack)
  }

  private handleReload = (): void => {
    window.location.reload()
  }

  private handleReset = (): void => {
    this.setState({ error: null })
  }

  render(): ReactNode {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div className="fatal">
        <div className="fatal__card">
          <span className="fatal__mark" aria-hidden="true" />
          <h1 className="fatal__title">页面出现异常</h1>
          <p className="fatal__desc">
            监控平台界面渲染时发生错误。实时数据服务可能未启动，或页面状态异常。
          </p>
          <pre className="fatal__detail">{error.message}</pre>
          <div className="fatal__actions">
            <button type="button" className="fatal__btn fatal__btn--primary" onClick={this.handleReload}>
              重新加载页面
            </button>
            <button type="button" className="fatal__btn" onClick={this.handleReset}>
              尝试恢复
            </button>
          </div>
          <p className="fatal__hint">
            若持续出现，请先确认后端服务已启动：
            <br />
            Windows：<code>scripts\backend.bat</code>
            <br />
            Linux / macOS：<code>./scripts/dev.sh</code>
            <br />
            也可直接打开线上地址 <code>http://110.42.236.65:18082/</code> 查看平台。
          </p>
        </div>
      </div>
    )
  }
}
