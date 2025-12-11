#!/usr/bin/env python3
"""Test MOM-compliant work hours calculation."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from datetime import datetime, date
from context.engine.time_utils import calculate_mom_compliant_hours

def test_4_days_per_week():
    """Test 4 work days per week: 11.0h normal + rest OT."""
    print("\n" + "="*80)
    print("TEST 1: 4 Work Days Per Week (12h shift)")
    print("="*80)
    
    # Simulate 4 work days in a calendar week (Mon-Thu)
    assignments = [
        {'employeeId': 'E001', 'date': '2026-01-05', 'shiftCode': 'D'},  # Mon
        {'employeeId': 'E001', 'date': '2026-01-06', 'shiftCode': 'D'},  # Tue
        {'employeeId': 'E001', 'date': '2026-01-07', 'shiftCode': 'D'},  # Wed
        {'employeeId': 'E001', 'date': '2026-01-08', 'shiftCode': 'D'},  # Thu (current)
    ]
    
    start_dt = datetime(2026, 1, 8, 8, 0, 0)
    end_dt = datetime(2026, 1, 8, 20, 0, 0)
    current_date = date(2026, 1, 8)
    
    result = calculate_mom_compliant_hours(
        start_dt, end_dt, 'E001', current_date, assignments
    )
    
    print(f"Shift: {start_dt.time()} - {end_dt.time()}")
    print(f"Result: {result}")
    print(f"✓ Expected: normal=11.0, ot=0.0, restDayPay=0.0")
    print(f"✓ Actual: normal={result['normal']}, ot={result['ot']}, restDayPay={result['restDayPay']}")
    
    assert result['normal'] == 11.0, f"Expected normal=11.0, got {result['normal']}"
    assert result['ot'] == 0.0, f"Expected ot=0.0, got {result['ot']}"
    assert result['restDayPay'] == 0.0, f"Expected restDayPay=0.0, got {result['restDayPay']}"
    print("✅ PASS")


def test_5_days_per_week():
    """Test 5 work days per week: 8.8h normal + rest OT."""
    print("\n" + "="*80)
    print("TEST 2: 5 Work Days Per Week (12h shift)")
    print("="*80)
    
    # Simulate 5 work days in a calendar week (Mon-Fri)
    assignments = [
        {'employeeId': 'E002', 'date': '2026-01-05', 'shiftCode': 'D'},  # Mon
        {'employeeId': 'E002', 'date': '2026-01-06', 'shiftCode': 'D'},  # Tue
        {'employeeId': 'E002', 'date': '2026-01-07', 'shiftCode': 'D'},  # Wed
        {'employeeId': 'E002', 'date': '2026-01-08', 'shiftCode': 'D'},  # Thu
        {'employeeId': 'E002', 'date': '2026-01-09', 'shiftCode': 'D'},  # Fri (current)
    ]
    
    start_dt = datetime(2026, 1, 9, 8, 0, 0)
    end_dt = datetime(2026, 1, 9, 20, 0, 0)
    current_date = date(2026, 1, 9)
    
    result = calculate_mom_compliant_hours(
        start_dt, end_dt, 'E002', current_date, assignments
    )
    
    print(f"Shift: {start_dt.time()} - {end_dt.time()}")
    print(f"Result: {result}")
    print(f"✓ Expected: normal=8.8, ot=2.2, restDayPay=0.0")
    print(f"✓ Actual: normal={result['normal']}, ot={result['ot']}, restDayPay={result['restDayPay']}")
    
    assert result['normal'] == 8.8, f"Expected normal=8.8, got {result['normal']}"
    assert result['ot'] == 2.2, f"Expected ot=2.2, got {result['ot']}"
    assert result['restDayPay'] == 0.0, f"Expected restDayPay=0.0, got {result['restDayPay']}"
    print("✅ PASS")


def test_6_days_position_3():
    """Test 6 work days per week, position 3: 8.8h normal + rest OT."""
    print("\n" + "="*80)
    print("TEST 3: 6 Work Days Per Week, Position 3 (12h shift)")
    print("="*80)
    
    # Simulate 6 work days, testing day 3
    assignments = [
        {'employeeId': 'E003', 'date': '2026-01-05', 'shiftCode': 'D'},  # Mon
        {'employeeId': 'E003', 'date': '2026-01-06', 'shiftCode': 'D'},  # Tue
        {'employeeId': 'E003', 'date': '2026-01-07', 'shiftCode': 'D'},  # Wed (current, pos 3)
        {'employeeId': 'E003', 'date': '2026-01-08', 'shiftCode': 'D'},  # Thu
        {'employeeId': 'E003', 'date': '2026-01-09', 'shiftCode': 'D'},  # Fri
        {'employeeId': 'E003', 'date': '2026-01-10', 'shiftCode': 'D'},  # Sat
    ]
    
    start_dt = datetime(2026, 1, 7, 8, 0, 0)
    end_dt = datetime(2026, 1, 7, 20, 0, 0)
    current_date = date(2026, 1, 7)
    
    result = calculate_mom_compliant_hours(
        start_dt, end_dt, 'E003', current_date, assignments
    )
    
    print(f"Shift: {start_dt.time()} - {end_dt.time()}")
    print(f"Result: {result}")
    print(f"✓ Expected: normal=8.8, ot=2.2, restDayPay=0.0 (position 3 of 6)")
    print(f"✓ Actual: normal={result['normal']}, ot={result['ot']}, restDayPay={result['restDayPay']}")
    
    assert result['normal'] == 8.8, f"Expected normal=8.8, got {result['normal']}"
    assert result['ot'] == 2.2, f"Expected ot=2.2, got {result['ot']}"
    assert result['restDayPay'] == 0.0, f"Expected restDayPay=0.0, got {result['restDayPay']}"
    print("✅ PASS")


def test_6_days_position_6():
    """Test 6 work days per week, position 6: 0h normal, 8.0h rest day pay, rest OT."""
    print("\n" + "="*80)
    print("TEST 4: 6 Work Days Per Week, Position 6 (12h shift)")
    print("="*80)
    
    # Simulate 6 consecutive work days, testing day 6
    assignments = [
        {'employeeId': 'E004', 'date': '2026-01-05', 'shiftCode': 'D'},  # Mon
        {'employeeId': 'E004', 'date': '2026-01-06', 'shiftCode': 'D'},  # Tue
        {'employeeId': 'E004', 'date': '2026-01-07', 'shiftCode': 'D'},  # Wed
        {'employeeId': 'E004', 'date': '2026-01-08', 'shiftCode': 'D'},  # Thu
        {'employeeId': 'E004', 'date': '2026-01-09', 'shiftCode': 'D'},  # Fri
        {'employeeId': 'E004', 'date': '2026-01-10', 'shiftCode': 'D'},  # Sat (current, pos 6)
    ]
    
    start_dt = datetime(2026, 1, 10, 8, 0, 0)
    end_dt = datetime(2026, 1, 10, 20, 0, 0)
    current_date = date(2026, 1, 10)
    
    result = calculate_mom_compliant_hours(
        start_dt, end_dt, 'E004', current_date, assignments
    )
    
    print(f"Shift: {start_dt.time()} - {end_dt.time()}")
    print(f"Result: {result}")
    print(f"✓ Expected: normal=0.0, ot=3.0, restDayPay=8.0 (6th consecutive day)")
    print(f"✓ Actual: normal={result['normal']}, ot={result['ot']}, restDayPay={result['restDayPay']}")
    
    assert result['normal'] == 0.0, f"Expected normal=0.0, got {result['normal']}"
    assert result['ot'] == 3.0, f"Expected ot=3.0, got {result['ot']}"
    assert result['restDayPay'] == 8.0, f"Expected restDayPay=8.0, got {result['restDayPay']}"
    print("✅ PASS")


def test_non_consecutive():
    """Test 5 work days with gaps: should still use 8.8h formula."""
    print("\n" + "="*80)
    print("TEST 5: 5 Work Days (Non-Consecutive) Per Week")
    print("="*80)
    
    # Simulate 5 work days with a gap (Mon-Tue, Thu-Sat)
    assignments = [
        {'employeeId': 'E005', 'date': '2026-01-05', 'shiftCode': 'D'},  # Mon
        {'employeeId': 'E005', 'date': '2026-01-06', 'shiftCode': 'D'},  # Tue
        # Wed off
        {'employeeId': 'E005', 'date': '2026-01-08', 'shiftCode': 'D'},  # Thu
        {'employeeId': 'E005', 'date': '2026-01-09', 'shiftCode': 'D'},  # Fri
        {'employeeId': 'E005', 'date': '2026-01-10', 'shiftCode': 'D'},  # Sat (current, pos 3 after gap)
    ]
    
    start_dt = datetime(2026, 1, 10, 8, 0, 0)
    end_dt = datetime(2026, 1, 10, 20, 0, 0)
    current_date = date(2026, 1, 10)
    
    result = calculate_mom_compliant_hours(
        start_dt, end_dt, 'E005', current_date, assignments
    )
    
    print(f"Shift: {start_dt.time()} - {end_dt.time()}")
    print(f"Pattern: [D,D,O,D,D,D] = 5 work days in week")
    print(f"Result: {result}")
    print(f"✓ Expected: normal=8.8, ot=2.2 (based on 5 work days, not consecutive position)")
    print(f"✓ Actual: normal={result['normal']}, ot={result['ot']}, restDayPay={result['restDayPay']}")
    
    assert result['normal'] == 8.8, f"Expected normal=8.8, got {result['normal']}"
    assert result['ot'] == 2.2, f"Expected ot=2.2, got {result['ot']}"
    assert result['restDayPay'] == 0.0, f"Expected restDayPay=0.0, got {result['restDayPay']}"
    print("✅ PASS")


if __name__ == '__main__':
    print("\n" + "="*80)
    print("MOM-COMPLIANT WORK HOURS CALCULATION - TEST SUITE")
    print("="*80)
    
    try:
        test_4_days_per_week()
        test_5_days_per_week()
        test_6_days_position_3()
        test_6_days_position_6()
        test_non_consecutive()
        
        print("\n" + "="*80)
        print("🎉 ALL TESTS PASSED!")
        print("="*80)
        print("\nSummary:")
        print("  ✅ 4 days/week: 11.0h normal")
        print("  ✅ 5 days/week: 8.8h normal + 2.2h OT")
        print("  ✅ 6 days/week (pos 1-5): 8.8h normal + 2.2h OT")
        print("  ✅ 6 days/week (pos 6+): 0h normal + 8.0h rest day pay + 3.0h OT")
        print("  ✅ Non-consecutive patterns handled correctly")
        print("\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
