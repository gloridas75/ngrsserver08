"""Debug script to understand why OT-aware ICPMP fails."""

import json
from datetime import datetime
from context.engine.config_optimizer_v3 import try_placement_with_n_employees

# Test with small numbers first
pattern = ['D', 'D', 'D', 'O', 'D', 'D', 'D']  # 6 work days
headcount = 2  # Start small
anchor_date = "2025-01-01"
calendar = [f"2025-01-{day:02d}" for day in range(1, 8)]  # Just 1 week

print("Testing with 5 employees, HC=2, 7 days, Scheme P, OT-aware")
print("=" * 80)

result = try_placement_with_n_employees(
    num_employees=5,
    pattern=pattern,
    headcount=headcount,
    calendar=calendar,
    anchor_date=anchor_date,
    cycle_length=len(pattern),
    scheme="P",
    enable_ot_aware=True
)

print(f"Feasible: {result['is_feasible']}")
print(f"Coverage rate: {result['coverage_rate']:.1f}%")
print(f"Total work days: {result['total_work_days']}")
print(f"Total U-slots: {result['total_u_slots']}")
print()

print("Employee patterns:")
for emp in result['employees']:
    print(f"  Emp {emp['employeeNumber']} (offset {emp['rotationOffset']}): {emp['pattern']}")
    print(f"    Work: {emp['workDays']}, U: {emp['uSlots']}, Rest: {emp['restDays']}")

print()
print("Daily coverage:")
for date, count in result['daily_coverage'].items():
    print(f"  {date}: {count}/{headcount}")
