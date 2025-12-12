#!/usr/bin/env python3
"""
Test calculate_mom_compliant_hours for employee 00154528 on June 11, 2026.

This should be the 6th consecutive work day, so should get:
- normal: 0.0
- restDayPay: 8.0
- ot: 3.0 (12h gross - 1h lunch - 8h restDayPay)
"""

import json
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[0]))

from datetime import datetime
from context.engine.time_utils import calculate_mom_compliant_hours, count_work_days_in_calendar_week, find_consecutive_position

# Load solver output
with open('/Users/glori/Downloads/solver_output_sync.json', 'r') as f:
    data = json.load(f)

assignments = data['assignments']
emp_id = "00154528"

# Get June 11 assignment
june11_assignment = next(
    (a for a in assignments if a['employeeId'] == emp_id and a['date'] == '2026-06-11'),
    None
)

if not june11_assignment:
    print("ERROR: June 11 assignment not found!")
    sys.exit(1)

print("=" * 80)
print(f"HOUR CALCULATION TEST FOR EMPLOYEE {emp_id} ON JUNE 11, 2026")
print("=" * 80)
print()

# Get assignment details
start_dt = datetime.fromisoformat(june11_assignment['startDateTime'])
end_dt = datetime.fromisoformat(june11_assignment['endDateTime'])
date_obj = datetime.fromisoformat(june11_assignment['date']).date()

# Check work days in calendar week
work_days = count_work_days_in_calendar_week(emp_id, date_obj, assignments)
print(f"Work days in calendar week (June 9-15, 2026): {work_days}")

# Check consecutive position
consecutive_pos = find_consecutive_position(emp_id, date_obj, assignments)
print(f"Consecutive position: {consecutive_pos}")
print()

# Calculate hours
hours_dict = calculate_mom_compliant_hours(
    start_dt=start_dt,
    end_dt=end_dt,
    employee_id=emp_id,
    assignment_date_obj=date_obj,
    all_assignments=assignments
)

print("Calculated hours:")
print(f"  Gross: {hours_dict['gross']}h")
print(f"  Lunch: {hours_dict['lunch']}h")
print(f"  Normal: {hours_dict['normal']}h")
print(f"  OT: {hours_dict['ot']}h")
print(f"  Rest Day Pay: {hours_dict['restDayPay']}h")
print(f"  Paid: {hours_dict['paid']}h")
print()

# Compare with output
output_hours = june11_assignment.get('hours', {})
print("Hours in output file:")
print(f"  Gross: {output_hours.get('gross')}h")
print(f"  Lunch: {output_hours.get('lunch')}h")
print(f"  Normal: {output_hours.get('normal')}h")
print(f"  OT: {output_hours.get('ot')}h")
print(f"  Rest Day Pay: {output_hours.get('restDayPay')}h")
print(f"  Paid: {output_hours.get('paid')}h")
print()

# Expected for 6th consecutive day
print("EXPECTED (6th consecutive day, 12h shift):")
print(f"  Normal: 0.0h")
print(f"  Rest Day Pay: 8.0h")
print(f"  OT: 3.0h (12h - 1h lunch - 8h restDayPay)")
print()

# Check if matches
if hours_dict['restDayPay'] == 8.0:
    print("✓ REST DAY PAY CALCULATED CORRECTLY")
else:
    print(f"✗ REST DAY PAY WRONG: Expected 8.0h, got {hours_dict['restDayPay']}h")
    if work_days < 6:
        print(f"  → REASON: work_days_in_week = {work_days} (< 6)")
    if consecutive_pos < 6:
        print(f"  → REASON: consecutive_position = {consecutive_pos} (< 6)")
