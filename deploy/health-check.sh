#!/bin/bash
#
# Health check for NGRS Solver
#
# Checks:
# 1. Redis is running
# 2. API server is responding
# 3. Redis connection is working
# 4. Worker status
#

echo "=========================================="
echo "NGRS Solver Health Check"
echo "=========================================="

# Check Redis container
echo ""
echo "[1/4] Checking Redis container..."
if docker ps | grep -q ngrs-redis; then
    echo "✓ Redis container is running"
    REDIS_STATUS="✓"
else
    echo "✗ Redis container not found"
    REDIS_STATUS="✗"
fi

# Check Redis connectivity
echo ""
echo "[2/4] Checking Redis connectivity..."
if redis-cli -h localhost ping > /dev/null 2>&1; then
    echo "✓ Redis is responding to PING"
else
    echo "✗ Cannot connect to Redis on localhost:6379"
fi

# Check API server
echo ""
echo "[3/4] Checking API server..."
API_URL="${API_URL:-http://localhost:8080}"

if curl -s -f "$API_URL/health" > /dev/null 2>&1; then
    echo "✓ API server is responding"
    HEALTH=$(curl -s "$API_URL/health")
    echo "  Response: $HEALTH"
else
    echo "✗ API server not responding at $API_URL"
fi

# Check async stats
echo ""
echo "[4/4] Checking async mode stats..."
if STATS=$(curl -s -f "$API_URL/solve/async/stats" 2>/dev/null); then
    echo "✓ Async mode is working"
    echo ""
    echo "Stats:"
    echo "$STATS" | python3 -m json.tool 2>/dev/null || echo "$STATS"
else
    echo "✗ Cannot retrieve async stats"
fi

# Summary
echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
echo ""
echo "Redis:      $REDIS_STATUS"
echo "API:        $(curl -s -f "$API_URL/health" > /dev/null 2>&1 && echo "✓" || echo "✗")"
echo ""

# Exit code
if [ "$REDIS_STATUS" = "✓" ] && curl -s -f "$API_URL/health" > /dev/null 2>&1; then
    echo "Status: HEALTHY ✓"
    exit 0
else
    echo "Status: UNHEALTHY ✗"
    exit 1
fi
