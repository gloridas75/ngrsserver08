#!/bin/bash
#
# Run NGRS Solver FastAPI Server
#
# Usage:
#   ./run_api_server.sh              # Development mode on port 8080
#   ./run_api_server.sh prod         # Production mode on port 8080
#   ./run_api_server.sh dev 9000     # Development mode on port 9000
#

cd "$(dirname "$0")"

MODE=${1:-dev}
PORT=${2:-8080}

if [ "$MODE" = "prod" ]; then
    echo "Starting NGRS API Server in PRODUCTION on port $PORT..."
    python -m uvicorn src.api_server:app --host 0.0.0.0 --port "$PORT" --workers 2
else
    echo "Starting NGRS API Server in DEVELOPMENT on port $PORT..."
    echo "  - Docs available at http://localhost:$PORT/docs"
    echo "  - ReDoc available at http://localhost:$PORT/redoc"
    python -m uvicorn src.api_server:app --reload --host 127.0.0.1 --port "$PORT"
fi
