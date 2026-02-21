#!/usr/bin/env python3
"""Analyze v2 output for the new features."""
import json
from datetime import datetime

with open('output/v2_RST-20260210-008E178F_Output.json') as f:
    d = json.load(f)

print('=== V2 OUTPUT ANALYSIS ===')
print(f'Schema Version: {d.get("schemaVersion")}')
print(f'Planning Reference: {d.get("planningReference")}')

# Check meta for v2 flags
meta = d.get('meta', {})
print(f'\n--- V2 Meta Info ---')
print(f'  API Version: {meta.get("apiVersion", "N/A")}')
print(f'  Used Daily Headcount: {meta.get("usedDailyHeadcount", "N/A")}')
print(f'  Used V2 Slot Builder: {meta.get("usedV2SlotBuilder", "N/A")}')

# Check assignments
assignments = d.get('assignments', [])
print(f'\n--- Assignments ---')
print(f'  Total: {len(assignments)}')

# Count by date and check for time overrides
by_date = {}
time_override_dates = []
for a in assignments:
    date_str = a.get('date', '')
    if date_str:
        by_date[date_str] = by_date.get(date_str, 0) + 1
    
    # Check Feb 15 for time override (07:00-19:00)
    if '2026-02-15' in a.get('startDateTime', ''):
        start = a.get('startDateTime', '')
        end = a.get('endDateTime', '')
        if start and '07:00' in start:
            time_override_dates.append({'date': date_str, 'start': start, 'end': end})

print(f'  Dates with assignments: {len(by_date)}')
print(f'  Sample dates: {list(by_date.items())[:5]}')

# Check for Feb 15 time override
if time_override_dates:
    print(f'\n--- Time Override Check (Feb 15) ---')
    for t in time_override_dates[:3]:
        print(f'  {t}')
else:
    # Look for any Feb 15 assignments
    feb15 = [a for a in assignments if '2026-02-15' in a.get('date', '')]
    if feb15:
        print(f'\n--- Feb 15 Assignments (checking time) ---')
        for a in feb15[:3]:
            print(f'  Start: {a.get("startDateTime")}, End: {a.get("endDateTime")}')

# Check dailyCoverage
coverage = d.get('dailyCoverage', [])
print(f'\n--- Daily Coverage ---')
print(f'  Total entries: {len(coverage)}')

if coverage:
    # Find Feb 15
    feb15_cov = [c for c in coverage if c.get('date') == '2026-02-15']
    if feb15_cov:
        print(f'  Feb 15 coverage: {feb15_cov[0]}')
    
    # Show dayType distribution
    by_type = {}
    for c in coverage:
        dt = c.get('dayType', 'Normal')
        by_type[dt] = by_type.get(dt, 0) + 1
    print(f'  By dayType: {by_type}')

# Check employee product types in assignments
print(f'\n--- Employee Product Types Used ---')
emp_products = set()
for a in assignments:
    pt = a.get('productTypeId')
    if pt:
        emp_products.add(pt)
print(f'  Product types in output: {emp_products}')
