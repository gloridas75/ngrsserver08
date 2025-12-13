#!/usr/bin/env python3
"""
Test pattern feasibility validation for Scheme P.
Demonstrates detection of infeasible patterns before solver runs.
"""
from context.engine.config_optimizer_v3 import validate_pattern_feasibility, calculate_optimal_with_u_slots
from datetime import date, timedelta

def test_patterns():
    """Test various patterns with Scheme P validation."""
    
    test_cases = [
        {
            'name': 'INFEASIBLE: 6 work days (DDDODDD)',
            'pattern': ['D', 'D', 'D', 'O', 'D', 'D', 'D'],
            'scheme': 'P',
            'expected_feasible': False
        },
        {
            'name': 'INFEASIBLE: 5 work days (DDDDDOO)',
            'pattern': ['D', 'D', 'D', 'D', 'D', 'O', 'O'],
            'scheme': 'P',
            'expected_feasible': False
        },
        {
            'name': 'FEASIBLE: 4 work days (DDDDOOO)',
            'pattern': ['D', 'D', 'D', 'D', 'O', 'O', 'O'],
            'scheme': 'P',
            'expected_feasible': True
        },
        {
            'name': 'FEASIBLE: 4 work days with break (DDODDOO)',
            'pattern': ['D', 'D', 'O', 'D', 'D', 'O', 'O'],
            'scheme': 'P',
            'expected_feasible': True
        },
        {
            'name': 'FEASIBLE Scheme A: 6 work days (DDDDDDOO)',
            'pattern': ['D', 'D', 'D', 'D', 'D', 'D', 'O'],
            'scheme': 'A',
            'expected_feasible': True
        },
        {
            'name': 'INFEASIBLE Scheme A: 7 work days (DDDDDDD)',
            'pattern': ['D', 'D', 'D', 'D', 'D', 'D', 'D'],
            'scheme': 'A',
            'expected_feasible': False
        }
    ]
    
    print("=" * 80)
    print("PATTERN FEASIBILITY VALIDATION TESTS")
    print("=" * 80)
    print()
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"Test: {test['name']}")
        print(f"  Pattern: {test['pattern']}")
        print(f"  Scheme: {test['scheme']}")
        
        result = validate_pattern_feasibility(test['pattern'], test['scheme'])
        
        is_feasible = result['is_feasible']
        expected = test['expected_feasible']
        
        if is_feasible == expected:
            print(f"  ✅ PASS - Correctly identified as {'FEASIBLE' if is_feasible else 'INFEASIBLE'}")
            passed += 1
        else:
            print(f"  ❌ FAIL - Expected {'FEASIBLE' if expected else 'INFEASIBLE'}, got {'FEASIBLE' if is_feasible else 'INFEASIBLE'}")
            failed += 1
        
        if not is_feasible:
            print(f"  Error: {result['error_message']}")
            if result['suggested_patterns']:
                print(f"  Suggestions:")
                for alt in result['suggested_patterns']:
                    print(f"    - {alt['pattern']}: {alt['description']}")
        
        print()
    
    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 80)
    print()
    
    # Test full ICPMP with infeasible pattern
    print("=" * 80)
    print("TESTING ICPMP WITH INFEASIBLE PATTERN")
    print("=" * 80)
    print()
    
    # Generate 31-day calendar
    start_date = date(2026, 1, 1)
    calendar = [(start_date + timedelta(days=i)).isoformat() for i in range(31)]
    
    print("Testing Pattern DDDODDD (6 work days) with Scheme P...")
    icpmp_result = calculate_optimal_with_u_slots(
        pattern=['D', 'D', 'D', 'O', 'D', 'D', 'D'],
        headcount=10,
        calendar=calendar,
        anchor_date='2026-01-01',
        requirement_id='TEST_102_1',
        scheme='P'
    )
    
    if not icpmp_result.get('is_feasible', True):
        print("✅ ICPMP correctly rejected infeasible pattern")
        print(f"   Error type: {icpmp_result['error']['type']}")
        print(f"   Message: {icpmp_result['error']['message']}")
        print()
        if icpmp_result['error'].get('suggested_patterns'):
            print("   Suggested alternatives:")
            for alt in icpmp_result['error']['suggested_patterns']:
                print(f"     • {alt['pattern']}: {alt['description']}")
    else:
        print("❌ ICPMP failed to detect infeasible pattern!")
        print(f"   Employees required: {icpmp_result['configuration']['employeesRequired']}")
    
    print()
    
    # Test with feasible pattern
    print("Testing Pattern DDDDOOO (4 work days) with Scheme P...")
    icpmp_result2 = calculate_optimal_with_u_slots(
        pattern=['D', 'D', 'D', 'D', 'O', 'O', 'O'],
        headcount=10,
        calendar=calendar,
        anchor_date='2026-01-01',
        requirement_id='TEST_102_2',
        scheme='P'
    )
    
    if icpmp_result2.get('is_feasible', True):
        print("✅ ICPMP correctly accepted feasible pattern")
        print(f"   Employees required: {icpmp_result2['configuration']['employeesRequired']}")
        print(f"   Coverage rate: {icpmp_result2['coverage']['achievedRate']}%")
    else:
        print("❌ ICPMP incorrectly rejected feasible pattern!")
        print(f"   Error: {icpmp_result2.get('error', {}).get('message')}")
    
    print()


if __name__ == '__main__':
    test_patterns()
