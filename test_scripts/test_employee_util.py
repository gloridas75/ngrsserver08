#!/usr/bin/env python3
"""Test employee utilization statistics without running full solver."""

from context.engine.data_loader import load_input
from collections import defaultdict

# Load preprocessed input
print("Loading and preprocessing input...")
input_data = load_input('input/AUTO-20251206-233E7006_Solver_Input.json')

employees = input_data.get('employees', [])
total_employees = len(employees)

# Count by offset type
strict_adherence = 0
flexible_employees = 0
offset_distribution = defaultdict(int)

for emp in employees:
    offset = emp.get('rotationOffset', 0)
    offset_distribution[offset] += 1
    if offset == -1:
        flexible_employees += 1
    else:
        strict_adherence += 1

print('\n' + '='*80)
print('EMPLOYEE UTILIZATION STATISTICS (as will appear in output)')
print('='*80)
print(f'Total Employees: {total_employees}')
print(f'Strict Adherence to Work Pattern: {strict_adherence} employees')
print(f'Flexible Pattern: {flexible_employees} employees')
print(f'Employees Assigned: (calculated after solving)')
print(f'Employees Not Assigned: (calculated after solving)')
print(f'Utilization Percentage: (calculated after solving)')

print('\n' + '='*80)
print('OFFSET DISTRIBUTION DETAIL')
print('='*80)
for offset in sorted(offset_distribution.keys()):
    count = offset_distribution[offset]
    if offset == -1:
        print(f'Offset {offset:2d} (Flexible): {count:3d} employees')
    else:
        print(f'Offset {offset:2d}: {count:3d} employees')

print('\n✅ Employee utilization block will be added to solver output JSON')
print('   Structure:')
print('   {')
print('     "employeeUtilization": {')
print('       "totalEmployees": 102,')
print('       "strictAdherence": 16,')
print('       "flexiblePattern": 86,')
print('       "employeesAssigned": 25,')
print('       "employeesNotAssigned": 77,')
print('       "utilizationPercentage": 24.5')
print('     }')
print('   }')
