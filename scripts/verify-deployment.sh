#!/usr/bin/env bash
# 双入口完整验证：独立端口 18082（主） + 路径式 /smoking/（备）
set -uo pipefail
PUB=110.42.236.65
HOST_HDR="Host: ${PUB}"

section() { printf '\n===== %s =====\n' "$1"; }

check() { # check <label> <url> [host-header]
  local label="$1" url="$2" host="${3:-}"
  local code
  if [ -n "$host" ]; then
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -H "$host" "$url")
  else
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$url")
  fi
  printf '  %-56s %s\n' "$label" "$code"
}

section "A. 主入口：独立端口 18082（外网）"
check "http://${PUB}:18082/"                        "http://${PUB}:18082/"
check "http://${PUB}:18082/favicon.svg"             "http://${PUB}:18082/favicon.svg"
check "http://${PUB}:18082/images/fallback.png"     "http://${PUB}:18082/images/main-monitor-fallback.png"
for ep in /api/health /api/system/status /api/realtime /api/devices /api/alarms \
          /api/alarms/options /api/prediction /api/knowledge /api/monitor-points; do
  check "http://${PUB}:18082${ep}" "http://${PUB}:18082${ep}"
done

section "B. 备用入口：路径式 /smoking/（走已放通的 80）"
check "http://${PUB}/smoking/"            "http://${PUB}/smoking/"
check "http://${PUB}/smoking/api/health"  "http://${PUB}/smoking/api/health"
check "http://${PUB}/smoking/api/realtime" "http://${PUB}/smoking/api/realtime"

section "C. 后端只走回环（不应对外暴露）"
printf '  %-56s %s\n' "18081 对外（期望超时/失败）" \
  "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://${PUB}:18081/api/health" 2>/dev/null || echo '不可达(正确)')"
printf '  %-56s %s\n' "18081 回环（期望 200）" \
  "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:18081/api/health)"

section "D. 已有站点回归"
printf '  %-56s %s\n' "fitness http://${PUB}/" \
  "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "http://${PUB}/")"
printf '  %-56s %s\n' "ccqspace.site https" \
  "$(curl -s -o /dev/null -w '%{http_code}' -k --max-time 8 https://127.0.0.1/ -H 'Host: ccqspace.site')"
printf '  %-56s %s\n' "其他项目 8000" \
  "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:8000/ 2>/dev/null || echo n/a)"
printf '  %-56s %s\n' "其他项目 18080（LLM API）" \
  "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:18080/ 2>/dev/null || echo n/a)"

section "E. 实时数据抽样（主入口）"
curl -s --max-time 10 "http://${PUB}:18082/api/realtime" | head -c 320
echo
