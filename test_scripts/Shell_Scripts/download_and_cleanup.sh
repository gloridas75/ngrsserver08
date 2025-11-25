#!/bin/bash

# Script to download async job result and immediately clean it up from memory
# Usage: ./download_and_cleanup.sh <job_id> [output_file]

if [ -z "$1" ]; then
    echo "Usage: $0 <job_id> [output_file]"
    echo "Example: $0 abc123-def456-ghi789 result.json"
    exit 1
fi

JOB_ID="$1"
OUTPUT_FILE="${2:-output/result_${JOB_ID}.json}"
API_URL="https://ngrssolver08.comcentricapps.com"

echo "================================================================================"
echo "DOWNLOAD & CLEANUP WORKFLOW"
echo "================================================================================"
echo "Job ID: $JOB_ID"
echo "Output: $OUTPUT_FILE"
echo ""

# Step 1: Check job status
echo "Step 1: Checking job status..."
STATUS=$(curl -s "${API_URL}/solve/async/${JOB_ID}" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('status', 'unknown'))
except:
    print('error')
")

echo "Status: $STATUS"
echo ""

if [ "$STATUS" != "completed" ]; then
    echo "❌ Job is not completed yet (status: $STATUS)"
    echo "   Cannot download. Please wait for job to complete."
    exit 1
fi

# Step 2: Download result
echo "Step 2: Downloading result..."
curl -s "${API_URL}/solve/async/${JOB_ID}" -o "$OUTPUT_FILE"

if [ -f "$OUTPUT_FILE" ]; then
    FILE_SIZE=$(wc -c < "$OUTPUT_FILE" | tr -d ' ')
    echo "✓ Downloaded: $OUTPUT_FILE (${FILE_SIZE} bytes)"
else
    echo "❌ Download failed"
    exit 1
fi
echo ""

# Step 3: Delete from Redis to free memory
echo "Step 3: Cleaning up from memory..."
DELETE_RESPONSE=$(curl -s -X DELETE "${API_URL}/solve/async/${JOB_ID}")

echo "$DELETE_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'message' in data:
        print(f\"✓ {data['message']}\")
    else:
        print('✓ Deleted successfully')
except:
    print('⚠️  Cleanup response unclear')
"

echo ""
echo "================================================================================"
echo "✅ WORKFLOW COMPLETE"
echo "================================================================================"
echo "Result saved to: $OUTPUT_FILE"
echo "Memory freed for: $JOB_ID"
echo ""
