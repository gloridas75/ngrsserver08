#!/usr/bin/env python3
"""Check expected work patterns for Mar 1-2."""
import json
from datetime import date, timedelta

f = open('/Users/glori/Downloads/RST-20260128-69B55E12_Solver_Input.json')
d = json.load(f)

# Get shift start date
demands = d.get('demandItems', [])
shift_start = demands[0].get('shiftStartDate', '')
print(f'shiftStartDate: {shift_start}')

# Pattern
reqs = demands[0].get('requirements', [])
pattern = reqs[0].get('workPattern', [])
print(f'Pattern: {pattern} (length: {len(pattern)})')

# Calculate work status for each employee on Mar 1-2
emps = d.get('employees', [])
base_date = date(2026, 3, 1)
shift_start_date = date.fromisoformat(shift_start[:10]) if shift_start else base_date

print(f'Shift start: {shift_start_date}')
print()
print('Work status for Mar 1-2:')

for e in emps:
    emp_id = e.get('employeeId')
    offset = e.get('rotationOffset', 0)
    
    for day_num in [1, 2]:
        check_date = date(2026, 3, day_num)
        days_from_start = (check_date - shift_start_date).days
        pattern_index = (days_from_start + offset) % len(pattern)
        status = pattern[pattern_index]
        print(f'  {emp_id} (offset {offset}): Mar {day_num} -> days={days_from_start}, idx={pattern_index} -> {status}')
