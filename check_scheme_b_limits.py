#!/usr/bin/env python
"""
Check why Scheme B SO employees get 124h OT cap instead of 72h
"""
import json
from context.engine.constraint_config import get_monthly_hour_limits

# Load input
with open('input/RST-20260301-739D3553_Solver_Input.json', 'r') as f:
    input_data = f.read()

# Fix schemaVersion field
input_data = input_data.replace('"schemaVersion": "0.70",', '"schemaVersion": "0.95",')
input_data = json.loads(input_data)

print("=" * 80)
print("CHECKING SCHEME B SO OT LIMITS (124h vs 72h)")
print("=" * 80)

# Find Scheme B SO employees
employees = input_data.get('employees', [])
for emp in employees:
    emp_id = emp['employeeId']
    scheme = emp.get('scheme', 'A')
    product_id = emp.get('productTypeId', '')
    emp_type = emp.get('employeeType', 'Local')
    
    if scheme == 'B' and product_id == 'SO':
        print(f"\nEmployee: {emp_id}")
        print(f"  Scheme: {scheme}")
        print(f"  ProductTypeId: {product_id}")
        print(f"  EmployeeType: {emp_type}")
        
        # Build minimal ctx
        ctx = {
            'monthlyHourLimits': input_data.get('monthlyHourLimits', [])
        }
        
        # Get limits for May 2026 (31 days)
        limits = get_monthly_hour_limits(ctx, emp, 2026, 5)
        
        print(f"  Monthly Hour Limits (May 2026, 31 days):")
        print(f"    minimumContractualHours: {limits.get('minimumContractualHours')}h")
        print(f"    maxOvertimeHours: {limits.get('maxOvertimeHours')}h")
        print(f"    totalMaxHours: {limits.get('totalMaxHours')}h")
        print(f"    ruleId: {limits.get('ruleId')}")
        print(f"    enforcement: {limits.get('enforcement')}")

print("\n" + "=" * 80)
print("EXPECTED: maxOvertimeHours = 72h (standard cap)")
print("ACTUAL: maxOvertimeHours = 124h (why?)")
print("=" * 80)
print("\nChecking monthlyHourLimits configuration...")

monthly_limits = input_data.get('monthlyHourLimits', [])
print(f"\nFound {len(monthly_limits)} monthly hour limit rules:")

for idx, rule in enumerate(monthly_limits):
    print(f"\nRule {idx + 1}:")
    print(f"  ruleId: {rule.get('ruleId')}")
    applicable_to = rule.get('applicableTo', {})
    print(f"  applicableTo:")
    print(f"    employeeType: {applicable_to.get('employeeType', 'All')}")
    print(f"    schemes: {applicable_to.get('schemes', 'All')}")
    print(f"    productTypeIds: {applicable_to.get('productTypeIds', 'All')}")
    
    # Check month 31
    month_31_config = rule.get('monthLengthConfigurations', {}).get('31')
    if month_31_config:
        print(f"  Month 31 config:")
        print(f"    standardMonthlyHours: {month_31_config.get('standardMonthlyHours')}h")
        print(f"    maxOvertimeHours: {month_31_config.get('maxOvertimeHours')}h")
