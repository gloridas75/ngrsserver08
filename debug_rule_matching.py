#!/usr/bin/env python
"""
Debug why Rule 6 (Local Scheme B SO) is not matching
"""
import json
from context.engine.time_utils import normalize_scheme
from context.engine.constraint_config import get_employee_type, matches_monthly_limit_filters

# Load input
with open('input/RST-20260301-739D3553_Solver_Input.json', 'r') as f:
    input_data = f.read()
    input_data = input_data.replace('"schemaVersion": "0.70",', '"schemaVersion": "0.95",')
    input_data = json.loads(input_data)

print("=" * 80)
print("DEBUGGING RULE MATCHING FOR SCHEME B SO")
print("=" * 80)

# Get Scheme B SO employee
employees = input_data.get('employees', [])
scheme_b_so = [emp for emp in employees if emp.get('scheme') == 'Scheme B' and emp.get('productTypeId') == 'SO'][0]

print(f"\nEmployee: {scheme_b_so['employeeId']}")
print(f"  RAW scheme: '{scheme_b_so.get('scheme')}'")
print(f"  Normalized scheme: '{normalize_scheme(scheme_b_so.get('scheme'))}'")
print(f"  RAW productTypeId: '{scheme_b_so.get('productTypeId')}'")
print(f"  RAW employeeType: '{scheme_b_so.get('employeeType')}'")
print(f"  Computed employeeType: '{get_employee_type(scheme_b_so)}'")

# Check Rule 6 (Local Scheme B SO)
monthly_limits = input_data.get('monthlyHourLimits', [])
rule6 = monthly_limits[5]

print(f"\nRule 6 configuration:")
print(f"  applicableTo: {json.dumps(rule6.get('applicableTo'), indent=4)}")

# Test if rule matches
matches = matches_monthly_limit_filters(rule6, scheme_b_so)
print(f"\nDoes Rule 6 match this employee? {matches}")

if not matches:
    print("\n❌ Rule 6 does NOT match - debugging why...")
    
    applicable_to = rule6.get('applicableTo', {})
    
    # Check employeeType
    allowed_emp_types = applicable_to.get('employeeType', 'All')
    emp_type = get_employee_type(scheme_b_so)
    print(f"\n  EmployeeType check:")
    print(f"    Allowed: {allowed_emp_types}")
    print(f"    Employee: {emp_type}")
    print(f"    Match: {emp_type == allowed_emp_types if allowed_emp_types != 'All' else True}")
    
    # Check schemes
    allowed_schemes = applicable_to.get('schemes', 'All')
    emp_scheme = normalize_scheme(scheme_b_so.get('scheme'))
    print(f"\n  Schemes check:")
    print(f"    Allowed: {allowed_schemes}")
    print(f"    Employee normalized: {emp_scheme}")
    if allowed_schemes != 'All':
        if isinstance(allowed_schemes, str):
            allowed_schemes = [allowed_schemes]
        print(f"    Match: {emp_scheme in allowed_schemes}")
    
    # Check productTypes
    allowed_products = applicable_to.get('productTypeIds', 'All')
    emp_product_id = scheme_b_so.get('productTypeId', '')
    emp_products = scheme_b_so.get('productTypes', [emp_product_id] if emp_product_id else [])
    print(f"\n  ProductTypes check:")
    print(f"    Allowed: {allowed_products}")
    print(f"    Employee: {emp_products}")
    if allowed_products != 'All':
        if isinstance(allowed_products, str):
            allowed_products = [allowed_products]
        print(f"    Match: {any(pt in emp_products for pt in allowed_products)}")

print("\n" + "=" * 80)
