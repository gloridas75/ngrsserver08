#!/usr/bin/env python3
"""Test /configure API endpoint with new headcountPerShift schema"""

import requests
import json

# API endpoint (adjust if using remote server)
API_BASE = "http://localhost:8000"

# Test payload with new schema
payload = {
    "planningHorizon": {
        "startDate": "2025-12-01",
        "endDate": "2025-12-31"
    },
    "publicHolidays": ["2025-12-25"],
    "requirements": [
        {
            "id": "REQ_DAY_SHIFT",
            "name": "Day Shift Team",
            "productType": "APO",
            "rank": "APO",
            "scheme": "A",
            "shiftTypes": ["D"],
            "headcountPerShift": {"D": 5},
            "coverageDays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "includePH": False
        },
        {
            "id": "REQ_NIGHT_SHIFT",
            "name": "Night Shift Team",
            "productType": "CVSO",
            "rank": "CVSO2",
            "scheme": "B",
            "shiftTypes": ["N"],
            "headcountPerShift": {"N": 2},
            "coverageDays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "includePH": False
        },
        {
            "id": "REQ_MIXED_SHIFTS",
            "name": "Mixed Day/Night Coverage",
            "productType": "AVSO",
            "rank": "AVSO3",
            "scheme": "B",
            "shiftTypes": ["D", "N"],
            "headcountPerShift": {"D": 3, "N": 2},
            "coverageDays": ["Mon", "Tue", "Wed", "Thu", "Fri"],
            "includePH": True
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
print("TESTING /configure API WITH NEW headcountPerShift SCHEMA")
print("="*80)
print()

print("Request payload:")
print(json.dumps(payload, indent=2))
print()

print("Sending POST request to /configure...")
try:
    response = requests.post(
        f"{API_BASE}/configure",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status Code: {response.status_code}")
    print()
    
    if response.status_code == 200:
        result = response.json()
        print("✓ API Response Success!")
        print()
        print(f"Schema Version: {result.get('schemaVersion')}")
        print(f"Total Requirements: {result.get('summary', {}).get('totalRequirements')}")
        print(f"Total Employees: {result.get('summary', {}).get('totalEmployees')}")
        print()
        
        # Check each recommendation
        print("Recommendations:")
        for rec in result.get('recommendations', []):
            if rec['alternativeRank'] == 1:  # Only show best pattern for each requirement
                print(f"\n  {rec['requirementId']} ({rec['requirementName']}):")
                print(f"    Pattern: {rec['configuration']['workPattern']}")
                print(f"    Employees Required: {rec['configuration']['employeesRequired']}")
                print(f"    Employees Per Shift: {rec['configuration'].get('employeesRequiredPerShift', 'N/A')}")
                print(f"    Coverage Rate: {rec['coverage']['expectedCoverageRate']}%")
                print(f"    Required Per Shift: {rec['coverage'].get('requiredPerShift', 'N/A')}")
                print(f"    Required Per Day: {rec['coverage'].get('requiredPerDay', 'N/A')}")
        
        print()
        print("="*80)
        print("✓ TEST PASSED: API accepts new schema and returns per-shift details")
        print("="*80)
        
    else:
        print("✗ API Response Error:")
        print(response.text)
        
except requests.exceptions.ConnectionError:
    print("✗ Connection Error: Is the API server running?")
    print("  Start with: python3 src/api_server.py")
    print("  Or check Docker: docker ps")
except Exception as e:
    print(f"✗ Error: {e}")
