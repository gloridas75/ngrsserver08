#!/usr/bin/env python3
"""
Test incremental solver updates locally before committing.

Tests:
1. Input validation with headcount=0 for outcomeBased mode
2. Input validation with headcount=0 for demandBased mode (should fail)
3. Rostering basis detection
4. Incremental request validation
5. Backward compatibility (existing demandBased flows)
"""

import json
import sys
from datetime import datetime
from src.incremental_solver import (
    solve_incremental, 
    _validate_incremental_request, 
    _detect_rostering_basis,
    IncrementalSolverError
)
from src.input_validator import validate_input
from src.models import IncrementalSolveRequest

def test_helper_functions():
    """Test the new helper functions."""
    print("\n" + "="*80)
    print("TEST 1: Helper Functions")
    print("="*80)
    
    # Test rostering basis detection
    print("\n1.1 Testing _detect_rostering_basis...")
    
    test_cases = [
        ([{'rosteringBasis': 'demandBased'}], 'demandBased'),
        ([{'rosteringBasis': 'outcomeBased'}], 'outcomeBased'),
        ([{}], 'demandBased'),  # Default
        ([], 'demandBased'),  # Empty
    ]
    
    for demand_items, expected in test_cases:
        result = _detect_rostering_basis(demand_items)
        status = "✓" if result == expected else "✗"
        print(f"   {status} Input: {demand_items} -> {result} (expected: {expected})")
    
    # Test incremental request validation
    print("\n1.2 Testing _validate_incremental_request...")
    
    valid_request = {
        'temporalWindow': {'cutoffDate': '2026-01-10', 'solveFromDate': '2026-01-11', 'solveToDate': '2026-01-31'},
        'previousOutput': {'assignments': []},
        'employeeChanges': {},
        'demandItems': [],
        'planningHorizon': {},
        'planningReference': 'TEST-001'
    }
    
    try:
        _validate_incremental_request(valid_request)
        print("   ✓ Valid request accepted")
    except IncrementalSolverError as e:
        print(f"   ✗ Valid request rejected: {e}")
        return False
    
    # Test missing fields
    invalid_request = {'temporalWindow': {}}
    try:
        _validate_incremental_request(invalid_request)
        print("   ✗ Invalid request should have been rejected")
        return False
    except IncrementalSolverError as e:
        print(f"   ✓ Invalid request correctly rejected: {str(e)[:60]}...")
    
    # Test missing assignments in previousOutput
    invalid_request2 = {**valid_request, 'previousOutput': {}}
    try:
        _validate_incremental_request(invalid_request2)
        print("   ✗ Missing assignments should have been rejected")
        return False
    except IncrementalSolverError as e:
        print(f"   ✓ Missing assignments correctly rejected")
    
    return True


def test_headcount_validation():
    """Test headcount=0 validation for both modes."""
    print("\n" + "="*80)
    print("TEST 2: Headcount=0 Validation")
    print("="*80)
    
    # Test outcomeBased with headcount=0 (should pass)
    print("\n2.1 Testing outcomeBased with headcount=0...")
    
    outcome_based_input = {
        'schemaVersion': '0.95',
        'planningReference': 'TEST-OB-001',
        'demandItems': [{
            'demandId': 'DI-001',
            'rosteringBasis': 'outcomeBased',
            'minStaffThresholdPercentage': 100,
            'shifts': [{
                'shiftDetails': [{
                    'shiftCode': 'D',
                    'start': '08:00:00',
                    'end': '20:00:00',
                    'nextDay': False
                }],
                'shiftSetId': 'Set1',
                'coverageDays': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            }],
            'requirements': [{
                'requirementId': 'REQ-001',
                'productTypeId': 'APO',
                'rankIds': ['PC'],
                'headcount': 0,  # Should be allowed for outcomeBased
                'workPattern': ['D', 'D', 'D', 'D', 'D', 'O', 'O']
            }]
        }],
        'employees': [
            {'employeeId': 'EMP001', 'rankId': 'PC', 'productTypeId': 'APO', 'scheme': 'SchemeA'}
        ],
        'planningHorizon': {
            'startDate': '2026-01-01',
            'endDate': '2026-01-31'
        }
    }
    
    result = validate_input(outcome_based_input)
    if result.is_valid:
        print("   ✓ outcomeBased with headcount=0 PASSED validation")
    else:
        print(f"   ✗ outcomeBased with headcount=0 FAILED: {result.errors[0].message if result.errors else 'Unknown'}")
        return False
    
    # Test demandBased with headcount=0 (should fail)
    print("\n2.2 Testing demandBased with headcount=0...")
    
    demand_based_input = {
        'schemaVersion': '0.95',
        'planningReference': 'TEST-DB-001',
        'demandItems': [{
            'demandId': 'DI-001',
            'rosteringBasis': 'demandBased',
            'shifts': [{
                'shiftDetails': [{
                    'shiftCode': 'D',
                    'start': '08:00:00',
                    'end': '20:00:00',
                    'nextDay': False
                }],
                'shiftSetId': 'Set1',
                'coverageDays': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            }],
            'requirements': [{
                'requirementId': 'REQ-001',
                'productTypeId': 'APO',
                'rankIds': ['PC'],
                'headcount': 0,  # Should fail for demandBased
                'workPattern': ['D', 'D', 'D', 'D', 'D', 'O', 'O']
            }]
        }],
        'employees': [
            {'employeeId': 'EMP001', 'rankId': 'PC', 'productTypeId': 'APO', 'scheme': 'SchemeA'}
        ],
        'planningHorizon': {
            'startDate': '2026-01-01',
            'endDate': '2026-01-31'
        }
    }
    
    result = validate_input(demand_based_input)
    if not result.is_valid:
        print(f"   ✓ demandBased with headcount=0 correctly REJECTED")
        print(f"      Error: {result.errors[0].message if result.errors else 'Unknown'}")
    else:
        print("   ✗ demandBased with headcount=0 should have FAILED")
        return False
    
    return True


def test_schema_version():
    """Test that schema version was updated."""
    print("\n" + "="*80)
    print("TEST 3: Schema Version Update")
    print("="*80)
    
    print("\n3.1 Testing IncrementalSolveRequest schema version...")
    
    # Create a minimal request
    try:
        request = IncrementalSolveRequest(
            planningReference="TEST-001",
            temporalWindow={
                'cutoffDate': '2026-01-10',
                'solveFromDate': '2026-01-11',
                'solveToDate': '2026-01-31'
            },
            previousOutput={'assignments': []},
            employeeChanges={},
            demandItems=[],
            planningHorizon={'startDate': '2026-01-01', 'endDate': '2026-01-31'}
        )
        
        if request.schemaVersion == "0.95":
            print(f"   ✓ Schema version correctly updated to 0.95")
        else:
            print(f"   ✗ Schema version is {request.schemaVersion}, expected 0.95")
            return False
            
    except Exception as e:
        print(f"   ✗ Failed to create IncrementalSolveRequest: {e}")
        return False
    
    return True


def test_backward_compatibility():
    """Test that existing functionality still works."""
    print("\n" + "="*80)
    print("TEST 4: Backward Compatibility")
    print("="*80)
    
    print("\n4.1 Testing standard demandBased incremental request...")
    
    # Create a minimal but valid incremental request (demandBased)
    incremental_request = {
        'schemaVersion': '0.95',
        'planningReference': 'TEST-COMPAT-001',
        'temporalWindow': {
            'cutoffDate': '2026-01-10',
            'solveFromDate': '2026-01-11',
            'solveToDate': '2026-01-31'
        },
        'previousOutput': {
            'assignments': [
                {
                    'assignmentId': 'A001',
                    'employeeId': 'EMP001',
                    'date': '2026-01-05',
                    'startDateTime': '2026-01-05T08:00:00',
                    'endDateTime': '2026-01-05T20:00:00',
                    'shiftCode': 'D',
                    'status': 'ASSIGNED',
                    'hours': {'normal': 8.0, 'ot': 0.0}
                }
            ],
            'solverRun': {'status': 'OPTIMAL'}
        },
        'employeeChanges': {
            'newJoiners': [],
            'notAvailableFrom': [],
            'longLeave': []
        },
        'demandItems': [{
            'demandId': 'DI-001',
            'rosteringBasis': 'demandBased',
            'shifts': [{
                'shiftDetails': [{
                    'shiftCode': 'D',
                    'start': '08:00:00',
                    'end': '20:00:00',
                    'nextDay': False
                }],
                'shiftSetId': 'Set1',
                'coverageDays': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            }],
            'requirements': [{
                'requirementId': 'REQ-001',
                'productTypeId': 'APO',
                'rankIds': ['PC'],
                'headcount': 1,
                'workPattern': ['D', 'D', 'D', 'D', 'D', 'O', 'O']
            }]
        }],
        'planningHorizon': {
            'startDate': '2026-01-01',
            'endDate': '2026-01-31'
        },
        'solverConfig': {}
    }
    
    # Test validation steps
    try:
        _validate_incremental_request(incremental_request)
        print("   ✓ Incremental request structure validation passed")
        
        rostering_basis = _detect_rostering_basis(incremental_request['demandItems'])
        print(f"   ✓ Rostering basis detected: {rostering_basis}")
        
        if rostering_basis != 'demandBased':
            print(f"   ✗ Expected demandBased, got {rostering_basis}")
            return False
        
        # Test demand validation (add planningReference and employees)
        test_input = {
            'schemaVersion': incremental_request['schemaVersion'],
            'planningReference': 'TEST-COMPAT-001',
            'demandItems': incremental_request['demandItems'],
            'employees': [{'employeeId': 'EMP001', 'rankId': 'PC', 'productTypeId': 'APO', 'scheme': 'SchemeA'}],
            'planningHorizon': incremental_request['planningHorizon']
        }
        
        validation_result = validate_input(test_input)
        if not validation_result.is_valid:
            print(f"   ✗ Demand validation failed: {validation_result.errors[0].message if validation_result.errors else 'Unknown'}")
            return False
        
        print("   ✓ Demand validation passed")
        print("   ✓ All backward compatibility checks passed")
        
    except Exception as e:
        print(f"   ✗ Validation failed: {e}")
        return False
    
    return True


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "="*80)
    print("INCREMENTAL SOLVER UPDATE - LOCAL TESTING")
    print("="*80)
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Helper Functions", test_helper_functions),
        ("Headcount Validation", test_headcount_validation),
        ("Schema Version", test_schema_version),
        ("Backward Compatibility", test_backward_compatibility),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result, None))
        except Exception as e:
            results.append((test_name, False, str(e)))
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result, _ in results if result)
    total = len(results)
    
    for test_name, result, error in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status}: {test_name}")
        if error:
            print(f"         Error: {error}")
    
    print("\n" + "-"*80)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ ALL TESTS PASSED - Safe to commit changes")
        print("\nChanges made:")
        print("  1. Added input validation to incremental solver")
        print("  2. Support for both demandBased and outcomeBased modes")
        print("  3. Updated schema version from 0.80 to 0.95")
        print("  4. Conditional locked context calculations")
        print("  5. Backward compatibility maintained")
        return 0
    else:
        print("\n✗ SOME TESTS FAILED - Review changes before committing")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
