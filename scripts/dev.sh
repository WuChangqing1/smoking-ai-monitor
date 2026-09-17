#!/usr/bin/env bash
# ============================================================================
#  烟厂制丝线物流智能监控平台 —— 本地开发启动脚本（Linux / macOS）
#
#  按项目约定使用 conda `smoking` 环境启动后端，可选同时启动前端。
#  禁止使用 base 环境或系统 Python 安装依赖。
#
#  用法：
#    ./scripts/dev.sh          仅启动后端（http://127.0.0.1:18080）
#    ./scripts/dev.sh all      同时启动后端与前端（http://127.0.0.1:15173）
# ============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ---- 定位 conda smoking 环境 ----
if ! command -v conda >/dev/null 2>&1; then
  echo "[ERROR] 未找到 conda。请先安装 Miniconda/Anaconda。" >&2
  exit 1
fi

SMOKING_PY="$(conda run -n smoking python -c 'import sys;print(sys.executable)' 2>/dev/null || true)"
if [ -z "$SMOKING_PY" ]; then
  echo "[ERROR] 未找到 conda 环境 smoking。" >&2
  echo "        请先创建： conda create -n smoking python=3.12 -y" >&2
  exit 1
fi

case "$SMOKING_PY" in
  *envs/smoking/*) ;;
  *) echo "[ERROR] 解释器不在 envs/smoking 下：$SMOKING_PY" >&2; exit 1 ;;
esac

echo "[INFO] Python: $SMOKING_PY"

# ---- 后端依赖自检 ----
if ! "$SMOKING_PY" -c 'import fastapi, uvicorn' 2>/dev/null; then
  echo "[INFO] 后端依赖缺失，正在安装 requirements.txt ..."
  ( cd "$ROOT/backend" && "$SMOKING_PY" -m pip install -r requirements.txt )
fi

# ---- 启动后端 ----
echo "[INFO] 启动后端 http://127.0.0.1:18080"
( cd "$ROOT/backend" && exec "$SMOKING_PY" -m uvicorn app.main:app --host 127.0.0.1 --port 18080 ) &
BACKEND_PID=$!

cleanup() {
  echo
  echo "[INFO] 停止后端 (pid=$BACKEND_PID)"
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ---- 可选：启动前端 ----
if [ "${1:-}" = "all" ]; then
  echo "[INFO] 启动前端 http://127.0.0.1:15173"
  cd "$ROOT/frontend"
  [ -d node_modules ] || { echo "[INFO] 首次运行，安装前端依赖 ..."; npm install; }
  npm run dev
else
  echo
  echo "[DONE] 接口文档: http://127.0.0.1:18080/api/docs"
  echo "[TIP ] 需要前端时请执行: ./scripts/dev.sh all"
  wait "$BACKEND_PID"
fi
