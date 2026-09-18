#!/usr/bin/env bash
# ============================================================================
#  烟厂制丝线物流智能监控平台 —— 服务器运维脚本
#
#  目标服务器：ssh fengz (ubuntu@110.42.236.65, Ubuntu 22.04)
#  主入口    ：http://110.42.236.65:18082/
#  备用入口  ：http://110.42.236.65/smoking/
#
#  用法（在本地仓库根目录执行，脚本会自动 scp 到服务器再运行）：
#      bash scripts/remote-ops.sh status      查看服务与两个入口的探活
#      bash scripts/remote-ops.sh verify      完整验证（含已有站点回归）
#      bash scripts/remote-ops.sh ports       查看端口占用与安全组放通情况
#      bash scripts/remote-ops.sh logs        查看后端最近日志
#      bash scripts/remote-ops.sh restart     重启后端服务
#      bash scripts/remote-ops.sh rollback    移除备用入口（路径式），主入口不受影响
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
MAIN_URL="http://${PUBLIC_HOST}:18082"
ALT_URL="http://${PUBLIC_HOST}/smoking"

# 备用入口挂在 80 端口的某个 server 块上（server_name 110.42.236.65）。
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

  section "主入口（独立端口 18082，本机）"
  for u in / /api/health /api/realtime; do
    printf '  %-46s %s\n' "http://127.0.0.1:18082${u}" \
      "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "http://127.0.0.1:18082${u}")"
  done

  section "备用入口（路径式 /smoking/，本机带 Host 头）"
  for u in /smoking/ /smoking/api/health; do
    printf '  %-46s %s\n' "http://127.0.0.1${u}" "$(local_curl "$u")"
  done

  section "实时数据抽样（主入口）"
  curl -s --max-time 8 http://127.0.0.1:18082/api/system/status | head -c 300
  echo
}

# ---------------------------------------------------------------------------
cmd_verify() {
  section "1. 主入口（独立端口 18082）"
  for p in / /favicon.svg /images/main-monitor-fallback.png; do
    printf '  %-50s %s\n' "${MAIN_URL}${p}" \
      "$(curl -s -o /dev/null -w '%{http_code}' --max-time 12 "${MAIN_URL}${p}")"
  done
  local asset
  asset=$(curl -s --max-time 12 "${MAIN_URL}/" | grep -oE 'assets/[^"]+\.js' | head -1)
  [ -n "$asset" ] && printf '  %-50s %s\n' "${MAIN_URL}/${asset}" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "${MAIN_URL}/${asset}")"

  section "2. 主入口数据接口"
  for ep in /api/health /api/system/status /api/realtime /api/devices /api/alarms \
            /api/alarms/options /api/prediction /api/knowledge /api/monitor-points; do
    printf '  %-28s %s\n' "$ep" \
      "$(curl -s -o /dev/null -w '%{http_code}' --max-time 12 "${MAIN_URL}${ep}")"
  done

  section "3. 备用入口（路径式 /smoking/）"
  for p in / /api/health /api/realtime; do
    printf '  %-50s %s\n' "${ALT_URL}${p}" \
      "$(curl -s -o /dev/null -w '%{http_code}' --max-time 12 "${ALT_URL}${p}")"
  done

  section "4. 后端隔离（18081 不应对外可达）"
  printf '  %-50s %s\n' "公网 18081（期望不可达）" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://${PUBLIC_HOST}:18081/api/health" 2>/dev/null || echo '不可达(正确)')"
  printf '  %-50s %s\n' "回环 18081（期望 200）" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 6 http://127.0.0.1:18081/api/health)"

  section "5. 已有站点回归检查（必须不受影响）"
  printf '  %-50s %s\n' "fitness http://127.0.0.1/ (Host: IP)" \
    "$(local_curl /)"
  printf '  %-50s %s\n' "ccqspace.site https (Host 头)" \
    "$(curl -s -o /dev/null -w '%{http_code}' -k --max-time 8 https://127.0.0.1/ -H 'Host: ccqspace.site')"
  printf '  %-50s %s\n' "其他项目 8000" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:8000/ 2>/dev/null || echo 'n/a')"
  printf '  %-50s %s\n' "其他项目 18080（LLM API）" \
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
  section "移除备用入口（路径式 /smoking/）"
  echo "  注意：主入口 http://${PUBLIC_HOST}:18082/ 不受影响"
  echo
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
  printf '  主入口仍然可用：%s\n' \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 6 http://127.0.0.1:18082/)"
  echo
  echo "  文件保留在："
  echo "    $WWW_DIR/dist   （前端）"
  echo "    $APP_DIR        （后端）"
  echo "  彻底移除后端：sudo systemctl disable --now $SERVICE && sudo rm /etc/systemd/system/$SERVICE.service"
  echo "  彻底移除主入口：sudo rm /etc/nginx/conf.d/smoking-monitor.conf && sudo systemctl reload nginx"
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
