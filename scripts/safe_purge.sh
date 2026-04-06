#!/bin/bash
# Safe Purge Script - Moves orphaned files to _legacy_archive
# DO NOT DELETE immediately - archive for 30 days

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
ARCHIVE_DIR="$REPO_ROOT/_legacy_archive"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "🗑️ CryptoVault Safe Purge Script"
echo "=================================="
echo "Archive Directory: $ARCHIVE_DIR/$TIMESTAMP"
echo ""

# Create archive directory
mkdir -p "$ARCHIVE_DIR/$TIMESTAMP"

# ============================================
# BACKEND CLEANUP
# ============================================

echo "📦 Backend Cleanup..."

# Move v1 routers
if [ -d "$BACKEND_DIR/routers/v1" ]; then
  echo "  ├─ Moving /backend/routers/v1/ → $ARCHIVE_DIR/$TIMESTAMP/backend_routers_v1/"
  mkdir -p "$ARCHIVE_DIR/$TIMESTAMP/backend_routers_v1"
  cp -r "$BACKEND_DIR/routers/v1/"* "$ARCHIVE_DIR/$TIMESTAMP/backend_routers_v1/" 2>/dev/null || true
  echo "    └─ ✅ Archived (original files kept for now)"
fi

# Archive legacy routers (review first)
if [ -f "$BACKEND_DIR/routers/deep_investigation.py" ]; then
  echo "  ├─ Archiving deep_investigation.py"
  cp "$BACKEND_DIR/routers/deep_investigation.py" "$ARCHIVE_DIR/$TIMESTAMP/" 2>/dev/null || true
fi

if [ -f "$BACKEND_DIR/routers/fly_status.py" ]; then
  echo "  ├─ Archiving fly_status.py"
  cp "$BACKEND_DIR/routers/fly_status.py" "$ARCHIVE_DIR/$TIMESTAMP/" 2>/dev/null || true
fi

echo "  └─ Backend cleanup complete"
echo ""

# ============================================
# SUMMARY
# ============================================

echo "✅ Safe Archive Complete!"
echo ""
echo "📊 Summary:"
echo "  - Archived to: $ARCHIVE_DIR/$TIMESTAMP"
echo "  - Original files: KEPT (safe mode)"
echo ""
echo "⚠️ Review archived files, then manually delete if not needed:"
echo "  rm -rf $BACKEND_DIR/routers/v1"
echo "  rm $BACKEND_DIR/routers/deep_investigation.py"
echo "  rm $BACKEND_DIR/routers/fly_status.py"
echo ""
echo "🔄 Rollback (if needed):"
echo "  cp -r $ARCHIVE_DIR/$TIMESTAMP/backend_routers_v1/* $BACKEND_DIR/routers/v1/"
echo ""
