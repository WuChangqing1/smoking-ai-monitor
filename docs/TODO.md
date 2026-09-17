# 任务状态（TODO）

> 维护规则：完成即勾选，不要每次重新扫描代码库判断进度。
> 优先级：P0 能运行 → P1 首页视觉 → P2 视频 → P3 雷视联动 → P4 动态数据 → P5 报警溯源 → P6 提前预警 → P7 知识库 → P8 部署 → P9 细节。

## 轮次 1：资料分析 + 工程初始化（Commit 1）

- [x] 检查工作目录 / Git 状态 / GitHub CLI
- [x] 验证 conda `smoking` 环境（Python 3.12.14）
- [x] 提取 `申报书.doc`、`报告.doc` 文本（`scripts/extract_doc.py`，零依赖）
- [x] 提取 `功能模块对应截图.docx` 的模块表与 7 张截图
- [x] 提炼需求 → `docs/PROJECT_CONTEXT.md`
- [x] 建立 `docs/TODO.md`、`docs/DEVELOPMENT_LOG.md`
- [x] 确定技术栈（React+Vite+TS+ECharts / FastAPI / SQLite / Nginx）
- [x] 初始化 frontend（React 18 + Vite + TS）与 backend（FastAPI）
- [x] 建立 `.gitignore`、`README.md` 初稿
- [x] 前后端均可启动（自检通过）
- [x] Git init + 第一个 commit
- [x] 创建 GitHub **Private** 仓库并 push

## 轮次 2：工业风 UI 基础（Commit 2）

- [ ] 设计令牌（白/绿/深灰/蓝灰/橙/红）与全局样式
- [ ] 顶部栏（标题 + 日期时间 + 系统/AI/雷达/视频状态）
- [ ] 左侧导航（8 个模块）+ 路由（hash 路由，零依赖）
- [ ] 页面骨架 + 通用组件（Card / StatCard / Badge / Table / Panel / Chart）
- [ ] API 客户端（轮询 + 失败降级，不白屏）

## 轮次 3：综合监控首页（Commit 3）

- [ ] 核心监控视频区（视觉中心，Camera 01 / 制丝线 2 号工位 / 在线 / AI 检测中）
- [ ] 4 张核心状态卡（在线设备、当前风险、今日预警、连续运行）
- [ ] 设备状态概览、基础图表

## 轮次 4：后端仿真引擎（Commit 4）

- [ ] `SimulationEngine`：状态机 normal/attention/warning/alarm/stopped
- [ ] 状态驱动数据（雷达距离、覆盖率、置信度、温湿度、输送速度、风险指数）
- [ ] 预热历史数据（趋势图开局即有内容）
- [ ] `/api/system/status`、`/api/realtime`、`/api/realtime/history`、`/api/devices`
- [ ] `POST /api/detection/start|stop`、`/api/simulation/reset`

## 轮次 5：雷视联动（Commit 5）

- [ ] 雷达面板 / 视觉 AI 面板 / 联合判断（后端逻辑，非前端写死）
- [ ] 距离趋势图 + 堆积风险趋势图（滚动，只保留 60~120 点）
- [ ] "为什么不能只使用视觉"对比说明

## 轮次 6：报警与溯源（Commit 6）

- [ ] 当前报警 / 历史报警 / 报警详情（发现→判断→报警→处理→归档）
- [ ] 数据溯源多维筛选（日期/设备/类型/风险等级/状态）

## 轮次 7：智能预警与知识库（Commit 7）

- [ ] 未来 30 min 风险预测 + 预警依据 + 概率化措辞
- [ ] 知识库（SQLite，8~15 条高仿真事件，含 `EVT-20250519-02`）
- [ ] 扩展能力（杂质检测-规划中、行业推广）

## 轮次 8：稳定化与测试（Commit 8）

- [ ] 错误边界 / API 失败降级 / 视频 fallback
- [ ] 响应式适配、1920×1080 检查
- [ ] 前端 + 后端 + 联动测试清单逐项验证

## 轮次 9：Linux 部署（Commit 9）

- [ ] 部署前环境勘查（服务、端口、Nginx、目录）
- [ ] Nginx 站点 + systemd（或 user systemd）服务
- [ ] 部署脚本 + README 部署章节
- [ ] 独立 URL 验证

## 待确认 / 风险

- [ ] 最终监控视频未到位 → 已用固定路径 `frontend/public/videos/main-monitor.mp4` + 静态图 fallback 解耦
- [ ] 视频若超过 GitHub 单文件限制 → 走 Git LFS / 服务器单独部署 / gitignore（三选一，不阻塞开发）
