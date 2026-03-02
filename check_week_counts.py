#!/usr/bin/env python3
"""Analyze work days per week for Employee 00100012"""

import json
from datetime import datetime, timedelta
from collections import defaultdict

with open('output/RST-20260301-F9EA0EDE_FIXED2.json') as f:
    data = json.load(f)

emp_12 = [a for a in data['assignments'] if a['employeeId'] == '00100012']
print(f'Employee 00100012: {len(emp_12)} assignments\n')

# Group by calendar week (Mon-Sun)
weeks = defaultdict(list)
for a in emp_12:
    date_obj = datetime.fromisoformat(a['date']).date()
    # Get Monday of this week
    monday = date_obj - timedelta(days=date_obj.weekday())
    weeks[monday].append({
        'date': date_obj.strftime('%Y-%m-%d'),
        'shift': a['shiftCode'],
        'normal': a.get('normalHours', 0),
        'ot': a.get('overtimeHours', 0)
    })

for monday in sorted(weeks.keys()):
    print(f'Week of {monday} (Mon):')
    for item in sorted(weeks[monday], key=lambda x: x['date']):
        shift = item['shift']
        normal = item['normal']
        ot = item['ot']
        print(f'  {item["date"]}: {shift:2s}  normal={normal:5.2f}h  ot={ot:5.2f}h')
    
    work_days = len([item for item in weeks[monday] if item['shift'] not in ['O', 'PH']])
    total_normal = sum(item['normal'] for item in weeks[monday])
    total_ot = sum(item['ot'] for item in weeks[monday])
    print(f'  → {work_days} work days, {total_normal:.2f}h normal, {total_ot:.2f}h OT')
    
    # Calculate expected: 44h / work_days
    if work_days > 0:
        expected_normal_per_day = 44.0 / work_days
        print(f'  → Expected per work day: {expected_normal_per_day:.2f}h normal (44h / {work_days} days)')
    print()
