@echo off
REM Start VAR Live Daemon in background

cd /d "%~dp0"

echo Starting VAR Live Daemon...
echo Monitoring positions every 30 seconds
echo.

start "" python var_live_daemon.py

echo.
echo Daemon started in background!
echo Check Google Sheets for live updates
echo.
echo To stop: Close this window or kill the Python process
pause
