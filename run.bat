@echo off
title Trading System Pro
cd /d "%~dp0"

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)

:: Install dependencies if needed
if not exist ".venv" (
    echo [SETUP] Creating virtual environment...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo [SETUP] Installing dependencies...
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

:: Copy .env if missing
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env
        echo [SETUP] Created .env from .env.example — edit it before running.
        notepad .env
        pause
    )
)

echo.
echo ========================================
echo   Trading System Pro — Starting...
echo ========================================
echo.

python main.py %*
pause
