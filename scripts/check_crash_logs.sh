#!/bin/bash
# Script to check crash logs on Ubuntu server

echo "=== Checking for OOM (Out of Memory) Killer ==="
# Check if OOM killer terminated processes
sudo dmesg -T | grep -i "killed process\|out of memory\|oom" | tail -20

echo ""
echo "=== Checking System Logs for Python/Uvicorn Crashes ==="
# Check for uvicorn/python crashes
sudo journalctl -u ngrs-solver -n 100 --no-pager | grep -i "killed\|crash\|signal\|memory"

echo ""
echo "=== Checking Application Logs ==="
# Check application logs (adjust path as needed)
tail -100 /var/log/ngrs-solver/app.log 2>/dev/null || tail -100 /tmp/ngrs_server.log 2>/dev/null

echo ""
echo "=== Current Memory Usage ==="
free -h

echo ""
echo "=== Top Memory-Consuming Processes ==="
ps aux --sort=-%mem | head -10
