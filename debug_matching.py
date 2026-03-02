#!/usr/bin/env python3
"""Debug rule matching for employee 00100012"""

import json
import sys

def get_employee_type(employee):
    local_flag = employee.get('local', 1)
    return 'Local' if local_flag == 1 else 'Foreigner'

def normalize_scheme(scheme):
    if scheme in ['A', 'Scheme A']:
        return 'A'
    elif scheme in ['B', 'Scheme B']:
        return 'B'
    return scheme

def matches_monthly_limit_filters(limit_config, employee):
    applicable_to = limit_config.get('applicableTo', {})
    
    emp_type = get_employee_type(employee)
    emp_scheme = normalize_scheme(employee.get('scheme', 'A'))
    emp_product_id = employee.get('productTypeId', '')
    emp_products = [emp_product_id] if emp_product_id else []
    emp_rank = employee.get('rank', '') or employee.get('rankId', '')
    
    print(f"  Employee: {emp_type} | Scheme {emp_scheme} | Product {emp_product_id} | Rank {emp_rank}")
    
    # Check employeeType
    allowed_emp_types = applicable_to.get('employeeType', 'All')
    if allowed_emp_types != 'All':
        if isinstance(allowed_emp_types, str):
            allowed_emp_types = [allowed_emp_types]
        if emp_type not in allowed_emp_types:
            print(f"    ❌ employeeType mismatch: {emp_type} not in {allowed_emp_types}")
            return False
        print(f"    ✓ employeeType match: {emp_type} in {allowed_emp_types}")
    else:
        print(f"    ✓ employeeType: All (wildcard)")
    
    # Check schemes
    allowed_schemes = applicable_to.get('schemes', 'All')
    if allowed_schemes != 'All':
        if isinstance(allowed_schemes, str):
            allowed_schemes = [allowed_schemes]
        if emp_scheme not in allowed_schemes:
            print(f"    ❌ schemes mismatch: {emp_scheme} not in {allowed_schemes}")
            return False
        print(f"    ✓ schemes match: {emp_scheme} in {allowed_schemes}")
    else:
        print(f"    ✓ schemes: All (wildcard)")
    
    # Check productTypes
    allowed_products = applicable_to.get('productTypeIds') or applicable_to.get('productTypes', 'All')
    if allowed_products != 'All':
        if isinstance(allowed_products, str):
            allowed_products = [allowed_products]
        if not any(pt in emp_products for pt in allowed_products):
            print(f"    ❌ productTypes mismatch: {emp_products} doesn't match {allowed_products}")
            return False
        print(f"    ✓ productTypes match: {emp_products} overlaps with {allowed_products}")
    else:
        print(f"    ✓ productTypes: All (wildcard)")
    
    # Check ranks
    allowed_ranks = applicable_to.get('rankIds') or applicable_to.get('ranks', 'All')
    if allowed_ranks != 'All':
        if isinstance(allowed_ranks, str):
            allowed_ranks = [allowed_ranks]
        if 'All' not in allowed_ranks:
            if emp_rank not in allowed_ranks:
                print(f"    ❌ ranks mismatch: {emp_rank} not in {allowed_ranks}")
                return False
        print(f"    ✓ ranks match: {emp_rank} in {allowed_ranks} or 'All' present")
    else:
        print(f"    ✓ ranks: All (wildcard)")
    
    print(f"    ✅ RULE MATCHES!")
    return True

def main():
    with open('input/RST-20260301-F9EA0EDE_Solver_Input.json') as f:
        data = json.load(f)
    
    # Find employee 00100012
    employee = None
    for emp in data['employees']:
        if emp['employeeId'] == '00100012':
            employee = emp
            break
    
    if not employee:
        print("Employee 00100012 not found")
        return
    
    print("=" * 80)
    print("EMPLOYEE 00100012 MATCHING DEBUG")
    print("=" * 80)
    print(f"Employee data: {json.dumps(employee, indent=2)}")
    print()
    
    monthly_limits = data.get('monthlyHourLimits', [])
    print(f"Total monthlyHourLimits rules: {len(monthly_limits)}")
    print()
    
    for i, rule in enumerate(monthly_limits):
        rule_id = rule.get('id', f'Rule {i}')
        method = rule.get('hourCalculationMethod', 'unknown')
        print(f"\n[Rule {i+1}] {rule_id} ({method}):")
        print(f"  applicableTo: {json.dumps(rule.get('applicableTo', {}), indent=2)}")
        
        if matches_monthly_limit_filters(rule, employee):
            print(f"\n🎯 FIRST MATCH: {rule_id} ({method})")
            print(f"   For 31-day month: {rule.get('valuesByMonthLength', {}).get('31', {})}")
            break

if __name__ == '__main__':
    main()
