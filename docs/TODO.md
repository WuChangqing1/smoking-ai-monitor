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

- [x] 设计令牌（白/绿/深灰/蓝灰/橙/红）与全局样式
- [x] 顶部栏（标题 + 日期时间 + 系统/AI/雷达/视频状态）
- [x] 左侧导航（8 个模块）+ 路由（hash 路由，零依赖）
- [x] 页面骨架 + 通用组件（Panel / StatCard / Badge / MetricList / SectionTitle / EmptyState / Skeleton）
- [x] API 客户端（超时 + 失败降级，不白屏）+ useFetch 轮询 hook
- [x] MonitorVideo 组件（视频 / 静态图回退 / 占位三态）
- [x] Chart 组件（ECharts 按需注册 + 工业风主题 + 自适应 + 空数据占位）
- [x] ErrorBoundary 兜底，避免任何渲染异常导致白屏
- [x] 视频监控页、系统设置页（启停按钮 + 设备台账 + 能力区分）

## 轮次 3-A：后端统一仿真引擎（Commit 4）

- [x] `SimulationEngine`：severity 单一驱动，状态机 normal/attention/warning/alarm/stopped
- [x] 状态机驻留时长与概率迁移（大部分时间正常，报警不频繁）
- [x] 真实采样口径：内部 10 Hz（100 ms），历史接口降采样 10~180 点
- [x] 趋势项 + 慢漂移 + 带限振动 + 噪声 + 平滑滤波（非完美直线，跳变 < 3 mm）
- [x] 环境与辅助数据关联（覆盖率、输送速度、设备负载随 severity 变化）
- [x] 启动预热 1200 点（2 分钟），趋势图开局即有内容
- [x] 内存有界：`deque(maxlen=6000)` 原始采样 + `maxlen=300` 报警记录
- [x] 并发安全：`threading.RLock`，4 线程并发测试通过
- [x] 可复现：seed=20250519，reset 后数据完全重现
- [x] `/api/system/status`、`/api/realtime`、`/api/realtime/history`、`/api/devices`、`/api/monitor-points`
- [x] `POST /api/detection/start|stop`、`/api/simulation/reset`
- [x] `POST /api/simulation/scenario/{scenario}` + 退出演示场景
- [x] `/api/alarms`、`/api/alarms/{id}`（含发现→判断→报警→处理→归档时间线）
- [x] `/api/prediction`（未来 30 min 风险预测 + 预警依据 + 相似历史事件）
- [x] `/api/knowledge`（SQLite，12 条种子事件，含资料中真实事件）
- [x] pytest 109 项全部通过（引擎业务逻辑 + API 契约）
- [x] `backend/pytest.ini`、`scripts/dev.bat`、`scripts/dev.sh`

## 轮次 3-B：综合监控首页真实接入（Commit 5）

- [ ] 首页改用 `/api/realtime`（约 1 s 轮询）填充 4 张核心状态卡
- [ ] 主监控画面旁状态动态化（在线 / AI 检测中 / AI 已停止）
- [ ] 雷达距离趋势图 + 堆积风险趋势图（ECharts，增量更新不重建实例）
- [ ] 雷达图标注当前值、基准值、报警阈值
- [ ] 数据刷新失败时保留上次数据并轻提示

## 轮次 3-C：雷视联动页（Commit 6）

- [ ] 左视频 / 中雷达分析 / 右视觉 AI + 联合判定 / 下方趋势
- [ ] 雷达卡片（当前测距、基准、变化量、10 Hz 采集、规格 0.1–40 m ±5 cm）
- [ ] 明确区分"设备最高刷新率 1000 Hz"与"系统采集频率 10 Hz"
- [ ] 视觉 AI 卡片（类别、置信度、覆盖率，标注为概率模型输出）
- [ ] 联合判断区显示双方依据与结论
- [ ] 技术解释区（传感器 / 视觉 / 融合 的互补关系）

## 轮次 6：异常报警与数据溯源（Commit 7）

- [ ] 当前报警 / 历史报警 / 报警详情（发现→判断→报警→处理→归档）
- [ ] 数据溯源多维筛选（日期/设备/类型/风险等级/状态）

## 轮次 7：智能预警与知识库页（Commit 8）

- [ ] 智能预警页：预测曲线 + 预警依据 + 相似历史事件 + 概率化措辞
- [ ] 知识库页：检索、类型筛选、详情展开
- [ ] 数据溯源页
- [ ] 扩展能力（杂质检测-规划中、行业推广）

## 轮次 8：稳定化与测试（Commit 9）

- [ ] 错误边界 / API 失败降级 / 视频 fallback
- [ ] 响应式适配、1920×1080 检查
- [ ] 前端 + 后端 + 联动测试清单逐项验证

## 轮次 9：Linux 部署（Commit 10）

- [ ] 部署前环境勘查（服务、端口、Nginx、目录）
- [ ] Nginx 站点 + systemd（或 user systemd）服务
- [ ] 部署脚本 + README 部署章节
- [ ] 独立 URL 验证

## 待确认 / 风险

- [ ] 最终监控视频未到位 → 已用固定路径 `frontend/public/videos/main-monitor.mp4` + 静态图 fallback 解耦
- [ ] 视频若超过 GitHub 单文件限制 → 走 Git LFS / 服务器单独部署 / gitignore（三选一，不阻塞开发）

## 环境说明（非阻塞，已在 DEVELOPMENT_LOG 记录）

- [ ] 本机安全策略拦截工作区外写入、PyPI 出网、esbuild 与 git 凭据助手的命名管道 →
      `pip install` / `npm run build|dev` / `git push` 需放宽权限各执行一次
- [x] npm 缓存固定到仓库内（`frontend/.npmrc`），安装用 `--ignore-scripts`
- [x] pytest 缓存固定到仓库内（`backend/pytest.ini`），测试用 SQLite 内存库不写磁盘
