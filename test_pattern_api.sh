#!/bin/bash
# Test /validate-pattern endpoint with curl
# Run against production server: https://ngrssolver09.comcentricapps.com

SERVER="${1:-https://ngrssolver09.comcentricapps.com}"

echo "========================================="
echo "PATTERN VALIDATION API TESTS"
echo "Server: $SERVER"
echo "========================================="
echo

# Test 1: Scheme P - Infeasible (6 work days)
echo "Test 1: Scheme P with 6 work days (DDDODDD) - Should be INFEASIBLE"
curl -s -X POST "$SERVER/validate-pattern" \
  -H "Content-Type: application/json" \
  -d '{
    "pattern": ["D", "D", "D", "O", "D", "D", "D"],
    "scheme": "P",
    "shiftDuration": 9.0
  }' | jq '{is_feasible, violation_type, work_days_per_cycle, scheme_max_days_per_week, error_message}'
echo
echo "---"
echo

# Test 2: Scheme P - Feasible (4 work days)
echo "Test 2: Scheme P with 4 work days (DDDDOOO) - Should be FEASIBLE"
curl -s -X POST "$SERVER/validate-pattern" \
  -H "Content-Type: application/json" \
  -d '{
    "pattern": ["D", "D", "D", "D", "O", "O", "O"],
    "scheme": "P",
    "shiftDuration": 9.0
  }' | jq '{is_feasible, work_days_per_cycle, scheme_max_days_per_week, validation_details}'
echo
echo "---"
echo

# Test 3: Scheme P - Infeasible (5 work days)
echo "Test 3: Scheme P with 5 work days (DDDDDOO) - Should be INFEASIBLE"
curl -s -X POST "$SERVER/validate-pattern" \
  -H "Content-Type: application/json" \
  -d '{
    "pattern": ["D", "D", "D", "D", "D", "O", "O"],
    "scheme": "P",
    "shiftDuration": 8.0
  }' | jq '{is_feasible, violation_type, suggested_patterns: .suggested_patterns[:2]}'
echo
echo "---"
echo

# Test 4: Scheme A - Feasible (6 work days)
echo "Test 4: Scheme A with 6 work days (DDDDDDO) - Should be FEASIBLE"
curl -s -X POST "$SERVER/validate-pattern" \
  -H "Content-Type: application/json" \
  -d '{
    "pattern": ["D", "D", "D", "D", "D", "D", "O"],
    "scheme": "A",
    "shiftDuration": 12.0
  }' | jq '{is_feasible, work_days_per_cycle, scheme_max_days_per_week}'
echo
echo "---"
echo

# Test 5: Scheme A - Infeasible (7 work days)
echo "Test 5: Scheme A with 7 work days (DDDDDDD) - Should be INFEASIBLE"
curl -s -X POST "$SERVER/validate-pattern" \
  -H "Content-Type: application/json" \
  -d '{
    "pattern": ["D", "D", "D", "D", "D", "D", "D"],
    "scheme": "A",
    "shiftDuration": 12.0
  }' | jq '{is_feasible, violation_type, error_message}'
echo
echo "---"
echo

# Test 6: Invalid scheme
echo "Test 6: Invalid scheme 'X' - Should return 400 error"
curl -s -X POST "$SERVER/validate-pattern" \
  -H "Content-Type: application/json" \
  -d '{
    "pattern": ["D", "D", "O", "O"],
    "scheme": "X"
  }' | jq '{detail}'
echo

echo "========================================="
echo "TESTS COMPLETE"
echo "========================================="
