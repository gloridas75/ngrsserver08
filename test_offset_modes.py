#!/usr/bin/env python3
"""
Test script for new fixedRotationOffset string modes.

Tests:
1. Backward compatibility (true → "auto", false → "solverOptimized")
2. "auto" mode (sequential staggering)
3. "teamOffsets" mode with validation
4. Error handling for invalid configurations
"""

import json
import sys
from src.offset_manager import ensure_staggered_offsets, normalize_fixed_rotation_offset

def test_normalize_values():
    """Test backward compatibility conversion."""
    print("=" * 80)
    print("TEST 1: Normalize fixedRotationOffset Values")
    print("=" * 80)
    
    tests = [
        (True, "auto"),
        (False, "solverOptimized"),
        ("auto", "auto"),
        ("teamOffsets", "teamOffsets"),
        ("solverOptimized", "solverOptimized"),
        ("invalid", "auto"),  # Should default to auto with warning
    ]
    
    passed = 0
    for input_val, expected in tests:
        result = normalize_fixed_rotation_offset(input_val)
        status = "✅" if result == expected else "❌"
        print(f"{status} {input_val} → {result} (expected {expected})")
        if result == expected:
            passed += 1
    
    print(f"\n{passed}/{len(tests)} tests passed\n")
    return passed == len(tests)


def test_auto_mode():
    """Test auto mode (sequential staggering)."""
    print("=" * 80)
    print("TEST 2: Auto Mode (Sequential Staggering)")
    print("=" * 80)
    
    input_data = {
        "fixedRotationOffset": "auto",
        "demandItems": [{
            "requirements": [{
                "workPattern": ["D", "D", "D", "D", "D", "D", "D", "D", "O"]
            }]
        }],
        "employees": [
            {"employeeId": f"EMP{i:03d}", "teamId": "TM-A", "rotationOffset": 0}
            for i in range(1, 19)
        ]
    }
    
    result = ensure_staggered_offsets(input_data)
    
    # Check offsets are staggered 0-8
    offsets = [emp['rotationOffset'] for emp in result['employees']]
    expected_offsets = [0, 1, 2, 3, 4, 5, 6, 7, 8, 0, 1, 2, 3, 4, 5, 6, 7, 8]
    
    if offsets == expected_offsets:
        print("✅ Offsets correctly staggered 0-8 across 18 employees")
        print(f"   Distribution: {offsets}")
        return True
    else:
        print(f"❌ Expected: {expected_offsets}")
        print(f"❌ Got:      {offsets}")
        return False


def test_team_offsets_valid():
    """Test valid teamOffsets configuration."""
    print("=" * 80)
    print("TEST 3: Team Offsets (Valid Configuration)")
    print("=" * 80)
    
    input_data = {
        "fixedRotationOffset": "teamOffsets",
        "teamOffsets": [
            {"teamId": "TM-Alpha", "rotationOffset": 0},
            {"teamId": "TM-Bravo", "rotationOffset": 3},
            {"teamId": "TM-Charlie", "rotationOffset": 6}
        ],
        "demandItems": [{
            "requirements": [{
                "workPattern": ["D", "D", "D", "D", "D", "D", "D", "D", "O"]
            }]
        }],
        "employees": [
            {"employeeId": "E001", "teamId": "TM-Alpha", "rotationOffset": 0},
            {"employeeId": "E002", "teamId": "TM-Alpha", "rotationOffset": 0},
            {"employeeId": "E003", "teamId": "TM-Bravo", "rotationOffset": 0},
            {"employeeId": "E004", "teamId": "TM-Bravo", "rotationOffset": 0},
            {"employeeId": "E005", "teamId": "TM-Charlie", "rotationOffset": 0},
            {"employeeId": "E006", "teamId": "TM-Charlie", "rotationOffset": 0},
        ]
    }
    
    try:
        result = ensure_staggered_offsets(input_data)
        
        # Check team offsets applied correctly
        team_alpha = [emp for emp in result['employees'] if emp['teamId'] == 'TM-Alpha']
        team_bravo = [emp for emp in result['employees'] if emp['teamId'] == 'TM-Bravo']
        team_charlie = [emp for emp in result['employees'] if emp['teamId'] == 'TM-Charlie']
        
        alpha_correct = all(emp['rotationOffset'] == 0 for emp in team_alpha)
        bravo_correct = all(emp['rotationOffset'] == 3 for emp in team_bravo)
        charlie_correct = all(emp['rotationOffset'] == 6 for emp in team_charlie)
        
        if alpha_correct and bravo_correct and charlie_correct:
            print("✅ Team offsets correctly applied:")
            print(f"   TM-Alpha: offset 0 (2 employees)")
            print(f"   TM-Bravo: offset 3 (2 employees)")
            print(f"   TM-Charlie: offset 6 (2 employees)")
            return True
        else:
            print("❌ Team offsets not applied correctly")
            return False
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_team_offsets_missing_team():
    """Test error handling when team not in teamOffsets array."""
    print("=" * 80)
    print("TEST 4: Team Offsets (Missing Team Error)")
    print("=" * 80)
    
    input_data = {
        "fixedRotationOffset": "teamOffsets",
        "teamOffsets": [
            {"teamId": "TM-Alpha", "rotationOffset": 0},
        ],
        "demandItems": [{
            "requirements": [{
                "workPattern": ["D", "D", "D", "D", "D", "D", "O"]
            }]
        }],
        "employees": [
            {"employeeId": "E001", "teamId": "TM-Alpha", "rotationOffset": 0},
            {"employeeId": "E002", "teamId": "TM-Bravo", "rotationOffset": 0},  # NOT in teamOffsets!
        ]
    }
    
    try:
        result = ensure_staggered_offsets(input_data)
        print("❌ Should have raised ValueError for missing team")
        return False
    except ValueError as e:
        if "TM-Bravo" in str(e) and "not found" in str(e):
            print(f"✅ Correctly raised error: {str(e)[:100]}...")
            return True
        else:
            print(f"❌ Wrong error message: {e}")
            return False


def test_team_offsets_invalid_range():
    """Test error handling when offset out of cycle range."""
    print("=" * 80)
    print("TEST 5: Team Offsets (Invalid Offset Range)")
    print("=" * 80)
    
    input_data = {
        "fixedRotationOffset": "teamOffsets",
        "teamOffsets": [
            {"teamId": "TM-Alpha", "rotationOffset": 10},  # Out of range for 9-day cycle!
        ],
        "demandItems": [{
            "requirements": [{
                "workPattern": ["D", "D", "D", "D", "D", "D", "D", "D", "O"]  # 9-day cycle
            }]
        }],
        "employees": [
            {"employeeId": "E001", "teamId": "TM-Alpha", "rotationOffset": 0},
        ]
    }
    
    try:
        result = ensure_staggered_offsets(input_data)
        print("❌ Should have raised ValueError for out-of-range offset")
        return False
    except ValueError as e:
        if "out of range" in str(e) and "10" in str(e):
            print(f"✅ Correctly raised error: {str(e)[:100]}...")
            return True
        else:
            print(f"❌ Wrong error message: {e}")
            return False


def test_backward_compatibility():
    """Test that old boolean values still work."""
    print("=" * 80)
    print("TEST 6: Backward Compatibility (Boolean Values)")
    print("=" * 80)
    
    # Test with boolean true
    input_data_true = {
        "fixedRotationOffset": True,  # Old format
        "demandItems": [{
            "requirements": [{
                "workPattern": ["D", "D", "D", "O"]
            }]
        }],
        "employees": [
            {"employeeId": "E001", "teamId": "TM-A", "rotationOffset": 0},
            {"employeeId": "E002", "teamId": "TM-A", "rotationOffset": 0},
            {"employeeId": "E003", "teamId": "TM-A", "rotationOffset": 0},
            {"employeeId": "E004", "teamId": "TM-A", "rotationOffset": 0},
        ]
    }
    
    result = ensure_staggered_offsets(input_data_true)
    
    # Should convert to "auto" and stagger
    if result['fixedRotationOffset'] == "auto":
        offsets = [emp['rotationOffset'] for emp in result['employees']]
        if offsets == [0, 1, 2, 3]:
            print("✅ Boolean true → 'auto' → staggered offsets [0, 1, 2, 3]")
            return True
        else:
            print(f"❌ Offsets not staggered: {offsets}")
            return False
    else:
        print(f"❌ Not converted to 'auto': {result['fixedRotationOffset']}")
        return False


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "OFFSET MODE TEST SUITE" + " " * 36 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    results = []
    
    results.append(("Normalize Values", test_normalize_values()))
    results.append(("Auto Mode", test_auto_mode()))
    results.append(("Team Offsets (Valid)", test_team_offsets_valid()))
    results.append(("Team Offsets (Missing Team)", test_team_offsets_missing_team()))
    results.append(("Team Offsets (Invalid Range)", test_team_offsets_invalid_range()))
    results.append(("Backward Compatibility", test_backward_compatibility()))
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print()
    print(f"{'✅ ALL TESTS PASSED!' if passed == total else f'❌ {total - passed} TEST(S) FAILED'}")
    print(f"Score: {passed}/{total}")
    print("=" * 80)
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
