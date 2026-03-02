#!/usr/bin/env python
"""
Debug get_monthly_hour_limits to find why Scheme B SO gets 124h cap
"""
import json
from context.engine.constraint_config import get_monthly_hour_limits
from context.engine.data_loader import load_input

# Load input with proper schema handling
with open('input/RST-20260301-739D3553_Solver_Input.json', 'r') as f:
    input_data = f.read()
    input_data = input_data.replace('"schemaVersion": "0.70",', '"schemaVersion": "0.95",')
    input_data = json.loads(input_data)

print("=" * 80)
print("DEBUGGING get_monthly_hour_limits FOR SCHEME B SO")
print("=" * 80)

# Load input via data_loader to get ctx
ctx = load_input(input_data)

# Get Scheme B SO employee
employees = input_data.get('employees', [])
scheme_b_so = [emp for emp in employees if emp.get('scheme') == 'Scheme B' and emp.get('productTypeId') == 'SO'][0]

print(f"\nEmployee: {scheme_b_so['employeeId']}")
print(f"  Scheme: {scheme_b_so.get('scheme')}")
print(f"  ProductTypeId: {scheme_b_so.get('productTypeId')}")
print(f"  EmployeeType: {scheme_b_so.get('employeeType')}")

# Get limits
limits = get_monthly_hour_limits(ctx, scheme_b_so, 2026, 5)

print(f"\nget_monthly_hour_limits result:")
print(f"  minimumContractualHours: {limits.get('minimumContractualHours')}h")
print(f"  maxOvertimeHours: {limits.get('maxOvertimeHours')}h")
print(f"  totalMaxHours: {limits.get('totalMaxHours')}h")
print(f"  ruleId: {limits.get('ruleId')}")
print(f"  enforcement: {limits.get('enforcement')}")

print("\n" + "=" * 80)
print("EXPECTED: maxOvertimeHours = 72h")
print(f"ACTUAL: maxOvertimeHours = {limits.get('maxOvertimeHours')}h")
print("=" * 80)
