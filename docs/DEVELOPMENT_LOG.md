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

**Commit**：`7cf7fd60687f2d1cb7fc776a50a137b22b8efdc9`
（`feat: implement radar vision fusion monitoring` → 已推送）

---

## 轮次 4 — 异常报警与数据溯源

**完成内容**

- 新增通用组件：`Modal`（ESC/遮罩关闭、滚动锁定、焦点恢复）、`FilterBar`（行式筛选条）
- 新增 `components/AlarmDetailModal.tsx`：报警详情弹层，含完整处理闭环时间线
- `pages/AlarmsPage.tsx`：当前报警 / 历史报警双标签页 + 筛选 + 详情下钻
- `pages/TracePage.tsx`：六维筛选（起止日期、设备、异常类型、等级、状态）+ 分页 + 汇总
- 后端：`/api/alarms` 增加 `event_type_text` 中文标签；新增 `/api/alarms/options` 选项接口
- 后端：种子历史报警由 4 条扩展到 6 条，覆盖 3 台设备、4 种异常类型、2 个等级
- 后端：系统自动生成的报警改为按主导特征分类（`_classify_event`）

**关键决策**

1. **颜色纪律**：等级用行首 3px 细色条 + 小标签表达（提示=蓝灰、预警=橙、严重=红），
   不做整行染色、不做满屏红色；只有 critical 使用红色实心标签。
2. **当前报警不做筛选**：当前报警本就应当一览无余，
   筛选只出现在"历史报警"，避免使用者误以为有隐藏的未处置报警。
3. **翻译表留在后端**：异常类型中文由 `/api/alarms` 的 `event_type_text` 直接给出，
   前端不再散落 `material_accumulation → 物料堆积` 之类的映射。
4. **筛选选项来自后端**：`/api/alarms/options` 由实际数据 + 资料口径生成，
   避免前端下拉与数据脱节（选项筛不出数据的尴尬）。
5. **`/api/alarms/options` 必须注册在 `/api/alarms/{event_id}` 之前**，
   否则 "options" 会被当作 event_id 而返回 404 —— 已加测试固定该行为。
6. **种子数据必须覆盖多个维度**：原实现 4 条报警全在 RAD-02，
   会让"设备"筛选下拉只有一个选项、失去演示意义。
   现改为 3 台设备 × 4 种异常类型 × 2 个等级，且设备编号都经测试确认存在于台账中。
7. **报警"当时画面"复用主监控点静态帧**：与视频替换约定一致 ——
   视频就绪后同一路径自动变为视频帧，无需改代码。

**修正的真实缺陷**

- `AlarmRecord.ts` 前端类型写成 `string`，后端实际是 Unix 秒；
  连带报警详情缺少 `baseline_distance` 字段，均已修正。
- 系统自动生成的报警一律记成 `material_accumulation`，
  现按"测距明显下降 / 速度明显下降 / 仅覆盖率偏高"三种工况分类。
- 种子报警的 `device_id` 全部硬编码为主监控点，现通过 `device_of_position()` 按点位取设备。
- `devices.py` 中辅助函数定义在使用点之后，导致 `NameError`（已调整顺序）。

**未完成事项**

- 智能预警页、知识库页仍为占位（下一轮次）。

**验证**：后端 `pytest` **119 passed**；前端 `tsc + vite build` 通过（626 模块，无警告）。
联调实测（经 Vite 代理）：

- 筛选选项：设备 `RAD-01/02/03`、异常类型 4 种；
- 各维度筛选计数自洽：`RAD-01/02/03` 各 2 条、物料堆积 3 条、其余各 1 条、
  `date_from=两天前` → 2 条、未知类型 → 0 条；
- 分页 `page=1&page_size=2` 正常；
- 报警详情闭环完整：`发现 → 判断 → 报警 → 处理 → 归档` 五阶段齐全，
  雷达趋势 60 点，画面与处理说明齐备。

**Commit**：`b0008bab3830a13909df0580acf14ebad95f9240`
（`feat: add alarm and traceability workflow` → 已推送）

---

## 轮次 5 — 智能预警与知识库页

**完成内容**

- `pages/PredictionPage.tsx` + CSS：当前→预测对比、预测曲线、预警依据、相似历史、扩展能力
- `pages/KnowledgePage.tsx` + CSS：全文检索（防抖）、类型筛选、条目展开
- 后端：新增 `_window_delta` / `_has_full_window`；雷达下降判定加最小降幅约束
- 后端新增 3 项测试（正常态不得报"持续下降"、降幅不足不判趋势、分类函数可区分工况）

**关键决策**

1. **"当前 → 预测"可视化对比**：两个大号数值中间放箭头与"未来 30 分钟"标注，
   一眼看清这页在讲"提前量"，而不是又一组 KPI。
2. **依据逐条摊开**：雷达 / 视觉 / 输送 / 环境 / 历史经验各一条，
   每条都由实测数据算出。让评委看到结论怎么来的，而不是一个孤立百分比。
3. **措辞纪律**：页面固定展示免责说明，明确"不给确定性结论"；
   建议措施写"建议关注 / 建议检查 / 降低进料量后观察"，
   测试中显式断言不得出现"一定""必然"。
4. **扩展能力显式标注"规划能力"**：杂质检测与自动分拣画出
   `识别杂质 → 定位 → 机械臂/分拣 → 人工复核线` 四步链路，但不伪装成已部署。
5. **知识库按"复用价值"组织**：详情顺序为
   `雷达/视觉/环境记录 → 异常前兆模式（橙色强调）→ 人工审核/处理措施/结果 → 预防建议（绿色强调）`。
   "异常前兆模式"与"预防建议"是经验库真正可复用的部分，因此单独配色强调。
6. **搜索做防抖**：关键词输入 280 ms 防抖，避免每敲一个字请求一次；
   用 `useEffect` 而非 `useMemo`（后者不提供清理时机之外的语义保证）。

**修正的真实缺陷**

- **依据自相矛盾**：正常状态下雷达围绕基准抖动会被判成"连续下降 2 分钟"，
  而同一句里显示"变化 -0.00 m"。根因是趋势判定只看逐点单调性、不看累计幅度。
  现要求累计降幅 ≥ 5 mm 才判定为下降趋势，并有测试锁定该不变量。
- **观察窗口不足时的误读**：刚切换场景或刚重置时历史不足 3 分钟，
  却仍输出"近 3 分钟变化 +0.0 个百分点"。现改为
  "历史窗口不足 3 分钟，暂无法给出覆盖率变化趋势"；
  雷达侧同理输出"已持续下降至少 N 分钟"，不夸大观测时长。

**未完成事项**

- 稳定化（错误边界已具备，仍需响应式与 1920×1080 逐项核查）
- Linux 部署

**验证**：后端 `pytest` **121 passed**；前端 `tsc + vite build` 通过（626 模块，无警告）。
联调实测：

| 场景 | 当前风险 | 30 min 预测 | 变化 | 依据条数 | 最高相似事件 |
|---|---|---|---|---|---|
| normal | 23.4% | 17.7% | 稳定 | 4 | — |
| warning | 69.8% | 96.0% | 快速上升 | 5 | EVT-20250517-01 @ 0.95 |

知识库 12 条记录、4 种异常类型；`keyword=0.71` → 6 条，
`event_type=物料堆积` → 8 条；资料中的真实事件 `EVT-20250519-02` 存在且前兆描述含 `0.71`。

**Commit**：`08606ce3d8084bc5f89b40becffa857e385a8c15`
（`feat: add predictive warning and knowledge base pages` → 已推送）

---

## 轮次 6 — 稳定化与演示模式

**完成内容**

- `SettingsPage` 新增「演示模式」区：四个场景按钮（正常/关注/预警/异常）+ 恢复自动循环
- `MonitorVideo` 重写为「先探测、再兜底」两层回退
- 完成 8 个页面 + 全部接口 + 联动行为的逐项核查

**关键决策**

1. **演示场景放进「系统设置」而非主界面**：按要求"不要把这个按钮突出展示在主界面给评委"，
   放在设置页并附说明文字，正常演示时无需使用。
2. **视频回退必须"先探测"**：原实现只依赖 `<video>` 的 `onError`。
   实测发现前端开发服务器对不存在的 `/videos/main-monitor.mp4` 返回的是
   `index.html`（状态码 **200**、`content-type: text/html`）而不是 404，
   仅看状态码会误判成"视频存在"。
   现在先发 HEAD 请求，只有 `content-type` 以 `video/` 开头才渲染 `<video>`，
   否则直接回退静态图；`onError` 作为第二层兜底（编码不支持、文件损坏）。
3. **探测期间保持容器尺寸**：用同尺寸骨架占位，避免"先空后满"的布局跳动。
4. `notImplemented` 兜底文案由"将在轮次 4 生效"改为版本不匹配提示 ——
   接口其实早已实现，旧文案会误导。

**核查结果（逐项）**

*前端*：8 个页面模块全部转译通过（0 失败）；静态资源可达；
`/videos/main-monitor.mp4` 探测为 `text/html` → 正确回退静态图。

*接口*：`client.ts` 中每个 GET 调用都能解析到真实路由；
5 个 POST 控制接口（start / stop / reset / scenario/{s} / scenario）实测 `ok=true`。

*联动*：停止检测后 `ts` 完全冻结（`frozen=True`）；开始后恢复推进（`advancing=True`）；
重置后回到 normal（风险 23.9%、低风险、今日预警归零）。

*风险变化驱动 UI*：normal → warning → alarm 三态下，
`realtime.sim_state` 与 `system.sim_state` 始终一致，
风险指数 23.6% → 67.2% → 88.2% 单调上升，联合判断 正常 → 预警 → 异常 同步变化。

*首页四项*：在线设备 18/18、当前风险等级、今日预警、连续运行均可正常取值；
顶栏四项状态为 系统运行=正常 / AI 分析=运行中 / 雷达数据=正常 / 视频监控=在线。

*响应式*：断点复核确认 1920×1080 命中完整宽屏布局
（顶栏状态胶囊完整、首页 4 列状态卡 + 右侧信息栏、雷视联动三列），
1366/1440 笔记本宽度进入预设收窄分支，无断点重叠冲突。

**未完成事项**

- Linux 部署（下一轮次）。

**验证**：后端 `pytest` **121 passed**；前端 `tsc + vite build` 通过（626 模块，无警告）。

**Commit**：`7e65f319941105677a975b00ed09543c11ddbeb4`
（`fix: improve dashboard stability and presentation` → 已推送）

---

## 轮次 7 — Linux 部署

**线上地址：http://110.42.236.65/smoking/**

**完成内容**

- 部署前只读勘查：`scripts/recon.sh`、`recon-ports.sh`、`recon-net.sh`、`recon-routing.sh`
- 后端部署到 `~/apps/smoking-monitor`（venv + systemd，开机自启 + 异常重启）
- 前端本地构建后上传到 `/var/www/smoking-monitor/dist`
- 通过路径前缀接入已放通的 80 端口，新增 1 行 `include`、2 个新文件
- `deployment/README.md`：完整部署记录、运维命令、回滚方式、改独立端口的步骤
- README 第 8 节按实测结论重写

**关键决策**

1. **云安全组是硬约束，决定了部署形态**。实测方式很直接：**在服务器上访问自身的公网 IP** ——
   放通的端口会连上，未放通的会超时。结果：只有 80/443 可连接，
   18080/18081/18082/8080/3000 等一律超时。
   因此"用独立端口对外"这条路走不通，只能复用 80。
2. **同端口无法再用第二个 server_name 命中**（80 已被 `server_name 110.42.236.65` 占用），
   于是采用与服务器上既有做法（`/market/`、`/home/`）一致的**路径前缀**接入：
   `http://110.42.236.65/smoking/`。
   实现上只在 fitness 的 server 块**追加一行 include**，改动面最小且可一行回滚。
3. **前端改为相对路径 base**：`vite.config.ts` 设 `base: './'`，
   并把 `MonitorVideo` 的视频/图片路径改成不带前导斜杠的相对路径。
   这样同一份构建产物既能挂根路径也能挂子路径，换部署位置不必重新构建 ——
   这是让"路径式接入"成立的前提。
4. **服务器不构建前端**：服务器 Node 为 v12 且无 npm，因此流程固定为
   「本地 build → 上传 dist」。deploy.sh 中已写明该约束。
5. **后端坚持只监听回环**：uvicorn 绑 `127.0.0.1:18081`，对外一律经 Nginx 反代。

**修正的真实缺陷**

- **陈旧 Nginx worker 导致 502**：master 进程自 4 月起已运行 141 天，
  reload 后旧 worker 仍持有旧配置。`systemctl restart nginx` 后恢复。
- `deploy.sh` 原先假设在服务器上构建前端，与服务器 Node v12 的现实冲突，
  已改为本地构建 + 上传。
- `gzip_types` 重复声明 `application/javascript`（新版 mime.types 已并入
  `text/javascript`）导致 `nginx -t` 警告，已修正。
- 前端静态资源与后端返回的 `snapshot` 路径统一改为相对路径，
  否则部署在 `/smoking/` 下会 404。

**未完成事项**

- 最终监控视频仍未到位（用静态图占位，替换方式已就绪）。

**验证（全部在公网地址上实测）**

| 检查项 | 结果 |
|---|---|
| 平台首页 | `/smoking/` → 200 |
| 静态资源 + 相对路径解析 | 全部 200，`./assets/...` → `/smoking/assets/...` |
| 8 个数据接口 | 全部 200 |
| 实时仿真数据 | state=normal、risk=23.6%、测距 0.721 m、10 Hz、历史 120 点 |
| 设备 / 报警 / 知识库 | 18/18 在线；报警 6 条覆盖 4 种类型；知识库 12 条 |
| 控制接口 | 场景切换与恢复均 `ok=true`，风险随之变化（预警场景实测 63.5%） |
| 进程与自启 | `active` + `enabled` |
| **已有站点回归** | fitness(80) → 200；ccqspace.site(443) → 200（服务器侧实测）；8000/18080 项目不受影响 |
| 服务器侧测试 | 部署后 `pytest` 121 passed（Python 3.10.12 下同样通过） |

**Commit**：`236d6480bd421d2298a72fb98daddc6e8dad08a8`
（`chore: add production deployment configuration` → 已推送）

---

## 轮次 8 — 独立端口入口启用（安全组放通后）

**背景**：用户在云控制台放通了 TCP 18082，独立端口入口得以启用。

**完成内容**

- 实测确认 18082 已放通
- 主入口生效：`/etc/nginx/conf.d/smoking-monitor.conf` 监听 18082
- 保留 `/smoking/` 路径式入口作为备用，两者共用同一份 dist 与同一个后端
- 文档统一为「主入口 18082 + 备用入口 /smoking/」双入口表述
- `scripts/remote-ops.sh verify` 升级为三段式：双入口 → 后端隔离 → 已有站点回归
- 新增 `scripts/verify-deployment.sh` 作为独立的一键复验脚本

**关键决策**

1. **两个入口都保留，而不是二选一**：18082 是完全独立的 server 块，
   不依赖任何其他站点配置，作为主入口；`/smoking/` 复用已放通的 80 端口作为兜底 ——
   万一以后 18082 被回收或调整，80 这条路依然通。
   两者共用同一份构建产物（相对路径 base），零额外维护成本。
2. **后端不因端口放通而改变监听方式**：仍只绑 `127.0.0.1:18081`。
   放通 18081 没有必要，反而增加绕过 Nginx 的攻击面；
   验证脚本中专门加了一项「公网 18081 应不可达」。
   实测：公网 18081 不可达（正确），回环 200。

**修正的真实缺陷**

- `monitor_point.stream` 原先返回 `/videos/main-monitor.mp4`（绝对路径），
  与前端改用相对路径的约定不一致。虽不影响使用（前端只取 `hasStream` 布尔量），
  但字段语义会误导后续真实设备接入方，已统一为相对路径。

**验证（全部实测）**

| 检查项 | 结果 |
|---|---|
| 主入口首页 + 静态资源 + assets | 全部 **200** |
| 主入口 9 个数据接口 | 全部 **200** |
| 备用入口 `/smoking/` 及接口 | 全部 **200** |
| 后端隔离 | 公网 18081 **不可达**（正确）；回环 **200** |
| 资源路径 | `stream` = `videos/main-monitor.mp4`、`snapshot` = `images/main-monitor-fallback.png`（均为相对路径） |
| 视频回退链 | 视频 404 → 前端 HEAD 探测失败 → 静态图 **200**（符合设计） |
| 已有站点回归 | fitness(80) 200、ccqspace.site(443) 200、8000 / 18080 项目不受影响 |

**线上地址**

- 主入口：**http://110.42.236.65:18082/**
- 备用入口：http://110.42.236.65/smoking/

**Commit**：`5a146982f9bfd435f22093414860ceb632a97cd4`
（`feat: enable dedicated port entry for the platform` → 已推送）

---

## 轮次 9 — 最终视频接入与画面同步遥测（video_sync）

**目标**：把最终监控视频正式接入平台，并让页面数值与视频画面严格同步。

**视频参数（实测 ffprobe）**

| 项 | 值 |
|---|---|
| 容器 / 编码 | MP4 / H.264（avc1）+ yuv420p，浏览器兼容性最佳，**无需转码** |
| 分辨率 | 1280×720（16:9） |
| 帧率 | 24 fps（240 帧） |
| 时长 | 10.00 s |
| 大小 | 2.21 MB（1.85 Mbps） |
| 音轨 | AAC 48 kHz 立体声（页面 muted 播放） |
| 接入路径 | `frontend/public/videos/main-monitor.mp4`（源文件 `Video.mp4` 保留在根目录，哈希一致） |

**完成内容**

- 后端 `app/services/video_sync.py`：关键帧轨迹 + 线性插值 + 确定性微扰
- 后端 `app/routers/video_sync.py`：`/api/video-sync/info`、`/api/video-sync/telemetry`
- 后端 `settings.run_mode`：`video_sync`（默认）/ `automatic`；`/api/meta` 暴露运行模式与视频参数
- 前端 `src/video/videoTelemetry.ts`：与后端**逐行等价**的解析实现
- 前端 `src/video/VideoSyncContext.tsx`：全站唯一时间源 + 唯一遥测解算
- 前端 `src/video/syncedTelemetry.ts`：适配层（遥测 → 页面已有快照结构）+ 预测派生
- `MonitorVideo`：接入 `playbackRate = 0.5`、注册为全站时间源、不显示播放器控件
- 系统设置新增「运行模式」区（画面同步 / 自动工况循环）
- `frontend/src/video/videoTelemetry.selftest.ts` + `frontend/scripts/check-telemetry-parity.mjs`
- 后端 `tests/test_video_sync.py`：36 项新测试

**关键决策**

1. **唯一时间源是 `video.currentTime`**，不用 `Date.now()`、不用"网页运行了多少秒"。
   采样用 `requestAnimationFrame` 读取，因此：
   * 视频暂停 → currentTime 不变 → 数据自动冻结（无需额外判断）；
   * 拖动进度 → 下一帧立即同步，不会从旧状态慢慢增长；
   * 切后台 → rAF 暂停，恢复后重新读真实值，不会因计时器累计而跑偏；
   * 循环回绕 → currentTime 变小 → 自动复位并开启新一轮趋势。
2. **0.5× 用浏览器调速，不重新编码**：源视频 10 s，演示周期约 20 s，
   文件大小与原视频不变。`playbackRate` 在 `loadedmetadata / loadeddata /
   canplay / play / playing / seeked` 六个时机重复应用 ——
   部分浏览器会在这些时点把它重置回 1.0。
3. **前后端同一套轨迹，两份实现 + 对等校验**：
   后端是权威定义，前端做本地插值以避免高频 HTTP 请求
   （UI 随 rAF 刷新，不需要 250 ms 一次请求）。
   用 `check-telemetry-parity.mjs` 做逐点比对，确保两边不会悄悄漂移。
4. **趋势图只展示当前这一轮**：`samplesUpTo(currentTime)`，
   循环后自然从 0 重新开始，不形成 `0.72→0.58→0.72` 的无限锯齿累积。
5. **报警不落库**：视频每约 20 秒循环一次，若每轮写库一分钟就有 3 条报警。
   给引擎加显式开关 `event_recording`，应用启动时在 video_sync 模式下关闭它。
   历史报警继续使用原有 6 条真实风格样例。
   （初版实现是运行时读配置，会让引擎行为隐式依赖环境变量，已改为显式开关。）
6. **保留全部既有能力**：`SimulationEngine` 与 automatic 模式完整保留，
   两种模式由 `run_mode` 选择；原 121 项测试全部继续通过。

**关键帧（实际采用，与任务规格一致）**

| t (s) | distance | risk | coverage | speed | state |
|---|---|---|---|---|---|
| 0 | 0.721 | 18 | 0.30 | 1.00 | normal |
| 2 | 0.706 | 27 | 0.37 | 0.98 | normal |
| 4 | 0.681 | 43 | 0.49 | 0.95 | attention |
| 6 | 0.651 | 59 | 0.61 | 0.91 | warning |
| 8 | 0.612 | 76 | 0.74 | 0.86 | warning |
| 10 | 0.582 | 89 | 0.83 | 0.80 | alarm |

> 未调整规格给定的数值：抽帧核对（t=0/2/4/6/7/9）确认视频中物料带
> 逐渐变宽变厚，与规格描述的堆积过程一致，因此沿用原切分点。
> 终点 0.582 m 对应资料中的真实报警测量值 0.58 m，且每个采样点存在
> ±1~3 mm 确定性微扰，不会每点都等于 0.580。

**验证**

| 检查项 | 结果 |
|---|---|
| 后端 pytest | **157 passed**（原 121 + 视频同步 36） |
| 前后端遥测对等 | **101 个时间点 × 6 个字段完全一致** |
| 前端 tsc + vite build | 通过（629 模块，无警告） |
| 视频可访问性 | `HEAD /videos/main-monitor.mp4` → 200，`content-type: video/mp4` |
| 越界安全 | t=12 → 夹到 10.0（alarm）；t=-3 → 夹到 0（normal） |
| 循环复位 | t=10 alarm → t=0 normal，同 t 数据可复现 |
| 原能力回归 | automatic 模式、启停控制、报警生成测试全部继续通过 |

**Commit**：`918950f493bff744ff0e79703a6a4a165eb77f8f`
（`feat: synchronize monitoring telemetry with demo video` → 已推送）

---

## 轮次 10 — 本地开发环境可用性修复

**问题**：用户反馈页面显示「实时数据不可用 / 无法连接后端服务（/api/realtime?points=120）/
后端服务未连接」。诊断结果：**本机后端（18080）与前端（15173）都没有在运行**，
而报错文案把问题指向了"请确认后端已在 127.0.0.1:18080 启动"，
但线上部署是正常的 —— 使用者无法判断该看哪个环境。

**完成内容**

- 新增 `scripts/backend.bat`：按项目约定用 conda `smoking` 环境启动后端，
  含环境校验（拒绝 base 环境）、依赖自检、端口占用检查
- 新增 `scripts/backend-daemon.bat`：后台守护，崩溃后 3 秒自动重启
- 重写前端连接失败提示：区分三种情况并给出**可执行**的下一步
- README 新增 4.5 一键启动与 4.6「实时数据不可用」专项排查章节

**关键决策**

1. **报错文案改为"给办法"而不是"给猜测"**：原文案硬编码端口猜测，
   现按场景分流：
   - `file://` 打开 → 告知浏览器禁止 file 协议访问接口，并给出正确地址；
   - 连接被拒 → 指向 `scripts/backend.bat` / `./scripts/dev.sh`；
   - 一致地附带线上地址，让"只想看效果"的人有一条立刻可用的路。
2. **`ApiError` 增加 `isConnectionError`**：把"连不上后端"与"后端返回错误码"
   区分开，便于后续在不同页面给出不同的降级策略。
3. **README 把该报错写成专章**：这是使用者最先撞到的问题，
   排查顺序（netstat → curl health）比一句"启动后端"更有用。
4. 补充说明：后端恢复后页面会在 1~2 秒内自动恢复（前端 1 秒轮询），**无需手动刷新**。

**验证**

| 环境 | 结果 |
|---|---|
| 本机后端 18080 | 运行中（pid 29908），`/api/health` 200，数据推进 8.00 s / 8 s |
| 本机前端 15173 | 运行中（pid 15404），`/api/realtime`、`/api/system/status` 经代理均 200 |
| 线上主入口 18082 | 200，数据推进 8.10 s / 8 s，重新部署最新产物 |
| 前端构建 | `tsc + vite build` 通过（626 模块，无警告） |

**Commit**：`cd706f6daaa952fc10e581462e2a0c90a38ecafb`
（`fix: make local startup reliable and error messages actionable` → 已推送）

---

## 轮次 11 — 视频同步版本部署与文案收尾

**部署结果（公网实测）**

| 检查项 | 主入口 `:18082` | 备用入口 `/smoking/` |
|---|---|---|
| 首页 | 200 | 200 |
| `/videos/main-monitor.mp4` | 200（`video/mp4`，2319296 字节） | 200 |
| 数据接口（health/status/realtime/alarms/knowledge/prediction） | 全部 200 | — |
| `/api/video-sync/info`、`/api/video-sync/telemetry` | 200 | 200 |
| 已有站点 fitness(80) | 200（不受影响） | — |

视频 SHA256 与源文件一致：`2ee747215adb4beff99f1368e2425c2f0efe518659a82cbf292fb10f392ebbb7`

**循环不写库验证**：连续观察 88 秒（≈4.4 个视频循环周期），
报警总数稳定为 **6 条**、知识库稳定为 **12 条**，未发生增长。

**文案收尾**：产物中 `演示` 还剩 4 处（如"主监控点演示视频的源时长"），
已改为"监控视频 / 展示周期"等中性表述。现在产物中
`仿真` / `演示` / `v0.1.0` 均为 **0 处**。

**修正的真实缺陷**

- `.gitignore` 此前被 `Add-Content` 以 GBK 写入了中文注释，
  导致该文件不是合法 UTF-8（read 工具直接报错）。已整体重写为干净的 UTF-8。
- 视频忽略规则原先只覆盖 `frontend/public/videos/*.mp4`，
  根目录的 `Video.mp4` 因此被误提交（2.21 MB）。
  已改为 `*.mp4` 通配规则并 `git rm --cached`，仓库与远端现均无任何视频文件；
  源文件在磁盘上保留未动。

**Commit**：`d1b39542846f97345652ac9761ff45b782c6db96`
（`fix: remove leftover demo wording and tidy deployment docs` → 已推送）

---

## 轮次 12 — YOLO 风格异常框与视觉证据链

**目标**：在主监控视频上叠加固定异常检测框，并把带框证据图接入报警详情与数据溯源。

**定位**：这是**展示层**的视觉异常表达，不是真实在线推理 ——
不运行 YOLO、不加载模型权重、不引入推理依赖；框位置与尺寸固定，
只随 video_sync 阶段决定是否显示。"有框"即代表"视觉已确认异常区域"。

**检测框**

| 项 | 值 |
|---|---|
| 归一化坐标 | x=0.3359, y=0.2639, w=0.1039, h=0.2403 |
| 像素坐标（1280×720） | 430,190 → 563,363 |
| 显示阶段 | 风险 ≥ 55（warning 及以上）；normal / attention 不显示 |
| 边框颜色 | warning `#d97706` 橙 / alarm `#c62828` 红 |
| 标签 | `物料堆积 0.92`（内部类别仍为 `material_accumulation`） |
| 置信度 | warning 0.888→0.93，alarm 0.93→0.944（确定性插值，非随机） |

**框位置如何确定**：物料带是灰棕色（实测 RGB≈111,90,86），与深色输送带
对比度低，纯像素分割不可靠（试过两轮阈值都误判了灰白设备）。
因此改用**人工目视 + ffmpeg 叠加候选框迭代**：先抽帧确认物料带走向，
再生成 8 个候选框（probe A~J）逐一目视比对，最终选定物料带完整落在框内
中左部、且不含大片空输送带与设备区域的一组坐标。

**证据图**

| 项 | 值 |
|---|---|
| 生成方式 | `scripts/generate_evidence.py`（ffmpeg + 标准库，**零新依赖**） |
| 坐标来源 | 从 `app.services.video_detection` 读取 —— **单一事实源**，脚本内不重复写 |
| warning 图 | `images/evidence/main-camera-material-accumulation.jpg`（t=8.5s, 0.92, 橙） |
| alarm 图 | `images/evidence/main-camera-material-accumulation-alarm.jpg`（t=9.5s, 0.94, 红） |
| 尺寸 | 1280×720（16:9，未拉伸） |
| 接入位置 | 报警详情弹层「异常证据图」区块；数据溯源复用同一弹层 |

**关键决策**

1. **前后端同源**：框由 `telemetry.risk_index` 派生，与数值、趋势同源，
   首页与雷视联动拿到的是**同一个对象**，架构上不可能出现页面间不一致。
2. **overlay 与视频同尺寸**：`.monitor-video` 本身为 `aspect-ratio: 16/9`，
   overlay 绝对定位铺满，百分比坐标天然正确 —— 不受 `object-fit` 影响。
3. **静态图回退时同样显示框**：fallback 图与视频在同一 16:9 容器内，不会错位。
4. **两张证据图而非一张**：warning 橙框 + alarm 红框，与网页状态一一对应；
   只做一张会导致 alarm 阶段图文颜色不符。
5. **按 cameraId 组织配置**：`DETECTION_CONFIGS` 字典 + `detectionConfigFor()`；
   Camera 02~04 接入时只需追加配置项，解析逻辑不动。
6. **不伪造自动发送**：文案统一为"系统已生成带框截图供现场人员复核"，
   不写"已通过钉钉自动发送"。

**修正的真实缺陷**

- **Python `round()` 是银行家舍入，JS `Math.round()` 是 half-up** ——
  两者在恰好落在 .5 的值上差一个最小单位，实测在 t=8.7 的检测框置信度上
  复现（后端 0.931 / 前端 0.932）。已在 `video_sync.py` 显式实现
  `round_half_up()` 并替换全部对外数值的舍入，前后端恢复逐位一致。
- 前端 `resolveVideoDetectionBox` 初版只接收 risk 而非 `t`，与后端不等价、
  无法做对等校验（校验脚本一跑就暴露了 303 处不一致）。
  已改为接收 `t`（内部解算遥测），另提供 `resolveDetectionBoxForRisk`
  供已有遥测的页面直接派生。

**新增校验工具**

- `scripts/export_parity_fixtures.py`：导出后端期望值
- `frontend/scripts/check-detection-parity.mjs`：检测框对等校验
- 遥测对等校验脚本默认路径统一为 `.parity-telemetry.json`

**验证**

| 检查项 | 结果 |
|---|---|
| 后端 pytest | **217 passed**（原 157 + 检测框与证据图 **60**） |
| 遥测对等 | 101 时间点 × 6 字段一致 |
| 检测框对等 | **303 组合（101 t × 3 camera）× 9 字段一致** |
| 前端 tsc + vite build | 通过（632 模块，无警告） |
| 检测框阶段 | t=0/4/5.5 无框；t=6/8 warning；t=9/10 alarm；t=12 夹到 10；t=-3 无框 |
| 证据图静态资源 | 两张均 200 / `image/jpeg` |
| 证据图接线 | 物料堆积类报警均带证据图；其他异常类型正确返回无 |
| 循环与越界 | t 越界安全 clamp；循环回 0 框立即消失 |
| 无新依赖 | 检测模块不引用 torch / ultralytics / cv2 / onnxruntime / numpy / PIL（有测试断言） |

**Commit**：`f9a124471f421155cc32004bfb872635b24bdebf`
（`feat: add yolo anomaly evidence workflow` → 已推送）

### 轮次 12 部署与公网验证

| 检查项 | 主入口 `:18082` | 备用入口 `/smoking/` |
|---|---|---|
| 首页 | 200 | 200 |
| 监控视频 `main-monitor.mp4` | 200（`video/mp4`，2319296 字节） | — |
| 证据图（warning / alarm） | 200 / `image/jpeg`（145300 / 146626 字节） | 200 / `image/jpeg` |
| 检测框接口 | t=0/2/4/5.5 无框；t=6/7/8/8.5 warning；t=9/9.5/10 alarm；t=12 夹到 10；t=-3 无框 | — |
| 框坐标恒定 | 全部时间点均为 x=0.3359 y=0.2639（尺寸按轮次 14 收窄为 0.1039×0.2403） | — |
| 产物含检测框代码 | `物料堆积`×10、`material_accumulation`×6、证据图路径×1、`detection-overlay`×3 | — |
| 报警证据图接线 | 3 条物料堆积类报警均带证据图与说明；其余 3 条正确返回无 | — |
| 已有站点回归 | fitness(80) 200、ccqspace.site(443) 200 | — |
| **循环不写库** | 连续 5 次采样（跨 4 个循环）报警稳定 **6 条**、知识库 **12 条** | — |

**顺带修正**：`scripts/deploy-yolo-evidence.sh` 中证据图路径的 `cut` 取字段错误
（路径含斜杠，`-f4` 会截断），已改为直接输出整行。

---

## 轮次 13 — 替换监控视频为去水印修复版

**背景**：用户提供了 `Video_repaired.mp4`（去掉了右下角四角星水印），要求替换接入视频，
YOLO 检测框保留不变。

**新旧视频参数对比（ffprobe 实测）**

| 项 | 旧 `Video.mp4` | 新 `Video_repaired.mp4` |
|---|---|---|
| 编码 / 像素格式 | H.264 / yuv420p | H.264 / yuv420p |
| 分辨率 | 1280×720 | 1280×720 |
| 帧率 / 帧数 | 24 fps / 240 | 24 fps / 240 |
| 时长 | 10.000 s | 10.000 s |
| 大小 | 2,319,296 B（1.85 Mbps） | 5,441,230 B（4.35 Mbps） |
| SHA256 | `2EE747…EBBB7` | `8BDCDE…DA63` |

**画面差异分析（逐像素比对，纯 stdlib + ffmpeg rawvideo）**

| t | 差异像素占比 | 差异区域 |
|---|---|---|
| 0.0 s | 0.119% | X[1132..1183] Y[576..631] |
| 4.0 s | 0.123% | 同上（含少数编码噪声） |
| 8.5 s | 0.113% | 同上 |

差异**全部集中在右下角水印位置**，检测框内仅 2~5 个像素的编码噪声差异。
**结论：画面主体与物料带完全未变，检测框坐标无需调整** —— 实测在新视频上按
同一组坐标叠加，覆盖效果与旧视频一致。

**执行内容**

- `frontend/public/videos/main-monitor.mp4` 替换为修复版（SHA256 与源文件一致）
- **证据图重新生成**：这一步是必须的 —— 原证据图取自带水印的旧素材，
  不重做会把水印留在证据图上，与页面画面对不上
- `scripts/generate_evidence.py` 的视频来源修正：原先硬编码读根目录 `Video.mp4`，
  现改为**优先读实际接入网页的那份视频**（`frontend/public/videos/main-monitor.mp4`），
  避免"网页用 A 视频、证据图用 B 视频"这类不一致
- 新增 `scripts/replace-monitor-video.sh`：线上替换视频的幂等脚本
  （含替换前后 SHA256 核对与 HTTP 探活）
- 检测框坐标、置信度、显示阶段、报警接线**全部未改动**

**保留的约定**：两份源视频文件（`Video.mp4`、`Video_repaired.mp4`）都保留在磁盘，
视频一律不入库（`.gitignore` 的 `*.mp4` 规则覆盖）。

**验证**

| 检查项 | 结果 |
|---|---|
| 后端 pytest | **217 passed**（无回归） |
| 前后端对等校验 | 遥测 101 点、检测框 303 组合均一致 |
| 前端 tsc + vite build | 通过（632 模块，无警告） |
| 线上视频 | 200 / `video/mp4` / **5441230 字节**，SHA256 与本地一致 |
| **水印核对** | 从公网下载视频抽帧放大比对：旧版四角星清晰可见，新版该区域干净 |
| 检测框 | t=6/8 warning、t=9/10 alarm，坐标恒为 0.3359/0.2639（尺寸见轮次 14） |
| 证据图 | 两张均 200 / `image/jpeg`，为重新生成的版本 |
| 备用入口 `/smoking/` | 首页与视频均 200 |
| 已有站点回归 | fitness(80) 200 |
| 循环不写库 | 跨 3 个循环报警稳定 6 条、知识库 12 条 |

**Commit**：`637eb9e0c34f16e10d0bac65951f047df6378035`
（`chore: replace monitor video with the watermark-free version` → 已推送）

---

## 轮次 14 — 检测框收窄为原框的左上 1/4

**背景**：用户反馈框的位置准确，但**尺寸偏大**，要求改为当前框的左上 1/4。

**改动**

| 项 | 原值 | 新值 |
|---|---|---|
| 左上角 x / y | 0.3359 / 0.2639 | **不变** |
| width | 0.2070 | **0.1039**（≈ 原值一半） |
| height | 0.4792 | **0.2403**（≈ 原值一半） |
| 像素（1280×720） | 430,190 → 695,535 | **430,190 → 563,363** |

框面积缩小到原来的 1/4，**左上角锚点完全不变**，符合"取左上 1/4"的要求。
实测该子区域完整包含物料开始增厚的那一段，物料带未被边缘截断。

**同步更新**

- `backend/app/services/video_detection.py` 与
  `frontend/src/video/videoDetection.ts` 的配置（两处必须一致，有对等校验兜底）
- **证据图按新尺寸重新生成** —— 证据图坐标读自后端配置，
  不重做会导致图片上的框比网页上的大一倍
- 调整框尺寸的合理性测试：新增面积下限断言（≥0.020）与
  「下边缘不得越过物料延伸范围」断言；物料覆盖断言保留，
  校验点收紧为确实位于小框内的位置

**验证**

| 检查项 | 结果 |
|---|---|
| 后端 pytest | **217 passed** |
| 前后端对等校验 | 遥测 101 点一致；检测框 **303 组合 × 9 字段一致** |
| 前端 tsc + vite build | 通过（632 模块，无警告） |
| 线上配置 | `x=0.3359 y=0.2639 width=0.1039 height=0.2403`（像素 430,190 尺寸 133×173） |
| 坐标恒定 | 全部时间点取值为 1 种 ✅ |
| 显示阶段 | t=6/7/8/8.5 warning；t=9/9.5/10/12 alarm；t=0/4/5.5 无框 |
| 证据图 | 两张均 200 / `image/jpeg`，已按新尺寸重新生成 |
| 双入口 | 主入口与 `/smoking/` 首页、视频、证据图均 200 |
| 已有站点回归 | fitness(80) 200 |

**Commit**：`116b0b802b6bcd6b2ad3316b377cb6725691f881`
（`fix: narrow the anomaly detection box to the top-left quarter` → 已推送）

---

## 轮次 15 — 移除报警详情中的"闭环"叙事

**背景**：用户反馈报警详情里的"闭环完整"看起来假，要求删除。

**这个判断是对的，而且有具体原因**：`闭环完整` 徽标的判定条件是
「五个阶段是否都存在」，而后端的 `_build_alarm` 对每条记录**固定生成
全部五个阶段**（发现/判断/报警/处理/归档）。实测 6 条报警的阶段序列
完全一致，因此该徽标**恒为真** —— 它不携带任何信息，纯粹是装饰。

**移除内容**

| 位置 | 原内容 |
|---|---|
| 报警详情「处理过程」标题栏 | `闭环完整` / `闭环待补齐` 徽标 |
| 报警详情 | 处理过程的编号圆点（1~5）与竖向连接线 |
| 报警详情 | 模块头注释中的「补齐完整闭环 / 发现 → 判断 → 报警 → 处理 → 归档」 |
| 报警列表页 | 「查看报警详情与处理闭环」→「处理过程」 |
| 报警列表空态 | 「保留完整处理闭环」→「记录处理过程」 |
| 报警列表模块注释 | 去掉「形成…闭环」表述 |
| 数据溯源页说明 | 去掉「每条记录都保留完整闭环：发现 → … → 归档」 |
| 侧栏导航副标题 | 「当前报警、历史报警与处置闭环」→「…与处理记录」 |
| 类型定义注释 | 「发现→判断→报警→处理→归档 闭环」→「报警详情」 |

`EXPECTED_STAGES` 常量、`.alarm-detail__closure` / `.alarm-detail__step-index`
样式及相关 CSS 规则一并删除。

**保留内容**：处理过程本身仍是真实记录（有阶段、标题、时间、说明、处理结果），
只是不再把它包装成"闭环证明"。证据图、AI 判断、雷达趋势、当时画面全部不受影响。

**验证**

| 检查项 | 结果 |
|---|---|
| 后端 pytest | **217 passed** |
| 前端 tsc + vite build | 通过（632 模块，无警告） |
| 产物复查 | `闭环` / `闭环待补齐` / `step-index` / `__closure` / `处置闭环` 在 JS 与 CSS 中**均为 0 处** |
| 保留项复查 | `处理过程`×4、`异常证据图`×1、`AI 判断`×2、`物料堆积`×10、`detection-overlay`×3 |
| 报警详情接口 | 6 条记录 timeline 正常返回（阶段序列确实全是五段，印证徽标恒真） |
| 双入口 | 主入口与 `/smoking/` 首页、视频、证据图均 200 |
| 已有站点回归 | fitness(80) 200 |

**Commit**：`c344c2eae68ad7c6cca38873ca00c34372b16b0a`
（`fix: drop the closed-loop narrative from alarm details` → 已推送）

---

## 轮次 16 — 修正主监控画面的机位标识为 Camera 01

**背景**：用户反馈核心监控画面上方显示的是 `Camera 02`，应为 `Camera 01`。

**根因**：机位编号与点位号被混为一谈。后端 `monitor_points()` 原先用
`f"Camera {position:02d}"` 由点位号直接生成机位标识，而主监控点是
**点位 2**（制丝线 2 号输送段），于是主画面被标成了 `Camera 02`。

这造成**三处口径冲突**：

| 位置 | 原值 |
|---|---|
| 后端 `monitor_points()` / `primary_point()` → `/api/realtime` | `Camera 02` |
| 前端 `syncedTelemetry.ts` 快照（video_sync 模式实际显示的值） | `Camera 02` |
| 前端 `VideoPage.tsx` 机位表 | `Camera 01`（与用户预期一致） |

**修正方式**：新增显式的机位编号映射，而不是用点位号顶替。

```python
CAMERA_NUMBER = {2: 1, 1: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7}
PRIMARY_CAMERA = f"Camera {CAMERA_NUMBER[PRIMARY_POINT]:02d}"   # → "Camera 01"
```

- `monitor_points()` 改用 `CAMERA_NUMBER` 生成 code
- `system.py` 的「视频监控」状态明细改用 `PRIMARY_CAMERA`，不再硬编码字符串
- 前端 `syncedTelemetry.ts` 的 `PRIMARY_POINT.code` 同步为 `Camera 01`
- `VideoPage.tsx` 机位表补注释，说明编号与点位号是两套编号

**保留不变**：`device_id`（`RAD-02`）、`device_ip`（`192.168.1.198`）、
`position`（2）、`id`（`P02`）全部未动 —— 编号只是**显示标识**，
不影响数据关联（原始资料的报警记录同样是"设备位置 2 / .198"）。

**新增**

- `scripts/check_camera_mapping.py`：打印点位↔机位映射并断言一致性
- `test_api_simulation.py` 新增 3 项回归测试：主监控点 code 为 `Camera 01`、
  `/api/realtime` 返回 `Camera 01`、机位编号唯一且与 `CAMERA_NUMBER` 一致

**验证**

| 检查项 | 结果 |
|---|---|
| 后端 pytest | **220 passed**（原 217 + 3） |
| 前端 tsc + vite build | 通过（632 模块，无警告） |
| 映射一致性 | `check_camera_mapping.py` 通过；点位 2 → Camera 01 |
| 公网 `/api/realtime` | `monitor_point.code = Camera 01` |
| 公网 `/api/system/status` | video 明细 = `Camera 01 · 制丝线 2 号输送段` |
| 全部 7 个点位 | 编号唯一；P02 为 Camera 01 且是唯一带 `stream` 的点位 |
| 产物复查 | `Camera 01`×7、`Camera 02`×1（视频监控页待接入机位，正确） |
| 检测框与证据图 | 未受影响，配置与资源均正常 |
| 已有站点回归 | fitness(80) 200 |

**Commit**：`6d135f88304c83cdf5554a7e8857c490618ce0cb`
（`fix: label the main monitor feed as Camera 01` → 已推送）

---

## 轮次 17 — 修复监控视频被浏览器长期缓存的问题

**现象**：用户报告在 http://110.42.236.65:18082/ 看到的仍是**修改前**的状态。

**排查**：先排除"文件没换成功"的可能 ——

| 位置 | SHA256 | 大小 |
|---|---|---|
| 本地 `Video_repaired.mp4` | `8BDCDE…DA63` | 5,441,230 B |
| 本地 `frontend/public/videos/main-monitor.mp4` | `8BDCDE…DA63` | 5,441,230 B |
| 线上 `/var/www/.../videos/main-monitor.mp4` | `8BDCDE…DA63` | 5,441,230 B |
| **公网下载实际内容** | `8BDCDE…DA63` | 5,441,230 B |

**文件全链路都是修复版**，问题在 HTTP 缓存。响应头：

```
Cache-Control: max-age=604800     ← 7 天
Expires: Fri, 25 Sep 2026         ← 一周后
```

`/videos/` 与 `/images/` 配的是 `expires 7d`。这两类资源在部署时是
**直接覆盖、文件名不变**，因此浏览器在一周内根本不会回源 ——
换素材后用户看到的一直是缓存里的旧文件。

**双重修复**（已被缓存的客户端无法靠服务端单方面解决）

1. **URL 版本参数**（对已缓存的浏览器立即生效）
   `MonitorVideo.tsx` 引入 `MONITOR_VIDEO_VERSION`，请求地址变为
   `videos/main-monitor.mp4?v=2`。URL 变了，浏览器只能重新拉取。
   约定：**替换视频文件时同步把该版本号 +1**。
2. **修正服务端缓存策略**（避免同类问题复发）
   `expires 7d` → `add_header Cache-Control "public, max-age=300"`，
   两个入口（18082 与 `/smoking/`）的 `/videos/`、`/images/` 同步修改。
   5 分钟足够减少重复请求，又保证换素材后无需用户清缓存。

**顺带修正**：显式 `add_header Accept-Ranges bytes` 会产生**重复响应头**
（nginx 对静态文件默认已下发该头）。已移除显式声明 ——
Range 请求仍正常（实测 `Range: bytes=0-1023` → **206 Partial Content**）。

**验证**

| 检查项 | 结果 |
|---|---|
| 公网 `?v=2` | 200 / `video/mp4` / 5441230 字节 |
| 缓存头 | `Cache-Control: public, max-age=300`；单一 `Accept-Ranges` |
| Range 请求 | `bytes=0-1023` → **206 Partial Content**，返回 1024 字节 |
| 产物视频地址 | `videos/main-monitor.mp4?v=2` |
| 产物标识 | `Camera 01`×7 |
| 接口 | `/api/realtime` 等 200；`monitor_point.code = Camera 01` |
| 双入口 | 主入口与 `/smoking/`（含 `?v=2`）均 200 |
| 后端 pytest | **220 passed** |
| 已有站点回归 | fitness(80) 200 |

**新增**：`scripts/fix-nginx-cache.sh`（幂等，自带备份 + `nginx -t` + reload）。

**Commit**：`2c5cbfe43c66406665b18cd831027f6805fa02a1`
（`fix: stop browsers from caching the monitor video for a week` → 已推送）

---

## 轮次 18 — 移除监控画面上的机位标识叠加

**背景**：用户指出核心监控画面上叠加的 `Camera 01` 是多余的 ——
**视频画面本身右下角就带 "Camera 01" 水印**，UI 再叠一层属于重复信息。

**改动**：彻底移除该叠加层，而不是仅对主画面隐藏。

- `MonitorVideo.tsx`：删除 `.monitor-video__camera` 渲染与 `cameraLabel` 属性
- `MonitorVideo.css`：删除 `.monitor-video__camera` 样式；
  回退提示 `.monitor-video__notice` 原为避免与该标签重叠而下移 36px，
  现回归右下角 9px
- 4 处调用点同步去掉 `cameraLabel`：
  `OverviewPage`（核心监控画面）、`FusionPage`（雷视联动）、
  `VideoPage`（主画面 + 多监控点缩略区）

**为什么选择彻底移除而不是只对主画面隐藏**：
视频监控页每个缩略图上方已有 Panel 标题写着 `Camera 02/03/04`，
机位信息并未丢失；组件里保留一个全站都不再渲染的"死属性"反而是负担。

**保留**：画面左上角的实时时间戳叠加（这是设备 OSD 之外的信息）、
YOLO 异常检测框、静态图回退提示均不受影响。

**验证**

| 检查项 | 结果 |
|---|---|
| 前端 tsc + vite build | 通过（632 模块，无警告） |
| 产物复查 | `monitor-video__camera` 与 `cameraLabel` 在 JS 与 CSS 中**均为 0 处** |
| 保留项复查 | `monitor-video__timestamp`×1、`detection-overlay`×3、视频路径×4 |
| 视频版本参数 | 产物中为 `videos/main-monitor.mp4?v=2`（缓存修复未受影响） |
| 资源与接口 | 首页、视频、证据图、`/api/realtime`、检测框接口均 200 |
| 双入口 | 主入口与 `/smoking/` 均 200 |
| 已有站点回归 | fitness(80) 200 |

**Commit**：`a5656b7bca34adbf4eebdb83ad2bcae641ce22e8`
（`fix: drop the duplicated camera label overlay on the monitor feed` → 已推送）

---

## 轮次 19 — 清理界面上面向开发者的说明文案

**背景**：用户指出视频监控页的「画面说明」面板"太假"，要求去掉。

**该判断成立**：该面板写的是**给开发者看的接入说明**，不是监控系统该有的内容：

- 「只需将文件放置为 `public/videos/main-monitor.mp4`，……**无需修改业务代码**」
  —— 直接把源码路径和开发约定暴露给现场用户
- 「原系统具备摄像头多点监控能力（点位 1~7）……待接入完成后陆续开放」
  —— 面向评委的"说明性"文字，而非运行信息

**清理范围**（顺带排查了同类文案，共 4 处）

| 位置 | 原内容 | 处理 |
|---|---|---|
| 视频监控页「画面说明」面板 | 两段接入说明 | **整块删除** |
| 无画面占位说明 | 「将文件放置为 `public/videos/main-monitor.mp4` 即可自动显示」 | → 「视频信号恢复后自动显示画面」 |
| 图表空状态 | 「等待后端实时数据接入后自动绘制」 | → 「采集数据恢复后自动更新」 |
| 首页系统状态空态 | 「系统运行状态由后端 /api/system/status 提供，启动后端后自动刷新」 | → 「监控服务恢复后自动刷新」 |

同时删除了随之不再使用的 `.video-page__note` 样式（含 `+` 相邻选择器与 `strong` 规则）。

**保留**：顶栏的「后端服务未连接 / 等待后端」—— 这是**真实的运行状态指示**
（后端断开时用户需要知道），不属于开发说明。

**验证**

| 检查项 | 结果 |
|---|---|
| 前端 tsc + vite build | 通过（632 模块，无警告） |
| 产物复查（应移除） | `画面说明` / `public/videos` / `无需修改业务代码` / `启动后端后自动刷新` / `等待后端实时数据` / `video-page__note` 在 JS 与 CSS 中**均为 0 处** |
| 产物复查（应保留） | `监控点概览`×1、新占位文案×1、新空态文案×1、`detection-overlay`×3、`物料堆积`×10 |
| 资源与接口 | 首页、视频、证据图、`/api/realtime`、`/api/monitor-points`、检测框接口均 200 |
| 双入口 | 主入口与 `/smoking/` 均 200 |
| 已有站点回归 | fitness(80) 200 |

**Commit**：`a6e9e2aba61d0761e3bb91eae358804523871d71`
（`fix: remove developer-facing copy from the monitoring UI` → 已推送）

---

## 轮次 20 — Camera 02/03/04 接入循环画面

**背景**：用户提供了 `Video002.mp4`，要求视频监控页的 Camera 02/03/04
也播放画面（循环播放），三个机位共用同一份素材，同样 0.5× 速度。

**素材**：`Video002.mp4` —— H.264 / yuv420p / 1280×720 / 24 fps / **7.000 s** /
168 帧 / 1.19 MB，画面为同一条制丝线的另一机位，右下角无水印。

**改动**

| 文件 | 改动 |
|---|---|
| `frontend/public/videos/camera-02.mp4` | 新增（`Video002.mp4` 的副本，哈希一致） |
| `MonitorVideo.tsx` | 新增 `videoSrc` 与 `rate` 两个可选属性（默认主监控视频 / 0.5×）；HEAD 探测与 `<video src>` 改用 `videoSrc`；速率应用逻辑改用 `rate` 并纳入依赖 |
| `VideoPage.tsx` | Camera 02/03/04 的 `hasStream` 改为 `true`，传入 `CAMERA_VIDEO_SRC` |

**为什么用 `videoSrc` 属性而不是卡片里写死路径**：
主监控画面需要参与全站时间同步并叠加检测框，其余机位只是画面循环 ——
两者共用同一个组件、只靠属性区分，避免复制出一份几乎相同的组件。

**三个机位共用同一个文件的理由**：用户明确说明三个机位都用这份素材。
`CAMERA_VIDEO_SRC` 是独立常量，将来某个机位拿到专属素材时只改那一处即可。

**顺带**：`Video002.mp4` 与 `camera-02.mp4` 均被 `.gitignore` 的 `*.mp4` 规则忽略
（视频按约定不入库，部署时单独上传）。

**验证**

| 检查项 | 结果 |
|---|---|
| 前端 tsc + vite build | 通过（632 模块，无警告） |
| 产物视频地址 | `videos/main-monitor.mp4?v=2`（主）与 `videos/camera-02.mp4?v=1`（其余机位） |
| 公网视频资源 | 两者均 200 / `video/mp4`（5441230 / 1245184 字节），带与不带版本参数都正常 |
| Range 请求 | `camera-02.mp4` `bytes=0-1023` → **206 Partial Content**（循环播放依赖） |
| 备用入口 | `/smoking/` 下两段视频均 200 |
| 主监控能力未受影响 | 检测框接口、证据图、`/api/realtime`、`/api/monitor-points` 均 200 |
| 已有站点回归 | fitness(80) 200 |

**新增**：`scripts/deploy-camera-videos.sh`（放置素材 + 双入口探活 + Range 校验）。

**Commit**：`87e54b167ee9358ee5e9dc63783600e11633d1f3`
（`feat: play looping footage for cameras 02-04` → 已推送）

---

## 轮次 21 — Camera 03/04 接入各自素材

**背景**：用户提供了 `003.mp4` 与 `004.mp4`，要求分别作为 Camera 03、Camera 04
的画面，同样 0.5× 循环播放。此前三个机位共用同一份素材。

**素材**

| 文件 | 用途 | 时长 | 帧数 | 大小 |
|---|---|---|---|---|
| `Video002.mp4` | Camera 02 | 7.000 s | 168 | 1.19 MB |
| `003.mp4` | Camera 03 | 7.000 s | 168 | 1.31 MB |
| `004.mp4` | Camera 04 | 7.500 s | 180 | 1.43 MB |

三者均为 H.264 / yuv420p / 1280×720 / 24 fps，抽帧确认是同一现场的不同机位。

**改动**

| 文件 | 改动 |
|---|---|
| `frontend/public/videos/camera-03.mp4`、`camera-04.mp4` | 新增（与源文件哈希一致） |
| `MonitorVideo.tsx` | `CAMERA_VIDEO_PATH` / `CAMERA_VIDEO_VERSION` 由单值改为**按机位编号的映射**，新增 `cameraVideoSrc(camera)` 取值函数 |
| `VideoPage.tsx` | 改用 `cameraVideoSrc(slot.camera)`，各机位取各自素材 |
| `frontend/public/videos/README.md` | 补全四个文件清单、替换步骤与「为什么必须改版本号」 |

**为什么用映射而不是继续传同一个常量**：三个机位已有独立素材，
将来替换其中某一个时，只需改对应键的路径与版本号，不必动其它机位。

**验证**

| 检查项 | 结果 |
|---|---|
| 前端 tsc + vite build | 通过（632 模块，无警告） |
| 产物机位映射 | `Camera 02/03/04` → `camera-02/03/04.mp4` 完整 |
| 公网四段视频 | 均 200 / `video/mp4`（5441230 / 1245184 / 1371140 / 1498080 字节） |
| Range 请求 | 四段全部 **206**，`Content-Range` 正确（循环播放依赖） |
| 双入口 | 主入口与 `/smoking/` 下四段视频均 200 |
| 平台功能 | 检测框接口、证据图、`/api/realtime`、`/api/monitor-points` 均 200 |
| 已有站点回归 | fitness(80) 200 |

**新增**：`scripts/put-camera-video.sh`（按文件名增补机位素材，不触碰其它视频）。

**Commit**：`待填`
