#!/usr/bin/env python3
"""Test Scheme P daily hours filtering."""

import json
import sys

# Add context path
sys.path.insert(0, '/Users/glori/1 Anthony_Workspace/My Developments/NGRS/ngrs-solver-v0.7/ngrssolver')

from context.engine.constraint_config import get_constraint_param
from context.engine.time_utils import normalize_scheme

# Load input
with open('/Users/glori/Downloads/RST-20260111-52038D2B_Solver_Input.json', 'r') as f:
    input_data = json.load(f)

# Create minimal ctx
ctx = {
    'constraintList': input_data.get('constraintList', [])
}

# Test employees
employees = input_data.get('employees', [])

print("=" * 80)
print("SCHEME P DAILY HOURS CAP TEST")
print("=" * 80)

for emp in employees:
    emp_id = emp.get('employeeId')
    scheme_raw = emp.get('scheme', '')
    scheme = normalize_scheme(scheme_raw)
    
    # Get daily hours cap
    max_daily_hours = get_constraint_param(
        ctx,
        'momDailyHoursCap',
        employee=emp,
        param_name='maxDailyHours',
        default=14.0
    )
    
    print(f"\nEmployee: {emp_id}")
    print(f"  Scheme: {scheme_raw} → {scheme}")
    print(f"  Product Type: {emp.get('productTypeId', 'N/A')}")
    print(f"  Rank: {emp.get('rankId', 'N/A')}")
    print(f"  Daily Hours Cap: {max_daily_hours}h")

print("\n" + "=" * 80)
print("SHIFT ANALYSIS")
print("=" * 80)

# Analyze shift
demand_items = input_data.get('demandItems', [])
for dmd in demand_items:
    for shift_group in dmd.get('shifts', []):
        for shift_detail in shift_group.get('shiftDetails', []):
            shift_code = shift_detail.get('shiftCode')
            start = shift_detail.get('start')
            end = shift_detail.get('end')
            next_day = shift_detail.get('nextDay', False)
            
            from datetime import datetime, timedelta
            start_time = datetime.strptime(start, '%H:%M:%S')
            end_time = datetime.strptime(end, '%H:%M:%S')
            if next_day:
                end_time += timedelta(days=1)
            
            shift_hours = (end_time - start_time).total_seconds() / 3600.0
            
            print(f"\nShift: {shift_code}")
            print(f"  Time: {start} - {end}{' +1 day' if next_day else ''}")
            print(f"  Duration: {shift_hours}h")
            print(f"  After 1h lunch: {shift_hours - 1}h")

print("\n" + "=" * 80)
print("ELIGIBILITY CHECK")
print("=" * 80)

# Check eligibility
shift_hours = 12.0  # D shift 08:00-20:00

for emp in employees:
    emp_id = emp.get('employeeId')
    scheme = normalize_scheme(emp.get('scheme', ''))
    
    max_daily_hours = get_constraint_param(
        ctx,
        'momDailyHoursCap',
        employee=emp,
        default=14.0
    )
    
    eligible = shift_hours <= max_daily_hours
    
    print(f"\n{emp_id} (Scheme {scheme}):")
    print(f"  Shift hours: {shift_hours}h")
    print(f"  Daily cap: {max_daily_hours}h")
    print(f"  Eligible: {'✅ YES' if eligible else '❌ NO - SHOULD BE EXCLUDED'}")
