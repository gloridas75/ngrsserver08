#!/usr/bin/env python3
"""Analyze solver output for UNASSIGNED slots and work distribution."""
import json
import os
from collections import defaultdict
from datetime import datetime

# Find the latest output file
files = [f for f in os.listdir('output') if f.startswith('output_2801')]
latest = sorted(files)[-1]
print(f"Analyzing: {latest}")

with open(f'output/{latest}', 'r') as f:
    data = json.load(f)

assignments = data.get('output', {}).get('assignments', [])

# Check unassigned
print('=== UNASSIGNED SLOTS ===')
unassigned = [a for a in assignments 
              if a.get('assignmentStatus') == 'UNASSIGNED' and a.get('shiftType') != 'OFF_DAY']
              
by_date = defaultdict(list)
for u in unassigned:
    date = u.get('startDateTime', '')[:10]
    by_date[date].append(u.get('employeeId'))
    
for date in sorted(by_date.keys()):
    print(f'{date}: {len(by_date[date])} employees - {by_date[date]}')

# Check work days per week per employee  
print()
print('=== WORK DAYS BY ISO WEEK ===')
assigned = [a for a in assignments
            if a.get('assignmentStatus') == 'ASSIGNED' and a.get('shiftType') != 'OFF_DAY']

by_emp_week = defaultdict(lambda: defaultdict(int))
for a in assigned:
    emp = a.get('employeeId')
    date_str = a.get('startDateTime', '')[:10]
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    iso_week = dt.isocalendar()[1]
    by_emp_week[emp][iso_week] += 1

print('Employee work days per ISO week:')
for emp in sorted(by_emp_week.keys())[:5]:
    weeks = by_emp_week[emp]
    print(f'  {emp}: {dict(sorted(weeks.items()))}')
    
# Show total work days per employee
print()
print('=== TOTAL WORK DAYS PER EMPLOYEE ===')
for emp in sorted(by_emp_week.keys()):
    total = sum(by_emp_week[emp].values())
    print(f'  {emp}: {total} work days')
