/**
 * 轮次 1 最小外壳：仅用于确认工程可构建、可启动。
 * 轮次 2 将替换为「顶部栏 + 左侧导航 + 主工作区」的完整工业风布局。
 */
export default function App() {
  return (
    <div className="boot-screen">
      <div className="boot-card">
        <div className="boot-mark" aria-hidden="true" />
        <h1>烟厂制丝线物流智能监控平台</h1>
        <p className="boot-sub">
          视觉识别 + 激光雷达 多模态融合 · 提前预警与异常溯源
        </p>
        <p className="boot-note">
          前端工程已就绪（React + Vite + TypeScript）。
          <br />
          监控视频固定替换路径：<code>public/videos/main-monitor.mp4</code>
        </p>
      </div>
    </div>
  )
}
