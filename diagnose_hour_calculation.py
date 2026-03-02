#!/usr/bin/env python
"""
Detailed analysis of why hours are miscalculated for RST-20260301-F9EA0EDE
"""
import json

with open('input/RST-20260301-F9EA0EDE_Solver_Input.json', 'r') as f:
    input_data = json.load(f)

print("=" * 80)
print("DETAILED ROOT CAUSE ANALYSIS")
print("=" * 80)

print("\n1. EMPLOYEE CONFIGURATION MISMATCH")
print("-" * 80)

employees = input_data.get('employees', [])
monthly_limits = input_data.get('monthlyHourLimits', [])

for emp in employees:
    emp_id = emp['employeeId']
    scheme = emp.get('scheme', 'A')
    product_id = emp.get('productTypeId', '')
    local_flag = emp.get('local', 1)
    emp_type = 'Local' if local_flag == 1 else 'Foreigner'
    
    print(f"\nEmployee {emp_id}:")
    print(f"  Raw Scheme: '{scheme}'")
    print(f"  ProductTypeId: '{product_id}'")
    print(f"  Local flag: {local_flag} → {emp_type}")
    
    # Check which rules match
    print(f"\n  Checking against monthlyHourLimits rules:")
    
    for i, rule in enumerate(monthly_limits, 1):
        rule_id = rule.get('id', f'Rule {i}')
        applicable = rule.get('applicableTo', {})
        
        allowed_emp_type = applicable.get('employeeType', 'All')
        allowed_schemes = applicable.get('schemes', ['All'])
        allowed_products = applicable.get('productTypeIds', ['All'])
        
        # Normalize scheme for comparison
        scheme_normalized = scheme.replace('Scheme ', '')
        
        # Check matches
        emp_type_match = allowed_emp_type == 'All' or allowed_emp_type == emp_type
        scheme_match = 'All' in allowed_schemes or scheme_normalized in allowed_schemes
        product_match = 'All' in allowed_products or product_id in allowed_products
        
        matches = emp_type_match and scheme_match and product_match
        
        if matches or rule_id in ['SO_A', 'SO_B', 'APO_A', 'standardMonthlyHours']:
            status = '✅ MATCH' if matches else '❌ NO MATCH'
            print(f"\n    {status} - {rule_id}:")
            print(f"      EmployeeType: {allowed_emp_type} vs {emp_type} → {emp_type_match}")
            print(f"      Schemes: {allowed_schemes} vs {scheme_normalized} → {scheme_match}")
            print(f"      ProductTypes: {allowed_products} vs {product_id} → {product_match}")
            
            if matches:
                calc_method = rule.get('hourCalculationMethod')
                values_31 = rule.get('valuesByMonthLength', {}).get('31', {})
                print(f"      Calculation Method: {calc_method}")
                print(f"      minimumContractualHours: {values_31.get('minimumContractualHours')}h")
                print(f"      maxOvertimeHours: {values_31.get('maxOvertimeHours')}h")

print("\n\n2. EXPECTED vs ACTUAL RULE MATCHING")
print("-" * 80)

print("\nScheme A SO Foreigners (00100012, 00100014):")
print("  SHOULD match: SO_A (Local) rule - NO, they're Foreigners!")
print("  SHOULD match: SO_B (Foreigner) rule - NO, they're Scheme A!")
print("  ACTUALLY matches: standardMonthlyHours (All/All/All)")
print("  Calculation Method: dailyProrated (WRONG! Should be weeklyThreshold)")

print("\nScheme B SO Foreigners (00100008, 00100011):")
print("  SHOULD match: SO_B (Foreigner) rule - YES!")
print("  Rule configuration:")
for rule in monthly_limits:
    if rule.get('id') == 'SO_B':
        applicable = rule.get('applicableTo', {})
        if applicable.get('employeeType') == 'Foreigner':
            print(f"    EmployeeType: {applicable.get('employeeType')}")
            print(f"    Schemes: {applicable.get('schemes')}")
            print(f"    ProductTypeIds: {applicable.get('productTypeIds')}")
            print(f"    Calculation Method: {rule.get('hourCalculationMethod')}")
            values_31 = rule.get('valuesByMonthLength', {}).get('31', {})
            print(f"    minimumContractualHours (31 days): {values_31.get('minimumContractualHours')}h")

print("\n\n3. THE CORE PROBLEM")
print("-" * 80)

print("""
ISSUE: Missing rule for "Scheme A SO Foreigners"

The input file has:
✅ SO_A (Local) - weeklyThreshold, 195h contractual
✅ SO_B (Foreigner) - weeklyThreshold, 196h contractual  
✅ SO_B (Local) - weeklyThreshold, 196h contractual
❌ SO_A (Foreigner) - MISSING!

When Scheme A SO Foreigners don't match any specific rule, they fall back to:
  standardMonthlyHours (All/All/All)
    - Calculation Method: dailyProrated (WRONG!)
    - minimumContractualHours: 195h
    
The dailyProrated method divides contractual hours by calendar days:
  195h / 31 days = 6.29h per day
  
For a 12-hour shift:
  6.29h = normal
  5.71h = OT
  
But for 24 work days x 12h = 288h:
  Expected: 195h normal + 93h OT
  Actual: 219.98h normal + 68.02h OT (WRONG!)

The calculation is prorating incorrectly because dailyProrated is for 
employees who work every day, not 6-on-1-off patterns.

SOLUTION: Add this rule to monthlyHourLimits:
""")

print(json.dumps({
    "id": "SO_A",
    "description": "SO A - Foreigner weeklyThreshold hours",
    "enforcement": "hard",
    "applicableTo": {
        "employeeType": "Foreigner",
        "rankIds": ["All"],
        "schemes": ["A"],
        "productTypeIds": ["SO"]
    },
    "hourCalculationMethod": "weeklyThreshold",
    "valuesByMonthLength": {
        "28": {"maxOvertimeHours": 72, "minimumContractualHours": 176, "totalMaxHours": 248},
        "29": {"maxOvertimeHours": 72, "minimumContractualHours": 182, "totalMaxHours": 254},
        "30": {"maxOvertimeHours": 72, "minimumContractualHours": 189, "totalMaxHours": 262},
        "31": {"maxOvertimeHours": 72, "minimumContractualHours": 195, "totalMaxHours": 268}
    }
}, indent=2))

print("\n" + "=" * 80)
