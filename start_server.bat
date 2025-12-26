@echo off
setlocal EnableDelayedExpansion

REM ========================================
REM   n8n Architect MCP Server - GOD MODE
REM   Advanced Startup & Process Manager
REM ========================================

title n8n Architect MCP - Monitor
cd /d "%~dp0"

REM ANSI Colors (Windows 10/11)
set "ESC="
set "RED=%ESC%[91m"
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "CYAN=%ESC%[96m"
set "WHITE=%ESC%[97m"
set "GRAY=%ESC%[90m"
set "RESET=%ESC%[0m"
set "BOLD=%ESC%[1m"

cls
echo.
echo  %CYAN%╔══════════════════════════════════════════════════════════════╗%RESET%
echo  %CYAN%║%RESET%  %WHITE%%BOLD%n8n Architect MCP Server%RESET% %GRAY%- Process Manager v3.0%RESET%      %CYAN%║%RESET%
echo  %CYAN%╚══════════════════════════════════════════════════════════════╝%RESET%
echo.

REM ========================================
REM MONITORING: Cleanup Old Instances
REM ========================================
echo %CYAN%[MONITOR]%RESET% Scanning for orphaned instances...

REM Define logic to identify our specific processes
REM specifically looking for 'run.py' running in simple python mode
REM or 'app.main:app' running in uvicorn mode
set "TARGET_XS=run.py"
set "TARGET_UV=app.main:app"

REM Execute Powershell one-liner to kill matching processes
powershell -NoProfile -Command ^
  "$app = '%TARGET_XS%'; " ^
  "$uv = '%TARGET_UV%'; " ^
  "$currentPath = [System.Text.RegularExpressions.Regex]::Escape('%~dp0'.Replace('\', '\\')); " ^
  "Write-Host 'Searching processes in: ' -NoNewline; Write-Host '%~dp0' -ForegroundColor Gray; " ^
  "$procs = Get-CimInstance Win32_Process | Where-Object { " ^
  "  $_.CommandLine -and ($_.Name -eq 'python.exe') -and " ^
  "  ($_.CommandLine -match $currentPath) " ^
  "}; " ^
  "if ($procs) { " ^
  "  foreach ($p in $procs) { " ^
  "    Write-Host '  Found active instance (PID ' $p.ProcessId ')... ' -NoNewline -ForegroundColor Yellow; " ^
  "    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue; " ^
  "    Write-Host 'TERMINATED' -ForegroundColor Red; " ^
  "  } " ^
  "} else { " ^
  "  Write-Host '  No active instances found.' -ForegroundColor Green; " ^
  "}"

echo.

REM ========================================
REM Step 1: Check Python
REM ========================================
python --version >nul 2>&1
if errorlevel 1 (
    echo %RED%[ERROR] Python unavailable in PATH.%RESET%
    pause
    exit /b 1
)

REM ========================================
REM Step 2: Environment Setup
REM ========================================
if not exist "venv" (
    echo %YELLOW%[SETUP]%RESET% Initializing Virtual Environment...
    python -m venv venv
    echo %GREEN%        Done.%RESET%
)

REM ========================================
REM Step 3: Activation & Integrity
REM ========================================
echo %GRAY%        Activating VENV...%RESET%
call venv\Scripts\activate.bat >nul 2>&1
if errorlevel 1 (
    echo %RED%[ERROR] VENV Protection Fault.%RESET%
    pause
    exit /b 1
)

REM Check/Install deps only if requirements.txt changed (simple check)
REM or just run pip install quietly every time to be safe
echo %GRAY%        Verifying Neural Link (Dependencies)...%RESET%
pip install -q -r requirements.txt
if errorlevel 1 (
    echo %RED%[ERROR] Dependency sync failed.%RESET%
    pause
    exit /b 1
)

REM ========================================
REM Step 4: Configuration Check
REM ========================================
if not exist ".env" (
    echo %RED%[WARNING] .env file missing!%RESET%
    (
        echo N8N_BASE_URL=http://localhost:5678/api/v1
        echo N8N_API_KEY=change_me
        echo API_PORT=8001
        echo DEBUG=true
    ) > .env
    echo %YELLOW%        Created default .env template.%RESET%
)

REM Extract PORT from .env using simple finding string
set PORT=8000
for /f "tokens=2 delims==" %%a in ('findstr "API_PORT" .env') do set PORT=%%a
REM Clean spaces if any (basic trim)
set PORT=%PORT: =%


REM ========================================
REM LAUNCH SEQUENCE
REM ========================================
echo.
echo %GREEN%[SYSTEM]%RESET% All Systems Nominal.
echo %GREEN%[LAUNCH]%RESET% Ignition Sequence Start...
echo.
echo    %CYAN%Protocol:%RESET%    SSE / HTTP
echo    %CYAN%Endpoint:%RESET%    http://localhost:%PORT%/sse
echo    %CYAN%Swagger:%RESET%     http://localhost:%PORT%/docs
echo.
echo %WHITE%================ [ SERVER LOGS ] ================%RESET%

python run.py

echo.
echo %RED%[SYSTEM]%RESET% Server Shutdown Unexpectedly.
echo Press any key to restart...
pause >nul
goto :eof
