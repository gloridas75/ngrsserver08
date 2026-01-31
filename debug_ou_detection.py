#!/usr/bin/env python3
"""Check if single OU detection is working."""
import json

with open('output/RST-20260127-838E64D9_Solver_Input.json', 'r') as f:
    input_data = json.load(f)

employees = input_data.get('employees', [])

print("=== OU ANALYSIS ===")
unique_ous = set(emp.get('ouId') for emp in employees)
print(f"Unique OUs: {unique_ous}")
print(f"Is single OU: {len(unique_ous) == 1}")

print("\n=== ROTATION OFFSET ANALYSIS ===")
employee_offsets = [emp.get('rotationOffset') for emp in employees]
unique_offsets = set(employee_offsets)
print(f"Unique offsets: {sorted(unique_offsets)}")
print(f"Has individual offsets (varied): {len(unique_offsets) > 1}")
print(f"Employee count: {len(employees)}")
print(f"Is ≤50 employees: {len(employees) <= 50}")

print("\n=== MODE SWITCHING DECISION ===")
is_single_ou = len(unique_ous) == 1
has_individual_offsets = len(unique_offsets) > 1
should_switch = is_single_ou and has_individual_offsets and len(employees) <= 50

if should_switch:
    print("✅ SHOULD SWITCH to demandBased mode!")
else:
    print("❌ Will stay in outcomeBased mode")
    if not is_single_ou:
        print("  Reason: Multiple OUs detected")
    if not has_individual_offsets:
        print("  Reason: All employees have same offset")
    if len(employees) > 50:
        print("  Reason: Too many employees (>50)")

print("\n=== INPUT rosteringBasis ===")
demand = input_data.get('demandItems', [{}])[0]
print(f"rosteringBasis in input: {demand.get('rosteringBasis')}")

# Check offset values
print("\n=== ALL EMPLOYEE OFFSETS ===")
for emp in employees:
    print(f"  {emp.get('employeeId')}: rotationOffset = {emp.get('rotationOffset')}")
