@echo off
REM ============================================================================
REM  烟厂制丝线物流智能监控平台 —— 本地开发启动脚本（Windows）
REM
REM  按项目约定使用 conda `smoking` 环境启动后端，可选同时启动前端。
REM  禁止使用 base 环境或系统 Python 安装依赖。
REM
REM  用法：
REM    scripts\dev.bat          仅启动后端（http://127.0.0.1:18080）
REM    scripts\dev.bat all      同时启动后端与前端（http://127.0.0.1:15173）
REM ============================================================================

setlocal
set "ROOT=%~dp0.."

REM ---- 定位 conda smoking 环境的解释器 ----
set "SMOKING_PY="
for /f "delims=" %%i in ('conda run -n smoking python -c "import sys;print(sys.executable)" 2^>nul') do set "SMOKING_PY=%%i"

if not defined SMOKING_PY (
  echo [ERROR] 未找到 conda 环境 smoking。
  echo         请先创建： conda create -n smoking python=3.12 -y
  exit /b 1
)

echo [INFO] Python: %SMOKING_PY%
echo %SMOKING_PY% | findstr /i "envs\\smoking" >nul
if errorlevel 1 (
  echo [ERROR] 解析出的解释器不在 envs\smoking 下，请检查 conda 配置。
  exit /b 1
)

REM ---- 后端依赖自检 ----
"%SMOKING_PY%" -c "import fastapi, uvicorn" 2>nul
if errorlevel 1 (
  echo [INFO] 后端依赖缺失，正在安装 requirements.txt ...
  pushd "%ROOT%\backend"
  "%SMOKING_PY%" -m pip install -r requirements.txt
  popd
)

REM ---- 启动后端 ----
echo [INFO] 启动后端 http://127.0.0.1:18080
pushd "%ROOT%\backend"
start "smoking-backend" cmd /k ""%SMOKING_PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 18080"
popd

REM ---- 可选：启动前端 ----
if /i "%~1"=="all" (
  echo [INFO] 启动前端 http://127.0.0.1:15173
  pushd "%ROOT%\frontend"
  if not exist node_modules (
    echo [INFO] 首次运行，安装前端依赖 ...
    call npm install
  )
  start "smoking-frontend" cmd /k "npm run dev"
  popd
)

echo.
echo [DONE] 接口文档: http://127.0.0.1:18080/api/docs
if /i not "%~1"=="all" echo [TIP ] 需要前端时请执行: scripts\dev.bat all
endlocal
