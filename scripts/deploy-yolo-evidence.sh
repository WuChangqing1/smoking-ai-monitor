#!/usr/bin/env bash
# 部署 YOLO 证据链版本：后端源码 + 前端产物（含证据图）+ 重启服务
set -euo pipefail

BACKEND="$HOME/apps/smoking-monitor/backend"
WWW=/var/www/smoking-monitor

echo "=== 1. 同步后端源码 ==="
rm -rf "$BACKEND/app"
mkdir -p "$BACKEND/app"
cp -r /tmp/be-app/. "$BACKEND/app/"
find "$BACKEND/app" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
printf '  已同步 Python 文件: %s\n' "$(find "$BACKEND/app" -name '*.py' | wc -l)"

echo
echo "=== 2. 更新前端产物（assets / images / index.html，保留 videos） ==="
rm -rf "$WWW/dist/assets" "$WWW/dist/images"
mkdir -p "$WWW/dist/assets"
cp -r /tmp/smoking-dist/assets/. "$WWW/dist/assets/"
[ -d /tmp/smoking-dist/images ] && cp -r /tmp/smoking-dist/images "$WWW/dist/images"
for f in /tmp/smoking-dist/*; do
  [ -d "$f" ] && continue
  cp -f "$f" "$WWW/dist/$(basename "$f")"
done

echo "=== 3. 修正权限（Nginx 以 www-data 运行） ==="
sudo -n chmod -R a+rX "$WWW"
sudo -n find "$WWW" -type d -exec chmod 755 {} +
sudo -n find "$WWW" -type f -exec chmod 644 {} +

echo
echo "=== 4. 重启后端 ==="
sudo -n systemctl restart smoking-monitor-api
sleep 3
systemctl is-active smoking-monitor-api

echo
echo "=== 5. 证据图与检测框验证（本机） ==="
for p in \
  /images/evidence/main-camera-material-accumulation.jpg \
  /images/evidence/main-camera-material-accumulation-alarm.jpg ; do
  printf '  %-58s %s  %s\n' "$p" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://127.0.0.1:18082${p}")" \
    "$(curl -s -o /dev/null -w '%{content_type}' --max-time 10 "http://127.0.0.1:18082${p}")"
done

echo
echo "  检测框解算："
for t in 0 4 5.5 6 8 9 10; do
  body=$(curl -s --max-time 8 "http://127.0.0.1:18082/api/video-sync/detection-box?t=${t}&duration=10")
  vis=$(printf '%s' "$body" | tr ',' '\n' | grep '"visible"' | cut -d: -f2)
  sev=$(printf '%s' "$body" | tr ',' '\n' | grep '"severity"' | cut -d'"' -f4)
  conf=$(printf '%s' "$body" | tr ',' '\n' | grep '"confidence"' | cut -d: -f2)
  printf '    t=%-5s visible=%-6s severity=%-8s confidence=%s\n' "$t" "$vis" "$sev" "$conf"
done

echo
echo "=== 6. 报警证据图接线 ==="
printf '  报警总数: %s\n' "$(curl -s --max-time 8 'http://127.0.0.1:18082/api/alarms?page_size=100' | tr ',' '\n' | grep -m1 '"total"' | cut -d: -f2)"
FIRST=$(curl -s --max-time 8 'http://127.0.0.1:18082/api/alarms?page_size=1' | tr ',' '\n' | grep -m1 '"id"' | cut -d'"' -f4)
# 注意：证据图路径本身含斜杠，用 -f4 会截断，必须取第 4 个字段之后的全部内容
printf '  首条详情 %s\n' "$FIRST"
curl -s --max-time 8 "http://127.0.0.1:18082/api/alarms/${FIRST}" | tr ',' '\n' \
  | grep -E '"evidence_image"' | sed 's/^/    /'

echo
echo "=== 7. 已有站点回归 ==="
printf '  %-24s %s\n' "fitness(80)" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1/ -H 'Host: 110.42.236.65')"
printf '  %-24s %s\n' "ccqspace.site(443)" "$(curl -s -o /dev/null -w '%{http_code}' -k --max-time 8 https://127.0.0.1/ -H 'Host: ccqspace.site')"
printf '  %-24s %s\n' "/smoking/ 备用入口" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1/smoking/ -H 'Host: 110.42.236.65')"
