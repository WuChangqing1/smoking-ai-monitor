#!/usr/bin/env bash
# 同步后端源码并重启服务（用于检测框配置等后端改动）
set -euo pipefail

BACKEND="$HOME/apps/smoking-monitor/backend"

echo "=== 同步后端源码 ==="
rm -rf "$BACKEND/app"
mkdir -p "$BACKEND/app"
cp -r /tmp/be-app/. "$BACKEND/app/"
find "$BACKEND/app" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
printf '  已同步 Python 文件: %s\n' "$(find "$BACKEND/app" -name '*.py' | wc -l)"
sudo -n chmod -R a+rX "$BACKEND"

echo
echo "=== 重启后端 ==="
sudo -n systemctl restart smoking-monitor-api
sleep 3
printf '  服务状态: %s\n' "$(systemctl is-active smoking-monitor-api)"
sudo -n journalctl -u smoking-monitor-api -n 4 --no-pager | grep -E '监控服务已就绪|tick' | sed 's/^/  /' || true

echo
echo "=== 检测框配置核对（本机） ==="
printf '  %-46s %s\n' "首页" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:18082/)"
curl -s --max-time 10 'http://127.0.0.1:18082/api/video-sync/detection-config' | tr '}' '\n' | grep -o '"x":[0-9.]*,"y":[0-9.]*,"width":[0-9.]*,"height":[0-9.]*' | sed 's/^/  /'
echo
for t in 0 5.5 6 8 9 10; do
  body=$(curl -s --max-time 8 "http://127.0.0.1:18082/api/video-sync/detection-box?t=${t}&duration=10")
  vis=$(printf '%s' "$body" | tr ',' '\n' | grep '"visible"' | cut -d: -f2)
  sev=$(printf '%s' "$body" | tr ',' '\n' | grep '"severity"' | cut -d'"' -f4)
  printf '    t=%-5s visible=%-6s severity=%s\n' "$t" "$vis" "$sev"
done

echo
echo "=== 证据图 ==="
for f in main-camera-material-accumulation.jpg main-camera-material-accumulation-alarm.jpg; do
  printf '  %-46s %s %s %s\n' "$f" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "http://127.0.0.1:18082/images/evidence/$f")" \
    "$(curl -s -o /dev/null -w '%{content_type}' --max-time 15 "http://127.0.0.1:18082/images/evidence/$f")" \
    "$(curl -s -o /dev/null -w '%{size_download}' --max-time 15 "http://127.0.0.1:18082/images/evidence/$f")"
done

echo
echo "=== 已有站点回归 ==="
printf '  %-24s %s\n' "fitness(80)" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1/ -H 'Host: 110.42.236.65')"
printf '  %-24s %s\n' "/smoking/ 备用入口" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1/smoking/ -H 'Host: 110.42.236.65')"
