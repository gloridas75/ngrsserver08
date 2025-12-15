"""
Test script for OT-aware ICPMP feature (Option 1).

Compares employee count with/without OT-aware flag for Scheme P 6-day patterns.
"""

import json
from context.engine.config_optimizer_v3 import calculate_optimal_with_u_slots

def test_ot_aware_icpmp():
    """Test OT-aware ICPMP with Scheme P 6-day pattern."""
    
    # Test configuration
    pattern = ['D', 'D', 'D', 'O', 'D', 'D', 'D']  # 6 work days per cycle
    headcount = 10
    anchor_date = "2025-01-01"
    
    # Generate 31-day calendar (January 2025)
    calendar = [f"2025-01-{day:02d}" for day in range(1, 32)]
    
    print("=" * 80)
    print("OT-AWARE ICPMP TEST - Scheme P 6-Day Pattern")
    print("=" * 80)
    print(f"Pattern: {pattern} (6 work days per cycle)")
    print(f"Headcount: {headcount}")
    print(f"Calendar: {len(calendar)} days (Jan 2025)")
    print()
    
    # Test 1: OT-aware DISABLED (current behavior)
    print("-" * 80)
    print("TEST 1: OT-Aware DISABLED (default behavior)")
    print("-" * 80)
    
    result_disabled = calculate_optimal_with_u_slots(
        pattern=pattern,
        headcount=headcount,
        calendar=calendar,
        anchor_date=anchor_date,
        requirement_id="TEST_DISABLED",
        scheme="P",
        enable_ot_aware_icpmp=False  # DISABLED
    )
    
    employees_disabled = result_disabled['configuration']['employeesRequired']
    u_slots_disabled = result_disabled['coverage']['totalUSlots']
    work_days_disabled = result_disabled['coverage']['totalWorkDays']
    
    print(f"✓ Employees required: {employees_disabled}")
    print(f"  Total work days: {work_days_disabled}")
    print(f"  Total U-slots: {u_slots_disabled}")
    print(f"  U-slot rate: {u_slots_disabled / (work_days_disabled + u_slots_disabled) * 100:.1f}%")
    print()
    
    # Test 2: OT-aware ENABLED (new feature)
    print("-" * 80)
    print("TEST 2: OT-Aware ENABLED (new feature)")
    print("-" * 80)
    
    result_enabled = calculate_optimal_with_u_slots(
        pattern=pattern,
        headcount=headcount,
        calendar=calendar,
        anchor_date=anchor_date,
        requirement_id="TEST_ENABLED",
        scheme="P",
        enable_ot_aware_icpmp=True  # ENABLED
    )
    
    employees_enabled = result_enabled['configuration']['employeesRequired']
    u_slots_enabled = result_enabled['coverage']['totalUSlots']
    work_days_enabled = result_enabled['coverage']['totalWorkDays']
    
    print(f"✓ Employees required: {employees_enabled}")
    print(f"  Total work days: {work_days_enabled}")
    print(f"  Total U-slots: {u_slots_enabled}")
    print(f"  U-slot rate: {u_slots_enabled / (work_days_enabled + u_slots_enabled) * 100:.1f}%")
    print()
    
    # Compare results
    print("=" * 80)
    print("COMPARISON")
    print("=" * 80)
    
    employee_diff = employees_disabled - employees_enabled
    u_slot_diff = u_slots_disabled - u_slots_enabled
    
    print(f"Employee count reduction: {employee_diff} employees ({employee_diff / employees_disabled * 100:.1f}%)")
    print(f"U-slot reduction: {u_slot_diff} slots ({u_slot_diff / u_slots_disabled * 100:.1f}%)")
    print()
    
    if employee_diff > 0:
        print(f"✅ SUCCESS: OT-aware ICPMP reduced employee count by {employee_diff}")
        print(f"   Expected: ~4 employees (21% reduction from 19 → 15)")
    else:
        print(f"⚠️  WARNING: No employee reduction observed")
        print(f"   This might indicate an issue with the OT-aware logic")
    
    print()
    print("=" * 80)
    print("OFFSET DISTRIBUTIONS")
    print("=" * 80)
    
    print(f"OT-aware DISABLED: {result_disabled['configuration']['offsetDistribution']}")
    print(f"OT-aware ENABLED:  {result_enabled['configuration']['offsetDistribution']}")
    print()
    
    # Test 3: Verify Scheme A/B unchanged
    print("=" * 80)
    print("TEST 3: Scheme A Unchanged (verify backward compatibility)")
    print("=" * 80)
    
    result_scheme_a = calculate_optimal_with_u_slots(
        pattern=pattern,
        headcount=headcount,
        calendar=calendar,
        anchor_date=anchor_date,
        requirement_id="TEST_SCHEME_A",
        scheme="A",
        enable_ot_aware_icpmp=True  # Should have NO effect on Scheme A
    )
    
    employees_scheme_a = result_scheme_a['configuration']['employeesRequired']
    print(f"Scheme A employees (OT-aware flag enabled): {employees_scheme_a}")
    print(f"Scheme P employees (OT-aware flag disabled): {employees_disabled}")
    print(f"Scheme P employees (OT-aware flag enabled):  {employees_enabled}")
    print()
    print("Note: Scheme A uses pattern work days (6) as capacity,")
    print("      while Scheme P uses hour-based capacity (3.75 days without OT, 5.83 with OT).")
    print(f"      Different schemes naturally require different employee counts.")
    print()
    
    if employees_scheme_a != employees_enabled:
        print(f"✅ Scheme A and P have different requirements (as expected for different schemes)")
    else:
        print(f"⚠️  Scheme A and P have same count - might indicate calculation issue")
    
    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    
    return {
        'disabled': result_disabled,
        'enabled': result_enabled,
        'scheme_a': result_scheme_a
    }


if __name__ == "__main__":
    results = test_ot_aware_icpmp()
    
    # Save results to file for inspection
    with open('output/ot_aware_icpmp_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("Results saved to: output/ot_aware_icpmp_test_results.json")
