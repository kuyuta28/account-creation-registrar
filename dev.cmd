@echo off
title Account Creator - Dev
pushd %~dp0

echo [0/7] Kill process cu tren port 1421, 8799, 8800, 8801, 8802, 8080, 8889 (neu co)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :1421 ^| findstr LISTENING') do (
    echo Killing PID %%a...
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8799 ^| findstr LISTENING') do (
    echo Killing PID %%a...
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8800 ^| findstr LISTENING') do (
    echo Killing PID %%a...
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8801 ^| findstr LISTENING') do (
    echo Killing PID %%a...
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8802 ^| findstr LISTENING') do (
    echo Killing PID %%a...
    taskkill /PID %%a /F >nul 2>&1
)
if not exist "%~dp0logs" mkdir "%~dp0logs"

echo [1/7] Khoi dong API server (port 8799)...
powershell -WindowStyle Hidden -Command "Start-Process python -ArgumentList 'run_api.py' -WorkingDirectory '%~dp0' -WindowStyle Hidden -RedirectStandardOutput '%~dp0logs\api.log' -RedirectStandardError '%~dp0logs\api_err.log'"

echo [2/7] Khoi dong TTS Proxy (port 8800)...
powershell -WindowStyle Hidden -Command "Start-Process python -ArgumentList '-m','uvicorn','src.tts_proxy.server:app','--host','0.0.0.0','--port','8800' -WorkingDirectory '%~dp0' -WindowStyle Hidden -RedirectStandardOutput '%~dp0logs\tts.log' -RedirectStandardError '%~dp0logs\tts_err.log'"

echo [3/7] Khoi dong any-auto-register (port 8080)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8080 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)
powershell -WindowStyle Hidden -Command "$env:PORT='8080'; $env:PYTHONUTF8='1'; Start-Process python -ArgumentList 'main.py' -WorkingDirectory '%~dp0any-auto-register' -WindowStyle Hidden -RedirectStandardOutput '%~dp0logs\aar.log' -RedirectStandardError '%~dp0logs\aar_err.log'"

echo [4/7] Khoi dong Mail Service (port 8801)...
powershell -WindowStyle Hidden -Command "Start-Process python -ArgumentList 'main.py' -WorkingDirectory '%~dp0mail-service' -WindowStyle Hidden -RedirectStandardOutput '%~dp0logs\mail.log' -RedirectStandardError '%~dp0logs\mail_err.log'"

echo [5/7] Khoi dong AA Proxy (port 8802)...
powershell -WindowStyle Hidden -Command "Start-Process python -ArgumentList 'main.py' -WorkingDirectory '%~dp0aa-proxy' -WindowStyle Hidden -RedirectStandardOutput '%~dp0logs\aa_proxy.log' -RedirectStandardError '%~dp0logs\aa_proxy_err.log'"

echo [6/7] Khoi dong Turnstile Solver (port 8889)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8889 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)
powershell -WindowStyle Hidden -Command "$env:PYTHONUTF8='1'; Start-Process python -ArgumentList 'services/turnstile_solver/start.py','--browser_type','camoufox','--port','8889' -WorkingDirectory '%~dp0any-auto-register' -WindowStyle Hidden -RedirectStandardOutput '%~dp0logs\solver.log' -RedirectStandardError '%~dp0logs\solver_err.log'"

echo [7/7] Khoi dong Tauri UI...
cd ui
node node_modules\@tauri-apps\cli\tauri.js dev
