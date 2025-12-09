#!/bin/bash

# Start the custom HTTP server with file browsing API
# This allows the HTML viewer to browse files in the output/ folder

cd "$(dirname "$0")"

echo "Starting NGRS Solver Viewer Server..."
echo "Open your browser to: http://localhost:8000/viewer.html"
echo ""
echo "Features:"
echo "  - Browse all JSON files from the output/ folder"
echo "  - Server API at /api/output-files and /api/input-files"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python3 server.py
