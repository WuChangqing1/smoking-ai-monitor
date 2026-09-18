#!/usr/bin/env bash
# 放置 Camera 02/03/04 的循环画面素材并验证
set -euo pipefail

WWW=/var/www/smoking-monitor
SRC=/tmp/smoking-video/camera-02.mp4
DST="$WWW/dist/videos/camera-02.mp4"

echo "=== 放置 Camera 02/03/04 循环素材 ==="
if [ ! -f "$SRC" ]; then
  echo "  !! 未找到 $SRC" >&2
  exit 1
fi
cp "$SRC" "$DST"
sudo -n chmod 644 "$DST"
printf '  已放置 camera-02.mp4（%s 字节）\n' "$(stat -c%s "$DST")"

echo
echo "=== 视频目录 ==="
ls -l "$WWW/dist/videos/"

echo
echo "=== 本机探活（主入口 18082）==="
for f in main-monitor.mp4 camera-02.mp4; do
  printf '  %-20s %s  %s  %s bytes\n' "$f" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "http://127.0.0.1:18082/videos/$f")" \
    "$(curl -s -o /dev/null -w '%{content_type}' --max-time 20 "http://127.0.0.1:18082/videos/$f")" \
    "$(curl -s -o /dev/null -w '%{size_download}' --max-time 20 "http://127.0.0.1:18082/videos/$f")"
done

echo
echo "=== 带版本参数（页面实际请求的地址）==="
for u in "/videos/main-monitor.mp4?v=2" "/videos/camera-02.mp4?v=1"; do
  printf '  %-34s %s  %s\n' "$u" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "http://127.0.0.1:18082$u")" \
    "$(curl -s -o /dev/null -w '%{content_type}' --max-time 20 "http://127.0.0.1:18082$u")"
done

echo
echo "=== Range 请求（循环播放依赖）==="
printf '  camera-02.mp4 Range 0-1023 -> %s\n' \
  "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 -H 'Range: bytes=0-1023' http://127.0.0.1:18082/videos/camera-02.mp4)"

echo
echo "=== 备用入口（/smoking/） ==="
for u in "/smoking/videos/main-monitor.mp4?v=2" "/smoking/videos/camera-02.mp4?v=1"; do
  printf '  %-42s %s\n' "$u" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 -H 'Host: 110.42.236.65' "http://127.0.0.1$u")"
done

echo
echo "=== 已有站点回归 ==="
printf '  %-20s %s\n' "fitness(80)" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1/ -H 'Host: 110.42.236.65')"
printf '  %-20s %s\n' "首页(18082)" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18082/)"
