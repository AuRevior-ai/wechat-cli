@echo off
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"
set "EXE=%ROOT%app\wechat-cli.exe"

if not exist "%EXE%" (
  echo Cannot find "%EXE%".
  echo Please run install-and-start.bat again or unzip the full package.
  pause
  exit /b 1
)

echo Starting WeChat CLI Web...
echo URL: http://127.0.0.1:8787
echo.
echo Keep this window open while using the web console.
echo Press Ctrl+C here to stop the local server.
echo.
"%EXE%" web --port 8787 --open
echo.
echo WeChat CLI Web has stopped.
pause
