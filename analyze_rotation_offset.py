#!/usr/bin/env python3
"""Analyze rotation offset adherence in solver output."""
import json
from datetime import datetime, date
from collections import defaultdict

# Load input to get employees and their offsets
with open('input/RST-20260127-DBCCA45D_Solver_Input.json', 'r') as f:
    input_data = json.load(f)

# Load output
with open('input/RST-20260127-DBCCA45D_Solver_Output.json', 'r') as f:
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
emp_assignments = defaultdict(dict)
for a in output_data['assignments']:
    emp_id = a.get('employeeId')
    if not emp_id:
        continue
    shift_code = a.get('shiftCode')
    date_str = str(a.get('date', ''))[:10]  # Extract date only
    pattern_day = a.get('patternDay')
    
    emp_assignments[emp_id][date_str] = {'shift': shift_code, 'patternDay': pattern_day}

print(f"\nTotal employees with assignments: {len(emp_assignments)}")

# Analyze Feb 2026 patterns for each employee
print("\n" + "="*80)
print("ANALYZING PATTERN ADHERENCE FOR FEBRUARY 2026")
print("="*80)

start_date = date(2026, 2, 1)
coverage_anchor = start_date

total_mismatches = 0
for emp_id in sorted(emp_offsets.keys()):
    offset = emp_offsets[emp_id]
    print(f"\n{emp_id} (offset={offset}):")
    
    # Calculate expected pattern for each day
    expected_row = []
    actual_row = []
    
    for day in range(1, 29):  # Feb 1-28
        day_date = date(2026, 2, day)
        date_str = f"2026-02-{day:02d}"
        
        # Calculate which pattern day this should be
        days_from_anchor = (day_date - coverage_anchor).days
        expected_pattern_day = (days_from_anchor + offset) % len(work_pattern)
        expected_shift = work_pattern[expected_pattern_day]
        
        # Get actual assignment
        actual = emp_assignments.get(emp_id, {}).get(date_str, {})
        actual_shift = actual.get('shift', '-')
        actual_pattern_day = actual.get('patternDay')
        
        expected_row.append(expected_shift)
        actual_row.append(actual_shift)
    
    print(f"  Expected: {' '.join(expected_row)}")
    print(f"  Actual:   {' '.join(actual_row)}")
    
    # Check for mismatches
    mismatches = sum(1 for e, a in zip(expected_row, actual_row) if e != a and a != '-')
    if mismatches > 0:
        print(f"  ⚠️  {mismatches} mismatches found!")
        total_mismatches += mismatches

print(f"\n{'='*80}")
print(f"TOTAL MISMATCHES: {total_mismatches}")
print(f"{'='*80}")

# Now check pattern days with formula
print(f"\n{'='*80}")
print("CHECKING PATTERN DAY CALCULATION LOGIC")
print(f"{'='*80}")
print(f"\nFormula: pattern_day = (days_from_anchor + emp_offset) % pattern_length")
print(f"  pattern_length = {len(work_pattern)}")
print(f"  coverage_anchor = {coverage_anchor}")
print(f"\nSample calculation for Feb 1, 2026 (day 0):")
for emp_id in sorted(emp_offsets.keys())[:5]:
    offset = emp_offsets[emp_id]
    days_from_anchor = 0
    expected_pattern_day = (days_from_anchor + offset) % len(work_pattern)
    expected_shift = work_pattern[expected_pattern_day]
    print(f"  {emp_id}: (0 + {offset}) % {len(work_pattern)} = {expected_pattern_day} → {expected_shift}")
