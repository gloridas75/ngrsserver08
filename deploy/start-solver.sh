#!/bin/bash
#
# Start NGRS Solver (API + Workers)
#
# This script starts the solver with Redis-backed async mode.
# Workers run in the same process as the API server.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "Starting NGRS Solver"
echo "=========================================="

# Load environment variables
if [ -f "$HOME/.ngrs-env" ]; then
    source "$HOME/.ngrs-env"
    echo "✓ Loaded environment from ~/.ngrs-env"
else
    # Default values
    export START_WORKERS=true
    export SOLVER_WORKERS=4
    export REDIS_URL=localhost:6379
    export PORT=8080
    echo "⚠ Using default environment (no ~/.ngrs-env found)"
fi

# Check Redis is running
echo ""
echo "Checking Redis..."
if docker ps | grep -q ngrs-redis; then
    echo "✓ Redis container is running"
else
    echo "⚠ Redis container not found. Starting Redis..."
    docker run -d \
        --name ngrs-redis \
        --restart unless-stopped \
        -p 6379:6379 \
        redis:7-alpine
    sleep 2
    echo "✓ Redis started"
fi

# Verify Redis connectivity
if redis-cli -h localhost ping > /dev/null 2>&1; then
    echo "✓ Redis is responding"
else
    echo "✗ Cannot connect to Redis"
    exit 1
fi

# Start the solver
echo ""
echo "Starting API server with $SOLVER_WORKERS workers..."
echo "API will be available at: http://0.0.0.0:$PORT"
echo ""
echo "Environment:"
echo "  START_WORKERS=$START_WORKERS"
echo "  SOLVER_WORKERS=$SOLVER_WORKERS"
echo "  REDIS_URL=$REDIS_URL"
echo ""
echo "Press Ctrl+C to stop"
echo "=========================================="
echo ""

cd "$PROJECT_DIR"
python3 -m uvicorn src.api_server:app --host 0.0.0.0 --port $PORT
