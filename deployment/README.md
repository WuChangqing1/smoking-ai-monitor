# Linux 部署说明（实测记录）

目标服务器：`ssh fengz` → `ubuntu@110.42.236.65`（腾讯云，Ubuntu 22.04.5 LTS）

## 线上访问地址

| 入口 | 地址 | 说明 |
|---|---|---|
| **主入口（推荐）** | **http://110.42.236.65:18082/** | 独立端口，与服务器上其他项目完全隔离 |
| 备用入口 | http://110.42.236.65/smoking/ | 路径式，复用 80 端口 |
| 接口健康检查 | http://110.42.236.65:18082/api/health | |
| 接口文档 | http://110.42.236.65:18082/api/docs | FastAPI 自动文档 |

> 两个入口指向同一份构建产物与同一个后端，可同时使用。
> 主入口是独立端口，不依赖任何其他站点的配置，**建议评委/演示时使用主入口**；
> 备用入口的价值在于：万一以后 18082 被回收或调整，80 端口这条路依然通。

---

## 一、部署前勘查结论（决定了最终部署形态）

部署前按要求先做了只读勘查（`scripts/recon.sh`、`scripts/recon-ports.sh`），结论如下：

### 1. 云安全组只放通了 22 / 80 / 443

这是最关键的限制。实测方式：**在服务器上访问自身的公网 IP**——
若安全组放通该端口，连接会成功；未放通则超时。

```
从服务器访问 110.42.236.65:80    → 200（可连接）
从服务器访问 110.42.236.65:443   → 400（可连接）
从服务器访问 110.42.236.65:18080 → 超时
从服务器访问 110.42.236.65:18081 → 超时
从服务器访问 110.42.236.65:18082 → 超时
从服务器访问 110.42.236.65:8080  → 超时
```

**结论：对外服务只能复用 80 端口**，靠新开端口对外是行不通的。

### 2. 80 / 443 已被两个已有项目占用

| 端口 | 站点 | 配置文件 | 说明 |
|---|---|---|---|
| 80 | fitness（`server_name 110.42.236.65`） | `sites-enabled/fitness` | 健身平台 |
| 443 | ccqspace.site（Certbot SSL） | `conf.d/mysite.conf` | 个人站点，含 `/home/`、`/market/`、`/api/` |
| 8000 | Exercises Platform | `exercises.service` | 后端 |
| 8080 | （ccqspace 的 `/api/` 上游） | — | 当前未监听 |
| 18080 | LLM API Platform | `llm-api-platform.service` | **已被占用，本平台不能用** |

### 3. 服务器工具链

| 项 | 版本 | 影响 |
|---|---|---|
| Python | 3.10.12（`venv` 可用） | 用 venv 装后端依赖，不动系统 Python |
| Node | **v12.22.9，且无 npm** | **前端必须在本地构建**，服务器只接收 `dist` |
| pip | 已配置华为云镜像 | 服务器可正常安装依赖 |
| nginx | 1.18.0 | 使用系统 Nginx |
| sudo | ubuntu 用户免密 sudo | 可用系统级 systemd |

---

## 二、最终部署形态

### 2.1 主入口：独立端口 18082

安全组放通后启用，与服务器上其他项目**完全隔离**：

```
http://110.42.236.65:18082/            ← 主入口（Nginx 独立 server 块）
        │
        ├── /            → /var/www/smoking-monitor/dist/   （前端静态文件，SPA 回退）
        ├── /assets/     → dist/assets/                      （长缓存）
        ├── /images/     → dist/images/                      （静态监控图）
        ├── /videos/     → dist/videos/                      （监控视频，缺失时前端自动回退图片）
        └── /api/        → http://127.0.0.1:18081/api/       （FastAPI 反向代理）
```

配置文件：`/etc/nginx/conf.d/smoking-monitor.conf`（独立文件，不与其他站点共享）

### 2.2 备用入口：路径式 /smoking/（复用 80 端口）

**为什么当初需要它**：部署时云安全组只放通了 22/80/443，
实测（在服务器上访问自身公网 IP）18080/18081/18082/8080 等端口一律超时，
而 80 端口已被 fitness 站点占用（`server_name 110.42.236.65`）、
443 被 ccqspace.site 占用，且**同一端口无法再用第二个 server_name 命中**。

于是采用与服务器上既有做法（`/market/`、`/home/`）一致的路径前缀方式接入：

```
http://110.42.236.65/smoking/          ← 备用入口
        ├── /smoking/          → /var/www/smoking-monitor/dist/
        ├── /smoking/assets/   → dist/assets/
        ├── /smoking/images/   → dist/images/
        ├── /smoking/videos/   → dist/videos/
        └── /smoking/api/      → http://127.0.0.1:18081/api/
```

实现方式：在 `sites-available/fitness` 的 server 块中**追加 1 行 include**，
引入 `deployment/nginx/smoking-monitor-locations.conf`（一行即可回滚）。

### 2.3 后端（两种入口共用）

后端 uvicorn 只监听 `127.0.0.1:18081`，**不直接对外暴露** ——
实测 `http://110.42.236.65:18081/api/health` 不可达（正确），
本机回环访问 200。Nginx 是两个入口唯一的对外通道。

### 2.4 前端 `base` 配置（重要）

`frontend/vite.config.ts` 中设置 `base: './'`，构建产物使用相对路径引用资源：

```html
<script src="./assets/index-xxx.js"></script>
```

这样同一份构建产物**既能挂在根路径（18082）、也能挂在 /smoking/ 子路径**，
两种入口共用同一份 dist，不需要为部署位置重新构建。

---

## 三、部署目录结构

```
/var/www/smoking-monitor/
└── dist/                     # 前端构建产物（Nginx 静态根）
    ├── index.html
    ├── favicon.svg
    ├── assets/               # 带 hash，长缓存
    ├── images/               # 静态监控图（fallback）
    └── videos/               # 监控视频放置处（大文件不入 Git）

/home/ubuntu/apps/smoking-monitor/
├── backend/                  # 后端代码（app/ tests/ requirements.txt pytest.ini）
├── venv/                     # Python 虚拟环境
└── data/                     # SQLite 数据库目录
```

---

## 四、涉及的系统配置（可一行回滚）

| 文件 | 动作 | 回滚方式 |
|---|---|---|
| `/etc/nginx/conf.d/smoking-monitor.conf` | **新增**（主入口，监听 18082） | 删除该文件并 reload |
| `/etc/nginx/snippets/smoking-monitor-locations.conf` | **新增**（备用入口片段） | 删除该文件 |
| `/etc/nginx/sites-available/fitness` | **追加 1 行 include** | 删除该行并 `nginx -t && systemctl reload nginx` |
| `/etc/systemd/system/smoking-monitor-api.service` | **新增** | `systemctl disable --now smoking-monitor-api && rm` |

> **没有修改任何已有 server 块的其他指令，没有删除任何文件，没有终止任何不认识的进程。**
> 所有改动集中在两个新增 conf 文件、一行 include 与一个 service 文件上。
> 一键回滚备用入口：`bash scripts/remote-ops.sh rollback`

---

## 五、重新部署（迭代更新）

前端有改动时，因为服务器无法构建，流程是「本地构建 → 上传」：

```bash
# 1. 本地构建（conda smoking 环境与前端无关，前端用 Node）
cd frontend && npm run build

# 2. 上传新产物
scp -r dist/* fengz:/tmp/smoking-dist/
ssh fengz "rm -rf /var/www/smoking-monitor/dist && \
           cp -r /tmp/smoking-dist /var/www/smoking-monitor/dist && \
           sudo chmod -R a+rX /var/www/smoking-monitor"

# 3. 后端有改动时
scp -r backend/app fengz:~/apps/smoking-monitor/backend/
ssh fengz "sudo systemctl restart smoking-monitor-api"
```

也可以直接运行 `deployment/deploy.sh`（完整流程：勘查 → 构建 → 上传 → 安装 → 探活）。

---

## 六、运维命令

```bash
ssh fengz

# 服务状态与日志
systemctl status smoking-monitor-api
sudo journalctl -u smoking-monitor-api -f

# 重启 / 停止
sudo systemctl restart smoking-monitor-api
sudo systemctl stop smoking-monitor-api

# Nginx
sudo nginx -t
sudo systemctl reload nginx

# 探活
curl -s http://127.0.0.1:18081/api/health
curl -s http://127.0.0.1/smoking/api/health
```

---

## 七、双入口与端口说明

| 端口 | 用途 | 对外 | 说明 |
|---|---|---|---|
| 18082 | **Nginx 主入口** | 已放通 | 独立 server 块，推荐使用 |
| 80 | Nginx 备用入口（`/smoking/`） | 已放通 | 与 fitness 共用 server 块 |
| 18081 | 后端 uvicorn | **不应对外** | 只监听 127.0.0.1，Nginx 反代 |
| 443 | ccqspace.site | 已放通 | 其他项目，未改动 |
| 18080 | LLM API Platform | 其他项目 | 未改动 |

> **18081 不需要对外开放。** 安全组若放通了它，建议收回 ——
> 后端只应通过 Nginx 访问，直接暴露会绕过统一入口。
> `scripts/verify-deployment.sh` 中有一项专门检查"18081 对外应不可达"。

### 如需下线备用入口

保留主入口即可，备用入口不是必需的：

```bash
bash scripts/remote-ops.sh rollback     # 移除 fitness 中的 include 行与该片段文件
```

主入口（18082）不受影响。

---

## 八、部署验证结果（实测）

| 检查项 | 结果 |
|---|---|
| **主入口首页** | `http://110.42.236.65:18082/` → **200**，标题正确 |
| **主入口 9 个接口** | health / system-status / realtime / devices / alarms / alarms-options / prediction / knowledge / monitor-points → 全部 **200** |
| 主入口静态资源 | favicon.svg / fallback 图 / assets JS → 全部 **200** |
| 备用入口 | `/smoking/`、`/smoking/api/health`、`/smoking/api/realtime` → 全部 **200** |
| 相对路径解析 | `./assets/...` 在两种入口下均正确解析 |
| **后端隔离** | 18081 对外**不可达**（正确）；本机回环 200 |
| 实时数据 | 仿真正常：测距 0.721 m、10 Hz 采集、历史 120 点 |
| 设备与报警 | 在线设备 18/18；报警 6 条，覆盖 4 种异常类型 |
| 知识库 | 12 条经验记录 |
| 控制接口 | 演示场景切换 / 恢复自动循环 → 均 `ok=true`，风险随之变化 |
| 进程与自启 | `systemctl is-active` → active；`is-enabled` → enabled |
| **已有站点回归** | fitness(80) → **200**；ccqspace.site(443) → **200**；其他项目 8000/18080 不受影响 |

一键复验：`bash scripts/verify-deployment.sh`

---

## 九、域名访问（可选，需要 DNS 解析）

腾讯云服务器在中国大陆，**80/443 对外服务需要域名已备案**，直接用 IP 访问则不受此限制。
若后续希望用域名访问（例如 `smoking.example.com`）：

1. 添加 DNS A 记录指向 `110.42.236.65`；
2. 在 443 的 server 块中追加一个 `server_name` 与证书配置；
3. 复用本平台的 location 片段即可。

当前用 IP + 路径访问已经满足"评委直接打开即可查看"的要求。
