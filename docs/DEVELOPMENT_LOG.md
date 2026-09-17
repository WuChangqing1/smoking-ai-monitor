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

**Commit**：`待填（轮次 1 提交后回填）`
