#!/usr/bin/env python3
import json

# Check the new output
with open('/tmp/test_FIXED.json') as f:
    output = json.load(f)

with open('input/RST-20260228-003BBFE2_Solver_Input.json') as f:
    inp = json.load(f)

# Build unavailability map
unavail_map = {}
for emp in inp['employees']:
    emp_id = emp['employeeId']
    unavail = set(emp.get('unavailability', []))
    if unavail:
        unavail_map[emp_id] = unavail

# Check violations
print("Checking for violations...")
violations_found = 0
for emp_id, unavail_dates in unavail_map.items():
    emp_assignments = [a for a in output['assignments'] if a.get('employeeId') == emp_id]
    assigned_dates = set(a['date'] for a in emp_assignments)
    violations = unavail_dates & assigned_dates
    
    if violations:
        violations_found += len(violations)
        print(f"  Employee {emp_id}: {len(violations)} violations")

if violations_found == 0:
    print("\n✅ NO UNAVAILABILITY VIOLATIONS! Fix worked!")
else:
    print(f"\n🚨 Still has {violations_found} violations - fix didnt work")
