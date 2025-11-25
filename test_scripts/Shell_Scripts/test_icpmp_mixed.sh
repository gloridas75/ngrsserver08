#!/bin/bash

echo "================================================================================"
echo "ICPMP TEST: Mixed ShiftTypes ['D','N'] with 50 headcount"
echo "================================================================================"
echo ""

curl -X POST "https://ngrssolver08.comcentricapps.com/configure" \
  -H "Content-Type: application/json" \
  -d @input/requirements_simple.json \
  -o output/icpmp_mixed_test.json \
  -w "HTTP Status: %{http_code}\nTime: %{time_total}s\n" \
  -s

echo ""
echo "Response saved to: output/icpmp_mixed_test.json"
echo ""
echo "================================================================================"
echo "ANALYSIS"
echo "================================================================================"

python3 << 'PYTHON_SCRIPT'
import json
from collections import defaultdict

with open('output/icpmp_mixed_test.json', 'r') as f:
    data = json.load(f)

print(f"Total Employees (best): {data['summary']['totalEmployees']}")
print(f"Requirement: {data['recommendations'][0]['requirementId']}")
print()

# Group by rank
alternatives = []
for rec in data['recommendations']:
    if rec['requirementId'] == 'REQ_APO_DAY':
        alternatives.append(rec)

print(f"Total Alternatives: {len(alternatives)}")
print()

# Analyze shift types
has_d_only = False
has_n_only = False
has_mixed = False

for i, alt in enumerate(alternatives, 1):
    pattern = alt['configuration']['workPattern']
    employees = alt['configuration']['employeesRequired']
    coverage = alt['coverage']['expectedCoverageRate']
    score = alt['configuration']['score']
    
    shifts = set(pattern) - {'O'}
    
    # Determine type
    if shifts == {'D'}:
        type_label = "D-only"
        has_d_only = True
    elif shifts == {'N'}:
        type_label = "N-only"
        has_n_only = True
    elif 'D' in shifts and 'N' in shifts:
        type_label = "Mixed D+N"
        has_mixed = True
    else:
        type_label = "Unknown"
    
    icon = "⭐" if i == 1 else f"{i}."
    print(f"{icon} Rank #{i}: {pattern}")
    print(f"   Type: {type_label} | {employees} employees | {coverage:.1f}% coverage | Score: {score:.2f}")

print()
print("===============================================================================")
print("VALIDATION: Mixed ShiftTypes Feature")
print("===============================================================================")
print(f"✅ Has D-only patterns: {has_d_only}" if has_d_only else "❌ No D-only patterns")
print(f"✅ Has N-only patterns: {has_n_only}" if has_n_only else "❌ No N-only patterns")
print(f"✅ Has mixed D+N patterns: {has_mixed}" if has_mixed else "❌ No mixed D+N patterns")

print()
if has_d_only and has_n_only and has_mixed:
    print("✅ MIXED SHIFTTYPES TEST PASSED!")
else:
    print("❌ MIXED SHIFTTYPES TEST FAILED")

# Check for large team
best = alternatives[0]
if best['configuration']['employeesRequired'] > 100:
    print(f"✅ Large team optimization: {best['configuration']['employeesRequired']} employees")
else:
    print(f"ℹ️  Team size: {best['configuration']['employeesRequired']} employees (under 100)")

PYTHON_SCRIPT
