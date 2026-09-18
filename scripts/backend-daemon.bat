@echo off
REM ============================================================================
REM  本地后端守护脚本（Windows）：崩溃自动重启
REM
REM  用最小化窗口的 cmd 循环拉起 uvicorn，进程退出后 3 秒自动重启。
REM  适合长时间开着前端做演示，避免"实时数据不可用"。
REM
REM  停止方式：关闭标题为 smoking-backend 的窗口，或在任务管理器结束 python.exe
REM ============================================================================

setlocal
set "ROOT=%~dp0.."

set "SMOKING_PY="
for /f "delims=" %%i in ('conda run -n smoking python -c "import sys;print(sys.executable)" 2^>nul') do set "SMOKING_PY=%%i"

if not defined SMOKING_PY (
  echo [ERROR] 未找到 conda 环境 smoking。
  pause
  exit /b 1
)

title smoking-backend
echo [INFO] 后端守护已启动，崩溃将自动重启（关闭本窗口即停止）
echo.

:loop
echo [%date% %time%] 启动后端 ...
pushd "%ROOT%\backend"
"%SMOKING_PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 18080
popd
echo [%date% %time%] 后端已退出，3 秒后重启 ...
timeout /t 3 /nobreak >nul
goto loop
