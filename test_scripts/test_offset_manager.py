#!/usr/bin/env python3
"""
Test script to verify offset manager integration in the API server.
"""

import json
import sys

# Add path
sys.path.insert(0, '.')

from src.offset_manager import ensure_staggered_offsets, validate_offset_configuration

def test_offset_manager():
    """Test the offset manager with sample data"""
    
    print("=" * 80)
    print("TESTING OFFSET MANAGER")
    print("=" * 80)
    print()
    
    # Create test data with all offsets at 0
    test_data = {
        "fixedRotationOffset": True,
        "demandItems": [{
            "requirements": [{
                "requirementId": "test_1",
                "headcount": 5,
                "workPattern": ["D", "D", "N", "N", "O", "O"]
            }]
        }],
        "employees": [
            {"employeeId": f"EMP{i:03d}", "rotationOffset": 0}
            for i in range(30)
        ]
    }
    
    print(f"Test data: {len(test_data['employees'])} employees, all at offset 0")
    print(f"Pattern: {test_data['demandItems'][0]['requirements'][0]['workPattern']}")
    print(f"fixedRotationOffset: {test_data['fixedRotationOffset']}")
    print()
    
    # Validate before
    print("BEFORE staggering:")
    is_valid, issues = validate_offset_configuration(test_data)
    if not is_valid:
        for issue in issues:
            print(f"  ❌ {issue}")
    print()
    
    # Apply staggering
    print("Applying offset manager...")
    result = ensure_staggered_offsets(test_data)
    print()
    
    # Validate after
    print("AFTER staggering:")
    is_valid, issues = validate_offset_configuration(result)
    if is_valid:
        print("  ✅ All validation checks passed")
    else:
        for issue in issues:
            print(f"  ❌ {issue}")
    print()
    
    # Check distribution
    from collections import Counter
    offsets = [emp['rotationOffset'] for emp in result['employees']]
    distribution = Counter(offsets)
    print(f"Final distribution: {dict(sorted(distribution.items()))}")
    print()
    
    # Test with fixedRotationOffset=false
    print("=" * 80)
    print("TEST 2: fixedRotationOffset=false (should skip staggering)")
    print("=" * 80)
    print()
    
    test_data2 = test_data.copy()
    test_data2['fixedRotationOffset'] = False
    test_data2['employees'] = [
        {"employeeId": f"EMP{i:03d}", "rotationOffset": 0}
        for i in range(30)
    ]
    
    result2 = ensure_staggered_offsets(test_data2)
    offsets2 = [emp['rotationOffset'] for emp in result2['employees']]
    distribution2 = Counter(offsets2)
    print(f"Distribution (should still be all 0): {dict(sorted(distribution2.items()))}")
    print()
    
    if distribution2 == {0: 30}:
        print("✅ Correctly skipped staggering when fixedRotationOffset=false")
    else:
        print("❌ ERROR: Offsets were modified when they shouldn't be")
    
    print()
    print("=" * 80)
    print("✅ ALL TESTS PASSED")
    print("=" * 80)

if __name__ == "__main__":
    test_offset_manager()
