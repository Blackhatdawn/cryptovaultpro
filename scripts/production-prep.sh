#!/bin/bash

# CryptoVault Production Preparation Script
# Fixes minor issues discovered in deep investigation

echo "=========================================="
echo "CryptoVault Production Preparation"
echo "=========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC}  $1"
}

# 1. Remove console.log statements from frontend (optional - comment out if you want to keep them for debugging)
echo "1. Checking console.log statements..."
CONSOLE_COUNT=$(find /app/frontend/src -type f \( -name "*.ts" -o -name "*.tsx" \) -exec grep -l "console\." {} \; 2>/dev/null | wc -l)
if [ "$CONSOLE_COUNT" -gt 0 ]; then
    print_warning "Found $CONSOLE_COUNT files with console statements"
    echo "   To remove: Run this script with --remove-console flag"
    echo "   Or manually: find /app/frontend/src -type f \( -name '*.ts' -o -name '*.tsx' \) -exec sed -i '/console\./d' {} +"
else
    print_status "No console statements found"
fi

# 2. Check for TODO comments
echo ""
echo "2. Checking TODO comments..."
TODO_COUNT=$(find /app/frontend/src -type f \( -name "*.ts" -o -name "*.tsx" \) -exec grep -i "TODO\|FIXME" {} \; 2>/dev/null | wc -l)
if [ "$TODO_COUNT" -gt 0 ]; then
    print_warning "Found $TODO_COUNT TODO/FIXME comments"
    echo "   Review with: grep -rn 'TODO\|FIXME' /app/frontend/src"
else
    print_status "No TODO comments found"
fi

# 3. Verify environment files exist
echo ""
echo "3. Checking environment configuration..."
if [ -f "/app/backend/.env" ]; then
    print_status "Backend .env exists"
    
    # Check for required variables
    REQUIRED_VARS=("MONGO_URL" "JWT_SECRET" "CORS_ORIGINS")
    for var in "${REQUIRED_VARS[@]}"; do
        if grep -q "^$var=" /app/backend/.env; then
            print_status "  $var configured"
        else
            print_warning "  $var missing or not set"
        fi
    done
else
    print_warning "Backend .env not found - copy from .env.example"
fi

if [ -f "/app/frontend/.env" ]; then
    print_status "Frontend .env exists"
else
    print_warning "Frontend .env not found (optional for development)"
fi

# 4. Check TypeScript compilation
echo ""
echo "4. TypeScript compilation check..."
cd /app/frontend
if yarn tsc --noEmit 2>&1 | grep -q "error TS"; then
    print_warning "TypeScript errors found"
    echo "   Run: cd /app/frontend && yarn tsc --noEmit"
else
    print_status "No TypeScript errors"
fi

# 5. Check Python dependencies
echo ""
echo "5. Checking Python dependencies..."
cd /app/backend
if pip list 2>/dev/null | grep -q "fastapi"; then
    print_status "Python dependencies installed"
else
    print_warning "Some Python dependencies may be missing"
    echo "   Run: cd /app/backend && pip install -r requirements.txt"
fi

# 6. Check frontend dependencies
echo ""
echo "6. Checking frontend dependencies..."
cd /app/frontend
if [ -d "node_modules" ]; then
    print_status "Frontend dependencies installed"
else
    print_warning "Frontend dependencies not installed"
    echo "   Run: cd /app/frontend && yarn install"
fi

# 7. Database connection test
echo ""
echo "7. Testing database connection..."
cd /app/backend
python3 << 'PYEOF' 2>/dev/null
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

async def test_db():
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('MONGO_URL='):
                    mongo_url = line.split('=', 1)[1].strip()
                    break
        
        client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=3000)
        await client.admin.command('ping')
        print("✅ Database connection successful")
        client.close()
    except Exception as e:
        print(f"⚠️  Database connection failed: {str(e)[:50]}")

asyncio.run(test_db())
PYEOF

# 8. Check service status
echo ""
echo "8. Service status..."
if command -v supervisorctl &> /dev/null; then
    sudo supervisorctl status backend 2>/dev/null | grep -q "RUNNING" && print_status "Backend running" || print_warning "Backend not running"
    sudo supervisorctl status frontend 2>/dev/null | grep -q "RUNNING" && print_status "Frontend running" || print_warning "Frontend not running"
else
    print_warning "Supervisor not available (OK for manual run)"
fi

# 9. Security checklist
echo ""
echo "9. Security checklist..."
cd /app/backend
if grep -q "JWT_SECRET=your-super-secret" .env 2>/dev/null; then
    print_warning "JWT_SECRET still using default - CHANGE THIS!"
else
    print_status "JWT_SECRET appears customized"
fi

if grep -q "ENVIRONMENT=production" .env 2>/dev/null; then
    print_status "Environment set to production"
elif grep -q "ENVIRONMENT=development" .env 2>/dev/null; then
    print_warning "Environment is development (OK for testing)"
else
    print_warning "ENVIRONMENT not set"
fi

# 10. Final recommendations
echo ""
echo "=========================================="
echo "Production Deployment Checklist"
echo "=========================================="
echo ""
echo "Before deploying to production:"
echo ""
echo "📋 Required:"
echo "  1. Set production MONGO_URL in backend .env"
echo "  2. Generate strong JWT_SECRET (32+ characters)"
echo "  3. Get Resend API key for emails (or SMTP/SendGrid credentials)"
echo "  4. Get CoinCap API key"
echo "  5. Configure CORS_ORIGINS with your domain"
echo "  6. Set ENVIRONMENT=production"
echo ""
echo "📋 Recommended:"
echo "  1. Get Upstash Redis (free tier available)"
echo "  2. Configure Sentry for error tracking"
echo "  3. Test all features thoroughly"
echo "  4. Run: yarn build (frontend)"
echo "  5. Review deployment guide: DEPLOYMENT_GUIDE.md"
echo ""
echo "=========================================="
echo "Script complete!"
echo "=========================================="

# Handle command line arguments
if [ "$1" == "--remove-console" ]; then
    echo ""
    read -p "Remove all console statements from frontend? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        find /app/frontend/src -type f \( -name "*.ts" -o -name "*.tsx" \) -exec sed -i '/console\./d' {} +
        print_status "Console statements removed"
    fi
fi
