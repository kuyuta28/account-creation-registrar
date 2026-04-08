@echo off
title Registrar - Dev
pushd %~dp0

echo [0/1] Kill process cu tren port 8709 (neu co)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8709 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)

if not exist "%~dp0logs" mkdir "%~dp0logs"

echo [1/1] Khoi dong Registrar API (port 8709)...
start "Registrar (8709)" python run_api.py
