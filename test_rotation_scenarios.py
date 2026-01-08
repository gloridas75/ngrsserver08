#!/usr/bin/env python3
"""
Test rotation offset scenarios:
1. All employees same offset
2. Some employees share offsets
3. All employees offset=0
"""

import json
import subprocess
from collections import defaultdict

def load_base_input():
    with open('/Users/glori/Downloads/RST-20260108-29F82395_Solver_Input.json', 'r') as f:
        return json.load(f)

def run_test(test_name, offsets):
    print(f"\n{'='*70}")
    print(f"TEST: {test_name}")
    print(f"Offsets: {offsets}")
    print(f"{'='*70}")
    
    # Create test input with specified offsets
    input_data = load_base_input()
    for i, offset in enumerate(offsets):
        if i < len(input_data['employees']):
            input_data['employees'][i]['rotationOffset'] = offset
    
    # Write test input
    test_input_path = f'output/test_rotation_{test_name.replace(" ", "_").lower()}.json'
    with open(test_input_path, 'w') as f:
        json.dump(input_data, f, indent=2)
    
    # Run solver
    output_path = f'output/test_rotation_{test_name.replace(" ", "_").lower()}_output.json'
    cmd = [
        'python', 'src/run_solver.py',
        '--in', test_input_path,
        '--out', output_path,
        '--time', '60'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Analyze results
    with open(output_path, 'r') as f:
        output = json.load(f)
    
    # Group assignments by employee
    by_employee = defaultdict(list)
    for assign in output['assignments']:
        emp_id = assign.get('employeeId')
        if emp_id and assign['status'] == 'ASSIGNED':
            by_employee[emp_id].append(assign['date'])
    
    # Show first 10 dates for each employee
    print("\nAssigned Dates (first 10):")
    for emp_id in sorted(by_employee.keys()):
        dates = sorted(by_employee[emp_id])[:10]
        emp_offset = next((emp['rotationOffset'] for emp in input_data['employees'] if emp['employeeId'] == emp_id), None)
        print(f"  {emp_id} (offset={emp_offset}): {', '.join(dates)}")
    
    # Check for identical schedules
    print("\nSchedule Analysis:")
    date_sets = {}
    for emp_id in sorted(by_employee.keys()):
        dates_tuple = tuple(sorted(by_employee[emp_id]))
        if dates_tuple not in date_sets:
            date_sets[dates_tuple] = []
        date_sets[dates_tuple].append(emp_id)
    
    for i, (dates, emp_ids) in enumerate(date_sets.items(), 1):
        if len(emp_ids) > 1:
            print(f"  Schedule Group {i}: {len(emp_ids)} employees work IDENTICAL dates")
            for emp_id in emp_ids:
                emp_offset = next((emp['rotationOffset'] for emp in input_data['employees'] if emp['employeeId'] == emp_id), None)
                print(f"    - {emp_id} (offset={emp_offset})")
        else:
            emp_offset = next((emp['rotationOffset'] for emp in input_data['employees'] if emp['employeeId'] == emp_ids[0]), None)
            print(f"  Schedule Group {i}: {emp_ids[0]} (offset={emp_offset}) works UNIQUE dates")

if __name__ == '__main__':
    print("Testing Rotation Offset Scenarios")
    print("="*70)
    
    # Test 1: All same offset
    run_test("All Same Offset", [2, 2, 2])
    
    # Test 2: All offset=0
    run_test("All Zero Offset", [0, 0, 0])
    
    # Test 3: Some duplicate (0, 1, 1)
    run_test("Some Duplicates", [0, 1, 1])
    
    # Test 4: Original staggered (0, 1, 2)
    run_test("Staggered", [0, 1, 2])
    
    print(f"\n{'='*70}")
    print("✓ All rotation offset scenarios tested successfully")
    print(f"{'='*70}")
