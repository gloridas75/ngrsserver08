#!/usr/bin/env python3
"""
Quick test to verify C2 pattern-aware logic for 6-day patterns.

Tests that 6-day pattern (DDDDDOD) correctly applies:
- Position 1-5: 8.8h normal per shift
- Position 6+: 0h normal (rest day pay)
- Weekly total: 5 × 8.8h = 44h (compliant!)
"""

def test_pattern_aware_logic():
    """Test the pattern-aware normal hours calculation."""
    
    # Simulate a 6-day pattern: DDDDDOD
    work_pattern = ['D', 'D', 'D', 'D', 'D', 'O', 'D']
    work_days_in_pattern = sum(1 for day in work_pattern if day not in ['O', '0'])
    pattern_length = len(work_pattern)
    
    print(f"Work Pattern: {work_pattern}")
    print(f"Work days: {work_days_in_pattern}, Pattern length: {pattern_length}")
    print(f"Estimated work days/week: {(work_days_in_pattern / pattern_length) * 7:.1f}")
    print()
    
    # 12-hour shift: gross = 12h, lunch = 1h
    gross = 12.0
    lunch = 1.0
    
    # Test each pattern day
    print("Pattern Day | Position | Normal Hours | OT Hours | Weekly Cap Status")
    print("-" * 75)
    
    weekly_normal = 0.0
    
    for pattern_day in range(len(work_pattern)):
        day_type = work_pattern[pattern_day]
        
        if day_type in ['O', '0']:
            print(f"Day {pattern_day}       | OFF      | -            | -        | (off day)")
            continue
        
        # Count work days before this position
        work_days_before = sum(1 for i, day in enumerate(work_pattern[:pattern_day]) 
                             if day not in ['O', '0'])
        consecutive_position = work_days_before + 1
        
        # Apply pattern-aware logic
        estimated_work_days_per_week = (work_days_in_pattern / pattern_length) * 7.0
        
        if estimated_work_days_per_week >= 5.5:
            # 6+ days/week
            if consecutive_position >= 6:
                # 6th+ consecutive day: 0h normal (rest day pay)
                normal_hours = 0.0
                ot_hours = max(0.0, gross - lunch - 8.0)  # 8.0h rest day pay
                status = "REST DAY PAY (8.0h)"
            else:
                # Positions 1-5: 8.8h normal
                normal_hours = min(8.8, gross - lunch)
                ot_hours = max(0.0, gross - lunch - 8.8)
                status = "Normal"
        else:
            # Fallback (shouldn't happen with DDDDDOD)
            normal_hours = min(8.8, gross - lunch)
            ot_hours = max(0.0, gross - lunch - 8.8)
            status = "Normal"
        
        weekly_normal += normal_hours
        
        print(f"Day {pattern_day}       | Pos {consecutive_position}    | {normal_hours:6.1f}h      | {ot_hours:5.1f}h | {status}")
    
    print("-" * 75)
    print(f"TOTAL WEEKLY NORMAL HOURS: {weekly_normal:.1f}h")
    print()
    
    if weekly_normal <= 44.0:
        print(f"✅ COMPLIANT: {weekly_normal:.1f}h <= 44h weekly cap")
    else:
        print(f"❌ VIOLATION: {weekly_normal:.1f}h > 44h weekly cap")
    
    print()
    print("Expected behavior:")
    print("  - Days 0-4 (positions 1-5): 5 × 8.8h = 44.0h normal")
    print("  - Day 6 (position 6): 0h normal (rest day pay = 8.0h)")
    print("  - Total: 44.0h normal (compliant!)")


if __name__ == '__main__':
    test_pattern_aware_logic()
