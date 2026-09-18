#!/usr/bin/env bash
# 在承载 80 端口的已有 server 块中，以 /smoking/ 前缀接入本平台。
# 只追加一行 include，不改动该 server 块的其他任何指令；可一行删除回滚。
set -uo pipefail

FITNESS_CONF=/etc/nginx/sites-available/fitness
SNIPPET=/etc/nginx/snippets/smoking-monitor-locations.conf
BACKUP="/tmp/fitness.conf.bak-$(date +%Y%m%d%H%M%S)"

echo "=== 0. 备份现有站点配置（只备份，不改内容） ==="
sudo -n cp "$FITNESS_CONF" "$BACKUP"
echo "  备份到 $BACKUP"

echo
echo "=== 1. 安装 smoking location 片段 ==="
sudo -n cp /tmp/smoking-monitor-locations.conf "$SNIPPET"
sudo -n chmod 644 "$SNIPPET"
echo "  已安装 $SNIPPET"

echo
echo "=== 2. 幂等追加 include（已存在则跳过） ==="
if sudo -n grep -q 'smoking-monitor-locations.conf' "$FITNESS_CONF"; then
  echo "  include 已存在，跳过"
else
  # 在 server_name 110.42.236.65; 之后插入一行 include
  sudo -n sed -i '/server_name 110\.42\.236\.65;/a\    include /etc/nginx/snippets/smoking-monitor-locations.conf;' "$FITNESS_CONF"
  echo "  已追加 include"
fi
echo "  --- fitness 配置前 12 行 ---"
sudo -n head -12 "$FITNESS_CONF"

echo
echo "=== 3. 校验并重载（失败自动回滚） ==="
if sudo -n nginx -t 2>&1; then
  sudo -n systemctl reload nginx
  echo "  nginx reloaded ✓"
else
  echo "  !! 校验失败，正在回滚 fitness 配置"
  sudo -n cp "$BACKUP" "$FITNESS_CONF"
  sudo -n nginx -t 2>&1 | tail -1
  exit 1
fi

echo
echo "=== 4. 本机验证 /smoking/ 入口 ==="
for u in \
  http://127.0.0.1/smoking/ \
  http://127.0.0.1/smoking/index.html \
  http://127.0.0.1/smoking/api/health \
  http://127.0.0.1/smoking/api/system/status \
  http://127.0.0.1/smoking/api/realtime ; do
  printf '  %-46s %s\n' "$u" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "$u")"
done

echo
echo "=== 5. 资源相对路径验证（应解析到 /smoking/assets/） ==="
echo "  index.html 引用："
curl -s --max-time 8 http://127.0.0.1/smoking/index.html | grep -oE '(src|href)="[^"]+"' | sed 's/^/    /'
echo "  实际取 assets 文件："
ASSET=$(curl -s --max-time 8 http://127.0.0.1/smoking/index.html | grep -oE 'assets/[^"]+\.js' | head -1)
printf '    /smoking/%s -> %s\n' "$ASSET" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "http://127.0.0.1/smoking/$ASSET")"
printf '    /smoking/images/main-monitor-fallback.png -> %s\n' "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1/smoking/images/main-monitor-fallback.png)"

echo
echo "=== 6. 已有站点回归检查（必须全部仍然正常） ==="
printf '  fitness       http://127.0.0.1/ (Host 110.42.236.65) -> %s\n' "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1/ -H 'Host: 110.42.236.65')"
printf '  fitness /media/                                    -> %s\n' "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1/media/ -H 'Host: 110.42.236.65')"
printf '  ccqspace.site 443                                  -> %s\n' "$(curl -s -o /dev/null -w '%{http_code}' -k --max-time 8 https://127.0.0.1/ -H 'Host: ccqspace.site')"
printf '  /market/  (ccqspace)                               -> %s\n' "$(curl -s -o /dev/null -w '%{http_code}' -k --max-time 8 https://127.0.0.1/market/ -H 'Host: ccqspace.site')"
printf '  其他项目 8000                                      -> %s\n' "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:8000/ || echo n/a)"
printf '  其他项目 18080                                     -> %s\n' "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18080/ || echo n/a)"

echo
echo "=== 7. 后端服务仍正常 ==="
systemctl is-active smoking-monitor-api
