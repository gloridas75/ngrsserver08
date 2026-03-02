#!/usr/bin/env python3
"""Check OT hours for employees to verify 72h limit."""
import json
import sys

output_file = '/tmp/test_739D3553.json'
input_file = 'input/RST-20260301-739D3553_Solver_Input.json'

with open(output_file, 'r') as f:
    output = json.load(f)

with open(input_file, 'r') as f:
    input_data = json.load(f)

# Get employee details
employees = {emp['employeeId']: emp for emp in input_data['employees']}

# Calculate OT hours per employee
employee_hours = {}
for asg in output['assignments']:
    emp_id = asg.get('employeeId')
    if not emp_id or asg.get('status') != 'ASSIGNED':
        continue
    
    if emp_id not in employee_hours:
        employee_hours[emp_id] = {
            'normal': 0.0,
            'ot': 0.0,
            'ph': 0.0,
            'total': 0.0
        }
    
    hours = asg.get('hours', {})
    employee_hours[emp_id]['normal'] += hours.get('normal', 0.0)
    employee_hours[emp_id]['ot'] += hours.get('ot', 0.0)
    employee_hours[emp_id]['ph'] += hours.get('publicHolidayHours', 0.0)
    employee_hours[emp_id]['total'] += hours.get('gross', 0.0)

print("\nEmployee Hour Summary:")
print("=" * 100)
for emp_id in sorted(employee_hours.keys()):
    hours = employee_hours[emp_id]
    emp = employees[emp_id]
    scheme = emp['scheme']
    product = emp['productTypeId']
    rank = emp['rankId']
    local = emp['local']
    
    print(f"\n{emp_id} ({scheme}, {product}, {rank}, {'Local' if local else 'Foreigner'}):")
    print(f"  Normal Hours:  {hours['normal']:.1f}h")
    ot_warning = ' *** EXCEEDS 72h' if hours['ot'] > 72 else ''
    print(f"  OT Hours:      {hours['ot']:.1f}h{ot_warning}")
    print(f"  PH Hours:      {hours['ph']:.1f}h")
    print(f"  Total Hours:   {hours['total']:.1f}h")

# Check Scheme A SO employees specifically
print("\n\nScheme A SO Employees (should be limited to 72h OT):")
print("=" * 100)
violations = []
for emp_id in sorted(employee_hours.keys()):
    hours = employee_hours[emp_id]
    emp = employees[emp_id]
    if emp['scheme'] == 'Scheme A' and emp['productTypeId'] == 'SO':
        local_str = 'Local' if emp['local'] else 'Foreigner'
        print(f"{emp_id} ({emp['rankId']}, {local_str}): OT = {hours['ot']:.1f}h")
        if hours['ot'] > 72:
            violation = f"  *** VIOLATION: Exceeds 72h limit by {hours['ot'] - 72:.1f}h"
            print(violation)
            violations.append((emp_id, hours['ot']))

if violations:
    print(f"\n!!! Found {len(violations)} OT violations for Scheme A SO employees !!!")
    sys.exit(1)
else:
    print("\nNo OT violations found.")
    sys.exit(0)
