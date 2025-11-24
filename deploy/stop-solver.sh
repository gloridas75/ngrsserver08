#!/bin/bash
#
# Stop NGRS Solver
#

echo "Stopping NGRS Solver..."

# Stop API server
pkill -f "uvicorn.*api_server" && echo "✓ API server stopped" || echo "⚠ No API server process found"

# Optionally stop Redis (uncomment if needed)
# docker stop ngrs-redis && echo "✓ Redis stopped" || echo "⚠ Redis container not running"

echo "Done"
