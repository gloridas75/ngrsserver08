#!/usr/bin/env python3
"""Check public holiday handling in solver output."""

import json
import glob

# Find the latest output file by modification time
import os
outputs = glob.glob('output/output_*.json')
if outputs:
    latest = max(outputs, key=os.path.getmtime)
    print(f'Checking: {latest}')
    with open(latest, 'r') as f:
        data = json.load(f)
    
    # Check public holiday date (2026-03-21)
    ph_date = '2026-03-21'
    ph_assignments = [a for a in data.get('assignments', []) if a.get('date') == ph_date and a.get('shiftCode') != 'O']
    
    print(f'\nPublic holiday {ph_date}:')
    print(f'  Work assignments on PH: {len(ph_assignments)}')
    
    if ph_assignments:
        print(f'  Sample assignment on PH:')
        sample = ph_assignments[0]
        print(f'    Employee: {sample.get("employeeId")}')
        print(f'    Shift: {sample.get("shiftCode")}')
        print(f'    Hours: {json.dumps(sample.get("hours", {}), indent=6)}')
    else:
        print('  ✓ No work assignments on PH (includePublicHolidays=false working)')
    
    # Check for publicHolidayHours field in any assignment  
    has_ph_hours = any('publicHolidayHours' in a.get('hours', {}) for a in data.get('assignments', []))
    print(f'\nPublicHolidayHours field present: {has_ph_hours}')
    
    # Show a sample work assignment with hours
    work_assignments = [a for a in data.get('assignments', []) if a.get('shiftCode') not in ['O', None]]
    if work_assignments:
        sample = work_assignments[0]
        print(f'\nSample work assignment hours structure:')
        print(f'  {json.dumps(sample.get("hours", {}), indent=2)}')
