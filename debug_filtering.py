#!/usr/bin/env python3
"""Debug script to trace employee filtering for requirement 57_1"""

import sys
sys.path.insert(0, '.')

import json
from context.engine.slot_builder import build_slots

# Load input
with open('/Users/glori/Downloads/RST-20251208-3B20055D_Solver_Input.json') as f:
    inputs = json.load(f)

# Build slots
slots = build_slots(inputs)
employees = inputs['employees']

# Get first slot for requirement 57_1
req_57_1_slots = [s for s in slots if '57_1' in s.slot_id]
if not req_57_1_slots:
    print("No slots found for requirement 57_1!")
    sys.exit(1)

slot = req_57_1_slots[0]
print(f"Analyzing slot: {slot.slot_id}")
print(f"  productTypeId: '{slot.productTypeId}'")
print(f"  rankId: '{slot.rankId}'")
print(f"  schemeRequirement: '{slot.schemeRequirement}'")
print(f"  genderRequirement: '{slot.genderRequirement}'")
print(f"  whitelist: {slot.whitelist}")
print(f"  blacklist: {slot.blacklist}")
print()

# Check each Scheme P employee
scheme_p_employees = [e for e in employees if e.get('scheme') == 'P']
print(f"Testing {len(scheme_p_employees)} Scheme P employees:")
print()

for emp in scheme_p_employees:
    emp_id = emp.get('employeeId')
    print(f"Employee {emp_id}:")
    print(f"  productTypeId: '{emp.get('productTypeId')}'")
    print(f"  rankId: '{emp.get('rankId')}'")
    print(f"  scheme: '{emp.get('scheme')}'")
    print(f"  gender: '{emp.get('gender')}'")
    print(f"  teamId: '{emp.get('teamId', 'NO TEAM')}'")
    
    # Simulate filtering logic
    reasons = []
    
    # 1. Product type check
    slot_product = slot.productTypeId
    emp_product = emp.get('productTypeId', '')
    if slot_product and emp_product != slot_product:
        reasons.append(f"❌ Product type mismatch: slot='{slot_product}' vs emp='{emp_product}'")
    else:
        reasons.append(f"✅ Product type match: '{emp_product}'")
    
    # 2. Rank check
    slot_rank = slot.rankId
    emp_rank = emp.get('rankId', '')
    if slot_rank and emp_rank != slot_rank:
        reasons.append(f"❌ Rank mismatch: slot='{slot_rank}' vs emp='{emp_rank}'")
    else:
        reasons.append(f"✅ Rank match: '{emp_rank}'")
    
    # 3. Gender check
    gender_req = slot.genderRequirement
    emp_gender = emp.get('gender', 'Unknown')
    if gender_req == 'M' and emp_gender != 'M':
        reasons.append(f"❌ Gender mismatch: need M, got {emp_gender}")
    elif gender_req == 'F' and emp_gender != 'F':
        reasons.append(f"❌ Gender mismatch: need F, got {emp_gender}")
    else:
        reasons.append(f"✅ Gender allowed: req='{gender_req}', emp='{emp_gender}'")
    
    # 4. Scheme check
    scheme_req = slot.schemeRequirement
    emp_scheme = emp.get('scheme', '')
    if scheme_req != 'Global' and scheme_req != emp_scheme:
        reasons.append(f"❌ Scheme mismatch: slot='{scheme_req}' vs emp='{emp_scheme}'")
    else:
        reasons.append(f"✅ Scheme match: req='{scheme_req}', emp='{emp_scheme}'")
    
    # 5. Blacklist check
    blacklist = slot.blacklist
    is_blacklisted = False
    if blacklist and 'employeeIds' in blacklist:
        if emp_id in [str(bl) for bl in blacklist.get('employeeIds', [])]:
            is_blacklisted = True
    if is_blacklisted:
        reasons.append(f"❌ Employee is blacklisted")
    else:
        reasons.append(f"✅ Not blacklisted")
    
    # 6. Whitelist check
    whitelist = slot.whitelist
    has_whitelist_constraints = any(whitelist.get(k) for k in ['employeeIds', 'teamIds'])
    
    if has_whitelist_constraints:
        is_whitelisted = False
        if whitelist.get('employeeIds') and emp_id in whitelist['employeeIds']:
            is_whitelisted = True
        elif whitelist.get('teamIds') and emp.get('teamId') in whitelist['teamIds']:
            is_whitelisted = True
        
        if is_whitelisted:
            reasons.append(f"✅ Employee is whitelisted")
        else:
            reasons.append(f"❌ Employee not in whitelist (required)")
    else:
        reasons.append(f"✅ No whitelist constraints")
    
    # Print results
    for reason in reasons:
        print(f"  {reason}")
    
    # Final verdict
    all_passed = all('✅' in r for r in reasons)
    print(f"  {'=' * 50}")
    if all_passed:
        print(f"  ✅✅ SHOULD CREATE VARIABLE for {emp_id}")
    else:
        print(f"  ❌❌ SHOULD SKIP {emp_id}")
    print()
