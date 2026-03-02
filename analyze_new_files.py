#!/usr/bin/env python3
"""Check new files for unavailability violations."""

import json

# Load both files
with open('input/RST-20260228-E13007DE_Solver_Input.json') as f:
    input_data = json.load(f)

with open('input/RST-20260228-E13007DE_Solver_Output.json') as f:
    output_data = json.load(f)

print("\n=== CHECKING RST-20260228-E13007DE FOR UNAVAILABILITY VIOLATIONS ===\n")

# Build unavailability map
unavail_map = {}
for emp in input_data['employees']:
    emp_id = emp['employeeId']
    unavail = set(emp.get('unavailability', []))
    unavail_map[emp_id] = unavail

# Check solver metadata
print("Solver Run Info:")
print(f"  Version: {output_data['solverRun']['solverVersion']}")
print(f"  Duration: {output_data['solverRun']['durationSeconds']} seconds")
print(f"  Status: {output_data['solverRun']['status']}")
print()

# Check each employee's assignments
violations_found = False
total_violations = 0

for emp in input_data['employees']:
    emp_id = emp['employeeId']
    unavail_dates = unavail_map[emp_id]
    
    if not unavail_dates:
        continue
    
    # Get assignments for this employee
    emp_assignments = [a for a in output_data['assignments'] if a['employeeId'] == emp_id]
    assigned_dates = set(a['date'] for a in emp_assignments)
    
    # Check for violations
    violations = unavail_dates & assigned_dates
    
    if violations:
        violations_found = True
        total_violations += len(violations)
        print(f"Employee {emp_id}:")
        print(f"  Product: {emp['productTypeId']}, Scheme: {emp['scheme']}")
        print(f"  Total unavailable days: {len(unavail_dates)}")
        print(f"  Total assigned days: {len(assigned_dates)}")
        print(f"  VIOLATIONS: {len(violations)} assignments on unavailable days")
        violation_list = sorted(list(violations))
        if len(violations) <= 10:
            print(f"  Violation dates: {violation_list}")
        else:
            print(f"  Violation dates: {violation_list[:5]} ... {violation_list[-3:]}")
        print()

if not violations_found:
    print("✅ NO UNAVAILABILITY VIOLATIONS!")
    print("All employees properly respect unavailability constraints.")
    print()
else:
    print(f"\n🚨 CRITICAL: {total_violations} total unavailability violations found!")
    print()

# Check input configuration
print("Input Configuration:")
di = input_data['demandItems'][0]
print(f"  rosteringBasis: {di.get('rosteringBasis')}")
print(f"  templateGenerationMode: {di.get('templateGenerationMode')}")
for req in di['requirements']:
    print(f"  Requirement {req['requirementId']}:")
    print(f"    headcount: {req['headcount']}")
    print(f"    productType: {req['productTypeId']}")
