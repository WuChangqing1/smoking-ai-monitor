#!/usr/bin/env bash
# 放置各机位的循环画面素材 —— 只增补指定文件，不触碰其它视频
#
# 用法：
#   put-camera-video.sh camera-03.mp4 camera-04.mp4
#   （文件名需与 frontend/public/videos/ 下一致；素材放在 /tmp/smoking-video/）
set -euo pipefail

WWW=/var/www/smoking-monitor
SRC_DIR=/tmp/smoking-video
DST_DIR="$WWW/dist/videos"

if [ "$#" -eq 0 ]; then
  echo "用法: $0 <文件名> [文件名...]" >&2
  exit 1
fi

echo "=== 放置素材 ==="
for name in "$@"; do
  src="$SRC_DIR/$name"
  dst="$DST_DIR/$name"
  if [ ! -f "$src" ]; then
    echo "  !! 未找到 $src" >&2
    exit 1
  fi
  cp "$src" "$dst"
  sudo -n chmod 644 "$dst"
  printf '  %-18s %9s 字节\n' "$name" "$(stat -c%s "$dst")"
done

echo
echo "=== 视频目录当前内容 ==="
ls -l "$DST_DIR" | sed 's/^/  /'

echo
echo "=== 双入口探活 ==="
for f in main-monitor.mp4 camera-02.mp4 camera-03.mp4 camera-04.mp4; do
  [ -f "$DST_DIR/$f" ] || continue
  printf '  %-18s 主 %s  备 %s  %s\n' "$f" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "http://127.0.0.1:18082/videos/$f")" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 -H 'Host: 110.42.236.65' "http://127.0.0.1/smoking/videos/$f")" \
    "$(curl -s -o /dev/null -w '%{content_type}' --max-time 20 "http://127.0.0.1:18082/videos/$f")"
done

echo
echo "=== Range 请求（循环播放依赖）==="
for f in camera-03.mp4 camera-04.mp4; do
  [ -f "$DST_DIR/$f" ] || continue
  printf '  %-18s %s\n' "$f" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 -H 'Range: bytes=0-1023' "http://127.0.0.1:18082/videos/$f")"
done

echo
echo "=== 平台与已有站点 ==="
printf '  %-18s %s\n' "首页(18082)" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18082/)"
printf '  %-18s %s\n' "fitness(80)" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1/ -H 'Host: 110.42.236.65')"
