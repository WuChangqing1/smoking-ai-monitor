#!/usr/bin/env bash
# 只更新前端产物（assets / index.html / images），**不动 videos 目录**，避免误删监控视频
set -euo pipefail

WWW=/var/www/smoking-monitor
SRC=/tmp/smoking-dist

echo "=== 更新前 ==="
ls -l "$WWW/dist/videos/" 2>/dev/null | sed 's/^/  /'

echo
echo "=== 同步产物（保留 videos） ==="
# assets / images 是构建产物，整体替换
rm -rf "$WWW/dist/assets" "$WWW/dist/images"
mkdir -p "$WWW/dist/assets"
cp -r "$SRC/assets/." "$WWW/dist/assets/"
[ -d "$SRC/images" ] && cp -r "$SRC/images" "$WWW/dist/images"
# 顶层文件逐个覆盖，不删除目录
for f in "$SRC"/*; do
  name=$(basename "$f")
  [ "$name" = "videos" ] && continue
  [ -d "$f" ] && continue
  cp -f "$f" "$WWW/dist/$name"
done

echo
echo "=== 修正权限 ==="
sudo -n chmod -R a+rX "$WWW"
sudo -n find "$WWW" -type d -exec chmod 755 {} +
sudo -n find "$WWW" -type f -exec chmod 644 {} +

echo
echo "=== 更新后 ==="
echo "  assets:"
ls -1 "$WWW/dist/assets/" | sed 's/^/    /'
echo "  videos（必须仍在）:"
ls -l "$WWW/dist/videos/" | sed 's/^/    /'
printf '  视频 SHA256: %s\n' "$(sha256sum "$WWW/dist/videos/main-monitor.mp4" 2>/dev/null | cut -d' ' -f1)"

echo
echo "=== 本机探活 ==="
for u in / /videos/main-monitor.mp4 /api/health /api/video-sync/info; do
  printf '  %-32s %s\n' "$u" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://127.0.0.1:18082${u}")"
done

echo
echo "=== 产物文案复查 ==="
BUNDLE=$(ls "$WWW"/dist/assets/index-*.js | head -1)
for w in 仿真 演示; do
  printf '  %s: %s 次\n' "$w" "$(grep -o "$w" "$BUNDLE" 2>/dev/null | wc -l)"
done
