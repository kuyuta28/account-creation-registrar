#!/usr/bin/env pwsh
# Browser Gateway watchdog — auto-restart on crash. Runs as Task Scheduler at logon.
# Memory: gateway-architecture — gateway must run host-native (camoufox binary).

$ErrorActionPreference = 'Continue'
$python = 'C:\Users\admin\AppData\Local\Programs\Python\Python312\python.exe'
$repo   = 'D:\business\account-creation'
$script = Join-Path $repo 'registrar\tools\host_browser_agent.py'
$logDir = Join-Path $repo 'registrar\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir 'gateway.log'

$env:PYTHONPATH = "$repo\registrar;$repo\common"
$env:HOST_BROWSER_AGENT_URL = 'http://127.0.0.1:9999'
$env:NINEROUTER_PASSWORD     = '@Anhtuan13'
$env:TWOCAPTCHA_API_KEY      = 'e3d2b699ddd12357052812f925563d4d'
$env:INTERNAL_API_KEY        = 'dev-internal-key'
$env:DATABASE_URL            = 'postgresql+asyncpg://ccs:ccs_dev_only@127.0.0.1:5432/account_creator'
$env:CAMOUFOX_HEADLESS       = '1'

while ($true) {
    $start = Get-Date
    "[$start] starting gateway..." | Out-File -FilePath $logFile -Append -Encoding utf8
    $p = Start-Process -FilePath $python -ArgumentList $script -NoNewWindow -PassThru `
        -RedirectStandardOutput $logFile -RedirectStandardError $logFile
    $p.WaitForExit()
    $exit = $p.ExitCode
    $end = Get-Date
    "[$end] gateway exited code=$exit — restarting in 3s" | Out-File -FilePath $logFile -Append -Encoding utf8
    Start-Sleep -Seconds 3
}
