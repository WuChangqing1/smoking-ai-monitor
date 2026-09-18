@echo off
REM ============================================================================
REM  本地后端守护脚本（Windows）
REM
REM  作用：自动重启本机后端（127.0.0.1:18080），解决
REM        "无法连接后端服务（/api/realtime）。请确认后端已在 127.0.0.1:18080 启动"
REM
REM  用法：
REM    scripts\backend.bat            前台运行（关掉窗口即停止，适合调试）
REM    scripts\backend-daemon.bat     后台守护（崩溃自动重启，最小化窗口）
REM
REM  前提：conda 环境 smoking 已创建，且已 pip install -r backend\requirements.txt
REM ============================================================================

setlocal
set "ROOT=%~dp0.."
set "PORT=18080"

REM ---- 定位 conda smoking 环境 ----
set "SMOKING_PY="
for /f "delims=" %%i in ('conda run -n smoking python -c "import sys;print(sys.executable)" 2^>nul') do set "SMOKING_PY=%%i"

if not defined SMOKING_PY (
  echo [ERROR] 未找到 conda 环境 smoking。
  echo         请先创建： conda create -n smoking python=3.12 -y
  exit /b 1
)

echo %SMOKING_PY% | findstr /i "envs\\smoking" >nul
if errorlevel 1 (
  echo [ERROR] 解释器不在 envs\smoking 下：%SMOKING_PY%
  exit /b 1
)

REM ---- 依赖自检 ----
"%SMOKING_PY%" -c "import fastapi, uvicorn" 2>nul
if errorlevel 1 (
  echo [INFO] 后端依赖缺失，正在安装 ...
  pushd "%ROOT%\backend"
  "%SMOKING_PY%" -m pip install -r requirements.txt
  popd
)

REM ---- 端口占用检查（避免重复启动） ----
netstat -ano | findstr /r /c:"127.0.0.1:%PORT% .*LISTENING" >nul
if not errorlevel 1 (
  echo [INFO] 端口 %PORT% 已在监听，后端可能已在运行。
  echo        如需重启，请先结束占用该端口的进程。
  echo.
  echo        查看健康状态： curl http://127.0.0.1:%PORT%/api/health
  exit /b 0
)

echo [INFO] Python : %SMOKING_PY%
echo [INFO] 启动后端 http://127.0.0.1:%PORT%
echo [INFO] 接口文档 http://127.0.0.1:%PORT%/api/docs
echo.

pushd "%ROOT%\backend"
"%SMOKING_PY%" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%
popd
endlocal
