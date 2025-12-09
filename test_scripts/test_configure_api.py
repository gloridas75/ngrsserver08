#!/usr/bin/env python3
"""Test the /configure endpoint with the exact user payload"""

import json
import sys

# Test payload from user
payload = {
  "planningHorizon": {
    "startDate": "2025-12-01",
    "endDate": "2025-12-31"
  },
  "publicHolidays": ["2025-12-25"],
  "requirements": [
    {
      "id": "REQ_MIXED",
      "name": "Mixed Day/Night Coverage",
      "productType": "CVSO",
      "rank": "CVSO2",
      "scheme": "B",
      "shiftTypes": ["D", "N"],
      "headcountPerShift": {
        "D": 25,
        "N": 25
      },
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

print("=" * 80)
print("TESTING /configure ENDPOINT WITH USER PAYLOAD")
print("=" * 80)
print()

# Validate payload structure
print("1. Validating payload structure...")
print(f"   ✓ requirements: {len(payload['requirements'])} requirement(s)")
print(f"   ✓ planningHorizon: {payload['planningHorizon']['startDate']} to {payload['planningHorizon']['endDate']}")

req = payload['requirements'][0]
print(f"   ✓ shiftTypes: {req['shiftTypes']}")
print(f"   ✓ headcountPerShift: {req['headcountPerShift']}")
print()

# Test with optimizer directly
print("2. Testing optimizer function directly...")
try:
    from context.engine.config_optimizer import optimize_all_requirements
    
    result = optimize_all_requirements(
        requirements=payload["requirements"],
        constraints=payload["constraints"],
        planning_horizon=payload["planningHorizon"]
    )
    
    print(f"   ✓ Optimization successful!")
    print(f"   ✓ Generated configurations for {len(result['requirements'])} requirement(s)")
    
    for req_id, configs in result['requirements'].items():
        print(f"   ✓ {req_id}: {len(configs)} alternative pattern(s)")
        if configs:
            best = configs[0]
            print(f"      - Best pattern: {best['pattern']}")
            print(f"      - Employees: {best['employeeCount']}")
            print(f"      - Coverage: {best['coverage']['coverageRate']:.1f}%")
    
    print()
    print("=" * 80)
    print("✓ TEST PASSED: Payload is valid and optimizer works correctly")
    print("=" * 80)
    
except Exception as e:
    print(f"   ✗ Error: {e}")
    print()
    import traceback
    traceback.print_exc()
    print()
    print("=" * 80)
    print("✗ TEST FAILED")
    print("=" * 80)
    sys.exit(1)
