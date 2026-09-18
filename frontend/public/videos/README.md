# 监控视频目录 / Monitor video directory

平台**唯一**的视频接入约定是这个目录下的固定文件名：

```
frontend/public/videos/main-monitor.mp4
```

## 接入步骤（不需要改任何业务代码）

1. 把监控视频命名为 `main-monitor.mp4`；
2. 复制到本目录；
3. 刷新页面即可（开发环境会自动热更新，生产环境重新 `npm run build` 或直接覆盖服务器上的同名文件）。

## 视频不存在时会怎样

`<video>` 加载失败时，前端的 `MonitorVideo` 组件会自动回退到静态监控画面
`frontend/public/images/main-monitor-fallback.png`（由 `检测图片.png` 生成），
页面不会报错、不会白屏。因此**视频未接入也不会影响平台运行与监控展示**。

回退是两层的：先对视频路径发 HEAD 请求确认返回的确实是视频类型
（避免某些服务器对不存在的路径返回 `index.html` 且状态码 200 导致误判），
再由 `<video>` 的 `onError` 兜底。

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
2. 部署到服务器时单独上传（推荐，见 `deployment/README.md`）；
3. 保持忽略，仅在目标机器上放置文件。

以上任一种方式都**不改变**上面的固定接入约定。
