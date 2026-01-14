#!/usr/bin/env python3
"""Test assignment validator with violation cases."""

import json
from datetime import datetime, timedelta
from src.assignment_validator import AssignmentValidator
from src.models import ValidateAssignmentRequest

def test_c1_violation():
    """Test C1: Daily hours cap violation (Scheme P)."""
    test_data = {
        "employee": {
            "employeeId": "EMP002",
            "name": "Sarah Lee",
            "rank": "SO",
            "gender": "F",
            "scheme": "P"  # 9h daily cap
        },
        "existingAssignments": [],
        "candidateSlots": [
            {
                "slotId": "slot_long_shift",
                "startDateTime": "2026-01-15T07:00:00+08:00",
                "endDateTime": "2026-01-15T19:00:00+08:00",  # 12 hours
                "shiftType": "DAY"
            }
        ]
    }
    
    print("\n" + "="*80)
    print("TEST 1: C1 VIOLATION - Daily Hours Cap (Scheme P)")
    print("="*80)
    print("Employee: EMP002 (Scheme P - 9h cap)")
    print("Candidate Slot: 12h shift (SHOULD FAIL)")
    
    request = ValidateAssignmentRequest(**test_data)
    validator = AssignmentValidator()
    response = validator.validate(request)
    
    result = response.validationResults[0]
    print(f"\nResult: {result.isFeasible}")
    print(f"Processing Time: {response.processingTimeMs:.2f}ms")
    
    if result.violations:
        print(f"\n✓ EXPECTED VIOLATION DETECTED:")
        for v in result.violations:
            print(f"  [{v.constraintId}] {v.constraintName}")
            print(f"  {v.description}")
    else:
        print("✗ ERROR: Should have detected C1 violation!")
    
    return not result.isFeasible


def test_c2_violation():
    """Test C2: Weekly hours cap violation."""
    # Week: Sun Jan 11 to Sat Jan 17, 2026
    # Create 6 days of 10h shifts (Sun-Fri) = 6 × 8h normal = 48h
    # Add 7th shift on Sat = 56h (exceeds 52h cap)
    existing = []
    dates = [
        "2026-01-11",  # Sunday
        "2026-01-12",  # Monday
        "2026-01-13",  # Tuesday
        "2026-01-14",  # Wednesday
        "2026-01-15",  # Thursday
        "2026-01-16",  # Friday
    ]
    
    for date_str in dates:
        existing.append({
            "startDateTime": f"{date_str}T07:00:00+08:00",
            "endDateTime": f"{date_str}T17:00:00+08:00",  # 10h (9h - 1h lunch = 8h normal + 1h OT)
            "shiftType": "DAY",
            "hours": 10.0,
            "date": date_str
        })
    
    test_data = {
        "employee": {
            "employeeId": "EMP003",
            "name": "David Wong",
            "rank": "SO",
            "gender": "M",
            "scheme": "A"
        },
        "existingAssignments": existing,
        "candidateSlots": [
            {
                "slotId": "slot_saturday",
                "startDateTime": "2026-01-17T07:00:00+08:00",  # Saturday (still in same week)
                "endDateTime": "2026-01-17T17:00:00+08:00",  # 10h
                "shiftType": "DAY"
            }
        ]
    }
    
    print("\n" + "="*80)
    print("TEST 2: C2 VIOLATION - Weekly Hours Cap")
    print("="*80)
    print("Employee: EMP003")
    print("Week: Sun Jan 11 - Sat Jan 17, 2026")
    print("Existing: 6 days × 10h shifts = 48h normal hours")
    print("Candidate: +10h on Saturday = 56h normal (exceeds 52h cap)")
    
    request = ValidateAssignmentRequest(**test_data)
    validator = AssignmentValidator()
    response = validator.validate(request)
    
    result = response.validationResults[0]
    print(f"\nResult: {result.isFeasible}")
    print(f"Processing Time: {response.processingTimeMs:.2f}ms")
    
    if result.violations:
        print(f"\n✓ EXPECTED VIOLATION DETECTED:")
        for v in result.violations:
            print(f"  [{v.constraintId}] {v.constraintName}")
            print(f"  {v.description}")
            if v.context:
                print(f"  Weekly hours: {v.context.get('weeklyHours')}h / {v.context.get('weeklyCap')}h")
    else:
        print("✗ ERROR: Should have detected C2 violation!")
        print(f"  Debug: Check week boundary calculation")
    
    return not result.isFeasible


def test_c4_violation():
    """Test C4: Rest period violation."""
    test_data = {
        "employee": {
            "employeeId": "EMP004",
            "name": "Amy Lim",
            "rank": "SO",
            "gender": "F",
            "scheme": "A"
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
                "startDateTime": "2026-01-16T05:00:00+08:00",  # Starts 5am (10h rest)
                "endDateTime": "2026-01-16T13:00:00+08:00",
                "shiftType": "DAY"
            }
        ]
    }
    
    print("\n" + "="*80)
    print("TEST 3: C4 VIOLATION - Rest Period Between Shifts")
    print("="*80)
    print("Employee: EMP004")
    print("Previous shift ends: 2026-01-15 19:00 (7pm)")
    print("Next shift starts: 2026-01-16 05:00 (5am) - Only 10h rest!")
    print("Required: Minimum 12h rest")
    
    request = ValidateAssignmentRequest(**test_data)
    validator = AssignmentValidator()
    response = validator.validate(request)
    
    result = response.validationResults[0]
    print(f"\nResult: {result.isFeasible}")
    print(f"Processing Time: {response.processingTimeMs:.2f}ms")
    
    if result.violations:
        print(f"\n✓ EXPECTED VIOLATION DETECTED:")
        for v in result.violations:
            print(f"  [{v.constraintId}] {v.constraintName}")
            print(f"  {v.description}")
            if v.context:
                print(f"  Rest hours: {v.context.get('restHours')}h / {v.context.get('minRequired')}h required")
    else:
        print("✗ ERROR: Should have detected C4 violation!")
    
    return not result.isFeasible


def test_multiple_slots():
    """Test validation of multiple slots at once."""
    test_data = {
        "employee": {
            "employeeId": "EMP005",
            "name": "Michael Chen",
            "rank": "SO",
            "gender": "M",
            "scheme": "A"
        },
        "existingAssignments": [],
        "candidateSlots": [
            {
                "slotId": "slot_good_1",
                "startDateTime": "2026-01-15T07:00:00+08:00",
                "endDateTime": "2026-01-15T15:00:00+08:00",  # 8h OK
                "shiftType": "DAY"
            },
            {
                "slotId": "slot_good_2",
                "startDateTime": "2026-01-17T07:00:00+08:00",
                "endDateTime": "2026-01-17T15:00:00+08:00",  # 8h OK
                "shiftType": "DAY"
            },
            {
                "slotId": "slot_too_long",
                "startDateTime": "2026-01-19T07:00:00+08:00",
                "endDateTime": "2026-01-19T22:00:00+08:00",  # 15h FAIL
                "shiftType": "DAY"
            }
        ]
    }
    
    print("\n" + "="*80)
    print("TEST 4: MULTIPLE SLOTS - Mixed Results")
    print("="*80)
    print("Employee: EMP005 (Scheme A - 14h cap)")
    print("Validating 3 slots:")
    print("  1. slot_good_1: 8h (OK)")
    print("  2. slot_good_2: 8h (OK)")
    print("  3. slot_too_long: 15h (SHOULD FAIL)")
    
    request = ValidateAssignmentRequest(**test_data)
    validator = AssignmentValidator()
    response = validator.validate(request)
    
    print(f"\nProcessing Time: {response.processingTimeMs:.2f}ms")
    print(f"Results:")
    
    all_correct = True
    for i, result in enumerate(response.validationResults, 1):
        expected_feasible = i <= 2  # First 2 should pass
        status = "✓" if result.isFeasible == expected_feasible else "✗"
        print(f"\n  {status} Slot {i} ({result.slotId}): {result.isFeasible}")
        
        if result.violations:
            for v in result.violations:
                print(f"      [{v.constraintId}] {v.description}")
        
        if result.isFeasible != expected_feasible:
            all_correct = False
    
    return all_correct


# Run all tests
if __name__ == "__main__":
    print("\n" + "="*80)
    print("ASSIGNMENT VALIDATION - COMPREHENSIVE TEST SUITE")
    print("="*80)
    
    results = []
    
    results.append(("C1 Violation Test", test_c1_violation()))
    results.append(("C2 Violation Test", test_c2_violation()))
    results.append(("C4 Violation Test", test_c4_violation()))
    results.append(("Multiple Slots Test", test_multiple_slots()))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = 0
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\nTotal: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 ALL TESTS PASSED - Feature is working correctly!")
    else:
        print("\n⚠️  Some tests failed - please review")
    
    print("="*80 + "\n")
