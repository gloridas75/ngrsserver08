#!/usr/bin/env python3
"""Check monthlyHourLimits configuration."""
import json

with open('input/RST-20260301-739D3553_Solver_Input.json', 'r') as f:
    input_data = json.load(f)

print("Monthly Hour Limits Configuration:")
print("=" * 100)

for limit in input_data.get('monthlyHourLimits', []):
    limit_id = limit.get('id')
    desc = limit.get('description', '')
    applicable = limit.get('applicableTo', {})
    method = limit.get('hourCalculationMethod', '')
    
    print(f"\n{limit_id}: {desc}")
    print(f"  Method: {method}")
    print(f"  ApplicableTo:")
    print(f"    - Employee Type: {applicable.get('employeeType', 'N/A')}")
    print(f"    - Schemes: {applicable.get('schemes', 'N/A')}")
    print(f"    - Product Types: {applicable.get('productTypeIds', 'N/A')}")
    
    values = limit.get('valuesByMonthLength', {})
    if '31' in values:
        month_31 = values['31']
        max_ot = month_31.get('maxOvertimeHours', 'NOT SET')
        min_cont = month_31.get('minimumContractualHours', 'NOT SET')
        total_max = month_31.get('totalMaxHours', 'NOT SET')
        print(f"  For 31-day month (May 2026):")
        print(f"    - maxOvertimeHours: {max_ot}")
        print(f"    - minimumContractualHours: {min_cont}")
        print(f"    - totalMaxHours: {total_max}")

print("\n\nScheme B SO Configuration:")
print("=" * 100)
print("Looking for monthlyHourLimits entry for Scheme B + SO...")
found = False
for limit in input_data.get('monthlyHourLimits', []):
    applicable = limit.get('applicableTo', {})
    schemes = applicable.get('schemes', [])
    products = applicable.get('productTypeIds', [])
    
    if 'B' in schemes or 'Scheme B' in schemes:
        if 'SO' in products or 'All' in products:
            found = True
            print(f"Found: {limit.get('id')} - {limit.get('description')}")
            
if not found:
    print("NOT FOUND - Scheme B SO may be using standardMonthlyHours (daily proration)")
    print("This would calculate OT differently than Scheme A SO")
