"""
Test file for Assignment Validation API - Phase 1

Tests employee-specific hard constraints:
- C1: Daily Hours Cap
- C2: Weekly Hours Cap
- C3: Consecutive Working Days
- C4: Rest Period Between Shifts
- C17: Monthly OT Cap

Run tests:
    python test_assignment_validation.py
    
Or with curl:
    curl -X POST http://localhost:8080/validate/assignment \
      -H "Content-Type: application/json" \
      -d @test_assignment_validation.json
"""

import json
import requests
from datetime import datetime, timedelta


# ============================================================================
# TEST DATA
# ============================================================================

def generate_test_case_feasible():
    """Test Case 1: Valid assignment - no violations."""
    return {
        "employee": {
            "employeeId": "EMP001",
            "name": "John Tan",
            "rank": "SO",
            "gender": "M",
            "scheme": "A",
            "productTypes": ["Guarding", "Patrolling"],
            "workPattern": "DDNNOOO",
            "rotationOffset": 2
        },
        "existingAssignments": [
            {
                "assignmentId": "assign_001",
                "slotId": "slot_001",
                "startDateTime": "2026-01-13T07:00:00+08:00",
                "endDateTime": "2026-01-13T15:00:00+08:00",
                "shiftType": "DAY",
                "hours": 8.0,
                "date": "2026-01-13"
            },
            {
                "assignmentId": "assign_002",
                "slotId": "slot_002",
                "startDateTime": "2026-01-14T07:00:00+08:00",
                "endDateTime": "2026-01-14T15:00:00+08:00",
                "shiftType": "DAY",
                "hours": 8.0,
                "date": "2026-01-14"
            }
        ],
        "candidateSlots": [
            {
                "slotId": "slot_unassigned_456",
                "demandItemId": "DI005",
                "requirementId": "REQ_R1",
                "startDateTime": "2026-01-16T07:00:00+08:00",
                "endDateTime": "2026-01-16T15:00:00+08:00",
                "shiftType": "DAY",
                "productType": "Guarding",
                "rank": "SO",
                "scheme": "A"
            }
        ],
        "planningReference": {
            "startDate": "2026-01-01",
            "endDate": "2026-01-31",
            "ouName": "Security Division"
        },
        "constraintList": [
            {"constraintId": "C1", "enabled": True},
            {"constraintId": "C2", "enabled": True},
            {"constraintId": "C3", "enabled": True},
            {"constraintId": "C4", "enabled": True},
            {"constraintId": "C17", "enabled": True}
        ]
    }


def generate_test_case_c1_violation():
    """Test Case 2: C1 violation - shift exceeds daily cap."""
    return {
        "employee": {
            "employeeId": "EMP002",
            "name": "Sarah Lee",
            "rank": "SO",
            "gender": "F",
            "scheme": "P",  # Scheme P has 9h daily cap
            "productTypes": ["Guarding"],
            "workPattern": "DDNNOOO",
            "rotationOffset": 0
        },
        "existingAssignments": [],
        "candidateSlots": [
            {
                "slotId": "slot_long_shift",
                "startDateTime": "2026-01-15T07:00:00+08:00",
                "endDateTime": "2026-01-15T19:00:00+08:00",  # 12 hours - exceeds 9h cap for Scheme P
                "shiftType": "DAY",
                "productType": "Guarding",
                "rank": "SO",
                "scheme": "P"
            }
        ],
        "constraintList": [
            {"constraintId": "C1", "enabled": True}
        ]
    }


def generate_test_case_c2_violation():
    """Test Case 3: C2 violation - exceeds weekly hours cap."""
    base_date = datetime(2026, 1, 13)  # Monday
    
    # Create assignments for Mon-Fri (5 days × 10h = 50h normal hours)
    existing = []
    for i in range(5):
        date = base_date + timedelta(days=i)
        existing.append({
            "startDateTime": f"{date.strftime('%Y-%m-%d')}T07:00:00+08:00",
            "endDateTime": f"{date.strftime('%Y-%m-%d')}T18:00:00+08:00",  # 11h shifts
            "shiftType": "DAY",
            "hours": 11.0,
            "date": date.strftime('%Y-%m-%d')
        })
    
    # Try to add another 11h shift on Saturday (would push week total to 61h)
    return {
        "employee": {
            "employeeId": "EMP003",
            "name": "David Wong",
            "rank": "SO",
            "gender": "M",
            "scheme": "A",
            "productTypes": ["Guarding"]
        },
        "existingAssignments": existing,
        "candidateSlots": [
            {
                "slotId": "slot_saturday",
                "startDateTime": "2026-01-18T07:00:00+08:00",  # Saturday
                "endDateTime": "2026-01-18T18:00:00+08:00",
                "shiftType": "DAY",
                "productType": "Guarding",
                "rank": "SO",
                "scheme": "A"
            }
        ],
        "constraintList": [
            {"constraintId": "C2", "enabled": True}
        ]
    }


def generate_test_case_c4_violation():
    """Test Case 4: C4 violation - insufficient rest between shifts."""
    return {
        "employee": {
            "employeeId": "EMP004",
            "name": "Amy Lim",
            "rank": "SO",
            "gender": "F",
            "scheme": "A",
            "productTypes": ["Guarding"]
        },
        "existingAssignments": [
            {
                "startDateTime": "2026-01-15T07:00:00+08:00",
                "endDateTime": "2026-01-15T19:00:00+08:00",  # Ends 7pm
                "shiftType": "DAY",
                "hours": 12.0,
                "date": "2026-01-15"
            }
        ],
        "candidateSlots": [
            {
                "slotId": "slot_next_morning",
                "startDateTime": "2026-01-16T05:00:00+08:00",  # Starts 5am (only 10h rest)
                "endDateTime": "2026-01-16T13:00:00+08:00",
                "shiftType": "DAY",
                "productType": "Guarding",
                "rank": "SO",
                "scheme": "A"
            }
        ],
        "constraintList": [
            {"constraintId": "C4", "enabled": True}
        ]
    }


def generate_test_case_multiple_slots():
    """Test Case 5: Validate multiple slots at once."""
    return {
        "employee": {
            "employeeId": "EMP005",
            "name": "Michael Chen",
            "rank": "SO",
            "gender": "M",
            "scheme": "A",
            "productTypes": ["Guarding", "Patrolling"]
        },
        "existingAssignments": [
            {
                "startDateTime": "2026-01-13T07:00:00+08:00",
                "endDateTime": "2026-01-13T15:00:00+08:00",
                "shiftType": "DAY",
                "hours": 8.0,
                "date": "2026-01-13"
            }
        ],
        "candidateSlots": [
            {
                "slotId": "slot_good_1",
                "startDateTime": "2026-01-15T07:00:00+08:00",
                "endDateTime": "2026-01-15T15:00:00+08:00",
                "shiftType": "DAY",
                "productType": "Guarding"
            },
            {
                "slotId": "slot_good_2",
                "startDateTime": "2026-01-17T07:00:00+08:00",
                "endDateTime": "2026-01-17T15:00:00+08:00",
                "shiftType": "DAY",
                "productType": "Patrolling"
            },
            {
                "slotId": "slot_too_long",
                "startDateTime": "2026-01-19T07:00:00+08:00",
                "endDateTime": "2026-01-19T22:00:00+08:00",  # 15h - exceeds 14h cap
                "shiftType": "DAY",
                "productType": "Guarding"
            }
        ],
        "constraintList": [
            {"constraintId": "C1", "enabled": True},
            {"constraintId": "C4", "enabled": True}
        ]
    }


# ============================================================================
# TEST RUNNER
# ============================================================================

def run_test(test_name: str, test_data: dict, api_url: str = "http://localhost:8080/validate/assignment"):
    """Run a single test case."""
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"{'='*80}")
    
    try:
        # Send request
        response = requests.post(api_url, json=test_data, timeout=10)
        
        # Parse response
        result = response.json()
        
        print(f"Status Code: {response.status_code}")
        print(f"Employee ID: {result.get('employeeId')}")
        print(f"Processing Time: {result.get('processingTimeMs')}ms")
        print(f"\nValidation Results:")
        
        for slot_result in result.get('validationResults', []):
            print(f"\n  Slot ID: {slot_result['slotId']}")
            print(f"  Feasible: {slot_result['isFeasible']}")
            print(f"  Recommendation: {slot_result['recommendation']}")
            
            if slot_result['violations']:
                print(f"  Violations ({len(slot_result['violations'])}):")
                for violation in slot_result['violations']:
                    print(f"    - [{violation['constraintId']}] {violation['constraintName']}")
                    print(f"      {violation['description']}")
                    if violation.get('context'):
                        print(f"      Context: {json.dumps(violation['context'], indent=8)}")
            else:
                print(f"  ✓ No violations")
        
        return result
        
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Could not connect to API at {api_url}")
        print(f"Make sure the server is running: uvicorn src.api_server:app --reload --port 8080")
        return None
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return None


def run_all_tests():
    """Run all test cases."""
    print("\n" + "="*80)
    print("ASSIGNMENT VALIDATION API - TEST SUITE")
    print("="*80)
    
    tests = [
        ("Feasible Assignment", generate_test_case_feasible()),
        ("C1 Violation - Daily Hours Exceeded", generate_test_case_c1_violation()),
        ("C2 Violation - Weekly Hours Exceeded", generate_test_case_c2_violation()),
        ("C4 Violation - Insufficient Rest", generate_test_case_c4_violation()),
        ("Multiple Slots Validation", generate_test_case_multiple_slots()),
    ]
    
    results = []
    for test_name, test_data in tests:
        result = run_test(test_name, test_data)
        results.append((test_name, result))
    
    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    
    for test_name, result in results:
        if result:
            status = "✓ PASSED" if result.get('status') == 'success' else "✗ FAILED"
            print(f"{status} - {test_name}")
        else:
            print(f"✗ ERROR - {test_name}")


def save_sample_request():
    """Save a sample request as JSON file for curl testing."""
    test_data = generate_test_case_feasible()
    
    with open('test_assignment_validation.json', 'w') as f:
        json.dump(test_data, f, indent=2)
    
    print("\n✓ Sample request saved to: test_assignment_validation.json")
    print("\nTest with curl:")
    print("  curl -X POST http://localhost:8080/validate/assignment \\")
    print("    -H 'Content-Type: application/json' \\")
    print("    -d @test_assignment_validation.json")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--save':
        save_sample_request()
    else:
        run_all_tests()
