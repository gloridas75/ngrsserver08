#!/bin/bash
#
# NGRS Solver - Quick Restart Script
# Usage: ./quick_restart.sh
#
# Quick script to kill any hanging processes and restart service cleanly
#

set -e

SERVICE_NAME="ngrs-solver"
LOG_FILE="/var/log/ngrs-solver.log"

echo "🔄 Quick Restart - NGRS Solver"
echo "================================"
echo ""

# Stop service
echo "⏹  Stopping service..."
sudo systemctl stop $SERVICE_NAME || true
sleep 2

# Kill any processes on port 8080
echo "🔪 Killing processes on port 8080..."
sudo lsof -ti :8080 | xargs -r sudo kill -9 || true
sleep 1

# Verify port is free
if sudo lsof -i :8080 > /dev/null 2>&1; then
    echo "❌ ERROR: Port 8080 still in use!"
    sudo lsof -i :8080
    exit 1
fi
echo "✓ Port 8080 is free"
echo ""

# Archive old log
echo "📋 Archiving old logs..."
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
if [ -f "$LOG_FILE" ]; then
    sudo mv "$LOG_FILE" "$LOG_FILE.$TIMESTAMP"
fi
sudo touch "$LOG_FILE"
sudo chown ubuntu:ubuntu "$LOG_FILE"
echo "✓ Logs cleared"
echo ""

# Start service
echo "▶️  Starting service..."
sudo systemctl start $SERVICE_NAME
sleep 5

# Check status
if sudo systemctl is-active --quiet $SERVICE_NAME; then
    echo "✓ Service is running"
else
    echo "❌ Service failed to start!"
    sudo systemctl status $SERVICE_NAME --no-pager
    echo ""
    echo "Recent logs:"
    tail -30 "$LOG_FILE"
    exit 1
fi

# Check port
if sudo lsof -i :8080 | grep -q LISTEN; then
    echo "✓ Port 8080 is listening"
else
    echo "❌ Port 8080 is NOT listening!"
    echo ""
    echo "Service status:"
    sudo systemctl status $SERVICE_NAME --no-pager
    echo ""
    echo "Recent logs:"
    tail -50 "$LOG_FILE"
    exit 1
fi

# Test health
echo ""
echo "🏥 Testing health endpoint..."
HEALTH=$(curl -s http://localhost:8080/health || echo "failed")
if [[ "$HEALTH" == *"ok"* ]]; then
    echo "✓ Health check passed: $HEALTH"
else
    echo "❌ Health check failed: $HEALTH"
    exit 1
fi

echo ""
echo "================================"
echo "✅ Service restarted successfully!"
echo "================================"
echo ""
echo "Recent logs:"
tail -10 "$LOG_FILE"
