#!/usr/bin/env bash
#
# 烟厂制丝线物流智能监控平台 —— 一键部署脚本
#
# 设计原则（对应任务要求 38/40）：
#   * 部署前先勘查环境，不覆盖服务器已有项目
#   * 不 kill 不认识的进程、不删除其他项目、不改动已有 Nginx server 块
#   * 使用独立端口 + 独立目录
#   * SSH / 数据库口令等敏感信息全部走环境变量，绝不写死在仓库里
#
# 用法：
#   ./deploy.sh                 # 完整流程：勘查 → 构建 → 发布 → 重启 → 探活
#   ./deploy.sh --check         # 只做环境勘查
#   ./deploy.sh --no-build      # 跳过 npm build（假设 dist 已就绪）
#
# 可通过环境变量覆盖：
#   APP_DIR     部署根目录      默认 $HOME/apps/smoking-monitor
#   API_PORT    后端监听端口    默认 18080
#   WEB_PORT    Nginx 对外端口  默认 18081
#   PYTHON      虚拟环境解释器  默认 $APP_DIR/venv/bin/python
#   SERVICE     服务名          默认 smoking-monitor-api

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/apps/smoking-monitor}"
API_PORT="${API_PORT:-18080}"
WEB_PORT="${WEB_PORT:-18081}"
SERVICE="${SERVICE:-smoking-monitor-api}"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DO_CHECK_ONLY=0
DO_BUILD=1
for arg in "$@"; do
  case "$arg" in
    --check)    DO_CHECK_ONLY=1 ;;
    --no-build) DO_BUILD=0 ;;
    -h|--help)  sed -n '2,26p' "$0"; exit 0 ;;
    *) echo "未知参数: $arg" >&2; exit 2 ;;
  esac
done

log()  { printf '\033[32m[deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[warn ]\033[0m %s\n' "$*"; }
die()  { printf '\033[31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. 环境勘查
# ---------------------------------------------------------------------------
preflight() {
  log "===== 环境勘查 ====="
  log "当前用户: $(id -un) (uid=$(id -u))"
  log "仓库目录: $REPO_DIR"
  log "部署目录: $APP_DIR"

  log "--- 监听端口 ---"
  if command -v ss >/dev/null 2>&1; then
    ss -lntp 2>/dev/null | head -40 || true
  else
    warn "未找到 ss，尝试 netstat"
    netstat -lntp 2>/dev/null | head -40 || true
  fi

  for port in "$API_PORT" "$WEB_PORT"; do
    if command -v ss >/dev/null 2>&1 && ss -lnt 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${port}\$"; then
      die "端口 ${port} 已被占用。请设置 API_PORT / WEB_PORT 为其它高位空闲端口后重试（不要终止不认识的进程）。"
    fi
  done
  log "端口 ${API_PORT} / ${WEB_PORT} 均空闲 ✓"

  log "--- 已有 Nginx 站点（只读查看，不做修改）---"
  if command -v nginx >/dev/null 2>&1; then
    nginx -v 2>&1 || true
    nginx -T 2>/dev/null | grep -nE '^\s*(server_name|listen)' | head -30 || true
    log "配置目录:"
    ls -l /etc/nginx/conf.d/ /etc/nginx/sites-enabled/ 2>/dev/null || true
  else
    warn "未检测到 nginx"
  fi

  log "--- 运行中的服务（前 30 条）---"
  systemctl list-units --type=service --state=running --no-pager 2>/dev/null | head -30 || warn "systemctl 不可用（可能无 systemd）"

  log "--- 工具链 ---"
  for c in python3 node npm nginx curl; do
    if command -v "$c" >/dev/null 2>&1; then
      printf '  %-8s %s\n' "$c" "$($c --version 2>&1 | head -1)"
    else
      printf '  %-8s \033[33m缺失\033[0m\n' "$c"
    fi
  done

  log "--- 磁盘空间 ---"
  df -h "$(dirname "$APP_DIR")" 2>/dev/null || df -h / 2>/dev/null || true

  log "===== 勘查结束 ====="
}

# ---------------------------------------------------------------------------
# 2. 发布后端与前端产物
# ---------------------------------------------------------------------------
publish() {
  log "准备部署目录: $APP_DIR"
  mkdir -p "$APP_DIR"/{backend,dist,videos,data,logs}

  # 后端代码（只同步应用代码，不带 __pycache__ / 本地数据库）
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude '__pycache__/' --exclude '*.pyc' --exclude 'data/' \
      "$REPO_DIR/backend/" "$APP_DIR/backend/"
  else
    rm -rf "$APP_DIR/backend/app"
    cp -r "$REPO_DIR/backend/app" "$APP_DIR/backend/"
    cp -f "$REPO_DIR/backend/requirements.txt" "$APP_DIR/backend/"
  fi
  log "后端代码已同步"

  # Python 虚拟环境（不污染系统 Python，也不依赖 conda）
  if [ ! -x "$APP_DIR/venv/bin/python" ]; then
    log "创建虚拟环境 venv"
    python3 -m venv "$APP_DIR/venv"
  fi
  log "安装后端依赖"
  "$APP_DIR/venv/bin/pip" install --upgrade pip -q
  "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt" -q

  # 前端构建产物
  if [ "$DO_BUILD" -eq 1 ]; then
    log "构建前端"
    ( cd "$REPO_DIR/frontend" && npm ci --no-audit --no-fund && npm run build )
  fi
  [ -d "$REPO_DIR/frontend/dist" ] || die "未找到 $REPO_DIR/frontend/dist，请先执行 npm run build"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete "$REPO_DIR/frontend/dist/" "$APP_DIR/dist/"
  else
    rm -rf "$APP_DIR/dist"; cp -r "$REPO_DIR/frontend/dist" "$APP_DIR/dist"
  fi
  log "前端产物已发布到 $APP_DIR/dist"

  # 监控视频：文件较大，不入 Git，需单独上传。此处只做提示。
  if [ ! -f "$APP_DIR/dist/videos/main-monitor.mp4" ] && [ ! -f "$APP_DIR/videos/main-monitor.mp4" ]; then
    warn "未找到监控视频 main-monitor.mp4 —— 页面会自动回退到静态监控画面，不影响演示。"
    warn "上传方式: scp main-monitor.mp4 <server>:$APP_DIR/dist/videos/"
  fi

  # Nginx 配置：模板渲染后写独立 conf.d 文件，不动其它 server 块
  if [ -d /etc/nginx/conf.d ] && [ -w /etc/nginx/conf.d ]; then
    log "写入 Nginx 站点配置"
    sed -e "s#/var/www/smoking-monitor/dist#$APP_DIR/dist#" \
        -e "s#listen       18081#listen       $WEB_PORT#" \
        -e "s#listen       \[::\]:18081#listen       [::]:$WEB_PORT#" \
        -e "s#127.0.0.1:18080#127.0.0.1:$API_PORT#" \
        "$REPO_DIR/deployment/nginx/smoking-monitor.conf" \
        > /etc/nginx/conf.d/smoking-monitor.conf
    nginx -t && systemctl reload nginx && log "Nginx 已重载"
  else
    warn "无 /etc/nginx/conf.d 写权限，请手动执行："
    warn "  sudo sed -e 's#/var/www/smoking-monitor/dist#$APP_DIR/dist#' \\"
    warn "           -e 's#18081#$WEB_PORT#' -e 's#127.0.0.1:18080#127.0.0.1:$API_PORT#' \\"
    warn "           $REPO_DIR/deployment/nginx/smoking-monitor.conf \\"
    warn "           | sudo tee /etc/nginx/conf.d/smoking-monitor.conf"
    warn "  sudo nginx -t && sudo systemctl reload nginx"
  fi
}

# ---------------------------------------------------------------------------
# 3. 重启后端服务（systemd → user systemd → tmux 逐级退化）
# ---------------------------------------------------------------------------
restart_service() {
  log "重启后端服务"

  if systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE}.service"; then
    log "使用系统级 systemd: $SERVICE"
    sudo systemctl restart "$SERVICE"
    sleep 2
    systemctl is-active --quiet "$SERVICE" && log "服务运行中 ✓" || die "服务启动失败，请查看 journalctl -u $SERVICE -n 50"
    return
  fi

  if [ -d "$HOME/.config/systemd/user" ] && systemctl --user list-unit-files 2>/dev/null | grep -q "^${SERVICE}.service"; then
    log "使用用户级 systemd: $SERVICE"
    systemctl --user restart "$SERVICE"
    sleep 2
    systemctl --user is-active --quiet "$SERVICE" && log "服务运行中 ✓" || die "用户服务启动失败，请查看 journalctl --user -u $SERVICE -n 50"
    return
  fi

  warn "未找到 systemd 单元，退化使用 tmux"
  command -v tmux >/dev/null 2>&1 || die "tmux 也不可用，请手动启动后端：
  cd $APP_DIR/backend && $APP_DIR/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port $API_PORT"

  tmux kill-session -t smoking 2>/dev/null || true
  tmux new -d -s smoking "cd '$APP_DIR/backend' && SMOKING_PORT=$API_PORT \
    '$APP_DIR/venv/bin/uvicorn' app.main:app --host 127.0.0.1 --port $API_PORT 2>&1 | tee -a '$APP_DIR/logs/api.log'"
  sleep 3
  log "tmux 会话 smoking 已启动（查看日志: tmux attach -t smoking）"
}

# ---------------------------------------------------------------------------
# 4. 探活
# ---------------------------------------------------------------------------
verify() {
  log "===== 部署验证 ====="
  local ok=0
  for url in "http://127.0.0.1:${API_PORT}/api/health" "http://127.0.0.1:${WEB_PORT}/api/health"; do
    if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
      log "OK   $url"
      curl -fsS --max-time 5 "$url" | head -c 200; echo
      ok=$((ok + 1))
    else
      warn "FAIL $url"
    fi
  done
  if curl -fsS --max-time 5 "http://127.0.0.1:${WEB_PORT}/" >/dev/null 2>&1; then
    log "OK   前端首页 http://127.0.0.1:${WEB_PORT}/"
    ok=$((ok + 1))
  else
    warn "FAIL 前端首页 http://127.0.0.1:${WEB_PORT}/"
  fi

  log "访问地址: http://<服务器IP>:${WEB_PORT}/"
  [ "$ok" -ge 3 ] || die "部分探活失败，请检查 Nginx 配置与后端日志"
  log "部署完成 ✓"
}

# ---------------------------------------------------------------------------
preflight
[ "$DO_CHECK_ONLY" -eq 1 ] && exit 0
publish
restart_service
verify
