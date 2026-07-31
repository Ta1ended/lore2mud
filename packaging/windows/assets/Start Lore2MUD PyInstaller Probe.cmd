@echo off
setlocal
set "BUNDLE_ROOT=%~dp0"
set "GAME=%BUNDLE_ROOT%lore2mud.exe"
set "CONTENT=%BUNDLE_ROOT%original_demo"
if defined LORE2MUD_DATA_DIR (
  set "DATA_ROOT=%LORE2MUD_DATA_DIR%"
) else (
  set "DATA_ROOT=%LOCALAPPDATA%\lore2mud"
)
set "SAVE_DIR=%DATA_ROOT%\saves"
if not exist "%GAME%" (
  echo [ERROR] This probe is incomplete: lore2mud.exe is missing.
  exit /b 2
)
if not exist "%CONTENT%\pack.json" (
  echo [ERROR] This probe is incomplete: original_demo is missing.
  exit /b 2
)
if not exist "%SAVE_DIR%" mkdir "%SAVE_DIR%"
if /i "%~1"=="--diagnose" (
  echo lore2mud PyInstaller probe
  echo Executable: %GAME%
  echo Content pack: %CONTENT%
  echo Data directory: %DATA_ROOT%
  echo Save directory: %SAVE_DIR%
  "%GAME%" validate --content "%CONTENT%"
  exit /b %ERRORLEVEL%
)
"%GAME%" play --content "%CONTENT%" --save-dir "%SAVE_DIR%" %*
exit /b %ERRORLEVEL%
