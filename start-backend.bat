@echo off
REM CryptoVault Backend Startup Script for Windows
REM This script starts the Python FastAPI backend server on port 8001

setlocal enabledelayedexpansion

echo.
echo 🚀 Starting CryptoVault Backend Server...
echo ==================================================

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0
set BACKEND_DIR=%SCRIPT_DIR%backend

REM Change to backend directory
cd /d "%BACKEND_DIR%"

echo Backend directory: %BACKEND_DIR%
echo Current directory: %cd%

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed. Please install Python 3.8 or higher.
    pause
    exit /b 1
)

echo Python version:
python --version

REM Check if .env file exists
if not exist .env (
    echo ⚠️ .env file not found in backend directory
    echo Creating .env from .env.template...
    if exist .env.template (
        copy .env.template .env >nul
        echo ✅ .env created from template
    ) else (
        echo ❌ .env.template not found. Cannot create .env
        pause
        exit /b 1
    )
)

REM Check if virtual environment exists
if not exist venv (
    echo Creating Python virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies if needed
echo Checking and installing dependencies...
pip install -q -r requirements.txt 2>nul || goto :skip_error

:skip_error
REM Validate configuration
echo Validating configuration...
python -c "from config import settings, validate_startup_environment; print(f'✅ Config loaded: {settings.environment} mode'); validate_startup_environment()" || (
    echo ⚠️ Configuration validation encountered warnings (non-critical)
)

echo.
echo ==================================================
echo ✅ Backend services initialized
echo 📡 Starting FastAPI server on http://localhost:8001
echo 📚 API Documentation: http://localhost:8001/api/docs
echo ==================================================
echo.

REM Start the server
python -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload --log-level info

pause
