#!/usr/bin/env python
"""
Analyze RST-20260301-F9EA0EDE output for gaps and hour calculation issues
"""
import json
from collections import defaultdict
from datetime import datetime, timedelta

# Load files
with open('input/RST-20260301-F9EA0EDE_Solver_Output.json', 'r') as f:
    output = json.load(f)

with open('input/RST-20260301-F9EA0EDE_Solver_Input.json', 'r') as f:
    input_data = json.load(f)

print("=" * 80)
print("ISSUE 1: UNASSIGNED SLOTS / GAPS IN ASSIGNMENTS")
print("=" * 80)

assignments = output.get('assignments', [])
employee_roster = output.get('employeeRoster', [])

# Group assignments by employee
emp_assignments = defaultdict(list)
for a in assignments:
    emp_id = a.get('employeeId')
    if emp_id and a.get('status') == 'ASSIGNED':
        emp_assignments[emp_id].append(a)

# Check each employee's roster
employees = {emp['employeeId']: emp for emp in input_data.get('employees', [])}

for emp_id in sorted(employees.keys()):
    emps = emp_assignments[emp_id]
    
    if not emps:
        print(f"\nEmployee {emp_id}: NO ASSIGNMENTS")
        continue
    
    # Sort by date
    emps.sort(key=lambda x: x.get('date', ''))
    
    dates = [a.get('date') for a in emps]
    date_objs = [datetime.fromisoformat(d).date() for d in dates]
    
    print(f"\nEmployee {emp_id}:")
    print(f"  Assigned days: {len(emps)}")
    print(f"  Date range: {date_objs[0]} to {date_objs[-1]}")
    
    # Check for gaps (days in between with no assignment)
    gaps = []
    for i in range(len(date_objs) - 1):
        current = date_objs[i]
        next_date = date_objs[i + 1]
        expected = current + timedelta(days=1)
        
        if next_date != expected:
            gap_days = (next_date - current).days - 1
            # List the missing dates
            missing = []
            check_date = current + timedelta(days=1)
            while check_date < next_date:
                missing.append(check_date)
                check_date += timedelta(days=1)
            gaps.append((current, next_date, missing))
    
    if gaps:
        print(f"  ⚠️  GAPS FOUND: {len(gaps)} gaps, {sum(len(g[2]) for g in gaps)} missing days")
        for start, end, missing in gaps[:3]:
            print(f"    After {start} → Missing: {', '.join(str(d) for d in missing[:5])}")
    
    # Check employee roster for these employees
    emp_roster = None
    for roster in employee_roster:
        if roster.get('employeeId') == emp_id:
            emp_roster = roster
            break
    
    if emp_roster:
        daily_status = emp_roster.get('dailyStatus', [])
        unassigned_count = sum(1 for d in daily_status if d.get('status') == 'UNASSIGNED')
        off_days = sum(1 for d in daily_status if d.get('status') == 'OFF_DAY')
        
        print(f"  Daily status breakdown:")
        print(f"    UNASSIGNED: {unassigned_count} days")
        print(f"    OFF_DAY: {off_days} days")

print("\n" + "=" * 80)
print("ISSUE 2: NORMAL HOURS EXCEEDING minimumContractualHours")
print("=" * 80)

# Get expected contractual hours for each employee
monthly_limits = input_data.get('monthlyHourLimits', [])

for emp_id in sorted(employees.keys()):
    emp = employees[emp_id]
    scheme = emp.get('scheme', 'A')
    product_id = emp.get('productTypeId', '')
    local_flag = emp.get('local', 1)
    emp_type = 'Local' if local_flag == 1 else 'Foreigner'
    
    # Find matching monthlyHourLimits rule
    matched_rule = None
    for rule in monthly_limits:
        applicable = rule.get('applicableTo', {})
        
        # Check employeeType
        allowed_emp_type = applicable.get('employeeType', 'All')
        if allowed_emp_type != 'All' and allowed_emp_type != emp_type:
            continue
        
        # Check schemes
        allowed_schemes = applicable.get('schemes', ['All'])
        scheme_normalized = scheme.replace('Scheme ', '')
        if 'All' not in allowed_schemes and scheme_normalized not in allowed_schemes:
            continue
        
        # Check productTypes
        allowed_products = applicable.get('productTypeIds', ['All'])
        if 'All' not in allowed_products and product_id not in allowed_products:
            continue
        
        matched_rule = rule
        break
    
    # Get 31-day month limits (July has 31 days)
    expected_contractual = None
    max_ot = None
    calc_method = None
    
    if matched_rule:
        values_31 = matched_rule.get('valuesByMonthLength', {}).get('31', {})
        expected_contractual = values_31.get('minimumContractualHours')
        max_ot = values_31.get('maxOvertimeHours')
        calc_method = matched_rule.get('hourCalculationMethod')
        rule_id = matched_rule.get('id')
    
    # Calculate actual hours
    emps = emp_assignments[emp_id]
    total_normal = sum(a.get('hours', {}).get('normal', 0) for a in emps)
    total_ot = sum(a.get('hours', {}).get('ot', 0) for a in emps)
    total_gross = sum(a.get('hours', {}).get('gross', 0) for a in emps)
    
    print(f"\nEmployee {emp_id} ({emp_type}, {scheme}, {product_id}):")
    print(f"  Matched Rule: {rule_id if matched_rule else 'None - using default'}")
    print(f"  Calculation Method: {calc_method}")
    print(f"  Expected minimumContractualHours: {expected_contractual}h")
    print(f"  Expected maxOvertimeHours: {max_ot}h")
    print(f"  Actual Normal Hours: {total_normal:.2f}h")
    print(f"  Actual OT Hours: {total_ot:.2f}h")
    print(f"  Total Gross Hours: {total_gross:.2f}h")
    
    if expected_contractual and total_normal > expected_contractual:
        excess = total_normal - expected_contractual
        print(f"  ❌ ISSUE: Normal hours EXCEED contractual by {excess:.2f}h")
        print(f"      This suggests hour calculation is not classifying excess as OT")

print("\n" + "=" * 80)
print("ROOT CAUSE ANALYSIS")
print("=" * 80)

# Check work pattern
demand_items = input_data.get('demandItems', [])
if demand_items:
    req = demand_items[0].get('requirements', [{}])[0]
    work_pattern = req.get('workPattern', [])
    print(f"\nWork Pattern: {work_pattern}")
    print(f"Pattern length: {len(work_pattern)} days")
    work_days = sum(1 for d in work_pattern if d != 'O')
    off_days = sum(1 for d in work_pattern if d == 'O')
    print(f"Work days per cycle: {work_days}")
    print(f"Off days per cycle: {off_days}")
    
    # Calculate expected days in July
    print(f"\nJuly 2026 = 31 days")
    print(f"Pattern cycles: {31 / len(work_pattern):.2f} cycles")
    print(f"Expected work days: ~{int(31 * work_days / len(work_pattern))} days")
    print(f"Expected off days: ~{int(31 * off_days / len(work_pattern))} days")

print("\n" + "=" * 80)
