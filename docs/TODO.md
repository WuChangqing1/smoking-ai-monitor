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

- [x] 首页改用 `/api/realtime`（约 1 s 轮询）填充 4 张核心状态卡
- [x] 主监控画面旁状态动态化（在线 / AI 检测中 / AI 检测已停止）
- [x] 雷达距离趋势图 + 堆积风险趋势图（ECharts 增量更新不重建实例）
- [x] 雷达图标注当前值、基准值 0.72 m、报警阈值 0.58 m
- [x] 风险图颜色跟随等级 + 30/55/80 三条等级参考线
- [x] 首页雷视联动摘要（双方依据 + 联合结论）
- [x] 设备状态概览列表（在线数 / 雷达数 / 摄像机数）
- [x] 数据刷新失败时保留上次数据并轻提示，不白屏
- [x] 后端新增 `sample_interval_seconds`，趋势图如实标注时间跨度

## 轮次 3-C：雷视联动页（Commit 6）

- [x] 左视频 / 中雷达分析 / 右视觉 AI + 联合判定 / 下方趋势
- [x] 雷达卡片（当前测距、测量值、滤波值、基准、变化量、10 Hz 采集、规格 0.1–40 m ±5 cm）
- [x] 明确区分"设备最高刷新率 1000 Hz"与"系统采集频率 10 Hz"
- [x] 视觉 AI 卡片（类别、置信度、覆盖率、推理耗时，标注为概率模型输出）
- [x] 联合判断区：可视化公式 + 双方依据 + 联合结论 + 判断模式
- [x] 技术解释区（视觉 / 雷达 / 融合 三方对比，＋/－ 标记优劣）
- [x] 预测模型加固：外推饱和 + 封顶 96%，不再出现 100% 确定性结论
- [x] 新增 2 项预测分级测试（不早饱和、跨场景单调）

## 轮次 4：异常报警与数据溯源（Commit 7）

- [x] 当前报警 / 历史报警双标签页
- [x] 报警详情弹层（发现→判断→报警→处理→归档 完整闭环）
- [x] 详情含当时监控画面 + 雷达趋势 + AI 判断 + 处理结果与处理人
- [x] 等级配色纪律：提示=蓝灰、预警=橙、严重=红（行首细色条，不满屏红）
- [x] 数据溯源六维筛选（起止日期 / 设备 / 异常类型 / 等级 / 状态）+ 分页
- [x] 后端 `/api/alarms` 返回 `event_type_text` 中文标签
- [x] 后端新增 `/api/alarms/options` 筛选选项接口
- [x] 种子历史扩展为 3 台设备 × 4 种异常类型 × 2 个等级
- [x] 系统自动报警按主导特征分类（堆积 / 速度下降 / 流量波动）
- [x] 新增通用组件 Modal、FilterBar

## 轮次 5：智能预警与知识库页（Commit 8）

- [x] 智能预警页：当前 → 预测对比（大号数值 + 未来 30 分钟标注）
- [x] 预测曲线：实测实线 + 预测虚线，两条线在当前点相接
- [x] 预警依据 4~5 条（雷达 / 视觉 / 输送 / 环境 / 历史经验），全部由实测数据计算
- [x] 相似历史事件（含资料中的 EVT-20250519-02）与相似度排序
- [x] 建议措施 + 固定免责说明（概率化措辞，不给确定性结论）
- [x] 扩展能力区：杂质检测与自动分拣（标注"规划能力"，不伪装已部署）、行业推广
- [x] 知识库页：全文检索（280 ms 防抖）+ 类型筛选 + 条目展开
- [x] 知识库详情按复用价值组织（前兆模式、预防建议单独强调）
- [x] 修正依据自相矛盾（下降判定加最小累计降幅约束）
- [x] 修正观察窗口不足时的误读表述

## 轮次 6：稳定化与演示模式（Commit 9）

- [x] 「演示模式」区放入系统设置（四个场景 + 恢复自动循环），不占主界面
- [x] 视频回退改为两层：先 HEAD 探测 content-type，再 onError 兜底
- [x] 修正"开发服务器对缺失视频返回 index.html(200)"导致的误判
- [x] 探测期间保持容器尺寸，避免布局跳动
- [x] 8 个页面 + 全部 GET/POST 接口逐项核查通过
- [x] 联动核查：stop 冻结 / start 推进 / reset 回 normal
- [x] 风险变化驱动 UI 状态核查（normal→warning→alarm 三态一致）
- [x] 首页四项核心数值取值核查
- [x] 响应式断点复核（1920×1080 命中完整宽屏布局，无断点冲突）
- [x] ErrorBoundary 兜底 + useFetch 失败保留上次数据（此前已具备，本轮复核）

## 轮次 7：Linux 部署（Commit 10）

- [x] 部署前环境勘查（服务 / 端口 / Nginx / 目录 / 权限 / 出网）
- [x] 发现云安全组只放通 22/80/443（实测：服务器访问自身公网 IP 超时）
- [x] 后端部署到 `~/apps/smoking-monitor`（venv + systemd，自启 + 异常重启）
- [x] 前端本地构建后上传 `/var/www/smoking-monitor/dist`
- [x] 路径前缀接入 80 端口：新增 1 行 include + 2 个新文件，可一行回滚
- [x] 前端改 `base: './'` + 静态资源相对路径，兼容根路径与子路径部署
- [x] 修正陈旧 nginx worker 导致的 502
- [x] 线上逐项验证（首页 / 资源 / 8 接口 / 实时数据 / 控制接口 / 自启）
- [x] 已有站点回归验证（fitness 80、ccqspace.site 443 均不受影响）
- [x] `deployment/README.md` + README 第 8 节按实测重写
- [x] 服务器侧 `pytest` 121 passed（Python 3.10.12）

**线上地址（双入口，均可用）**

- 主入口：**http://110.42.236.65:18082/**（独立端口，与已有项目完全隔离）
- 备用入口：http://110.42.236.65/smoking/（复用 80 端口，路径式）

## 轮次 8：独立端口入口启用（Commit 12）

- [x] 确认安全组放通 18082（18081 保持不对公网，后端只走回环）
- [x] 主入口 `/etc/nginx/conf.d/smoking-monitor.conf` 生效
- [x] 保留路径式 `/smoking/` 作为备用入口
- [x] 双入口 + 后端隔离 + 已有站点回归 三段式验证通过
- [x] 修正 `monitor_point.stream` 绝对路径 → 相对路径
- [x] 新增 `scripts/verify-deployment.sh` 一键复验

## 轮次 9：最终视频接入与画面同步遥测（Commit 15）

- [x] 视频参数实测（1280×720 / H.264 / 24fps / 10.00s / 2.21MB，无需转码）
- [x] 视频接入 `frontend/public/videos/main-monitor.mp4`（源文件保留，哈希一致）
- [x] `playbackRate = 0.5` 浏览器侧调速（6 个时机重复应用，防止被浏览器重置）
- [x] 后端 `video_sync` 遥测引擎（关键帧 + 线性插值 + 确定性微扰）
- [x] `/api/video-sync/info`（关键帧轨迹）与 `/api/video-sync/telemetry`（按 t 解算）
- [x] `/api/meta` 暴露 `run_mode` 与视频参数
- [x] 前端 `VideoSyncProvider`：全站唯一时间源（rAF 采样 `video.currentTime`）
- [x] 首页 / 雷视联动 / 智能预警 / 当前报警 统一消费同一份遥测
- [x] 趋势图只展示当前这一轮，循环后自然重置（无无限锯齿）
- [x] 循环不写库：引擎 `event_recording` 显式开关
- [x] 保留 SimulationEngine 与 automatic 模式
- [x] 系统设置新增「运行模式」切换
- [x] 后端 36 项新测试 + 前后端遥测对等校验脚本
- [x] 视频 fallback 保留（HEAD 探测 + onError + 静态图）

## 轮次 12：YOLO 风格异常框与视觉证据链（Commit 16）

- [x] 主监控视频叠加固定 YOLO 风格异常检测框（位置/尺寸恒定，不跟踪不缩放）
- [x] 仅 warning 及以上显示；normal / attention 无框
- [x] warning 橙 / alarm 红；标签 `物料堆积 0.92`
- [x] 置信度确定性插值（warning 0.888→0.93，alarm 0.93→0.944）
- [x] 统一解算：`resolveVideoDetectionBox(t, cameraId)`（前后端等价 + 对等校验）
- [x] 首页与雷视联动复用同一个框（由 VideoSyncContext 统一派生）
- [x] 生成带框证据图两张（ffmpeg，零新依赖；坐标读自后端配置）
- [x] 报警详情新增「异常证据图」区块 + 现场复核说明
- [x] 数据溯源复用同一详情弹层，形成完整证据链
- [x] 后端 `/api/video-sync/detection-box` 与 `/detection-config`
- [x] 报警详情新增 `evidence_image` / `evidence_note` 字段
- [x] 按 cameraId 组织配置，未配置的摄像头安全返回空框（Camera 02~04 预留）
- [x] 修正 Python `round()` 银行家舍入与 JS `Math.round()` 不一致的真实缺陷
- [x] 后端新增 60 项测试；检测框对等校验 303 组合通过

## 待办（后续可选）

- [ ] Camera 02 / 03 / 04 若拿到**各自独立**的画面素材，
      替换 `CAMERA_VIDEO_SRC` 指向的文件即可（当前三者共用同一份）
- [ ] 可选：接入现场设备直采（`SMOKING_SIMULATION=0` + 数据源适配器，见 README 第 11 节）
- [ ] 可选：如需域名访问，添加 DNS A 记录（大陆服务器 80/443 需域名已备案）

## 交付文档

- `docs/PROJECT_SUMMARY.md` —— **完整项目文档（单一事实来源）**
  - 覆盖：立项背景、技术架构、数据模型、接口清单、功能详解、
    全部 28 轮修改记录、资产清单、验证方法、开发部署流程、
    全流程约束、已知边界
  - 含 37 次提交的对照表（与实际 git 历史逐条核对一致）
- `docs/任务进展.html` —— 面向队友的进度同步文档（单文件 HTML，含动效）
  - 浏览器直接打开即可，**不随平台部署**，也不需要服务器
  - 校验：`node scripts/check-progress-doc.mjs`（标签配对、脚本语法、SVG 坐标、关键数据）

## 待确认 / 风险

- [ ] 根目录 `无Camera版.png`（1475×1066，1.8 MB）用途待确认，暂未入库
- [ ] 视频若超过 GitHub 单文件限制 → 已用 `*.mp4` 通配规则忽略，走服务器单独部署

## 环境说明（非阻塞，已在 DEVELOPMENT_LOG 记录）

- [ ] 本机安全策略拦截工作区外写入、PyPI 出网、esbuild 与 git 凭据助手的命名管道 →
      `pip install` / `npm run build|dev` / `git push` 需放宽权限各执行一次
- [x] npm 缓存固定到仓库内（`frontend/.npmrc`），安装用 `--ignore-scripts`
- [x] pytest 缓存固定到仓库内（`backend/pytest.ini`），测试用 SQLite 内存库不写磁盘
