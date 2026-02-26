#!/usr/bin/env python3
"""Test script for Scheme A + SO hour calculation changes."""

from context.engine.time_utils import is_apgd_d10_employee, normalize_scheme, get_monthly_hour_limits
import json

def test_apgd_detection():
    """Test that APGD-D10 correctly identifies only Scheme A + APO."""
    print("=== APGD-D10 Detection Tests ===")
    
    # Test 1: Scheme A + APO should be APGD-D10
    emp_apo = {'scheme': 'Scheme A', 'productTypeId': 'APO', 'local': 1}
    result = is_apgd_d10_employee(emp_apo)
    print(f"Scheme A + APO is_apgd_d10: {result} (expected: True)")
    assert result == True, "Scheme A + APO should be APGD-D10"
    
    # Test 2: Scheme A + SO should NOT be APGD-D10
    emp_so = {'scheme': 'Scheme A', 'productTypeId': 'SO', 'local': 1}
    result = is_apgd_d10_employee(emp_so)
    print(f"Scheme A + SO is_apgd_d10: {result} (expected: False)")
    assert result == False, "Scheme A + SO should NOT be APGD-D10"
    
    # Test 3: Scheme B + SO should NOT be APGD-D10
    emp_b_so = {'scheme': 'Scheme B', 'productTypeId': 'SO', 'local': 1}
    result = is_apgd_d10_employee(emp_b_so)
    print(f"Scheme B + SO is_apgd_d10: {result} (expected: False)")
    assert result == False, "Scheme B + SO should NOT be APGD-D10"
    
    print("✅ All APGD-D10 detection tests passed!\n")

def test_monthly_hour_limits_defaults():
    """Test monthly hour limits with default values."""
    print("=== Monthly Hour Limits (Defaults) ===")
    
    emp_so = {'scheme': 'Scheme A', 'productTypeId': 'SO', 'local': 1}
    
    expected = {28: 176, 29: 182, 30: 189, 31: 195}
    
    for month_len in [28, 29, 30, 31]:
        limits = get_monthly_hour_limits(month_len, emp_so, None)
        print(f"Month {month_len} days: normalCap={limits['normalHoursCap']}, maxOT={limits['maxOvertimeHours']}")
        assert limits['normalHoursCap'] == expected[month_len], f"Expected {expected[month_len]} for {month_len} days"
        assert limits['maxOvertimeHours'] == 72, "Max OT should be 72"
    
    print("✅ All default tests passed!\n")

def test_monthly_hour_limits_with_input():
    """Test monthly hour limits with actual input JSON."""
    print("=== Monthly Hour Limits (With Input JSON) ===")
    
    with open('input/test2_21022026.json', 'r') as f:
        input_data = json.load(f)
    
    # Scheme A + APO (Local) - should get minimumContractualHours from apgdMinimumContractualHours
    emp_apo_local = {'scheme': 'Scheme A', 'productTypeId': 'APO', 'local': 1}
    limits_apo = get_monthly_hour_limits(31, emp_apo_local, input_data)
    print(f"Scheme A + APO (Local, 31 days): {limits_apo}")
    
    # Scheme A + SO - should get normalHours from standardMonthlyHours
    emp_so_a = {'scheme': 'Scheme A', 'productTypeId': 'SO', 'local': 1}
    limits_so_a = get_monthly_hour_limits(31, emp_so_a, input_data)
    print(f"Scheme A + SO (31 days): {limits_so_a}")
    assert limits_so_a['normalHoursCap'] == 195, "Scheme A + SO should use standard 195h for 31 days"
    
    # Scheme B + SO - should get normalHours from standardMonthlyHours
    emp_so_b = {'scheme': 'Scheme B', 'productTypeId': 'SO', 'local': 1}
    limits_so_b = get_monthly_hour_limits(31, emp_so_b, input_data)
    print(f"Scheme B + SO (31 days): {limits_so_b}")
    assert limits_so_b['normalHoursCap'] == 195, "Scheme B + SO should use standard 195h for 31 days"
    
    print("✅ All input JSON tests passed!\n")

if __name__ == '__main__':
    test_apgd_detection()
    test_monthly_hour_limits_defaults()
    test_monthly_hour_limits_with_input()
    print("🎉 All tests passed!")
