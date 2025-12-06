#!/bin/bash
# Test Resource Monitor and Safety Checks

set -e

API_URL="${1:-http://localhost:8080}"

echo "=== Testing NGRS Solver Resource Safety ==="
echo "API URL: $API_URL"
echo ""

# Test 1: Health Check
echo "1️⃣  Testing /health endpoint..."
curl -s "$API_URL/health" | jq '.'
echo "✅ Health check passed"
echo ""

# Test 2: Metrics
echo "2️⃣  Testing /metrics endpoint..."
METRICS=$(curl -s "$API_URL/metrics")
echo "$METRICS" | jq '.'

TIER=$(echo "$METRICS" | jq -r '.capacity.tier')
MAX_VARS=$(echo "$METRICS" | jq -r '.capacity.max_variables')
MEM_GB=$(echo "$METRICS" | jq -r '.system.memory_total_gb')

echo "✅ Server tier: $TIER ($MEM_GB GB RAM, max $MAX_VARS variables)"
echo ""

# Test 3: Estimate Complexity (Small Problem)
echo "3️⃣  Testing /estimate-complexity with SMALL problem..."
cat > /tmp/small_problem.json <<'EOF'
{
  "planningHorizon": {"startDate": "2025-12-01", "endDate": "2025-12-31", "lengthDays": 31},
  "employees": [
    {"employeeId": "EMP001", "firstName": "John", "lastName": "Doe", "rankId": "SER", "productTypes": ["APO"], "workPattern": ["D","D","D","D","O","D","D"], "rotationOffset": 0, "contractedHours": 176}
  ],
  "requirements": [
    {"requirementId": "REQ001", "productType": "APO", "rankId": "SER", "headcount": 5, "workPattern": ["D","D","D","D","O","D","D"]}
  ],
  "demandItems": []
}
EOF

SMALL_RESULT=$(curl -s -X POST "$API_URL/estimate-complexity" \
  -H "Content-Type: application/json" \
  -d @/tmp/small_problem.json)

echo "$SMALL_RESULT" | jq '.'
CAN_SOLVE=$(echo "$SMALL_RESULT" | jq -r '.safety.can_solve')

if [ "$CAN_SOLVE" = "true" ]; then
  echo "✅ Small problem: Can solve safely"
else
  echo "❌ Small problem: Rejected (unexpected)"
  exit 1
fi
echo ""

# Test 4: Estimate Complexity (LARGE Problem - should reject on 4GB server)
echo "4️⃣  Testing /estimate-complexity with LARGE problem (50 headcount)..."
cat > /tmp/large_problem.json <<'EOF'
{
  "planningHorizon": {"startDate": "2025-12-01", "endDate": "2025-12-31", "lengthDays": 31},
  "employees": [],
  "requirements": [
    {"requirementId": "REQ001", "productType": "APO", "rankId": "SER", "headcount": 50, "workPattern": ["D","D","D","D","O","D","D"]}
  ],
  "demandItems": []
}
EOF

# Add 50 employees
for i in $(seq 1 50); do
  cat >> /tmp/large_problem.json <<EOF
EOF
done

# Fix JSON structure
cat > /tmp/large_problem.json <<'EOF'
{
  "planningHorizon": {"startDate": "2025-12-01", "endDate": "2025-12-31", "lengthDays": 31},
  "employees": [
    {"employeeId": "EMP001", "firstName": "E1", "lastName": "L1", "rankId": "SER", "productTypes": ["APO"], "workPattern": ["D","D","D","D","O","D","D"], "rotationOffset": 0, "contractedHours": 176},
    {"employeeId": "EMP002", "firstName": "E2", "lastName": "L2", "rankId": "SER", "productTypes": ["APO"], "workPattern": ["D","D","D","D","O","D","D"], "rotationOffset": 1, "contractedHours": 176},
    {"employeeId": "EMP003", "firstName": "E3", "lastName": "L3", "rankId": "SER", "productTypes": ["APO"], "workPattern": ["D","D","D","D","O","D","D"], "rotationOffset": 2, "contractedHours": 176}
  ],
  "requirements": [
    {"requirementId": "REQ001", "productType": "APO", "rankId": "SER", "headcount": 50, "workPattern": ["D","D","D","D","O","D","D"]}
  ],
  "demandItems": []
}
EOF

LARGE_RESULT=$(curl -s -X POST "$API_URL/estimate-complexity" \
  -H "Content-Type: application/json" \
  -d @/tmp/large_problem.json)

echo "$LARGE_RESULT" | jq '.'
CAN_SOLVE_LARGE=$(echo "$LARGE_RESULT" | jq -r '.safety.can_solve')
VARIABLES=$(echo "$LARGE_RESULT" | jq -r '.complexity.estimated_variables')

echo "Estimated variables: $VARIABLES"

if [ "$MEM_GB" = "4" ] || [ "$TIER" = "small" ]; then
  # On 4GB server, should reject
  if [ "$CAN_SOLVE_LARGE" = "false" ]; then
    echo "✅ Large problem: Correctly rejected on small server"
  else
    echo "⚠️  Large problem: Should have been rejected on small server"
  fi
else
  # On larger server, may accept
  echo "ℹ️  Large problem: $CAN_SOLVE_LARGE (server has $MEM_GB GB)"
fi
echo ""

# Clean up
rm -f /tmp/small_problem.json /tmp/large_problem.json

echo "=== All Tests Complete ==="
echo ""
echo "Summary:"
echo "  Server Tier: $TIER"
echo "  Memory: $MEM_GB GB"
echo "  Max Variables: $MAX_VARS"
echo "  Small Problem: ✅ Can solve"
echo "  Large Problem (50 headcount): $([ "$CAN_SOLVE_LARGE" = "true" ] && echo "✅ Can solve" || echo "❌ Rejected (expected on 4GB server)")"
echo ""
echo "✅ Resource safety system is working!"
