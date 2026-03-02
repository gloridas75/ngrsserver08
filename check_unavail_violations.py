#!/usr/bin/env python3
"""Check for unavailability constraint violations in solver output."""

import json
import sys

def check_unavailability_violations(input_file, output_file):
    # Load both files
    with open(input_file) as f:
        input_data = json.load(f)

    with open(output_file) as f:
        output_data = json.load(f)

    print("\n=== UNAVAILABILITY CONSTRAINT VIOLATION CHECK ===\n")

    # Build unavailability map
    unavail_map = {}
    for emp in input_data['employees']:
        emp_id = emp['employeeId']
        unavail = set(emp.get('unavailability', []))
        unavail_map[emp_id] = unavail

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
        print("✅ No unavailability violations found!")
        print("All employees properly respect unavailability constraints.\n")
    else:
        print(f"\n🚨 CRITICAL: {total_violations} total unavailability constraint violations found!\n")

if __name__ == '__main__':
    input_file = 'input/RST-20260228-003BBFE2_Solver_Input.json'
    output_file = 'input/RST-20260228-003BBFE2_Solver_Output.json'
    check_unavailability_violations(input_file, output_file)
