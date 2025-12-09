#!/bin/bash
#
# Test ICPMP v2 on Production Server
# Usage: ./test_production_icpmp.sh
#

# Configuration
API_URL="https://ngrssolver09.comcentricapps.com"
INPUT_FILE="output/icpmp_v2_test2.json"
OUTPUT_FILE="output/icpmp_v2_test2_production_result.json"

echo "=========================================="
echo "ICPMP v2 Production API Test"
echo "=========================================="
echo ""
echo "API URL: $API_URL"
echo "Input File: $INPUT_FILE"
echo ""

# Check if input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "❌ ERROR: Input file not found: $INPUT_FILE"
    exit 1
fi

echo "✓ Input file found"
echo ""

# Test 1: Health Check
echo "Test 1: Health Check"
echo "--------------------"
HEALTH_RESPONSE=$(curl -s "$API_URL/health")
echo "Response: $HEALTH_RESPONSE"

if [[ "$HEALTH_RESPONSE" == *"ok"* ]]; then
    echo "✓ Health check passed"
else
    echo "❌ Health check failed"
    exit 1
fi
echo ""

# Test 2: Version Check
echo "Test 2: Version Check"
echo "--------------------"
VERSION_RESPONSE=$(curl -s "$API_URL/version")
echo "$VERSION_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$VERSION_RESPONSE"

if [[ "$VERSION_RESPONSE" == *"0.96.0"* ]] && [[ "$VERSION_RESPONSE" == *"2.0"* ]]; then
    echo "✓ Version check passed (v0.96.0 with ICPMP v2.0)"
else
    echo "⚠️  Warning: API version may not be updated yet"
fi
echo ""

# Test 3: ICPMP v2 Configuration Optimizer
echo "Test 3: ICPMP v2 Configuration Optimizer"
echo "----------------------------------------"
echo "Sending request to /configure endpoint..."
echo ""

RESPONSE=$(curl -s -X POST "$API_URL/configure" \
    -H "Content-Type: application/json" \
    -d @"$INPUT_FILE")

# Check if response is valid JSON
if echo "$RESPONSE" | python3 -m json.tool > /dev/null 2>&1; then
    echo "✓ Received valid JSON response"
    
    # Save response to file
    echo "$RESPONSE" | python3 -m json.tool > "$OUTPUT_FILE"
    echo "✓ Response saved to: $OUTPUT_FILE"
    echo ""
    
    # Parse and display summary
    echo "=========================================="
    echo "RESULTS SUMMARY"
    echo "=========================================="
    echo ""
    
    TOTAL_EMPLOYEES=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('summary', {}).get('totalEmployees', 'N/A'))" 2>/dev/null)
    OPTIMIZER_VERSION=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('summary', {}).get('optimizerVersion', 'N/A'))" 2>/dev/null)
    TOTAL_REQS=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('summary', {}).get('totalRequirements', 'N/A'))" 2>/dev/null)
    
    echo "Optimizer Version: $OPTIMIZER_VERSION"
    echo "Total Requirements: $TOTAL_REQS"
    echo "Total Employees Needed: $TOTAL_EMPLOYEES"
    echo ""
    
    # Display top recommendation
    echo "TOP RECOMMENDATION:"
    echo ""
    BEST_PATTERN=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); rec=data.get('recommendations', [])[0] if data.get('recommendations') else {}; print(' '.join(rec.get('configuration', {}).get('workPattern', [])))" 2>/dev/null)
    BEST_EMP=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); rec=data.get('recommendations', [])[0] if data.get('recommendations') else {}; print(rec.get('configuration', {}).get('employeesRequired', 'N/A'))" 2>/dev/null)
    BEST_SCORE=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); rec=data.get('recommendations', [])[0] if data.get('recommendations') else {}; print(rec.get('quality', {}).get('score', 'N/A'))" 2>/dev/null)
    
    echo "  Pattern: $BEST_PATTERN"
    echo "  Employees: $BEST_EMP"
    echo "  Quality Score: $BEST_SCORE"
    echo ""
    
    echo "=========================================="
    echo "✅ ICPMP v2 test completed successfully!"
    echo "=========================================="
    echo ""
    echo "Full results saved to: $OUTPUT_FILE"
    
else
    echo "❌ ERROR: Invalid response received"
    echo ""
    echo "Response:"
    echo "$RESPONSE"
    exit 1
fi
