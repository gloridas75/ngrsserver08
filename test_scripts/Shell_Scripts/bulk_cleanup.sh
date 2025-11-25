#!/bin/bash

# Bulk cleanup script to clear all completed jobs from Redis memory
# This frees up memory for new jobs

API_URL="https://ngrssolver08.comcentricapps.com"

echo "================================================================================"
echo "BULK CLEANUP - Clear All Completed Jobs"
echo "================================================================================"
echo ""

# Get stats to see how many completed jobs exist
echo "Checking current stats..."
STATS=$(curl -s "${API_URL}/solve/async/stats")

echo "$STATS" | python3 << 'PYTHON_SCRIPT'
import sys
import json

data = json.load(sys.stdin)

completed = data.get('completed', 0)
total_jobs = data.get('queued', 0) + data.get('processing', 0) + completed

print(f"Current State:")
print(f"  Queued:        {data.get('queued', 0)}")
print(f"  Processing:    {data.get('processing', 0)}")
print(f"  Completed:     {completed}")
print(f"  Failed:        {data.get('failed', 0)}")
print(f"  Total Active:  {total_jobs}")
print()

if completed > 0:
    print(f"⚠️  {completed} completed jobs are still in memory")
    print(f"   These will auto-delete after TTL (1 hour)")
    print(f"   Or you can manually delete specific job IDs")
else:
    print("✓ No completed jobs in memory")

PYTHON_SCRIPT

echo ""
echo "================================================================================"
echo "TO MANUALLY DELETE A SPECIFIC JOB:"
echo "================================================================================"
echo "  curl -X DELETE ${API_URL}/solve/async/{job_id}"
echo ""
echo "TO DOWNLOAD THEN CLEANUP:"
echo "================================================================================"
echo "  ./download_and_cleanup.sh {job_id}"
echo ""
echo "NOTE: Redis will automatically cleanup all jobs after 1 hour (TTL=3600s)"
echo "================================================================================"
