# 开发日志（DEVELOPMENT_LOG）

> 每个大阶段只记：完成内容 / 关键决策 / 未完成事项 / 当前 commit hash。保持简短。

---

## 轮次 1 — 资料分析与工程初始化

**完成内容**

- 勘查工作目录、Git、GitHub CLI、conda 环境。
- 编写零依赖 Word97 二进制提取器 `scripts/extract_doc.py`，成功提取 `报告.doc`、`申报书.doc` 全文（本机无 Word/LibreOffice，officecli 不支持旧版 `.doc`）。
- 解析 `功能模块对应截图.docx`：提取 10 行模块对照表 + 7 张原始截图到 `docs/reference/`。
- 人工查看全部截图与 `检测图片.png`，确认原系统界面结构与真实报警画面。
- 产出 `docs/PROJECT_CONTEXT.md`（后续唯一长期上下文）、`docs/TODO.md`、`docs/DEVELOPMENT_LOG.md`。
- 初始化 monorepo：`frontend/`（React 18 + Vite 6 + TS + ECharts）、`backend/`（FastAPI + Uvicorn + SQLite）、`docs/`、`scripts/`、`deployment/`。
- 前后端自检通过；首个 commit 并推送 GitHub Private 仓库。

**关键决策**

1. **不新建第二套项目**，全部文件位于 `D:\CodingData\Github\dsh\Smoking`，原始 4 个资料文件保持在根目录只读。
2. **Python 统一使用 conda `smoking` 环境**（`D:\App\Business\Coding\Python\Miniconda\envs\smoking\python.exe`，Python 3.12.14），不新建环境、不污染 base。
3. **依赖最小化**：前端不引路由库/组件库/状态库（自写 hash 路由 + 设计令牌 + 工业风组件），ECharts 为唯一重型依赖；后端只用 FastAPI + Uvicorn，数据库用 stdlib `sqlite3`。
4. **系统边界继承原项目**：3 台雷达 + 15 台摄像头共 18 台设备、7 个点位；点位 1–3 做雷视联合判断，点位 4–7 仅视觉单独判断（与资料中"同时配备则联合判断"一致）。
5. **仿真引擎单一数据源**：后端 `SimulationEngine` 用状态机 + 连续时间演化生成数据，前端只消费不理解业务；所有指标由同一状态派生，保证时序连续、指标关联，杜绝前端 `Math.random()`。
6. **视频解耦**：固定路径 `frontend/public/videos/main-monitor.mp4`，`<video>` onError 自动回退静态监控图；换视频不需要改业务代码。
7. node 工具链用 npm（随 Node 分发，评委机器可复现）。

**未完成事项**

- 最终监控视频未生成 → 当前用 `检测图片.png` 作主监控画面占位。
- Linux 服务器部署未开始（本地开发测试基本完成后再做，避免频繁 SSH）。

**Commit**：`8c9718ca0ec708c82dfcbdd59ab55165244723be`
（`chore: initialize smoking monitoring platform` → 已推送 GitHub **Private** 仓库 `WuChangqing1/smoking-ai-monitor`）

**环境说明（后续开发必须遵守）**

- Python 一律使用 conda `smoking` 环境：
  `D:\App\Business\Coding\Python\Miniconda\envs\smoking\python.exe`（Python 3.12.14）
- 本机安全策略会拦截：工作区外写入、PyPI 出网、以及 esbuild / git 凭据助手依赖的命名管道。
  因此 `pip install`、`npm run build`、`npm run dev`、`git push` 需要在放宽权限的情况下执行一次。
- npm 缓存固定在仓库内（`frontend/.npmrc` → `../.npm-cache`），安装使用 `--ignore-scripts`
  （esbuild / rollup 的平台二进制通过 optionalDependencies 分发，无需 postinstall）。

---

## 轮次 2 — 工业风 UI 基础

**完成内容**

- 设计系统：`tokens.css`（白底 / 绿主强调 / 深灰文字 / 蓝灰辅助 / 红橙绿状态语义）+ `base.css`。
- 布局：`AppLayout`（顶栏 + 左导航 + 主工作区）、`TopBar`（标题 + 日期时间 + 四项运行状态）、
  `Sidebar`（3 分组 8 模块，可折叠）。
- 自写 hash 路由替代 react-router。
- 通用组件：Panel / StatCard / Badge / MetricRow / SectionTitle / EmptyState / Skeleton /
  PagePlaceholder / ErrorBoundary / MonitorVideo / Chart（ECharts 按需注册）。
- 页面：综合监控首页（4 状态卡 + 核心视频区 + 运行状态栏）、视频监控（4 监控点，仅 Camera 01 有素材）、
  系统设置（检测任务启停 + 设备台账 + 已部署/规划能力区分）；其余 5 页为信息完整的占位页。
- 数据层：`api/client.ts`（超时、中文错误、降级）、`hooks/useFetch`（轮询 + 失败保留上次数据）、
  `types/index.ts`（与后端对齐的完整类型）。

**关键决策**

1. **不引入任何 UI 组件库与路由库**：只保留 React + ECharts 两个运行时依赖；
   图标用内联 SVG，路由用 40 行 hash 路由。依赖数量是可控的（见 README 技术栈表）。
2. **状态语义固定**：绿=正常、橙=预警/关注、红=严重报警、灰=停止/离线、蓝灰=提示，全站统一。
3. **占位页不放假数据**：未实现的页面明确写出职责、将展示内容与依赖接口，
   遵守「不允许全部页面使用 mock 静态 JSON」。
4. **`useFetch` 失败时保留上一次成功数据**，只在从未成功过时展示错误态 —— 这是"不白屏"的关键。
5. 修复 `styles/index.css` 误写 JS 风格 `import` 导致构建产物尾部注入无效 CSS 的问题：
   样式入口改由 `main.tsx` 显式按序引入。

**未完成事项**

- 实时数据尚未接入，首页/雷视联动等页面的数值区域为占位。
- 启停按钮已接好接口调用与错误提示，但后端接口未实现（轮次 4）。

**验证**：`tsc + vite build` 通过且无警告（62 模块）；dev server 与后端联调，
`/api/health` 经 Vite 代理正常返回。

**Commit**：`612e4e145773424c38470a90a0a41d0a034c14f9`
（`feat: build industrial monitoring UI foundation` → 已推送）

---

## 轮次 3-A — 后端统一仿真引擎

**完成内容**

- `app/services/simulation.py`：SimulationEngine（进程级单例）
- `app/services/models.py`：内部数据口径与状态/等级枚举、文案映射
- `app/services/ticker.py`：后台 10 Hz tick 守护线程
- `app/services/devices.py`：设备台账与 7 个监控点位（取自验收报告）
- `app/services/knowledge.py`：SQLite 知识库 + 12 条种子事件
- `app/schemas.py`：Pydantic 响应模型（API 契约）
- `app/routers/`：system / realtime / control / alarms / prediction / knowledge
- 测试：`tests/test_simulation.py`（44 项引擎业务逻辑）、
  `tests/test_api_simulation.py`（65 项 API 契约与行为）、`tests/conftest.py`
- `backend/pytest.ini`、`scripts/dev.bat`、`scripts/dev.sh`

**关键决策**

1. **severity 单一驱动**：引入"堵料严重度" 0~1，由状态机按固定斜率推进；
   雷达距离、物料覆盖率、输送速度、设备负载、风险指数全部由 severity 派生，
   因此指标之间天然自洽，`risk ↔ distance` 严格单调负相关（测试用皮尔逊相关系数验证）。
2. **不做完美直线**：每个信号 = 趋势项 + 慢漂移 + 带限振动 + 高斯噪声 + 一阶低通滤波。
   实测正常状态单步跳变 < 3 mm，粒度与工业传感器一致。
3. **10 Hz 内部 / 1 s 对外**：引擎按资料口径 100 ms 采样，历史接口降采样到
   10~180 点（默认 120），浏览器约 1 s 轮询一次，不会把数千点丢给前端。
4. **报警不频繁**：状态机大部分时间停在 normal；只有 32% 概率进入 warning、
   14% 概率进入 alarm，且每轮自动循环最多报警一次。
   轮次内实测：连续 2 分钟正常运行 **0 次报警**。
5. **演示场景接口**：`POST /api/simulation/scenario/{scenario}` 可强制切到
   normal/attention/warning/alarm，便于答辩前录屏；不放在主界面显眼位置。
   "退出演示场景"刻意用 `POST /api/simulation/scenario`（无路径参数）——
   `/scenario/clear` 会被 `/scenario/{scenario}` 抢先匹配而报 422。
6. **可复现**：seed 默认 20250519（即真实事件日期），固定 seed 下
   `reset()` 后能重现完全相同的初始数据；pytest 不会因随机偶发失败。
7. **内存有界**：原始采样 `deque(maxlen=6000)`（10 分钟 @10Hz），报警记录 `maxlen=300`。
8. **并发安全**：所有读写走同一把 `threading.RLock`；已用 4 线程 × 300 次
   `tick()+snapshot()` 并发测试验证状态不被写坏。
9. **知识库用 SQLite 内存库做测试**：`KnowledgeBase` 支持 `:memory:`，
   测试不写磁盘、不留垃圾文件；`conftest.py` 每个用例重建引擎与知识库。

**修正的真实缺陷**

- 知识库全文检索 SQL 的占位符数量与 `LIKE` 子句数量不一致（11 vs 10）导致查询报错。
- Pydantic v2 不接受内部 dataclass 直接作为响应模型，`/api/realtime` 需显式构造 Out 模型。
- 主监控点 IP 生成公式偏移一位（`.199` 而非资料中的 `.198`）。
- 覆盖率映射口径原先在仿真与报警记录两处各写一份，已统一为 `coverage_for_severity()`。

**未完成事项**

- 前端尚未接入这些接口（轮次 3-B）。

**验证**：`pytest` **109 passed**；uvicorn 实际启动后 10 Hz tick 推进正常
（5 秒样本时间推进 5.00 s），`/api/detection/stop` 后数据完全冻结，
`reset` 回到 normal，6 组只读接口全部 200。

**Commit**：`待填`
