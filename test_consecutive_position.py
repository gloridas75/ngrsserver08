#!/usr/bin/env python3
"""
Test find_consecutive_position logic for employee 00154528.

Employee 00154528 worked June 6-11 (6 consecutive days).
Let's trace what find_consecutive_position returns for each day.
"""

import json
from datetime import datetime, date, timedelta

def find_consecutive_position(employee_id: str, current_date_obj, all_assignments: list) -> int:
    """Find the position of current date in consecutive work days sequence."""
    # Build set of work dates for this employee
    work_dates = set()
    for assignment in all_assignments:
        if assignment.get('employeeId') != employee_id:
            continue
        
        assign_date_str = assignment.get('date')
        shift_code = assignment.get('shiftCode', '')
        
        if assign_date_str and shift_code and shift_code != 'O':
            try:
                assign_date = datetime.fromisoformat(assign_date_str).date()
                work_dates.add(assign_date)
            except Exception:
                continue
    
    # Count consecutive work days including current date
    position = 1
    check_date = current_date_obj - timedelta(days=1)
    
    # Look backward to count consecutive days
    while check_date in work_dates:
        position += 1
        check_date -= timedelta(days=1)
    
    return position


# Load solver output
with open('/Users/glori/Downloads/solver_output_sync.json', 'r') as f:
    data = json.load(f)

assignments = data['assignments']
emp_id = "00154528"

# Get this employee's work dates
emp_assignments = [a for a in assignments if a['employeeId'] == emp_id]
emp_assignments.sort(key=lambda x: x['date'])

print("=" * 80)
print(f"CONSECUTIVE POSITION TEST FOR EMPLOYEE {emp_id}")
print("=" * 80)
print()
print("June 6-11 sequence (6 consecutive days):")
print()

# Test June 6-11 (6 consecutive days)
test_dates = [
    date(2026, 6, 6),
    date(2026, 6, 7),
    date(2026, 6, 8),
    date(2026, 6, 9),
    date(2026, 6, 10),
    date(2026, 6, 11),
]

for test_date in test_dates:
    pos = find_consecutive_position(emp_id, test_date, assignments)
    print(f"Date: {test_date} → Consecutive Position: {pos}")

print()
print("Expected: June 11 should return position 6 (6th consecutive day)")
print("If position = 6, then restDayPay logic should apply (0h normal + 8h restDayPay)")
