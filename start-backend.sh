#!/bin/bash

# CryptoVault Backend Startup Script
# This script starts the Python FastAPI backend server on port 8001

set -e

echo "🚀 Starting CryptoVault Backend Server..."
echo "=================================================="

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$SCRIPT_DIR/backend"

# Change to backend directory
cd "$BACKEND_DIR"

echo "Backend directory: $BACKEND_DIR"
echo "Current directory: $(pwd)"

# Check if Python is installed
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "❌ Python is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Determine Python command
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

echo "Python command: $PYTHON_CMD"
echo "Python version: $($PYTHON_CMD --version)"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️ .env file not found in backend directory"
    echo "Creating .env from .env.template..."
    if [ -f .env.template ]; then
        cp .env.template .env
        echo "✅ .env created from template"
    else
        echo "❌ .env.template not found. Cannot create .env"
        exit 1
    fi
fi

# Check if virtual environment exists
if [ ! -d venv ]; then
    echo "Creating Python virtual environment..."
    $PYTHON_CMD -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate || . venv/Scripts/activate

# Install dependencies if needed
echo "Checking and installing dependencies..."
pip install -q -r requirements.txt 2>/dev/null || true

# Validate configuration
echo "Validating configuration..."
$PYTHON_CMD -c "from config import settings, validate_startup_environment; print(f'✅ Config loaded: {settings.environment} mode'); validate_startup_environment()" || {
    echo "⚠️ Configuration validation encountered warnings (non-critical)"
}

echo ""
echo "=================================================="
echo "✅ Backend services initialized"
echo "📡 Starting FastAPI server on http://localhost:8001"
echo "📚 API Documentation: http://localhost:8001/api/docs"
echo "=================================================="
echo ""

# Start the server
$PYTHON_CMD -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload --log-level info
