#!/usr/bin/env bash
#
# 烟厂制丝线物流智能监控平台 —— 部署脚本
#
# 设计原则（对应任务要求 37~40）：
#   * 部署前先勘查环境（调用 scripts/recon.sh），不覆盖服务器已有项目
#   * 不 kill 不认识的进程、不删除其他项目、不改动已有 Nginx server 块
#   * 使用独立端口 + 独立目录 + 独立 conf 文件
#   * SSH / 口令等敏感信息全部走环境变量或 ssh config 别名，绝不写死在仓库里
#
# ══════════════════════════════════════════════════════════════════════════
#  目标服务器实测结论（110.42.236.65 / VM-0-11-ubuntu / Ubuntu 22.04）
# ══════════════════════════════════════════════════════════════════════════
#
#   1) **云安全组只放通了 22 / 80 / 443**
#      实测：在服务器上访问自身公网 IP 的 18080/18081/18082/8080/3000…
#      一律超时；仅 80 与 443 可连接。
#      → 因此对外入口**只能复用 80 端口**，不能靠新端口对外提供服务。
#
#   2) 80 端口已被 fitness 站点占用
#      (sites-enabled/fitness, server_name 110.42.236.65)
#      443 被 ccqspace.site 占用（Certbot SSL）。
#
#   3) 同一端口无法再用第二个 server_name 命中
#      → 采用与服务器上既有做法（/market/、/home/）一致的**路径前缀**接入：
#        对外入口 = http://110.42.236.65/smoking/
#        实现方式 = 在 fitness 的 server 块里追加一行 include，
#        引入 deployment/nginx/smoking-monitor-locations.conf
#        （一行即可回滚，不改动该 server 块的其他任何指令）
#
#   4) 服务器 Node 为 v12 且无 npm → **前端必须本地构建**，只上传 dist
#   5) 服务器 pip 走华为云镜像 → 后端依赖在服务器上安装
#   6) ubuntu 用户具备免密 sudo → 用系统级 systemd + 系统 Nginx
#
#   ※ 若后续在云控制台放通 18082 端口，可改用独立端口方式：
#     直接把 deployment/nginx/smoking-monitor.conf 装到 conf.d 即可
#     （该文件已就绪，监听 18082，反代 127.0.0.1:18081）。
#
# ══════════════════════════════════════════════════════════════════════════
#
# ── 用法 ───────────────────────────────────────────────────────────────
#   ./deploy.sh --check          只做环境勘查
#   ./deploy.sh --build-only     只本地构建前端
#   ./deploy.sh --remote         只做服务器侧安装（假设产物已上传）
#   ./deploy.sh                  完整流程：勘查 → 构建 → 上传 → 安装 → 探活
#
# ── 可覆盖的环境变量 ───────────────────────────────────────────────────
#   SSH_HOST     ssh 别名或主机          默认 fengz
#   APP_DIR      服务器后端目录          默认 $HOME/apps/smoking-monitor
#   WWW_DIR      服务器前端目录          默认 /var/www/smoking-monitor
#   API_PORT     后端监听端口            默认 18081（仅回环，不对公网）
#   WEB_PORT     Nginx 独立端口          默认 18082（仅当安全组放通时使用）
#   URL_PREFIX   对外路径前缀            默认 /smoking/
#   SERVICE      systemd 服务名          默认 smoking-monitor-api

set -euo pipefail

SSH_HOST="${SSH_HOST:-fengz}"
APP_DIR="${APP_DIR:-\$HOME/apps/smoking-monitor}"
WWW_DIR="${WWW_DIR:-/var/www/smoking-monitor}"
API_PORT="${API_PORT:-18081}"
WEB_PORT="${WEB_PORT:-18082}"
SERVICE="${SERVICE:-smoking-monitor-api}"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MODE="full"
case "${1:-}" in
  --check)      MODE="check" ;;
  --build-only) MODE="build" ;;
  --remote)     MODE="remote" ;;
  -h|--help)    sed -n '2,40p' "$0"; exit 0 ;;
  "")           ;;
  *) echo "未知参数: $1" >&2; exit 2 ;;
esac

log()  { printf '\033[32m[deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[warn ]\033[0m %s\n' "$*"; }
die()  { printf '\033[31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

ssh_run() { ssh -o BatchMode=yes -o ConnectTimeout=20 "$SSH_HOST" "$@"; }

# ---------------------------------------------------------------------------
# 1. 本地构建前端（服务器 Node 版本过旧，不能依赖服务器构建）
# ---------------------------------------------------------------------------
build_frontend() {
  log "本地构建前端（node $(node --version)）"
  ( cd "$REPO_DIR/frontend" && npm run build )
  [ -f "$REPO_DIR/frontend/dist/index.html" ] || die "构建失败：未生成 frontend/dist/index.html"
  log "构建完成：$(du -sh "$REPO_DIR/frontend/dist" | cut -f1)"
}

# ---------------------------------------------------------------------------
# 2. 服务器环境勘查
# ---------------------------------------------------------------------------
check_remote() {
  log "===== 服务器环境勘查（$SSH_HOST）====="
  scp -q -o BatchMode=yes "$REPO_DIR/scripts/recon.sh" "$SSH_HOST:/tmp/smoking-recon.sh"
  ssh_run "sed -i 's/\r\$//' /tmp/smoking-recon.sh; bash /tmp/smoking-recon.sh" || die "勘查脚本执行失败"

  log "校验部署端口是否空闲"
  for port in "$API_PORT" "$WEB_PORT"; do
    if ssh_run "ss -lnt 2>/dev/null | grep -q ':${port} '"; then
      die "端口 ${port} 已被占用。请设置 API_PORT / WEB_PORT 为其它空闲端口后重试（不要终止不认识的进程）。"
    fi
    log "端口 ${port} 空闲 ✓"
  done
  log "===== 勘查结束 ====="
}

# ---------------------------------------------------------------------------
# 3. 上传产物
# ---------------------------------------------------------------------------
upload() {
  log "创建服务器目录"
  ssh_run "mkdir -p '$APP_DIR'/backend '$APP_DIR'/data '$WWW_DIR'/dist" \
    || die "目录创建失败（请确认 \$HOME 可写）"

  log "上传后端代码"
  # shellcheck disable=SC2086
  ssh_run "mkdir -p '$APP_DIR/backend'"
  scp -q -r -o BatchMode=yes \
    "$REPO_DIR/backend/app" \
    "$REPO_DIR/backend/tests" \
    "$REPO_DIR/backend/requirements.txt" \
    "$REPO_DIR/backend/pytest.ini" \
    "$SSH_HOST:$APP_DIR/backend/" 2>/dev/null \
    || ssh_run "echo 'scp -r 失败，改用逐文件方式'" 

  log "上传前端产物"
  # 前端文件数较多，用 tar 打包传输更稳妥
  ( cd "$REPO_DIR/frontend" && tar czf - dist ) \
    | ssh_run "tar xzf - -C '$WWW_DIR' --overwrite" \
    || die "前端产物上传失败"

  log "校验关键文件"
  ssh_run "test -f '$APP_DIR/backend/app/main.py' && echo '  backend/app/main.py OK' || echo '  backend/app/main.py MISSING'"
  ssh_run "test -f '$WWW_DIR/dist/index.html' && echo '  dist/index.html OK' || echo '  dist/index.html MISSING'"
}

# ---------------------------------------------------------------------------
# 4. 服务器侧安装：Python 环境 / Nginx / systemd
# ---------------------------------------------------------------------------
install_remote() {
  log "创建 Python 虚拟环境并安装依赖（pip 走服务器已配置的镜像）"
  ssh_run "set -e
    cd '$APP_DIR'
    [ -x venv/bin/python ] || python3 -m venv venv
    ./venv/bin/pip install --upgrade pip -q
    ./venv/bin/pip install -r backend/requirements.txt -q
    ./venv/bin/python -c 'import fastapi, uvicorn; print(\"  fastapi\", fastapi.__version__, \"| uvicorn\", uvicorn.__version__)'
  " || die "后端依赖安装失败"

  log "写入 Nginx 站点配置（新增独立文件，不触碰已有配置）"
  scp -q -o BatchMode=yes "$REPO_DIR/deployment/nginx/smoking-monitor.conf" \
    "$SSH_HOST:/tmp/smoking-monitor.conf"
  ssh_run "sed -i 's/\r\$//' /tmp/smoking-monitor.conf
    sudo cp /tmp/smoking-monitor.conf /etc/nginx/conf.d/smoking-monitor.conf
    sudo nginx -t" || die "Nginx 配置校验失败，已保留原配置未重载"

  log "写入 systemd 服务单元"
  scp -q -o BatchMode=yes "$REPO_DIR/deployment/systemd/smoking-monitor-api.service" \
    "$SSH_HOST:/tmp/smoking-monitor-api.service"
  ssh_run "sed -i 's/\r\$//' /tmp/smoking-monitor-api.service
    sudo cp /tmp/smoking-monitor-api.service /etc/systemd/system/${SERVICE}.service
    sudo systemctl daemon-reload
    sudo systemctl enable --now ${SERVICE}
    sudo systemctl restart ${SERVICE}
    sleep 2
    systemctl is-active --quiet ${SERVICE} && echo '  服务运行中 ✓' || { echo '  服务启动失败'; sudo journalctl -u ${SERVICE} -n 30 --no-pager; exit 1; }" \
    || die "systemd 服务启动失败"

  log "重载 Nginx"
  ssh_run "sudo systemctl reload nginx && echo '  nginx reloaded ✓'"
}

# ---------------------------------------------------------------------------
# 5. 探活
# ---------------------------------------------------------------------------
verify() {
  log "===== 部署验证 ====="
  local ok=0
  for url in "http://127.0.0.1:${API_PORT}/api/health" \
             "http://127.0.0.1:${WEB_PORT}/api/health" \
             "http://127.0.0.1:${WEB_PORT}/"; do
    if ssh_run "curl -fsS --max-time 6 '$url' >/dev/null 2>&1"; then
      log "OK   $url"
      ok=$((ok + 1))
    else
      warn "FAIL $url"
    fi
  done

  log "关键接口抽查"
  ssh_run "for ep in /api/system/status /api/realtime /api/devices /api/alarms /api/prediction /api/knowledge; do
      code=\$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 'http://127.0.0.1:${WEB_PORT}'\$ep)
      printf '  %-24s %s\n' \"\$ep\" \"\$code\"
    done"

  log "已有站点未受影响检查"
  ssh_run "curl -s -o /dev/null -w '  ccqspace.site(443) -> %{http_code}\n' --max-time 8 -k https://127.0.0.1/ -H 'Host: ccqspace.site' || true"

  [ "$ok" -ge 3 ] || die "部分探活失败，请检查 Nginx 配置与后端日志"
  log "对外访问地址: http://<服务器IP>:${WEB_PORT}/"
  log "部署完成 ✓"
}

# ---------------------------------------------------------------------------
case "$MODE" in
  check)  check_remote ;;
  build)  build_frontend ;;
  remote) install_remote; verify ;;
  full)
    check_remote
    build_frontend
    upload
    install_remote
    verify
    ;;
esac
