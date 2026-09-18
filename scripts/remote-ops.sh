#!/usr/bin/env bash
# ============================================================================
#  烟厂制丝线物流智能监控平台 —— 服务器运维脚本
#
#  目标服务器：ssh fengz (ubuntu@110.42.236.65, Ubuntu 22.04)
#  线上地址  ：http://110.42.236.65/smoking/
#
#  用法（在本地仓库根目录执行，脚本会自动 scp 到服务器再运行）：
#      bash scripts/remote-ops.sh status      查看服务与线上探活
#      bash scripts/remote-ops.sh verify      完整验证（含已有站点回归）
#      bash scripts/remote-ops.sh ports       查看端口占用与安全组放通情况
#      bash scripts/remote-ops.sh logs        查看后端最近日志
#      bash scripts/remote-ops.sh restart     重启后端服务
#      bash scripts/remote-ops.sh rollback    移除路径式入口（回滚 nginx 改动）
#
#  也可以把本文件传到服务器后直接运行同名子命令。
# ============================================================================

set -uo pipefail

SSH_HOST="${SSH_HOST:-fengz}"
APP_DIR="$HOME/apps/smoking-monitor"
WWW_DIR=/var/www/smoking-monitor
SERVICE=smoking-monitor-api
SNIPPET=/etc/nginx/snippets/smoking-monitor-locations.conf
FITNESS_CONF=/etc/nginx/sites-available/fitness
PUBLIC_HOST=110.42.236.65
PUBLIC_URL="http://${PUBLIC_HOST}/smoking"

# 本平台挂在 80 端口的某个 server 块上（server_name 110.42.236.65）。
# 直接 curl http://127.0.0.1/smoking/ 不带 Host 头会落到默认 server 而 404，
# 因此本机探活一律显式带上 Host 头，模拟真实外部请求。
local_curl() {
  local path="$1"
  curl -s -o /dev/null -w '%{http_code}' --max-time 8 \
    -H "Host: ${PUBLIC_HOST}" "http://127.0.0.1${path}"
}

section() { printf '\n===== %s =====\n' "$1"; }

# ---------------------------------------------------------------------------
cmd_status() {
  section "systemd 服务"
  systemctl is-active "$SERVICE" && echo "  active" || echo "  NOT ACTIVE"
  systemctl is-enabled "$SERVICE" 2>/dev/null | sed 's/^/  enabled: /'
  systemctl show "$SERVICE" -p MemoryCurrent 2>/dev/null | sed 's/^/  /'

  section "后端直连（回环）"
  printf '  %-46s %s\n' "http://127.0.0.1:18081/api/health" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 6 http://127.0.0.1:18081/api/health)"

  section "Nginx 路径式入口（本机，带 Host 头）"
  for u in /smoking/ /smoking/api/health /smoking/api/realtime; do
    printf '  %-46s %s\n' "http://127.0.0.1${u}" "$(local_curl "$u")"
  done

  section "实时数据抽样"
  curl -s --max-time 8 -H "Host: ${PUBLIC_HOST}" http://127.0.0.1/smoking/api/system/status | head -c 300
  echo
}

# ---------------------------------------------------------------------------
cmd_verify() {
  section "1. 首页与静态资源"
  for p in / /index.html /favicon.svg /images/main-monitor-fallback.png; do
    printf '  %-42s %s\n' "${PUBLIC_URL}${p}" \
      "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "${PUBLIC_URL}${p}")"
  done

  section "2. 相对路径资源解析"
  local asset
  asset=$(curl -s --max-time 10 "${PUBLIC_URL}/" | grep -oE 'assets/[^"]+\.js' | head -1)
  if [ -n "$asset" ]; then
    printf '  %-42s %s\n' "${PUBLIC_URL}/${asset}" \
      "$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "${PUBLIC_URL}/${asset}")"
  else
    echo "  未在 index.html 中找到 assets 引用"
  fi

  section "3. 数据接口"
  for ep in /api/health /api/system/status /api/realtime /api/devices /api/alarms \
            /api/alarms/options /api/prediction /api/knowledge /api/monitor-points; do
    printf '  %-28s %s\n' "$ep" \
      "$(curl -s -o /dev/null -w '%{http_code}' --max-time 12 "${PUBLIC_URL}${ep}")"
  done

  section "4. 兼容两种入口（路径式 / 独立端口）"
  printf '  %-42s %s\n' "路径式 /smoking/api/health" "$(local_curl /smoking/api/health)"
  printf '  %-42s %s\n' "独立端口 18082/api/health" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 6 http://127.0.0.1:18082/api/health 2>/dev/null || echo '未启用')"

  section "5. 已有站点回归检查（必须不受影响）"
  printf '  %-42s %s\n' "fitness http://127.0.0.1/ (Host: IP)" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1/ -H "Host: ${PUBLIC_HOST}")"
  printf '  %-42s %s\n' "ccqspace.site https (Host 头)" \
    "$(curl -s -o /dev/null -w '%{http_code}' -k --max-time 8 https://127.0.0.1/ -H 'Host: ccqspace.site')"
  printf '  %-42s %s\n' "其他项目 8000" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:8000/ 2>/dev/null || echo 'n/a')"
  printf '  %-42s %s\n' "其他项目 18080（LLM API）" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18080/ 2>/dev/null || echo 'n/a')"
}

# ---------------------------------------------------------------------------
cmd_ports() {
  section "监听端口"
  sudo -n ss -lntp 2>/dev/null | head -30

  section "从本机访问自身公网 IP（超时=安全组未放通）"
  for p in 22 80 443 8000 8080 18080 18081 18082; do
    out=$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 "http://110.42.236.65:${p}/" 2>/dev/null)
    if [ "$out" = "000" ]; then
      printf '  %-6s 未放通\n' "$p"
    else
      printf '  %-6s 已放通 (http %s)\n' "$p" "$out"
    fi
  done
}

# ---------------------------------------------------------------------------
cmd_logs() {
  section "后端日志（最近 60 行）"
  sudo -n journalctl -u "$SERVICE" -n 60 --no-pager
  section "Nginx 错误日志（最近 15 行）"
  sudo -n tail -15 /var/log/nginx/error.log
}

# ---------------------------------------------------------------------------
cmd_restart() {
  section "重启后端服务"
  sudo -n systemctl restart "$SERVICE"
  sleep 3
  systemctl is-active "$SERVICE" && echo "  restarted ✓"
  curl -s --max-time 8 http://127.0.0.1:18081/api/health | head -c 120
  echo
}
# ---------------------------------------------------------------------------
cmd_rollback() {
  section "回滚路径式入口"
  if sudo -n grep -q 'smoking-monitor-locations.conf' "$FITNESS_CONF"; then
    sudo -n sed -i '\#include /etc/nginx/snippets/smoking-monitor-locations.conf;#d' "$FITNESS_CONF"
    echo "  已从 fitness 移除 include 行"
  else
    echo "  include 行不存在，无需移除"
  fi
  sudo -n rm -f "$SNIPPET"
  echo "  已删除 $SNIPPET"
  if sudo -n nginx -t 2>&1 | tail -1; then
    sudo -n systemctl reload nginx
    echo "  nginx reloaded ✓"
  fi
  echo
  echo "  前端与后端文件仍保留在："
  echo "    $WWW_DIR/dist"
  echo "    $APP_DIR"
  echo "  如需彻底移除后端：sudo systemctl disable --now $SERVICE && sudo rm /etc/systemd/system/$SERVICE.service"
}

# ---------------------------------------------------------------------------
case "${1:-status}" in
  status)   cmd_status ;;
  verify)   cmd_verify ;;
  ports)    cmd_ports ;;
  logs)     cmd_logs ;;
  restart)  cmd_restart ;;
  rollback) cmd_rollback ;;
  *) echo "未知子命令: $1" >&2; sed -n '2,18p' "$0"; exit 2 ;;
esac
