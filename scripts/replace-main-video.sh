#!/usr/bin/env bash
# 替换主监控视频（main-monitor.mp4）并验证
#
# 只替换主监控画面素材，不触碰其它机位文件。
set -euo pipefail

WWW=/var/www/smoking-monitor
SRC=/tmp/smoking-video/main-monitor.mp4
DST="$WWW/dist/videos/main-monitor.mp4"

echo "=== 替换前 ==="
ls -l "$DST"
printf '  旧 SHA256: %s\n' "$(sha256sum "$DST" | cut -d' ' -f1)"

echo
echo "=== 替换主监控视频 ==="
if [ ! -f "$SRC" ]; then
  echo "  !! 未找到 $SRC" >&2
  exit 1
fi
cp "$SRC" "$DST"
sudo -n chmod 644 "$DST"
printf '  新 SHA256: %s\n' "$(sha256sum "$DST" | cut -d' ' -f1)"
printf '  大小: %s 字节\n' "$(stat -c%s "$DST")"

echo
echo "=== 视频目录（其它机位应保持不变）==="
ls -l "$WWW/dist/videos/" | sed 's/^/  /'

echo
echo "=== 双入口探活 ==="
for u in "/videos/main-monitor.mp4?v=3" "/videos/camera-02.mp4?v=1" \
         "/videos/camera-03.mp4?v=1" "/videos/camera-04.mp4?v=1"; do
  printf '  %-34s 主 %s  备 %s\n' "$u" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 "http://127.0.0.1:18082$u")" \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 -H 'Host: 110.42.236.65' "http://127.0.0.1/smoking$u")"
done

echo
echo "=== Range 请求（循环播放依赖）==="
printf '  main-monitor.mp4 -> %s\n' \
  "$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 -H 'Range: bytes=0-1023' 'http://127.0.0.1:18082/videos/main-monitor.mp4?v=3')"

echo
echo "=== 缓存策略 ==="
curl -s -I --max-time 20 'http://127.0.0.1:18082/videos/main-monitor.mp4?v=3' \
  | grep -iE 'HTTP/|cache-control|accept-ranges|content-type|content-length' | sed 's/^/  /'

echo
echo "=== 平台与已有站点 ==="
printf '  %-18s %s\n' "首页(18082)" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18082/)"
printf '  %-18s %s\n' "fitness(80)" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1/ -H 'Host: 110.42.236.65')"
