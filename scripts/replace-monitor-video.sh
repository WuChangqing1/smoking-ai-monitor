#!/usr/bin/env bash
# 替换线上监控视频为修复版（去水印），并核对证据图已更新
set -euo pipefail

WWW=/var/www/smoking-monitor
VIDEO="$WWW/dist/videos/main-monitor.mp4"
SRC=/tmp/smoking-video/main-monitor.mp4

echo "=== 替换前 ==="
ls -l "$WWW/dist/videos/"
printf '  旧 SHA256: %s\n' "$(sha256sum "$VIDEO" | cut -d' ' -f1)"

echo
echo "=== 替换视频 ==="
if [ ! -f "$SRC" ]; then
  echo "  !! 未找到 $SRC" >&2
  exit 1
fi
cp "$SRC" "$VIDEO"
sudo -n chmod 644 "$VIDEO"

echo
echo "=== 替换后 ==="
ls -l "$WWW/dist/videos/"
printf '  新 SHA256: %s\n' "$(sha256sum "$VIDEO" | cut -d' ' -f1)"

echo
echo "=== 证据图（应为本轮新生成） ==="
ls -l "$WWW/dist/images/evidence/"
for f in "$WWW"/dist/images/evidence/*.jpg; do
  printf '  %s  %s\n' "$(basename "$f")" "$(sha256sum "$f" | cut -d' ' -f1)"
done

echo
echo "=== 本机 HTTP 探活 ==="
printf '  %-46s %s\n' "首页" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:18082/)"
printf '  %-46s %s\n' "视频状态/类型/长度" "$(curl -s -o /dev/null -w '%{http_code} %{content_type} %{size_download}' --max-time 30 http://127.0.0.1:18082/videos/main-monitor.mp4)"
for f in main-camera-material-accumulation.jpg main-camera-material-accumulation-alarm.jpg; do
  printf '  %-46s %s\n' "$f" "$(curl -s -o /dev/null -w '%{http_code} %{content_type} %{size_download}' --max-time 20 "http://127.0.0.1:18082/images/evidence/$f")"
done
