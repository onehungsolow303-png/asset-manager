@echo off
REM Manual launcher for Asset Manager on port 7801.
REM Logs stream to %USERPROFILE%\..\..\Dev\logs\asset_manager.log (appends).
setlocal
set AM_ROOT=C:\Dev\Asset Manager
set LOG_DIR=C:\Dev\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
echo Starting Asset Manager on http://127.0.0.1:7801
echo Logs: %LOG_DIR%\asset_manager.log
cd /d "%AM_ROOT%"
"%AM_ROOT%\.venv\Scripts\uvicorn.exe" asset_manager.bridge.server:app --port 7801 --log-level info >> "%LOG_DIR%\asset_manager.log" 2>&1
endlocal
