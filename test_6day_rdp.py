#!/usr/bin/env python3
"""Test rest day pay for 6-day work patterns."""

from datetime import datetime, timedelta
from context.engine.time_utils import calculate_apgd_d10_hours

# Test scenario: 6 consecutive work days (Mon-Sat) for APGD-D10 employee
# Days 1-5: 8.8h normal + 2.2h OT each
# Day 6 (Sat): 0h normal + 8h RDP + 3h OT

employee_id = "TEST001"

# Create mock assignments for Jan 5-11, 2026 (Week 2 of planning period)
# Mon-Sat: 6 consecutive 12h shifts (08:00-20:00)
# Sun: OFF

assignments = []
start_date = datetime(2026, 1, 5)  # Monday

for i in range(7):
    date = start_date + timedelta(days=i)
    date_str = date.strftime('%Y-%m-%d')
    
    if i < 6:  # Mon-Sat (work days)
        assignments.append({
            'employeeId': employee_id,
            'date': date_str,
            'shiftCode': 'D',
            'startDateTime': f"{date_str}T08:00:00",
            'endDateTime': f"{date_str}T20:00:00",
            'status': 'ASSIGNED'
        })
    else:  # Sun (OFF)
        assignments.append({
            'employeeId': employee_id,
            'date': date_str,
            'shiftCode': 'O',
            'status': 'OFF_DAY'
        })

print("Testing 6-Day Pattern with Rest Day Pay")
print("=" * 70)
print(f"\nEmployee: {employee_id}")
print(f"Week: {start_date.strftime('%Y-%m-%d')} to {(start_date + timedelta(days=6)).strftime('%Y-%m-%d')}")
print(f"Pattern: 6 work days (Mon-Sat) + 1 OFF day (Sun)\n")

# Calculate hours for each work day
weekly_normal = 0
weekly_ot = 0
weekly_rdp = 0
weekly_gross = 0

print("Daily breakdown:")
print("-" * 70)

for i, asg in enumerate(assignments[:6]):  # Only work days
    date = start_date + timedelta(days=i)
    date_obj = date.date()
    
    start_dt = datetime.fromisoformat(asg['startDateTime'])
    end_dt = datetime.fromisoformat(asg['endDateTime'])
    
    # Calculate hours
    hours = calculate_apgd_d10_hours(
        start_dt=start_dt,
        end_dt=end_dt,
        employee_id=employee_id,
        assignment_date_obj=date_obj,
        all_assignments=assignments,
        employee_dict={'employeeId': employee_id, 'scheme': 'A', 'productTypeId': 'APO'}
    )
    
    weekly_normal += hours['normal']
    weekly_ot += hours['ot']
    weekly_rdp += hours['restDayPay']
    weekly_gross += hours['gross']
    
    day_name = date.strftime('%a')
    position = i + 1
    print(f"Day {position} ({day_name} {asg['date']}): "
          f"{hours['gross']:4.1f}h gross, "
          f"{hours['normal']:4.1f}h normal, "
          f"{hours['ot']:4.1f}h OT, "
          f"{hours['restDayPay']:2.0f}h RDP")

print("-" * 70)
print(f"Weekly totals:")
print(f"  Gross hours:      {weekly_gross:5.1f}h")
print(f"  Normal hours:     {weekly_normal:5.1f}h")
print(f"  OT hours:         {weekly_ot:5.1f}h")
print(f"  Rest day pay:     {weekly_rdp:5.0f}h")

print("\nMOM Compliance Check:")
print("-" * 70)
if weekly_normal <= 44:
    print(f"✅ PASS: {weekly_normal:.1f}h ≤ 44h weekly normal cap")
else:
    print(f"❌ FAIL: {weekly_normal:.1f}h > 44h weekly normal cap")

print("\nExpected vs Actual:")
print("-" * 70)
print("Expected:")
print("  Days 1-5: 5 × 8.8h normal = 44.0h")
print("  Day 6:    1 × 0.0h normal =  0.0h (rest day pay)")
print("  Total:    44.0h normal")
print(f"\nActual:")
print(f"  Total:    {weekly_normal:.1f}h normal")

if abs(weekly_normal - 44.0) < 0.1:
    print(f"\n✅ SUCCESS: Rest day pay logic working correctly!")
else:
    print(f"\n❌ FAILURE: Rest day pay NOT applied correctly!")
