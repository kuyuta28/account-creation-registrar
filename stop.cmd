@echo off
title Stopping Account Creator...

echo [1/2] Killing process on port 8799 (API server)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8799 " 2^>nul') do (
    taskkill /F /PID %%p >nul 2>&1
)

echo [2/2] Killing Tauri window by title...
taskkill /F /FI "WINDOWTITLE eq Account Creator - Dev" /T >nul 2>&1
taskkill /F /IM account-creator.exe /T >nul 2>&1

echo.
echo Done.
timeout /t 1 /nobreak >nul
