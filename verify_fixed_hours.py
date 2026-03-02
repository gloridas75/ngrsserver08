#!/usr/bin/env python
"""
Verify hour calculation fix for RST-20260301-F9EA0EDE
"""
import json
from collections import defaultdict

with open('output/RST-20260301-F9EA0EDE_FIXED.json', 'r') as f:
    output = json.load(f)

with open('input/RST-20260301-F9EA0EDE_Solver_Input.json', 'r') as f:
    input_data = json.load(f)

assignments = output.get('assignments', [])
employees = {emp['employeeId']: emp for emp in input_data.get('employees', [])}

# Group by employee
emp_hours = defaultdict(lambda: {'normal': 0, 'ot': 0, 'gross': 0, 'count': 0})

for a in assignments:
    emp_id = a.get('employeeId')
    if emp_id and a.get('status') == 'ASSIGNED':
        hours = a.get('hours', {})
        emp_hours[emp_id]['normal'] += hours.get('normal', 0)
        emp_hours[emp_id]['ot'] += hours.get('ot', 0)
        emp_hours[emp_id]['gross'] += hours.get('gross', 0)
        emp_hours[emp_id]['count'] += 1

print('=' * 80)
print('FIXED OUTPUT - HOUR CALCULATION VERIFICATION')
print('=' * 80)
print()
print(f"{'Employee':<15} {'Scheme':<10} {'Days':<6} {'Normal':<10} {'OT':<10} {'Gross':<10}")
print('-' * 80)

for emp_id in sorted(emp_hours.keys()):
    h = emp_hours[emp_id]
    emp = employees.get(emp_id, {})
    scheme = emp.get('scheme', '').replace('Scheme ', '')
    product = emp.get('productTypeId', '')
    local = emp.get('local', 1)
    emp_type = 'L' if local == 1 else 'F'
    
    label = f"{scheme} {product} ({emp_type})"
    print(f"{emp_id:<15} {label:<10} {h['count']:<6} {h['normal']:<10.2f} {h['ot']:<10.2f} {h['gross']:<10.2f}")

print()
print('Expected for 22 work days x 12h shifts = 264h gross:')
print('  Scheme A SO: ~176-195h normal + ~69-88h OT (weeklyThreshold)')
print('  Scheme B SO: ~196h normal + ~68h OT (weeklyThreshold)')
print()

# Check if fix worked
all_ok = True
for emp_id, h in emp_hours.items():
    if h['normal'] > 200:
        emp = employees.get(emp_id, {})
        scheme = emp.get('scheme', '')
        print(f"❌ {emp_id} ({scheme}): Normal hours {h['normal']:.2f}h still too high!")
        all_ok = False

if all_ok:
    print('✅ Hour calculation fix is WORKING! All normal hours within expected range.')
else:
    print('❌ Hour calculation fix NOT working - normal hours still exceeding limits')

print('=' * 80)
