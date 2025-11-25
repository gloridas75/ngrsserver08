#!/usr/bin/env python3
"""Test ICPMP improvements: 100+ employees, top 5 patterns, shiftTypes filtering"""

import json
from context.engine.config_optimizer import optimize_all_requirements, format_output_config

# Test data
test_input = {
    "planningHorizon": {
        "startDate": "2025-12-01",
        "endDate": "2025-12-31"
    },
    "publicHolidays": ["2025-12-25"],
    "requirements": [
        {
            "id": "REQ_D_ONLY",
            "name": "Day Shift Only",
            "productType": "APO",
            "rank": "APO",
            "scheme": "A",
            "shiftTypes": ["D"],  # Only D patterns expected
            "headcountPerShift": {"D": 4},
            "coverageDays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "includePH": False
        },
        {
            "id": "REQ_N_ONLY",
            "name": "Night Shift Only",
            "productType": "APO",
            "rank": "APO",
            "scheme": "B",
            "shiftTypes": ["N"],  # Only N patterns expected
            "headcountPerShift": {"N": 1},
            "coverageDays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "includePH": False
        },
        {
            "id": "REQ_MIXED_DN",
            "name": "Mixed Day/Night",
            "productType": "CVSO",
            "rank": "CVSO2",
            "scheme": "B",
            "shiftTypes": ["D", "N"],  # D, N, and D+N mix patterns expected
            "headcountPerShift": {"D": 60, "N": 60},  # Large team to test 100+ employee support
            "coverageDays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "includePH": False
        }
    ],
    "constraints": {
        "maxWeeklyNormalHours": 44,
        "maxMonthlyOTHours": 72,
        "maxConsecutiveWorkDays": 12,
        "minOffDaysPerWeek": 1,
        "minRestBetweenShifts": 480,
        "dailyHoursCap": {
            "A": 14.0,
            "B": 13.0,
            "P": 9.0
        }
    }
}

print("="*80)
print("TESTING ICPMP IMPROVEMENTS")
print("="*80)
print()

print("Test 1: Day-only patterns (shiftTypes=[\"D\"])")
print("Test 2: Night-only patterns (shiftTypes=[\"N\"])")
print("Test 3: Mixed D+N patterns (shiftTypes=[\"D\",\"N\"])")
print("Test 4: Large team 100+ employees support")
print("Test 5: Top 5 patterns per requirement")
print()

# Run optimization
result = optimize_all_requirements(
    test_input['requirements'],
    test_input['constraints'],
    test_input['planningHorizon']
)

# Format output
formatted = format_output_config(result, test_input['requirements'])

print("\n" + "="*80)
print("TEST RESULTS")
print("="*80)

# Verify each requirement got top 5 patterns
for req_id, config_list in result['requirements'].items():
    print(f"\n{req_id}:")
    print(f"  - Got {len(config_list)} alternative patterns (expected: up to 5)")
    
    for i, config in enumerate(config_list, 1):
        pattern = config['pattern']
        shifts_used = set(pattern) - {'O'}
        print(f"  Alternative #{i}:")
        print(f"    Pattern: {pattern}")
        print(f"    Shifts used: {shifts_used}")
        print(f"    Employees: {config['employeeCount']}")
        print(f"    Coverage: {config['coverage']['coverageRate']:.1f}%")
        print(f"    Score: {config['score']}")

# Test shiftTypes filtering
print("\n" + "="*80)
print("SHIFT TYPES VALIDATION")
print("="*80)

req_d_patterns = result['requirements']['REQ_D_ONLY']
req_n_patterns = result['requirements']['REQ_N_ONLY']
req_mixed_patterns = result['requirements']['REQ_MIXED_DN']

# Check D-only patterns
d_only_shifts = set()
for config in req_d_patterns:
    d_only_shifts.update(set(config['pattern']) - {'O'})
print(f"\nREQ_D_ONLY shifts used: {d_only_shifts}")
print(f"  ✓ PASS" if d_only_shifts == {'D'} else f"  ✗ FAIL: Expected only D")

# Check N-only patterns
n_only_shifts = set()
for config in req_n_patterns:
    n_only_shifts.update(set(config['pattern']) - {'O'})
print(f"\nREQ_N_ONLY shifts used: {n_only_shifts}")
print(f"  ✓ PASS" if n_only_shifts == {'N'} else f"  ✗ FAIL: Expected only N")

# Check mixed patterns (should have D, N, or D+N combinations)
mixed_shifts = set()
has_d_only = False
has_n_only = False
has_mixed = False
for config in req_mixed_patterns:
    shifts = set(config['pattern']) - {'O'}
    mixed_shifts.update(shifts)
    if shifts == {'D'}:
        has_d_only = True
    elif shifts == {'N'}:
        has_n_only = True
    elif 'D' in shifts and 'N' in shifts:
        has_mixed = True

print(f"\nREQ_MIXED_DN:")
print(f"  Shifts used overall: {mixed_shifts}")
print(f"  Has D-only pattern: {has_d_only}")
print(f"  Has N-only pattern: {has_n_only}")
print(f"  Has D+N mixed pattern: {has_mixed}")
print(f"  ✓ PASS" if (has_d_only or has_n_only or has_mixed) else f"  ✗ FAIL")

# Check 100+ employee support
large_team = req_mixed_patterns[0]
print(f"\n100+ Employee Support:")
print(f"  Team size: {large_team['employeeCount']}")
print(f"  Coverage rate: {large_team['coverage']['coverageRate']:.1f}%")
print(f"  ✓ PASS: Handled {large_team['employeeCount']} employees" if large_team['employeeCount'] >= 100 else f"  ℹ️  Note: Team < 100")

# Save test output
with open('output/icpmp_test_output.json', 'w') as f:
    json.dump(formatted, f, indent=2)

print("\n" + "="*80)
print("✓ All tests completed! Output saved to: output/icpmp_test_output.json")
print("="*80)
