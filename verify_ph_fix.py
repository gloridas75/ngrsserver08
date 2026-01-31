#!/usr/bin/env python
"""Verify the PUBLIC_HOLIDAY fix for March 21, 2026."""

import json

# Load input to get offsets
with open('input/RST-20260130-5B7971B2_Solver_Input.json') as f:
    input_data = json.load(f)

# Load output
with open('output/output_3001_1832.json') as f:
    output = json.load(f)

# Get offset for each employee from input
emp_offsets = {}
for emp in input_data.get('employees', []):
    emp_offsets[emp['employeeId']] = emp.get('rotationOffset', 0)

# Check March 21 status with offset info
print('=== March 21 Status with Offset Analysis ===')
work_pattern = ['D', 'D', 'N', 'N', 'O', 'O']

all_match = True
for emp in output.get('employeeRoster', []):
    emp_id = emp.get('employeeId')
    offset = emp_offsets.get(emp_id, 0)
    # Calculate pattern day for March 21 (day 20 from March 1)
    pattern_idx = (offset + 20) % 6
    pattern_day = work_pattern[pattern_idx]
    
    for ds in emp.get('dailyStatus', []):
        if ds.get('date') == '2026-03-21':
            status = ds.get('status')
            if pattern_day == 'O':
                expected = 'OFF_DAY'
            else:
                expected = 'PUBLIC_HOLIDAY'
            
            if status == expected:
                match_str = 'OK'
            else:
                match_str = 'MISMATCH'
                all_match = False
            
            print(f'{emp_id}: offset={offset}, pattern_day={pattern_day} -> status={status} (expected={expected}) {match_str}')
            break

print()
if all_match:
    print('SUCCESS: All employees have correct status on March 21 (PH date)')
else:
    print('FAILURE: Some employees have incorrect status')
