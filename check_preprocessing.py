#!/usr/bin/env python3
"""Check if preprocessing is actually applying offsets correctly."""

from context.engine.data_loader import load_input
from collections import defaultdict

# Load input (with preprocessing)
print("Loading input...")
input_data = load_input('input/AUTO-20251206-233E7006_Solver_Input.json')

# Check employee offsets
print('\n' + '='*100)
print('EMPLOYEE OFFSET DISTRIBUTION AFTER PREPROCESSING')
print('='*100)

offset_counts = defaultdict(int)
for emp in input_data['employees']:
    offset = emp.get('rotationOffset', 0)
    offset_counts[offset] += 1

for offset in sorted(offset_counts.keys()):
    print(f'Offset {offset:2d}: {offset_counts[offset]:3d} employees')

print(f'\nTotal: {len(input_data["employees"])} employees')
print(f'Flexible (offset=-1): {offset_counts.get(-1, 0)} employees ({offset_counts.get(-1, 0)/len(input_data["employees"])*100:.1f}%)')
print(f'Pattern-following: {len(input_data["employees"]) - offset_counts.get(-1, 0)} employees')

# Analyze the 5-day pattern specifically
pattern_1_offsets = defaultdict(list)
for emp in input_data['employees']:
    offset = emp.get('rotationOffset', 0)
    pattern_group = emp.get('_pattern_group')
    if pattern_group and "['D', 'D', 'D', 'O', 'O']" in str(pattern_group):
        pattern_1_offsets[offset].append(emp['employeeId'])

if pattern_1_offsets:
    print(f'\n' + '='*100)
    print('PATTERN 1 (Mon-Fri): [\'D\',\'D\',\'D\',\'O\',\'O\'] - OFFSET ANALYSIS')
    print('='*100)
    print('Pattern cycle: 5 days (Mon-Fri)')
    print('Day 0 (Mon): D')
    print('Day 1 (Tue): D')
    print('Day 2 (Wed): D')
    print('Day 3 (Thu): O')
    print('Day 4 (Fri): O')
    print()
    
    for offset in sorted(pattern_1_offsets.keys()):
        emp_ids = pattern_1_offsets[offset]
        print(f'Offset {offset}: {len(emp_ids)} employees')
        
        # Calculate which days these employees REST
        rest_day_1 = (3 - offset) % 5  # First O day
        rest_day_2 = (4 - offset) % 5  # Second O day
        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
        
        if offset >= 0:
            print(f'  Rest on: {day_names[rest_day_1]} and {day_names[rest_day_2]}')
            print(f'  Employee IDs: {", ".join(emp_ids[:5])}{"..." if len(emp_ids) > 5 else ""}')
        else:
            print(f'  Flexible - can work any day')

print(f'\n' + '='*100)
print('EXPECTED FRIDAY COVERAGE')
print('='*100)
print('Pattern 1 employees who REST on Friday (offset where Friday=O):')
print('  Offset -1: Flexible (can work Friday)')
print('  Offset 0: REST on Thu+Fri (NOT available Friday)')
print('  Offset 1: REST on Wed+Thu (available Friday)')
print('  Offset 2: REST on Tue+Wed (available Friday)')
print('  Offset 3: REST on Mon+Tue (available Friday)')
print('  Offset 4: REST on Fri+Mon (NOT available Friday)')
print()
print(f'Employees with offset=0: {offset_counts[0]} (NOT available Friday)')
print(f'Employees with offset=4: {offset_counts[4]} (NOT available Friday)')
print(f'Employees available for Friday: ~{len(input_data["employees"]) - offset_counts[0] - offset_counts[4]}')
