#!/usr/bin/env python3
"""Check pattern adherence in solver output."""
import json
from datetime import date

# Load input
with open('input/RST-20260127-DBCCA45D_Solver_Input.json', 'r') as f:
    input_data = json.load(f)

# Load latest output 
with open('output/RST-20260127-DBCCA45D_Fixed.json', 'r') as f:
    output_data = json.load(f)

# Get work pattern
work_pattern = input_data['demandItems'][0]['requirements'][0]['workPattern']
print(f"Work Pattern: {work_pattern} (length={len(work_pattern)})")

# Get employee offsets from input
emp_offsets = {e['employeeId']: e['rotationOffset'] for e in input_data['employees']}
print(f"\nEmployee rotation offsets from input:")
for emp_id, offset in sorted(emp_offsets.items()):
    print(f"  {emp_id}: offset={offset}")

# Build assignments per employee per date
emp_assignments = {}
for a in output_data['assignments']:
    emp_id = a.get('employeeId')
    if not emp_id:
        continue
    shift_code = a.get('shiftCode')
    date_str = a.get('date', '')[:10]
    pattern_day = a.get('patternDay')
    
    if emp_id not in emp_assignments:
        emp_assignments[emp_id] = {}
    emp_assignments[emp_id][date_str] = {'shift': shift_code, 'patternDay': pattern_day}

# Analyze Feb 2026 patterns for each employee
print("\n" + "="*80)
print("ANALYZING PATTERN ADHERENCE FOR FEBRUARY 2026")
print("="*80)

start_date = date(2026, 2, 1)
coverage_anchor = start_date

total_mismatches = 0
for emp_id in sorted(emp_offsets.keys()):
    offset = emp_offsets[emp_id]
    
    expected_row = []
    actual_row = []
    
    for day in range(1, 29):
        day_date = date(2026, 2, day)
        date_str = f"2026-02-{day:02d}"
        
        days_from_anchor = (day_date - coverage_anchor).days
        expected_pattern_day = (days_from_anchor + offset) % len(work_pattern)
        expected_shift = work_pattern[expected_pattern_day]
        
        actual = emp_assignments.get(emp_id, {}).get(date_str, {})
        actual_shift = actual.get('shift', '-')
        
        expected_row.append(expected_shift)
        actual_row.append(actual_shift)
    
    mismatches = sum(1 for e, a in zip(expected_row, actual_row) if e != a and a != '-')
    
    print(f"\n{emp_id} (offset={offset}):")
    print(f"  Expected: {' '.join(expected_row)}")
    print(f"  Actual:   {' '.join(actual_row)}")
    if mismatches > 0:
        print(f"  ⚠️  {mismatches} MISMATCHES!")
        total_mismatches += mismatches
    else:
        print(f"  ✓ Pattern matches!")

print(f"\n{'='*80}")
print(f"TOTAL MISMATCHES: {total_mismatches}")
print(f"{'='*80}")
