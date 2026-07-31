@echo off
setlocal
set "SCRIPT=%~dp0build_candidate.py"
where py.exe >nul 2>nul
if %ERRORLEVEL%==0 (
  py.exe -3 "%SCRIPT%" %*
) else (
  python.exe "%SCRIPT%" %*
)
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%
