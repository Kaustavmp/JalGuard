@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  py start_jalguard.py
) else (
  python start_jalguard.py
)

endlocal
