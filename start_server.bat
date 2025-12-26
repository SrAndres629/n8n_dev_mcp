@echo off
setlocal EnableDelayedExpansion

REM ========================================
REM   n8n Architect MCP Server - Launcher
REM   Production-Grade Startup Script
REM ========================================

title n8n Architect MCP Server

cd /d "%~dp0"

REM Colors
set "GREEN=[92m"
set "YELLOW=[93m"
set "RED=[91m"
set "CYAN=[96m"
set "RESET=[0m"

echo.
echo %CYAN%========================================%RESET%
echo %CYAN%   n8n Architect MCP Server%RESET%
echo %CYAN%========================================%RESET%
echo.

REM ========================================
REM Step 1: Check Python Installation
REM ========================================
echo %YELLOW%[1/5]%RESET% Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo %RED%ERROR: Python is not installed or not in PATH%RESET%
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo       Python %PYTHON_VERSION% detected

REM ========================================
REM Step 2: Create Virtual Environment
REM ========================================
if not exist "venv" (
    echo %YELLOW%[2/5]%RESET% Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo %RED%ERROR: Failed to create virtual environment%RESET%
        pause
        exit /b 1
    )
    echo       %GREEN%Virtual environment created%RESET%
) else (
    echo %YELLOW%[2/5]%RESET% Virtual environment exists %GREEN%✓%RESET%
)

REM ========================================
REM Step 3: Activate Virtual Environment
REM ========================================
echo %YELLOW%[3/5]%RESET% Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo %RED%ERROR: Failed to activate virtual environment%RESET%
    pause
    exit /b 1
)

REM ========================================
REM Step 4: Upgrade pip (silent)
REM ========================================
echo %YELLOW%[4/5]%RESET% Updating pip...
python -m pip install --upgrade pip -q >nul 2>&1

REM ========================================
REM Step 5: Install Dependencies
REM ========================================
echo %YELLOW%[5/5]%RESET% Installing dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo %RED%ERROR: Failed to install dependencies%RESET%
    echo Try running: pip install -r requirements.txt
    pause
    exit /b 1
)
echo       %GREEN%Dependencies installed ✓%RESET%

REM ========================================
REM Check .env file
REM ========================================
if not exist ".env" (
    echo.
    echo %RED%WARNING: .env file not found!%RESET%
    echo Please create .env with:
    echo   N8N_API_KEY=your_api_key
    echo   N8N_BASE_URL=http://localhost:5678/api/v1
    echo.
)

REM ========================================
REM Start Server
REM ========================================
echo.
echo %GREEN%========================================%RESET%
echo %GREEN%   Starting Server...%RESET%
echo %GREEN%========================================%RESET%
echo.
echo %CYAN%Health Check:%RESET%  http://localhost:8000/health
echo %CYAN%API Docs:%RESET%      http://localhost:8000/docs
echo %CYAN%MCP Tools:%RESET%     Available via FastMCP
echo.
echo Press %YELLOW%Ctrl+C%RESET% to stop the server
echo.

python run.py

echo.
echo %YELLOW%Server stopped.%RESET%
pause
