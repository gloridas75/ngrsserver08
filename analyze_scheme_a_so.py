#!/usr/bin/env python3
"""Analyze Scheme A SO employee assignments."""
import json

with open('/tmp/test_739D3553.json', 'r') as f:
    output = json.load(f)

with open('input/RST-20260301-739D3553_Solver_Input.json', 'r') as f:
    input_data = json.load(f)

# Find Scheme A SO employee assignments
for emp in input_data['employees']:
    if emp['scheme'] == 'Scheme A' and emp['productTypeId'] == 'SO':
        emp_id = emp['employeeId']
        print(f"\nEmployee {emp_id} ({emp['rankId']}) - Scheme A, SO:")
        print("=" * 80)
        
        assignments = [a for a in output['assignments'] if a.get('employeeId') == emp_id and a.get('status') == 'ASSIGNED']
        assignments.sort(key=lambda a: a.get('date', ''))
        
        total_assignments = len(assignments)
        total_work_days = len([a for a in assignments if a.get('shiftCode') not in ['O', 'PH', 'UNASSIGNED']])
        
        print(f"Total assignments: {total_assignments}")
        print(f"Work days (D shifts): {total_work_days}")
        print(f"\nDay-by-day breakdown:")
        for idx, asg in enumerate(assignments):
            if idx < 10 or idx >= len(assignments) - 5:  # First 10 and last 5
                date = asg.get('date')
                shift = asg.get('shiftCode')
                hours = asg.get('hours', {})
                normal = hours.get('normal', 0)
                ot = hours.get('ot', 0)
                ph = hours.get('publicHolidayHours', 0)
                print(f"  {date}: {shift:2s} - Normal: {normal:5.1f}h, OT: {ot:5.1f}h, PH: {ph:5.1f}h")
            elif idx == 10:
                print(f"  ... ({len(assignments) - 15} days omitted)")
        
        # Calculate totals
        total_normal = sum(a.get('hours', {}).get('normal', 0) for a in assignments)
        total_ot = sum(a.get('hours', {}).get('ot', 0) for a in assignments)
        total_ph = sum(a.get('hours', {}).get('publicHolidayHours', 0) for a in assignments)
        
        print(f"\nTotals:")
        print(f"  Normal Hours: {total_normal:.1f}h")
        print(f"  OT Hours: {total_ot:.1f}h")
        print(f"  PH Hours: {total_ph:.1f}h")
        print(f"  Total: {total_normal + total_ot + total_ph:.1f}h")
        print(f"\n  >>> Why only {total_ot:.1f}h OT when limit is 72h?")
