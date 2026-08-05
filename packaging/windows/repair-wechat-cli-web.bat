@echo off
setlocal
set "INSTALL_DIR=%LOCALAPPDATA%\WeChatCliWeb"
set "LAUNCHER=%INSTALL_DIR%\launcher\wechat-cli-launcher.exe"
if not exist "%LAUNCHER%" (
  echo WeChat CLI Launcher is missing. Reinstall the bootstrap package.
  pause
  exit /b 3
)
"%LAUNCHER%" --repair
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%
