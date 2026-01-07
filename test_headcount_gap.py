"""
Test headcount gap handling in template mode.

Verifies that when headcount > available employees,
UNASSIGNED slots are created to show the gap.
"""

import json

# Create test input with headcount=10, employees=3
test_input = {
    "schemaVersion": "0.95",
    "planningReference": {
        "scheme": "SchemeA",
        "planId": "TEST-HEADCOUNT-GAP",
        "createdDate": "2024-06-01"
    },
    "planningHorizon": {
        "startDate": "2024-06-01",
        "endDate": "2024-06-07"  # 1 week
    },
    "solverConfig": {
        "maxSolveTimeSeconds": 10,
        "optimizationMode": "minimizeEmployeeCount"
    },
    "employees": [
        {
            "employeeId": "EMP001",
            "ouId": "OU-A",
            "rank": "SGT",
            "employmentScheme": "SchemeA",
            "rotationOffset": 0
        },
        {
            "employeeId": "EMP002",
            "ouId": "OU-A",
            "rank": "SGT",
            "employmentScheme": "SchemeA",
            "rotationOffset": 1
        },
        {
            "employeeId": "EMP003",
            "ouId": "OU-A",
            "rank": "SGT",
            "employmentScheme": "SchemeA",
            "rotationOffset": 2
        }
    ],
    "demandItems": [
        {
            "id": "DEM-01",  # Use 'id' instead of 'demandId' for v0.95 schema
            "demandId": "DEM-01",
            "positionId": "SECURITY-OFFICER",
            "locationId": "SITE-A",
            "rosteringBasis": "outcomeBased",  # Key field for routing
            "templateGenerationMode": "cpsat",
            "shiftStartDate": "2024-06-01",
            "shiftEndDate": "2024-06-07",
            "shifts": [
                {
                    "coverageDays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                    "shiftDetails": [
                        {
                            "shiftCode": "D",
                            "startTime": "08:00",
                            "endTime": "20:00"
                        }
                    ]
                }
            ],
            "requirements": [  # Use 'requirements' not 'workRequirements'
                {
                    "id": "REQ-01",
                    "requirementId": "REQ-01",
                    "demandId": "DEM-01",
                    "requiredEmployeeCount": 3,
                    "minRank": "SGT",
                    "headcount": 10,  # ← KEY: Request 10 positions with only 3 employees
                    "workPattern": ["D", "D", "D", "D", "D", "D", "D"],
                    "rotationPatternName": "7D-CONTINUOUS",
                    "positionId": "SECURITY-OFFICER",
                    "locationId": "SITE-A"
                }
            ]
        }
    ],
    "constraintList": [
        {"constraintId": "C1", "enabled": True},
        {"constraintId": "C2", "enabled": True}
    ]
}

# Save test input
with open("input/test_headcount_gap.json", "w") as f:
    json.dump(test_input, f, indent=2)

print("=" * 80)
print("TEST CASE: Headcount Gap in Template Mode")
print("=" * 80)
print(f"\nTest input created: input/test_headcount_gap.json")
print(f"\nSetup:")
print(f"  - headcount: 10 (positions required per day)")
print(f"  - employees: 3 (available)")
print(f"  - templateGenerationMode: cpsat")
print(f"\nExpected Result:")
print(f"  - ASSIGNED: ~21 assignments (3 employees × 7 days)")
print(f"  - UNASSIGNED: ~49 slots (7 employees × 7 days gap)")
print(f"  - Total: ~70 assignments (10 positions × 7 days)")
print(f"\nRun test:")
print(f"  python src/run_solver.py --in input/test_headcount_gap.json --time 10")
print("=" * 80)
