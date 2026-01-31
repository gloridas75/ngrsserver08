#!/usr/bin/env python3
"""Debug Mar 1-2 constraint conflicts."""
import json
from datetime import datetime, date, timedelta
from collections import defaultdict

with open('/Users/glori/Downloads/RST-20260128-69B55E12_Solver_Input.json') as f:
    data = json.load(f)

pattern = ['D','D','D','D','O','D','D','D','D','D','O']  # 11-day cycle
start = datetime.fromisoformat(data['planningHorizon']['startDate'].replace('Z','')).date()

print("=" * 60)
print("Employee 00112626 (ASSIGNED on Mar 2) pattern:")
print("-" * 60)

for emp in data['employees']:
    if emp['employeeId'] == '00112626':
        offset = emp.get('rotationOffset', 0)
        print(f"  rotationOffset: {offset}")
        for i in range(14):
            day = start + timedelta(days=i)
            pattern_idx = (i + offset) % 11
            pattern_val = pattern[pattern_idx]
            iso_week = day.isocalendar()[1]
            print(f"    {day} ({day.strftime('%a')}) ISO wk {iso_week}: pattern[{pattern_idx}]={pattern_val}")

print("\n" + "=" * 60)
print("Employee 00007901 (UNASSIGNED on Mar 2) pattern:")
print("-" * 60)

for emp in data['employees']:
    if emp['employeeId'] == '00007901':
        offset = emp.get('rotationOffset', 0)
        print(f"  rotationOffset: {offset}")
        for i in range(14):
            day = start + timedelta(days=i)
            pattern_idx = (i + offset) % 11
            pattern_val = pattern[pattern_idx]
            iso_week = day.isocalendar()[1]
            print(f"    {day} ({day.strftime('%a')}) ISO wk {iso_week}: pattern[{pattern_idx}]={pattern_val}")

print("\n" + "=" * 60)
print("KEY DIFFERENCE ANALYSIS:")
print("-" * 60)

# Check which employees have OFF on specific days
print("\nEmployees with OFF day by date (first 7 days):")
for i in range(7):
    day = start + timedelta(days=i)
    off_employees = []
    for emp in data['employees']:
        offset = emp.get('rotationOffset', 0)
        pattern_idx = (i + offset) % 11
        if pattern[pattern_idx] == 'O':
            off_employees.append(emp['employeeId'])
    print(f"  {day} ({day.strftime('%a')}): OFF for {off_employees}")

