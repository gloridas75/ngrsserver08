#!/usr/bin/env python3
"""
Test the /validate-pattern API endpoint.
"""
import requests
import json

BASE_URL = "http://localhost:8080"

def test_pattern(pattern, scheme, shift_duration=None):
    """Test a single pattern."""
    payload = {
        "pattern": pattern,
        "scheme": scheme
    }
    if shift_duration:
        payload["shiftDuration"] = shift_duration
    
    print(f"\n{'='*80}")
    print(f"Testing: {pattern} (Scheme {scheme})")
    if shift_duration:
        print(f"Shift Duration: {shift_duration}h")
    print('='*80)
    
    try:
        response = requests.post(
            f"{BASE_URL}/validate-pattern",
            json=payload,
            timeout=10
        )
        
        result = response.json()
        
        if response.status_code == 200:
            if result['is_feasible']:
                print("✅ FEASIBLE")
                print(f"   Work days: {result['work_days_per_cycle']}/{result['cycle_length']}")
                print(f"   Max consecutive: {result['max_consecutive_work_days']} days")
                print(f"   Scheme limit: {result['scheme_max_days_per_week']} days/week")
                if 'scheme_note' in result:
                    print(f"   Note: {result['scheme_note']}")
            else:
                print("❌ INFEASIBLE")
                print(f"   Violation: {result['violation_type']}")
                print(f"   Error: {result['error_message']}")
                print(f"\n   Suggested alternatives:")
                for alt in result.get('suggested_patterns', []):
                    print(f"     • {alt['pattern']}: {alt['description']}")
        else:
            print(f"❌ ERROR {response.status_code}")
            print(f"   {result.get('detail', 'Unknown error')}")
        
        print(f"\n   Response time: {result.get('_meta', {}).get('validation_time_ms', 'N/A')}ms")
        
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Cannot connect to server. Is it running?")
        print(f"   Start with: uvicorn src.api_server:app --reload --port 8080")
    except Exception as e:
        print(f"❌ ERROR: {e}")


if __name__ == '__main__':
    print("\n" + "="*80)
    print("PATTERN VALIDATION API TEST")
    print("="*80)
    
    # Test 1: Scheme P - Infeasible (6 work days)
    test_pattern(
        pattern=["D", "D", "D", "O", "D", "D", "D"],
        scheme="P",
        shift_duration=9.0
    )
    
    # Test 2: Scheme P - Feasible (4 work days)
    test_pattern(
        pattern=["D", "D", "D", "D", "O", "O", "O"],
        scheme="P",
        shift_duration=9.0
    )
    
    # Test 3: Scheme P - Infeasible (5 work days)
    test_pattern(
        pattern=["D", "D", "D", "D", "D", "O", "O"],
        scheme="P",
        shift_duration=8.0
    )
    
    # Test 4: Scheme A - Feasible (6 work days)
    test_pattern(
        pattern=["D", "D", "D", "D", "D", "D", "O"],
        scheme="A",
        shift_duration=12.0
    )
    
    # Test 5: Scheme A - Infeasible (7 work days)
    test_pattern(
        pattern=["D", "D", "D", "D", "D", "D", "D"],
        scheme="A",
        shift_duration=12.0
    )
    
    # Test 6: Scheme B - Feasible (6 work days)
    test_pattern(
        pattern=["D", "D", "D", "D", "D", "D", "O"],
        scheme="B",
        shift_duration=12.0
    )
    
    # Test 7: Invalid scheme
    test_pattern(
        pattern=["D", "D", "O", "O"],
        scheme="X",
        shift_duration=8.0
    )
    
    # Test 8: Invalid pattern
    test_pattern(
        pattern=["D", "X", "O", "D"],
        scheme="P",
        shift_duration=8.0
    )
    
    print("\n" + "="*80)
    print("TESTS COMPLETE")
    print("="*80 + "\n")
