#!/bin/bash

# Admin Reset Script for NGRS Solver
# This script performs a complete system reset: flush Redis + restart workers

API_URL="https://ngrssolver08.comcentricapps.com"
API_KEY="${ADMIN_API_KEY:-change-me-in-production}"

echo "================================================================================"
echo "ADMIN SYSTEM RESET"
echo "================================================================================"
echo ""
echo "⚠️  WARNING: This will delete ALL jobs and results from Redis!"
echo "⚠️  WARNING: All worker processes will be restarted!"
echo ""

# Check if API key is set
if [ "$API_KEY" = "change-me-in-production" ]; then
    echo "❌ ERROR: ADMIN_API_KEY environment variable not set"
    echo ""
    echo "Usage:"
    echo "  export ADMIN_API_KEY='your-secret-key'"
    echo "  ./admin_reset.sh"
    echo ""
    echo "Or:"
    echo "  ADMIN_API_KEY='your-secret-key' ./admin_reset.sh"
    echo ""
    exit 1
fi

# Confirmation prompt
read -p "Are you sure you want to reset the system? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Reset cancelled."
    exit 0
fi

echo ""
echo "Sending reset request..."
echo ""

# Call admin reset endpoint
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -X POST "${API_URL}/admin/reset" \
  -H "x-api-key: ${API_KEY}" \
  -H "Content-Type: application/json")

# Extract HTTP status and body
HTTP_BODY=$(echo "$RESPONSE" | sed -e 's/HTTP_STATUS\:.*//g')
HTTP_STATUS=$(echo "$RESPONSE" | tr -d '\n' | sed -e 's/.*HTTP_STATUS://')

echo "HTTP Status: $HTTP_STATUS"
echo ""

# Parse response
echo "$HTTP_BODY" | python3 << 'PYTHON_SCRIPT'
import sys
import json

try:
    data = json.load(sys.stdin)
    
    if data.get('status') == 'success':
        print("✅ RESET SUCCESSFUL")
        print("=" * 80)
        print(f"Message: {data.get('message')}")
        print(f"Timestamp: {data.get('timestamp')}")
        print()
        
        print("Actions Performed:")
        for action in data.get('actions', []):
            print(f"  • {action}")
        
        print()
        print("Current System Stats:")
        stats = data.get('current_stats', {})
        print(f"  Total Jobs:        {stats.get('total_jobs', 0)}")
        print(f"  Active Jobs:       {stats.get('active_jobs', 0)}")
        print(f"  Queue Length:      {stats.get('queue_length', 0)}")
        print(f"  Results Cached:    {stats.get('results_cached', 0)}")
        print(f"  Workers:           {stats.get('workers', 0)}")
        print(f"  Redis Connected:   {stats.get('redis_connected', False)}")
        
    else:
        print("❌ RESET FAILED")
        print("=" * 80)
        print(f"Error: {data.get('detail', 'Unknown error')}")

except json.JSONDecodeError:
    print("❌ Invalid response from server")
except Exception as e:
    print(f"❌ Error: {e}")

PYTHON_SCRIPT

echo ""
echo "================================================================================"
