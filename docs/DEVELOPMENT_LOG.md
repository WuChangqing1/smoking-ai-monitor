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

**Commit**：`2c8600b08565fe647bd72a6b0760e2daf2b81f93`
（`feat: add realtime simulation backend` → 已推送）

---

## 轮次 3-B — 综合监控首页接入真实数据

**完成内容**

- `AppLayout` 统一轮询：`/api/system/status` 1.5 s、`/api/realtime` 1.0 s、`/api/devices` 一次
- `components/chartOptions.ts`：雷达距离趋势、堆积风险趋势、预测曲线三套工业风 option
- `OverviewPage` 重写为完全由后端驱动
- 后端 `/api/realtime` 新增 `sample_interval_seconds`，如实标注趋势图时间跨度

**关键决策**

1. **前端零业务数据**：页面不再有任何派生或伪造的数值，全部来自引擎快照；
   连"数据更新于 xx:xx:xx"都取自成功响应时间。
2. **图表不重建实例**：`<Chart>` 持有 ECharts 实例，option 变化只 `setOption`，
   配合 `ResizeObserver` 自适应；滚动更新因此是平滑的。
3. **趋势窗口固定 120 点**：由后端降采样后返回，前端不做累积，
   内存不随时间增长；X 轴按真实采样时刻标注（"最近约 2 分钟"）。
4. **雷达图标注三条信息**：当前值打点、基准线 0.72 m（蓝灰虚线）、
   报警阈值 0.58 m（红虚线，取自资料中的真实报警值）。
5. **风险图颜色跟随等级**而非彩虹渐变：低=绿、中=蓝灰、高=橙、严重=红，
   并画出 30/55/80 三条等级分界参考线。
6. **数据中断不清屏**：复用已有的 `useFetch`（失败时保留上次成功数据），
   页面顶部只加一条橙色轻提示"数据更新暂时中断"，不白屏。

**未完成事项**

- 雷视联动页仍为占位（轮次 3-C）。

**验证**：`tsc + vite build` 通过（617 模块，无警告）；后端 `pytest` **110 passed**；
前后端联调通过 Vite 代理验证 `/api/system/status`、`/api/realtime`、`/api/devices` 全部可达，
静态资源与模块转译正常，四个演示场景下 `realtime.sim_state` 与 `system.sim_state` 始终一致。

**Commit**：`093f10d7db8d603074bc791e2984954171ea127f`
（`feat: implement monitoring dashboard` → 已推送）

---

## 轮次 3-C — 雷视联动页

**完成内容**

- `pages/FusionPage.tsx` + `FusionPage.css`：左视频 / 中雷达分析 / 右视觉 AI + 联合判定 /
  下时间趋势 + 技术解释的四区布局
- 后端预测模型加固（饱和外推 + 封顶 96%），新增 2 项预测分级测试

**关键决策**

1. **联合判定做成可视化公式**：`雷达 ＋ 视觉 ↓ 结论`，
   下方逐条列出双方依据，让"融合"这件事本身可见，而不是只给一个结果词。
2. **明确区分设备能力与系统采集频率**：规格区同时列出
   "设备最高刷新率 1000 Hz" 与 "本系统采集频率 10 Hz"，并说明两者不是一回事。
3. **视觉区显式标注概率属性**：置信度旁注明"概率模型输出，不是准确率"，
   并给出推理耗时，说明视觉链路的固有延迟。
4. **技术解释区用三方对比**（视觉 / 雷达 / 融合），优劣项以 ＋/－ 标记，
   并明确写出"融合的目标不是用大模型替代传感器"。
5. **趋势图复用 `chartOptions`**：与首页共用同一套 option 生成函数，
   保证两个页面的图表口径、配色与标注完全一致。
6. **预测模型加固**：原实现会把预警阶段直接外推到 100%，等于给出确定性结论。
   改为三重约束 —— 斜率窗口 3→5 分钟、外推走饱和函数（渐近而不越界）、
   仅趋势向上时叠加状态机牵引且牵引量封顶，整体预测封顶 96%。

**修正的真实缺陷**

- 预测在 warning 场景下直接顶到 100%，不符合"概率预测"的定位。
- `FusionPage` 遗留未使用的 `STATE_TONE` 常量，被 `tsc --noUnusedLocals` 拦截。

**未完成事项**

- 异常报警 / 数据溯源 / 智能预警 / 知识库四个页面仍为占位（后续轮次）。

**验证**：`tsc + vite build` 通过（618 模块，无警告）；后端 `pytest` **112 passed**；
四场景联调（每场景收敛 25 s）确认状态一致性：

| 场景 | realtime | system | 联合判定 | 风险 | 测距 | 覆盖率 | 30 min 预测 |
|---|---|---|---|---|---|---|---|
| normal | normal | normal | normal | 23.7% | 0.721 | 0.31 | 23.7→21.2 |
| attention | attention | attention | attention | 45.8% | 0.673 | 0.49 | 45.8→78.0 |
| warning | warning | warning | warning | 70.0% | 0.621 | 0.68 | 70.0→96.0 |
| alarm | alarm | alarm | alarm | 88.7% | 0.581 | 0.82 | 88.7→96.0 |

首页、雷视联动、风险趋势、视觉判断随场景同步变化，无互相矛盾。

**Commit**：`待填`
