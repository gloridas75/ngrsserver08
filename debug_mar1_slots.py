#!/usr/bin/env python3
"""Debug Mar 1-2 slot assignments."""
import json
from datetime import datetime, timedelta

with open('/Users/glori/Downloads/RST-20260128-69B55E12_Solver_Input.json') as f:
    data = json.load(f)

# Planning horizon
start = datetime.fromisoformat(data['planningHorizon']['startDate'].replace('Z',''))
end = datetime.fromisoformat(data['planningHorizon']['endDate'].replace('Z',''))
print(f"Planning: {start.date()} to {end.date()}")
print(f"Start: {start.strftime('%A')} (ISO week {start.isocalendar()[1]})")

# Check pattern for each employee for first few days
pattern = ['D','D','D','D','O','D','D','D','D','D','O']  # 11-day
print(f"\nPattern: {pattern} (length={len(pattern)})")

for emp in data['employees']:
    offset = emp.get('rotationOffset', 0)
    emp_id = emp['employeeId']
    print(f"\nEmployee {emp_id}, offset={offset}:")
    
    # Calculate pattern days for Mar 1-7
    ref_date = start
    for i in range(7):
        day = start + timedelta(days=i)
        day_num = (day - ref_date).days
        pattern_idx = (day_num + offset) % len(pattern)
        pattern_val = pattern[pattern_idx]
        iso_week = day.isocalendar()[1]
        print(f"  {day.date()} ({day.strftime('%a')}) ISO wk {iso_week}: pattern[{pattern_idx}]={pattern_val}")
