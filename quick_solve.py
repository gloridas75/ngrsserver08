#!/usr/bin/env python3
"""Quick solver run with current input to generate analysis data."""

from context.engine.data_loader import load_input
from context.engine.solver_engine import solve
import json
from datetime import datetime

# Load and solve
print("\nLoading input and running solver...")
input_data = load_input('input/AUTO-20251206-233E7006_Solver_Input.json')
status_code, result, assignments, violations = solve(input_data)

# Print summary
print('\n' + '='*100)
print('SOLVER RESULTS WITH CORRECTED 5-DAY PATTERN')
print('='*100)
print(f'Status Code: {status_code}')
print(f'Status: {result["status"]}')
print(f'Overall Score: {result["scores"]["overall"]}')
print(f'Hard Score: {result["scores"]["hard"]}')
print(f'Soft Score: {result["scores"]["soft"]}')

unassigned = result['scoreBreakdown']['unassignedSlots']
print(f'\nTotal Slots: {unassigned["total"]}')
print(f'Assigned: {unassigned["total"] - unassigned["count"]} ({(1 - unassigned["count"]/unassigned["total"])*100:.1f}%)')
print(f'Unassigned: {unassigned["count"]} ({unassigned["count"]/unassigned["total"]*100:.1f}%)')

# Employee utilization
if 'employeeUtilization' in result:
    util = result['employeeUtilization']
    print(f'\n{"="*100}')
    print('EMPLOYEE UTILIZATION')
    print(f'{"="*100}')
    print(f'Total Employees: {util["totalEmployees"]}')
    print(f'Strict Adherence to Work Pattern: {util["strictAdherence"]} employees')
    print(f'Flexible Pattern: {util["flexiblePattern"]} employees')
    print(f'Employees Assigned: {util["employeesAssigned"]} ({util["utilizationPercentage"]:.1f}%)')
    print(f'Employees Not Assigned: {util["employeesNotAssigned"]}')

if unassigned["count"] > 0:
    print(f'\nUnassigned slots by date:')
    from collections import defaultdict
    by_date = defaultdict(int)
    for slot in unassigned.get("slots", []):
        by_date[slot["date"]] += 1
    for date in sorted(by_date.keys()):
        print(f'  {date}: {by_date[date]} slots')

# Build simple output dict
output_result = {
    "status": result["status"],
    "scores": result["scores"],
    "scoreBreakdown": result["scoreBreakdown"],
    "assignments": assignments,
    "duration_seconds": result["duration_seconds"]
}

# Save with timestamp
timestamp = datetime.now().strftime('%m%d_%H%M')
output_path = f'output/output_{timestamp}.json'
with open(output_path, 'w') as f:
    json.dump(output_result, f, indent=2)
print(f'\n✅ Saved to: {output_path}')
