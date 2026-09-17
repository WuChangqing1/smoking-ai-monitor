/**
 * 应用入口。
 *
 * 结构：ErrorBoundary（兜底不白屏）→ AppLayout（顶栏 + 导航 + 工作区）。
 */

import ErrorBoundary from './components/ErrorBoundary'
import AppLayout from './app/AppLayout'
import './components/ErrorBoundary.css'

export default function App() {
  return (
    <ErrorBoundary>
      <AppLayout />
    </ErrorBoundary>
  )
}
