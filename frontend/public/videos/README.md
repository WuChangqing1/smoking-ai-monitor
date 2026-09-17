# 监控视频目录 / Monitor video directory

平台**唯一**的视频替换约定是这个目录下的固定文件名：

```
frontend/public/videos/main-monitor.mp4
```

## 替换步骤（不需要改任何业务代码）

1. 把最终生成的监控视频重命名为 `main-monitor.mp4`；
2. 复制到本目录；
3. 刷新页面即可（开发环境会自动热更新，生产环境重新 `npm run build` 或直接覆盖服务器上的同名文件）。

## 视频不存在时会怎样

`<video>` 加载失败时，前端的 `MonitorVideo` 组件会自动回退到静态监控画面
`frontend/public/images/main-monitor-fallback.png`（由 `检测图片.png` 生成），
页面不会报错、不会白屏。因此**视频未就绪不会阻塞任何开发或演示**。

## 视频编码建议

- 容器：MP4（H.264 + yuv420p），浏览器兼容性最好；
- 分辨率：1920×1080 或 1280×720；
- 时长：10~60 秒循环片段即可（播放器已设置 `loop`）；
- 无音轨或有音轨均可（页面 `muted` 播放以满足浏览器自动播放策略）；
- 码率建议 ≤ 4 Mbps，文件尽量控制在 50 MB 以内。

## 关于 Git

超过 GitHub 普通 Git 单文件限制（100 MB）的视频**不要直接提交**。
`.gitignore` 已忽略 `frontend/public/videos/*.mp4`。大视频请三选一：

1. 使用 Git LFS 管理；
2. 部署到服务器时单独上传（推荐，见 `deployment/`）；
3. 保持忽略，仅在目标机器上放置文件。

以上任一种方式都**不改变**上面的固定替换路径约定。
