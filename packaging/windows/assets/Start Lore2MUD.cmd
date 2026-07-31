@echo off
setlocal
set "BUNDLE_ROOT=%~dp0"
set "LAUNCHER=%BUNDLE_ROOT%launcher.ps1"
if not exist "%LAUNCHER%" (
  echo [ERROR] This bundle is incomplete: launcher.ps1 is missing.
  pause
  exit /b 2
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER%" %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" if "%~1"=="" pause
exit /b %EXIT_CODE%
