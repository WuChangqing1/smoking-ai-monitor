# 烟厂制丝线物流智能监控与多模态预警平台

> 基于 **视觉识别 + 激光雷达** 多模态融合的制丝线物流监控平台，实现从「异常发生后才报警」
> 向「趋势预测 + 提前预警」的升级。
>
> 本项目依托已验收的科技项目《视觉识别及雷达技术在制丝线物流监视的研究与应用》
> （xx 卷烟厂制丝车间 × 重庆邮电大学），在其既有能力基础上建设可视化监控、多模态融合预警、
> 报警溯源与知识积累的完整平台。

---

## 1. 项目简介

制丝线是连接原料与成品的核心环节。传统物料输送监控依赖人工巡检或单一传感器，
存在实时性差、准确率低、滞后性明显的问题：**异常往往在已经堵料之后才被发现**。

本平台把摄像头视觉信息、激光雷达测距信息、环境辅助数据、历史异常数据与人工审核经验
汇聚到统一的多模态分析链路中：

```
摄像头视觉 + 雷达测距 + 环境数据 + 历史异常 + 人工经验
                     ↓
              多模态融合分析
                     ↓
     实时异常检测  +  趋势分析  +  提前预警
                     ↓
     异常报警 → 处理 → 溯源 → 知识积累
```

**核心理念**

| | 传统系统 | 本平台 |
|---|---|---|
| 链路 | 异常发生 → 检测异常 → 人员处理 | 持续观测 → 多模态融合 → 趋势变化 → 风险预测 → 提前预警 → 人工干预 |
| 目标 | 事后报警 | 降低异常发生概率 |

视觉与雷达不是替代关系，而是**互补**：

- **视觉 AI**：信息丰富，可识别形态、杂质，能做复杂语义判断；但属于概率模型，受光照、遮挡影响，推理延迟相对较高。
- **雷达 / 传感器**：测量稳定、精度高（±5 cm）、响应速度快，可毫秒级高频感知；但语义能力弱。
- **融合决策**：传感器负责高频快速感知，视觉负责复杂语义判断，AI 完成融合决策。

### ⚠️ 当前版本说明（务必阅读）

**本仓库当前为比赛展示 / 仿真环境。**

- 现场未连接真实硬件，**页面上所有实时数据由后端统一仿真引擎（`SimulationEngine`）产生**。
- 仿真数据严格遵循工业逻辑：状态机驱动、时间序列连续、指标相互关联，
  不使用随机跳变（不会出现 `0.72 → 0.31 → 0.89` 这类无意义抖动）。
- 接口结构（`/api/devices`、`/api/realtime`、数据源抽象）已**预留真实设备接入能力**，
  接入时替换数据源实现即可，业务与前端无需重写。详见 [第 11 节](#11-后续真实设备接入位置)。
- 监控视频仍在生成中，当前以静态监控画面占位；替换方式见 [第 7 节](#7-如何替换监控视频)。

---

## 2. 技术架构

选型原则：**简单、稳定、容易部署**。

| 层 | 技术 | 说明 |
|---|---|---|
| 前端 | React 18 + Vite 6 + TypeScript | 单页应用，桌面端优先（1920×1080 与常规笔记本） |
| UI | 自写工业风组件 + CSS 设计令牌 | 不引组件库，保证"企业生产监控系统"观感 |
| 图表 | ECharts 5 | 唯一重型前端依赖，趋势图滚动只保留最近 60~120 点 |
| 路由 | 自写 hash 路由（约 40 行） | 8 个页面不值得引入路由库 |
| 后端 | FastAPI + Uvicorn | Python 3.12 |
| 数据仿真 | SimulationEngine（自研状态机） | 后端唯一数据源，前端不产生业务数据 |
| 数据库 | SQLite（标准库 `sqlite3`） | 知识库与历史事件，零额外依赖 |
| 部署 | Nginx + Uvicorn | Nginx 提供静态文件并反代 `/api/` |

**刻意不引入**（比赛演示阶段没有必要，会拖慢部署并增加故障点）：
Milvus / Elasticsearch / Kafka / Redis Cluster / 向量数据库 / 重型 ORM / 大型 UI 组件库。

### 系统边界（继承原项目真实硬件口径）

原系统硬件：**激光雷达 3 台 + 网络摄像机 15 台 = 18 台设备**，覆盖**7 个监控点位**。

- 点位 1–3：同时具备雷达与摄像头 → **联合判断**
- 点位 4–7：仅具备摄像头 → **单独判断**

> 依据原始资料：*"同时配备激光雷达和摄像头的监控点将进行联合判断，若仅配备其中之一，则采用相应的单独判断方式。"*

---

## 3. 项目目录

```
Smoking/
├── frontend/                     # React + Vite + TypeScript 前端
│   ├── public/
│   │   ├── images/               # 静态监控画面 fallback
│   │   └── videos/               # ★ 监控视频固定替换目录（见该目录 README）
│   ├── src/
│   │   ├── components/           # 工业风通用组件
│   │   ├── pages/                # 8 个业务页面
│   │   ├── styles/               # 设计令牌与全局样式
│   │   ├── api/                  # 后端接口客户端
│   │   └── types/                # 与后端对齐的类型定义
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── backend/                      # FastAPI 后端
│   ├── app/
│   │   ├── main.py               # 应用入口与路由注册
│   │   ├── config.py             # 配置（全部走环境变量）
│   │   ├── simulation/           # SimulationEngine 仿真引擎
│   │   ├── routers/              # 各业务模块接口
│   │   └── data/                 # 知识库种子数据
│   ├── data/                     # SQLite 数据库文件（已 gitignore）
│   └── requirements.txt
├── docs/                         # 项目文档
│   ├── PROJECT_CONTEXT.md        # ★ 长期上下文，开发前先读这个
│   ├── TODO.md                   # 任务状态
│   ├── DEVELOPMENT_LOG.md        # 开发日志
│   └── reference/                # 原始资料提取结果（只读参考）
├── scripts/                      # 辅助脚本
│   └── extract_doc.py            # 旧版 .doc 文本提取（零依赖）
├── deployment/                   # Linux 部署配置
│   ├── nginx/
│   ├── systemd/
│   └── deploy.sh
├── README.md
├── .gitignore
│
├── 申报书.doc                     # ★ 原始资料，禁止删除/覆盖/重命名
├── 报告.doc                       # ★ 原始资料
├── 功能模块对应截图.docx           # ★ 原始资料
└── 检测图片.png                    # ★ 原始资料（监控画面素材来源）
```

---

## 4. 本地运行

### 4.0 环境要求

| 软件 | 版本 | 用途 |
|---|---|---|
| Node.js | ≥ 18（开发使用 v22） | 前端 |
| npm | ≥ 9（开发使用 10） | 前端包管理 |
| Miniconda / Anaconda | 任意较新版本 | Python 环境管理 |

### 4.1 Python 环境（必须）

本项目后端**统一使用 conda 环境 `smoking`**，不要新建环境，也不要用 base 环境安装依赖。

```bash
conda activate smoking
python --version          # 期望 Python 3.12.x
where python              # Windows；Linux/macOS 用 which python
```

`where python` 的输出必须指向 `...\envs\smoking\python.exe`，确认后再安装依赖：

```bash
cd backend
pip install -r requirements.txt
```

> 若 `smoking` 环境不存在，需要先创建（**仅在没有该环境时**）：
> `conda create -n smoking python=3.12 -y`

### 4.2 启动后端

```bash
conda activate smoking
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 18080 --reload
```

- 健康检查：<http://127.0.0.1:18080/api/health>
- 接口文档：<http://127.0.0.1:18080/api/docs>

### 4.3 启动前端

```bash
cd frontend
npm install          # 首次
npm run dev
```

打开 <http://127.0.0.1:15173>。Vite 已把 `/api` 代理到 `127.0.0.1:18080`，**无需配置跨域**。

### 4.4 生产构建

```bash
cd frontend
npm run build        # 产物在 frontend/dist
```

---

## 5. 模拟数据说明

### 单一数据源原则

所有实时数据由后端 `backend/app/simulation/` 下的 **SimulationEngine** 统一产生。
**前端不做任何业务数据生成**，只负责展示与轮询。这样保证：

- 刷新页面数据连续，不会出现前后无关的两组数值；
- 同一个状态下的雷达、视觉、风险、环境各指标互相自洽；
- 多人同时打开页面看到的是同一份数据。

### 状态机

引擎在 5 个状态间按**连续时间**演化（而非随机跳变）：

| 状态 | 含义 | 典型表现 |
|---|---|---|
| `normal` | 正常 | 雷达距离在基准值附近缓慢波动，风险 5%~20% |
| `attention` | 关注 | 距离开始单向缓慢下降，覆盖率上升，风险 20%~45% |
| `warning` | 预警 | 下降趋势确立，视觉检出堆积特征，风险 45%~80% |
| `alarm` | 异常 | 风险 ≥80%，触发报警并生成事件记录 |
| `stopped` | 已停止 | 检测任务停止，数据冻结在当前快照 |

### 数据演化示例（风险逐渐增加时）

雷达距离**单调缓变**，风险指数**同步单调上升**，视觉覆盖率与置信度**跟随变化**：

| 时刻 | 雷达距离 | 风险指数 | 联合判断 |
|---|---|---|---|
| t+0 | 0.72 m | 18% | 正常 |
| t+1 | 0.71 m | 22% | 正常 |
| t+2 | 0.70 m | 27% | 关注 |
| t+3 | 0.69 m | 35% | 关注 |
| t+4 | 0.67 m | 43% | 关注 |
| t+5 | 0.65 m | 55% | 预警 |
| t+6 | 0.62 m | 68% | 预警 |
| t+7 | 0.59 m | 82% | 异常 |

> 绝不会出现 `0.72 → 0.31 → 0.89 → 0.54` 这种与物理过程无关的随机抖动。

### 数据真实性依据

仿真参数并非凭空设定，而是取自原始验收资料：

- 雷达测距 **0.1–40 m**、精度 **±5 cm**、刷新率最高 **1000 Hz**；
- 采集频率 **10 Hz**，持续采集；
- 主监控点基准距离 **0.72 m**；
- 真实报警记录形如：`设备位置:2 / 测量值:0.58 / 滤波值:0.58 / 状态:物料变化异常警告!`；
- 真实事件：2025-05-19 加料堵料，系统报警并经钉钉通知，操作人员确认"进料量短时升高、下游输送速度降低"。

---

## 6. 如何使用启停控制

平台的"启停控制"**只控制检测任务，不控制真实生产设备**。

| 操作 | 效果 |
|---|---|
| **开始检测** | 仿真引擎恢复推进，数据与风险重新变化，AI 状态显示"运行中" |
| **停止检测** | 仿真数据暂停、风险变化暂停，AI 状态显示"已停止"；视频仍可作为监控画面继续播放 |
| **重置模拟** | 仿真状态回到初始正常态，历史缓冲清空并重新预热 |

> 页面上的按钮**不会**、也**不应该**被理解为可以关闭真实生产设备。

---

## 7. 如何替换监控视频

**固定约定路径（唯一）：**

```
frontend/public/videos/main-monitor.mp4
```

### 替换步骤

1. 把最终生成的监控视频命名为 `main-monitor.mp4`；
2. 复制到 `frontend/public/videos/`；
3. 刷新页面即可。

**不需要修改任何业务代码。** 开发环境下 Vite 直接提供 `public/` 静态文件；
生产环境把视频放到 Nginx 站点目录的同一相对位置即可。

### 视频不存在时

视频加载失败会自动回退到静态监控画面
`frontend/public/images/main-monitor-fallback.png`（由 `检测图片.png` 生成），
**页面不会报错、不会白屏，演示不中断**。

### 播放属性

播放器固定使用 `autoplay` + `muted` + `loop` + `playsInline`，并配合 `object-fit: contain`
保证窗口尺寸变化时画面不变形、不裁切。

### 大文件与 Git

超过 GitHub 单文件限制（100 MB）的视频**不要直接提交**，`.gitignore` 已忽略 `*.mp4`。
三种处理方式见 `frontend/public/videos/README.md`：
Git LFS / 部署时单独上传 / 保持忽略。任一种都**不改变**上述固定替换路径。

---

## 8. Linux 部署

前置原则：**不覆盖服务器已有项目，不 kill 不认识的进程，不动已有 Nginx 配置。**

### 8.1 部署前环境勘查（必做）

```bash
# 已运行服务与占用端口
ss -lntp
systemctl list-units --type=service --state=running | head -50
# 已有 Nginx 站点
nginx -T 2>/dev/null | grep -n "server_name\|listen\|location" | head -50
ls -l /etc/nginx/conf.d/ /etc/nginx/sites-enabled/ 2>/dev/null
# 可用目录与权限
ls -ld /var/www ~/ 2>/dev/null
id
```

据此选择一个**独立端口 + 独立目录 + 独立 server_name / location**。

### 8.2 推荐部署结构

```
~/apps/smoking-monitor/          # 或 /var/www/smoking-monitor/
├── dist/                        # 前端构建产物（frontend/dist）
├── backend/                     # 后端代码
├── venv/                        # Python 虚拟环境
└── videos/main-monitor.mp4      # 监控视频（单独上传）
```

后端监听 `127.0.0.1:18080`（若被占用，改用其它高位端口并在 Nginx 中同步）。
对外只暴露 Nginx 的独立端口或域名，后端不直接对外。

### 8.3 Nginx

配置模板见 `deployment/nginx/smoking-monitor.conf`：

- 静态文件指向 `dist/`；
- `location /api/` 反向代理到 `127.0.0.1:18080`；
- 使用独立的 `listen` 端口或 `server_name`，**不修改服务器上已有的 server 块**。

```bash
sudo cp deployment/nginx/smoking-monitor.conf /etc/nginx/conf.d/smoking-monitor.conf
sudo nginx -t && sudo systemctl reload nginx
```

### 8.4 后端常驻与异常重启

优先 **systemd**（模板见 `deployment/systemd/smoking-monitor-api.service`）。
**无 sudo 权限时**依次退化为 **user systemd**（`systemctl --user`）或 **tmux**：

```bash
# user systemd
mkdir -p ~/.config/systemd/user
cp deployment/systemd/smoking-monitor-api.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now smoking-monitor-api
loginctl enable-linger "$USER"      # 允许用户服务在注销后继续运行

# 或 tmux
tmux new -d -s smoking 'cd ~/apps/smoking-monitor/backend && \
  ../venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 18080'
```

一键部署脚本：`deployment/deploy.sh`（含环境勘查、构建、发布与探活，可重复执行）。

### 8.5 部署验证

```bash
curl -s http://127.0.0.1:18080/api/health
curl -s http://127.0.0.1:<nginx端口>/api/health
curl -sI http://127.0.0.1:<nginx端口>/
```

---

## 9. GitHub 版本管理

- 仓库：**Private**（`smoking-ai-monitor`）
- 提交节奏：**每完成一个大阶段提交一次**，不允许整个项目只提交一次
- 提交信息：遵循 Conventional Commits（`feat:` / `fix:` / `chore:` / `docs:`）

```bash
git status
git add <files>
git commit -m "feat: ..."
git push
```

### 安全约定

`.gitignore` 已排除 `.env`、`__pycache__/`、`node_modules/`、`dist/`、`*.db` 等。

**禁止提交**：密码、API Key、SSH 私钥、Token、用户认证信息。
**服务器 SSH 信息不得写死到仓库**：部署脚本从环境变量或本地未跟踪文件读取连接参数。

首次克隆后本地启动：

```bash
git clone <private-repo-url>
cd Smoking
cd frontend && npm install
conda activate smoking && cd ../backend && pip install -r requirements.txt
```

---

## 10. 当前演示模式限制

| 项目 | 当前状态 |
|---|---|
| 真实硬件连接 | ❌ 未连接，数据来自仿真引擎 |
| 雷达数据 | ⚠️ 仿真（参数与真实硬件一致：0.1–40 m、±5 cm、10 Hz） |
| 视觉 AI 推理 | ⚠️ 未接入真实模型，检测结果由引擎按业务逻辑产生 |
| 监控视频 | ⚠️ 静态监控画面占位，等待最终视频替换 |
| 多监控点 | ⚠️ Camera 01 使用真实素材，Camera 02~04 为"待切换"占位 |
| 杂质检测 / 机械臂分拣 | 📋 **规划能力**，未部署，页面明确标注 |
| 报警推送 | ⚠️ 演示环境不实际发送钉钉消息 |
| 车间集控系统对接 | ❌ 原系统即明确不与集控系统交互，本平台保持一致 |

> 页面对"规划能力"与"已部署能力"做了显式区分，不把未来能力伪装成现状。

---

## 11. 后续真实设备接入位置

平台按"数据源可替换"设计，接入真实硬件时**只需替换数据源层**：

| 接入项 | 需要改动的位置 | 说明 |
|---|---|---|
| 激光雷达 | `backend/app/simulation/` 的雷达数据源接口 | 按 10 Hz 采集，输出 `{ts, distance, quality}`；原系统经 UART 接入 |
| 网络摄像机 | 视频流地址与 `frontend/public/videos/` 约定 | 海康 DS-2CD2242CX8-L，H.265 码流；真实接入时替换为 HLS/WebRTC 播放器 |
| 视觉 AI 模型 | 视觉结果数据源接口 | 输出 `{label, confidence, coverage, bbox[]}`；原系统使用"物料异常检测模型" |
| 融合判断 | `SimulationEngine` 的联合判断函数 | 阈值可配置，对应原系统"更新维护报警点的阈值信息即可" |
| 报警推送 | 报警产生处的事件回调 | 对接钉钉机器人，内容 = 设备名称 + 设备IP + 报警时间 + 距离信息 |
| 启停联动 | `POST /api/detection/start\|stop` 的实现 | 原系统支持"根据生产时间开启与关闭物料监视功能" |
| 历史图像 | 数据溯源模块的附件路径 | 原系统异常图像落盘形如 `plot_机位1_<时间>.png` |

切换方式：设置环境变量 `SMOKING_SIMULATION=0` 并实现对应的数据源适配器。
**前端页面与业务逻辑无需修改。**

---

## 12. 文档索引

| 文档 | 用途 |
|---|---|
| `docs/PROJECT_CONTEXT.md` | **开发前先读**：完整需求、已确认能力、数据字段、UI 规范、约束 |
| `docs/TODO.md` | 当前任务状态与优先级 |
| `docs/DEVELOPMENT_LOG.md` | 各阶段完成内容、关键决策与 commit hash |
| `docs/reference/` | 原始资料提取结果（申报书/报告全文、原始截图） |
| `frontend/public/videos/README.md` | 监控视频替换细则与编码建议 |
