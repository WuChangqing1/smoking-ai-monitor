import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/index.css'

const rootEl = document.getElementById('root')

if (!rootEl) {
  // 极端情况：根节点缺失时也不能白屏，给出可读提示。
  document.body.innerHTML =
    '<div style="padding:32px;font-family:sans-serif">页面根节点缺失，请检查 index.html。</div>'
} else {
  ReactDOM.createRoot(rootEl).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
}
