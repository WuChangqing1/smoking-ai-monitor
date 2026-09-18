#!/usr/bin/env bash
# 修正线上 Nginx 的视频/图片缓存策略（把 expires 7d 改为短缓存）并重载
#
# 背景：/videos/ 与 /images/ 下的资源在部署时会被**直接覆盖**（文件名不变），
# 下发 max-age=604800 会让浏览器一周内一直用旧文件 —— 曾因此出现
# "服务器已是去水印的新视频、页面上仍是带水印旧视频"。
set -euo pipefail

CONF=/etc/nginx/conf.d/smoking-monitor.conf
SNIP=/etc/nginx/snippets/smoking-monitor-locations.conf

echo "=== 备份现有配置 ==="
STAMP=$(date +%Y%m%d%H%M%S)
sudo -n cp "$CONF" "${CONF}.bak-${STAMP}"
sudo -n cp "$SNIP" "${SNIP}.bak-${STAMP}"
printf '  已备份：%s 与 %s\n' "${CONF}.bak-${STAMP}" "${SNIP}.bak-${STAMP}"

echo
echo "=== 应用新的 location 配置 ==="
sudo -n cp /tmp/nginx-new/smoking-monitor.conf "$CONF"
sudo -n cp /tmp/nginx-new/smoking-monitor-locations.conf "$SNIP"

echo
echo "=== 语法检查 ==="
sudo -n nginx -t

echo
echo "=== 重载 Nginx ==="
sudo -n systemctl reload nginx
sleep 2
printf '  nginx 状态: %s\n' "$(systemctl is-active nginx)"

echo
echo "=== 验证响应头 ==="
for path in /videos/main-monitor.mp4 /images/evidence/main-camera-material-accumulation.jpg; do
  echo "  --- $path ---"
  curl -s -I --max-time 20 "http://127.0.0.1:18082${path}" \
    | grep -iE 'HTTP/|cache-control|expires|accept-ranges|content-type|content-length' \
    | sed 's/^/    /'
done

echo
echo "=== 备用入口验证 ==="
curl -s -I --max-time 20 -H 'Host: 110.42.236.65' http://127.0.0.1/smoking/videos/main-monitor.mp4 \
  | grep -iE 'HTTP/|cache-control|accept-ranges' | sed 's/^/  /'

echo
echo "=== 已有站点回归 ==="
printf '  %-24s %s\n' "fitness(80)" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1/ -H 'Host: 110.42.236.65')"
printf '  %-24s %s\n' "首页(18082)" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18082/)"
