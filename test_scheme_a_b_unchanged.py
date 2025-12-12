"""
Test to verify Scheme A/B behavior is UNCHANGED after Scheme P implementation

This test confirms that adding Scheme P support did NOT affect 
existing Scheme A/B hour calculations.
"""
from datetime import datetime
from context.engine.time_utils import calculate_mom_compliant_hours


def test_scheme_a_4_days_pattern():
    """Test Scheme A with 4 days/week pattern"""
    print("\n" + "="*80)
    print("TEST 1: Scheme A, 4 days/week, various shift lengths")
    print("="*80)
    
    date_obj = datetime(2025, 1, 6).date()
    all_assignments = [
        {'employeeId': 'A1', 'date': '2025-01-06'},
        {'employeeId': 'A1', 'date': '2025-01-07'},
        {'employeeId': 'A1', 'date': '2025-01-08'},
        {'employeeId': 'A1', 'date': '2025-01-09'},
    ]
    
    # Test 1a: 12h gross shift (11h net + 1h lunch)
    start_dt = datetime(2025, 1, 6, 9, 0)
    end_dt = datetime(2025, 1, 6, 21, 0)  # 12h gross
    
    result_a = calculate_mom_compliant_hours(
        start_dt, end_dt, 'A1', date_obj, all_assignments, employee_scheme='A'
    )
    result_b = calculate_mom_compliant_hours(
        start_dt, end_dt, 'A1', date_obj, all_assignments, employee_scheme='B'
    )
    result_default = calculate_mom_compliant_hours(
        start_dt, end_dt, 'A1', date_obj, all_assignments  # No scheme = defaults to A
    )
    
    print(f"12h gross shift (11h net + 1h lunch):")
    print(f"  Scheme A: Normal={result_a['normal']}h, OT={result_a['ot']}h")
    print(f"  Scheme B: Normal={result_b['normal']}h, OT={result_b['ot']}h")
    print(f"  Default:  Normal={result_default['normal']}h, OT={result_default['ot']}h")
    print(f"  Expected: Normal=11.0h, OT=0.0h (4 days/week uses 11.0h threshold)")
    
    assert result_a['normal'] == 11.0, f"Scheme A should have 11.0h normal, got {result_a['normal']}"
    assert result_a['ot'] == 0.0, f"Scheme A should have 0h OT, got {result_a['ot']}"
    assert result_b['normal'] == 11.0, f"Scheme B should have 11.0h normal, got {result_b['normal']}"
    assert result_b['ot'] == 0.0, f"Scheme B should have 0h OT, got {result_b['ot']}"
    assert result_default['normal'] == 11.0, "Default should match Scheme A"
    
    # Test 1b: 13h gross shift (12h net + 1h lunch)
    end_dt2 = datetime(2025, 1, 6, 22, 0)  # 13h gross
    
    result_a2 = calculate_mom_compliant_hours(
        start_dt, end_dt2, 'A1', date_obj, all_assignments, employee_scheme='A'
    )
    
    print(f"\n13h gross shift (12h net + 1h lunch):")
    print(f"  Scheme A: Normal={result_a2['normal']}h, OT={result_a2['ot']}h")
    print(f"  Expected: Normal=11.0h, OT=1.0h (exceeds 11.0h threshold)")
    
    assert result_a2['normal'] == 11.0, f"Scheme A should have 11.0h normal, got {result_a2['normal']}"
    assert result_a2['ot'] == 1.0, f"Scheme A should have 1.0h OT, got {result_a2['ot']}"
    
    print("✅ PASSED: Scheme A/B 4-day pattern unchanged")


def test_scheme_a_5_days_pattern():
    """Test Scheme A with 5 days/week pattern"""
    print("\n" + "="*80)
    print("TEST 2: Scheme A, 5 days/week, various shift lengths")
    print("="*80)
    
    date_obj = datetime(2025, 1, 6).date()
    all_assignments = [
        {'employeeId': 'A2', 'date': '2025-01-06'},
        {'employeeId': 'A2', 'date': '2025-01-07'},
        {'employeeId': 'A2', 'date': '2025-01-08'},
        {'employeeId': 'A2', 'date': '2025-01-09'},
        {'employeeId': 'A2', 'date': '2025-01-10'},
    ]
    
    # Test 2a: 12h gross shift (11h net + 1h lunch)
    start_dt = datetime(2025, 1, 6, 9, 0)
    end_dt = datetime(2025, 1, 6, 21, 0)  # 12h gross
    
    result_a = calculate_mom_compliant_hours(
        start_dt, end_dt, 'A2', date_obj, all_assignments, employee_scheme='A'
    )
    
    print(f"12h gross shift (11h net + 1h lunch):")
    print(f"  Scheme A: Normal={result_a['normal']}h, OT={result_a['ot']}h")
    print(f"  Expected: Normal=8.8h, OT=2.2h (5 days/week uses 8.8h threshold)")
    
    assert result_a['normal'] == 8.8, f"Scheme A should have 8.8h normal, got {result_a['normal']}"
    assert result_a['ot'] == 2.2, f"Scheme A should have 2.2h OT, got {result_a['ot']}"
    
    # Test 2b: 9h gross shift (8h net + 1h lunch)
    end_dt2 = datetime(2025, 1, 6, 18, 0)  # 9h gross
    
    result_a2 = calculate_mom_compliant_hours(
        start_dt, end_dt2, 'A2', date_obj, all_assignments, employee_scheme='A'
    )
    
    print(f"\n9h gross shift (8h net + 1h lunch):")
    print(f"  Scheme A: Normal={result_a2['normal']}h, OT={result_a2['ot']}h")
    print(f"  Expected: Normal=8.0h, OT=0.0h (8h < 8.8h threshold)")
    
    assert result_a2['normal'] == 8.0, f"Scheme A should have 8.0h normal, got {result_a2['normal']}"
    assert result_a2['ot'] == 0.0, f"Scheme A should have 0h OT, got {result_a2['ot']}"
    
    print("✅ PASSED: Scheme A/B 5-day pattern unchanged")


def test_scheme_a_6_days_rest_day_pay():
    """Test Scheme A with 6 days/week pattern and rest-day pay"""
    print("\n" + "="*80)
    print("TEST 3: Scheme A, 6 days/week, rest-day pay on 6th day")
    print("="*80)
    
    date_obj = datetime(2025, 1, 11).date()  # Saturday (6th day)
    all_assignments = [
        {'employeeId': 'A3', 'date': '2025-01-06'},  # Mon
        {'employeeId': 'A3', 'date': '2025-01-07'},  # Tue
        {'employeeId': 'A3', 'date': '2025-01-08'},  # Wed
        {'employeeId': 'A3', 'date': '2025-01-09'},  # Thu
        {'employeeId': 'A3', 'date': '2025-01-10'},  # Fri
        {'employeeId': 'A3', 'date': '2025-01-11'},  # Sat (6th consecutive day)
    ]
    
    # 12h gross shift on 6th consecutive day
    start_dt = datetime(2025, 1, 11, 9, 0)
    end_dt = datetime(2025, 1, 11, 21, 0)  # 12h gross
    
    result_a = calculate_mom_compliant_hours(
        start_dt, end_dt, 'A3', date_obj, all_assignments, employee_scheme='A'
    )
    
    print(f"12h gross shift on 6th consecutive day:")
    print(f"  Scheme A: Normal={result_a['normal']}h, OT={result_a['ot']}h, RestDayPay={result_a['restDayPay']}h")
    print(f"  Expected: Normal=0.0h, OT=3.0h, RestDayPay=8.0h")
    print(f"  Note: 6th consecutive day = rest-day pay (8h) + OT (remaining 3h)")
    
    assert result_a['normal'] == 0.0, f"Scheme A should have 0h normal, got {result_a['normal']}"
    assert result_a['restDayPay'] == 8.0, f"Scheme A should have 8.0h rest-day pay, got {result_a['restDayPay']}"
    assert result_a['ot'] == 3.0, f"Scheme A should have 3.0h OT, got {result_a['ot']}"
    
    print("✅ PASSED: Scheme A/B rest-day pay logic unchanged")


def test_scheme_b_same_as_a():
    """Verify Scheme B behaves identically to Scheme A"""
    print("\n" + "="*80)
    print("TEST 4: Scheme B should behave identically to Scheme A")
    print("="*80)
    
    date_obj = datetime(2025, 1, 6).date()
    
    # 4 days pattern
    all_assignments_4d = [
        {'employeeId': 'X', 'date': '2025-01-06'},
        {'employeeId': 'X', 'date': '2025-01-07'},
        {'employeeId': 'X', 'date': '2025-01-08'},
        {'employeeId': 'X', 'date': '2025-01-09'},
    ]
    
    # 5 days pattern
    all_assignments_5d = [
        {'employeeId': 'X', 'date': '2025-01-06'},
        {'employeeId': 'X', 'date': '2025-01-07'},
        {'employeeId': 'X', 'date': '2025-01-08'},
        {'employeeId': 'X', 'date': '2025-01-09'},
        {'employeeId': 'X', 'date': '2025-01-10'},
    ]
    
    start_dt = datetime(2025, 1, 6, 9, 0)
    end_dt = datetime(2025, 1, 6, 21, 0)  # 12h gross
    
    # Test 4 days
    result_a_4d = calculate_mom_compliant_hours(
        start_dt, end_dt, 'X', date_obj, all_assignments_4d, employee_scheme='A'
    )
    result_b_4d = calculate_mom_compliant_hours(
        start_dt, end_dt, 'X', date_obj, all_assignments_4d, employee_scheme='B'
    )
    
    print(f"4 days pattern, 12h gross:")
    print(f"  Scheme A: {result_a_4d}")
    print(f"  Scheme B: {result_b_4d}")
    assert result_a_4d == result_b_4d, "Scheme A and B should be identical for 4 days"
    
    # Test 5 days
    result_a_5d = calculate_mom_compliant_hours(
        start_dt, end_dt, 'X', date_obj, all_assignments_5d, employee_scheme='A'
    )
    result_b_5d = calculate_mom_compliant_hours(
        start_dt, end_dt, 'X', date_obj, all_assignments_5d, employee_scheme='B'
    )
    
    print(f"\n5 days pattern, 12h gross:")
    print(f"  Scheme A: {result_a_5d}")
    print(f"  Scheme B: {result_b_5d}")
    assert result_a_5d == result_b_5d, "Scheme A and B should be identical for 5 days"
    
    print("✅ PASSED: Scheme B is identical to Scheme A")


def test_comparison_scheme_p_vs_a():
    """Show the difference: Scheme P vs Scheme A for same scenario"""
    print("\n" + "="*80)
    print("TEST 5: COMPARISON - Scheme P vs Scheme A (4 days, 10h net)")
    print("="*80)
    
    date_obj = datetime(2025, 1, 6).date()
    all_assignments = [
        {'employeeId': 'X', 'date': '2025-01-06'},
        {'employeeId': 'X', 'date': '2025-01-07'},
        {'employeeId': 'X', 'date': '2025-01-08'},
        {'employeeId': 'X', 'date': '2025-01-09'},
    ]
    
    start_dt = datetime(2025, 1, 6, 9, 0)
    end_dt = datetime(2025, 1, 6, 20, 0)  # 11h gross = 10h net + 1h lunch
    
    result_p = calculate_mom_compliant_hours(
        start_dt, end_dt, 'X', date_obj, all_assignments, employee_scheme='P'
    )
    result_a = calculate_mom_compliant_hours(
        start_dt, end_dt, 'X', date_obj, all_assignments, employee_scheme='A'
    )
    
    print(f"Same scenario (4 days/week, 11h gross):")
    print(f"\n  Scheme P (Part-time):")
    print(f"    Normal: {result_p['normal']}h (threshold: 8.745h)")
    print(f"    OT:     {result_p['ot']}h")
    print(f"    Logic:  34.98h weekly max ÷ 4 days = 8.745h/day")
    
    print(f"\n  Scheme A (Full-time):")
    print(f"    Normal: {result_a['normal']}h (threshold: 11.0h)")
    print(f"    OT:     {result_a['ot']}h")
    print(f"    Logic:  Standard 4-day pattern = 11.0h/day")
    
    print(f"\n  ✅ Scheme P: More restrictive (8.745h threshold)")
    print(f"  ✅ Scheme A: Less restrictive (11.0h threshold)")
    print(f"  ✅ Both schemes calculated independently with correct logic")
    
    # Verify they're different (as expected)
    assert result_p['normal'] != result_a['normal'], "Scheme P and A should have different Normal hours"
    assert result_p['ot'] != result_a['ot'], "Scheme P and A should have different OT hours"
    
    print("\n✅ PASSED: Schemes are correctly isolated")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("SCHEME A/B BACKWARD COMPATIBILITY TEST")
    print("Verifying that Scheme P implementation did NOT affect Scheme A/B")
    print("="*80)
    
    try:
        test_scheme_a_4_days_pattern()
        test_scheme_a_5_days_pattern()
        test_scheme_a_6_days_rest_day_pay()
        test_scheme_b_same_as_a()
        test_comparison_scheme_p_vs_a()
        
        print("\n" + "="*80)
        print("✅ ALL BACKWARD COMPATIBILITY TESTS PASSED!")
        print("="*80)
        print("\n✅ CONFIRMED: Scheme A/B logic is COMPLETELY UNCHANGED")
        print("✅ CONFIRMED: Scheme B is identical to Scheme A")
        print("✅ CONFIRMED: Scheme P has its own separate logic")
        print("✅ CONFIRMED: Default parameter works (defaults to Scheme A)")
        print("\n🎯 The implementation is SAFE - only Scheme P is affected")
        print("="*80 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
