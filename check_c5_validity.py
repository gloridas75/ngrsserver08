#!/usr/bin/env python3
"""Check if pattern is valid against C5 constraint."""
import json
from datetime import datetime, timedelta

with open('/Users/glori/Downloads/RST-20260128-69B55E12_Solver_Input.json') as f:
    data = json.load(f)

pattern = ['D','D','D','D','O','D','D','D','D','D','O']  # 11-day cycle
start = datetime.fromisoformat(data['planningHorizon']['startDate'].replace('Z','')).date()

# Build work schedule for each employee
employees = data['employees']
emp_schedules = {}

for emp in employees:
    emp_id = emp['employeeId']
    offset = emp.get('rotationOffset', 0)
    schedule = []
    for i in range(31):  # March has 31 days
        day = start + timedelta(days=i)
        pattern_idx = (i + offset) % 11
        pattern_val = pattern[pattern_idx]
        if pattern_val == 'D':
            schedule.append(day)
    emp_schedules[emp_id] = schedule

# Check 7-day rolling windows for conflicts
print("Checking if ALL work days can be assigned respecting C5...")
print("C5: Each employee must have <= 6 work days in any 7-day window")
print()

conflict_count = 0
for emp_id, schedule in emp_schedules.items():
    # For each 7-day window, count work days
    for window_start_offset in range(25):  # 31 - 6 = 25 possible windows
        window_start = start + timedelta(days=window_start_offset)
        window_end = window_start + timedelta(days=6)
        work_days_in_window = sum(1 for d in schedule if window_start <= d <= window_end)
        if work_days_in_window > 6:
            print(f"  CONFLICT: {emp_id} has {work_days_in_window} work days in window {window_start} to {window_end}")
            conflict_count += 1

if conflict_count == 0:
    print("  OK - No C5 conflicts found - all schedules are valid!")
    print()
    print("Total work slots per employee:")
    for emp_id, schedule in emp_schedules.items():
        print(f"  {emp_id}: {len(schedule)} work days")
    print(f"\nTotal slots: {sum(len(s) for s in emp_schedules.values())}")
