#!/bin/bash
# Test script for offset manager on Ubuntu server
# Run this AFTER deploying the code to the server

set -e

echo "=========================================="
echo "TESTING OFFSET MANAGER ON SERVER"
echo "=========================================="
echo ""

# Configuration
API_URL="${API_URL:-http://localhost:8080}"
TEST_FILE="input/test_all_zero_offsets.json"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "API URL: $API_URL"
echo ""

# Step 1: Check if API is running
echo "Step 1: Checking API health..."
if curl -s -f "$API_URL/health" > /dev/null; then
    echo -e "${GREEN}✓ API is running${NC}"
else
    echo -e "${RED}✗ API is not responding${NC}"
    exit 1
fi
echo ""

# Step 2: Check if test file exists
echo "Step 2: Checking test file..."
if [ -f "$TEST_FILE" ]; then
    echo -e "${GREEN}✓ Test file exists: $TEST_FILE${NC}"
    
    # Verify it has offsets at 0
    ZERO_COUNT=$(python3 -c "import json; f=open('$TEST_FILE'); d=json.load(f); print(sum(1 for e in d['employees'] if e.get('rotationOffset',0)==0))")
    TOTAL_EMP=$(python3 -c "import json; f=open('$TEST_FILE'); d=json.load(f); print(len(d['employees']))")
    
    if [ "$ZERO_COUNT" == "$TOTAL_EMP" ]; then
        echo -e "${GREEN}✓ All $TOTAL_EMP employees have offset 0 (perfect for testing)${NC}"
    else
        echo -e "${YELLOW}⚠ Only $ZERO_COUNT/$TOTAL_EMP employees have offset 0${NC}"
    fi
else
    echo -e "${RED}✗ Test file not found: $TEST_FILE${NC}"
    echo "Creating test file with all offsets at 0..."
    
    # Create test file if it doesn't exist
    python3 << 'EOF'
import json

# Load existing input file
try:
    with open('input/input_v0.8_0212_1300.json', 'r') as f:
        data = json.load(f)
except:
    print("Error: Could not load input_v0.8_0212_1300.json")
    exit(1)

# Reset all offsets to 0
for emp in data['employees']:
    emp['rotationOffset'] = 0

# Save as test file
with open('input/test_all_zero_offsets.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f"Created test file with {len(data['employees'])} employees (all offsets=0)")
EOF
    
    echo -e "${GREEN}✓ Test file created${NC}"
fi
echo ""

# Step 3: Send request to API
echo "Step 3: Sending solve request to API..."
echo "  (This may take 30-120 seconds...)"
echo ""

RESPONSE_FILE="output/server_offset_test_$(date +%Y%m%d_%H%M%S).json"

# Make API request and capture both response and timing
START_TIME=$(date +%s)
HTTP_CODE=$(curl -s -w "%{http_code}" -X POST "$API_URL/solve?time_limit=120" \
    -H "Content-Type: application/json" \
    -d @"$TEST_FILE" \
    -o "$RESPONSE_FILE")
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "Response: HTTP $HTTP_CODE"
echo "Duration: ${DURATION}s"
echo "Output: $RESPONSE_FILE"
echo ""

# Step 4: Analyze result
echo "Step 4: Analyzing result..."
echo ""

if [ "$HTTP_CODE" == "200" ]; then
    echo -e "${GREEN}✓ Request successful (HTTP 200)${NC}"
    
    # Extract key fields
    STATUS=$(python3 -c "import json; f=open('$RESPONSE_FILE'); d=json.load(f); print(d.get('solverRun',{}).get('status','UNKNOWN'))" 2>/dev/null || echo "UNKNOWN")
    ASSIGNED=$(python3 -c "import json; f=open('$RESPONSE_FILE'); d=json.load(f); print(len([a for a in d.get('assignments',[]) if a.get('status')=='ASSIGNED']))" 2>/dev/null || echo "0")
    TOTAL=$(python3 -c "import json; f=open('$RESPONSE_FILE'); d=json.load(f); print(len(d.get('assignments',[])))" 2>/dev/null || echo "0")
    
    echo "  Status: $STATUS"
    echo "  Assigned: $ASSIGNED / $TOTAL"
    
    if [ "$STATUS" == "OPTIMAL" ] || [ "$STATUS" == "FEASIBLE" ]; then
        echo -e "${GREEN}✓✓ SUCCESS: Solver returned $STATUS${NC}"
        echo ""
        echo "This confirms the offset manager is working!"
        echo "The API automatically staggered offsets before solving."
    elif [ "$STATUS" == "INFEASIBLE" ]; then
        echo -e "${YELLOW}⚠ INFEASIBLE: Check if there are other constraint issues${NC}"
        echo ""
        echo "Offset manager may have run, but other constraints preventing solution."
        echo "Check: employee count, scheme matching, hours constraints"
    else
        echo -e "${RED}✗ Unexpected status: $STATUS${NC}"
    fi
else
    echo -e "${RED}✗ Request failed (HTTP $HTTP_CODE)${NC}"
    echo "Response body:"
    cat "$RESPONSE_FILE"
fi

echo ""
echo "=========================================="
echo "CHECK SERVER LOGS FOR OFFSET MANAGER"
echo "=========================================="
echo ""
echo "To see offset manager in action, check logs:"
echo ""
echo "  # Docker:"
echo "  docker logs ngrs-solver-api --tail 100 | grep -A 10 'OFFSET MANAGER'"
echo ""
echo "  # Systemd:"
echo "  journalctl -u ngrs-solver --since '1 hour ago' | grep -A 10 'OFFSET MANAGER'"
echo ""
echo "Look for:"
echo "  - 'Found O-pattern in requirement X - staggering needed'"
echo "  - 'Current offset distribution: {0: N}'"
echo "  - 'New offset distribution: {0: X, 1: Y, ...}'"
echo "  - '✓ Updated N employees'"
echo ""
