#!/usr/bin/env bash
# ============================================================================
#  烟厂制丝线物流智能监控平台 —— 部署前环境勘查
#
#  对应任务要求第 38 节：部署前必须先检查
#    已运行服务 / 已占用端口 / Nginx 配置 / 项目目录 / 权限
#
#  本脚本**只读**，不做任何修改。可以在目标服务器上反复安全执行。
#
#  用法（在目标服务器上）：
#      bash recon.sh
#  或从本地推送执行：
#      ssh <host> "bash -s" < scripts/recon.sh
# ============================================================================

set -uo pipefail

section() { printf '\n===== %s =====\n' "$1"; }

section "1. 系统信息"
echo "hostname : $(hostname 2>/dev/null)"
echo "user     : $(id -un) (uid=$(id -u))"
echo "groups   : $(id -Gn 2>/dev/null)"
echo "kernel   : $(uname -sr)"
if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  echo "distro   : ${PRETTY_NAME:-unknown}"
fi
echo "uptime   : $(uptime -p 2>/dev/null || uptime 2>/dev/null)"

section "2. 已监听端口（判断可用端口）"
if command -v ss >/dev/null 2>&1; then
  ss -lntp 2>/dev/null | head -50
else
  netstat -lntp 2>/dev/null | head -50
fi

section "3. 正在运行的服务（前 30 条）"
if command -v systemctl >/dev/null 2>&1; then
  systemctl list-units --type=service --state=running --no-pager 2>/dev/null | head -30
else
  echo "systemctl 不可用（可能无 systemd）"
fi

section "4. Nginx 现状（只读）"
if command -v nginx >/dev/null 2>&1; then
  nginx -v 2>&1
  echo "--- 已有 server / listen 指令 ---"
  nginx -T 2>/dev/null | grep -nE '^\s*(server_name|listen)' | head -40
  echo "--- /etc/nginx/conf.d ---"
  ls -l /etc/nginx/conf.d/ 2>/dev/null || echo "  (不存在)"
  echo "--- /etc/nginx/sites-enabled ---"
  ls -l /etc/nginx/sites-enabled/ 2>/dev/null || echo "  (不存在)"
  echo "--- conf.d 是否可写 ---"
  [ -w /etc/nginx/conf.d ] && echo "  可写" || echo "  不可写（需 sudo）"
else
  echo "未安装 nginx"
fi

section "5. 家目录与磁盘"
echo "--- \$HOME ---"
ls -la "$HOME" 2>/dev/null | head -25
echo "--- 磁盘空间 ---"
df -h / "$HOME" 2>/dev/null | sort -u

section "6. 工具链版本"
for c in python3 pip3 node npm nginx curl git tmux rsync; do
  if command -v "$c" >/dev/null 2>&1; then
    printf '  %-8s %s\n' "$c" "$("$c" --version 2>&1 | head -1)"
  else
    printf '  %-8s \033[33m缺失\033[0m\n' "$c"
  fi
done

section "7. 权限"
if sudo -n true 2>/dev/null; then
  echo "免密 sudo : 可用（可用系统级 systemd + 系统 Nginx）"
elif sudo -n -l >/dev/null 2>&1; then
  echo "免密 sudo : 不可用，但该用户有 sudo 权限（执行时需输入密码）"
else
  echo "免密 sudo : 不可用 → 请使用用户级 systemd（systemctl --user）或 tmux"
fi
echo "user systemd 可用性: $(systemctl --user is-system-running 2>/dev/null || echo '未知')"

section "8. 建议"
echo "根据以上结果选择："
echo "  * 一个未被占用的高位端口给后端（默认 18080）"
echo "  * 一个未被占用的端口给 Nginx 对外（默认 18081）"
echo "  * 一个独立部署目录，例如 \$HOME/apps/smoking-monitor"
echo "  * 不要修改/覆盖已有的 Nginx server 块，新增独立 conf 文件"
