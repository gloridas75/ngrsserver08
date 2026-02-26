"""Analyze OT calculation discrepancy."""
import json
from collections import defaultdict
from datetime import datetime

with open('/tmp/result.json') as f:
    data = json.load(f)

# Count assignments per employee
emp_assign = defaultdict(list)

for a in data.get('assignments', []):
    eid = a.get('employeeId')
    if eid:
        emp_assign[eid].append(a)

# Analyze one employee in detail
eid = '00100008'
assigns = emp_assign[eid]

# Calculate total hours
total_gross = 0
solver_ot = 0
output_ot = 0
output_normal = 0

for a in assigns:
    h = a.get('hours', {})
    gross = h.get('gross', 0)
    total_gross += gross
    # Solver logic: OT = max(0, gross - 9) per shift
    daily_ot = max(0, gross - 9)
    solver_ot += daily_ot
    output_ot += h.get('ot', 0)
    output_normal += h.get('normal', 0)

print(f"=== Employee {eid} ===")
print(f"Total gross hours: {total_gross:.2f}")
print(f"Solver OT calc (gross-9 per shift): {solver_ot:.2f}")
print(f"Output normal hours: {output_normal:.2f}")
print(f"Output OT hours: {output_ot:.2f}")

# Group by week
weeks = defaultdict(lambda: {'gross': 0, 'normal': 0, 'ot': 0, 'days': 0})
for a in assigns:
    if a.get('status') == 'UNASSIGNED':
        continue
    dt = datetime.strptime(a['date'], '%Y-%m-%d')
    iso = dt.isocalendar()
    week_key = "W" + str(iso.week)
    h = a.get('hours', {})
    weeks[week_key]['gross'] += h.get('gross', 0)
    weeks[week_key]['normal'] += h.get('normal', 0)
    weeks[week_key]['ot'] += h.get('ot', 0)
    weeks[week_key]['days'] += 1

print("\n=== Weekly breakdown ===")
print("Week   Days   Gross      Normal     OT")
print("-" * 45)
total_weekly_ot = 0
for wk in sorted(weeks.keys()):
    w = weeks[wk]
    weekly_ot = max(0, w['gross'] - 44)
    total_weekly_ot += weekly_ot
    print(f"{wk:<6} {w['days']:<6} {w['gross']:<10.2f} {w['normal']:<10.2f} {w['ot']:<10.2f}")

print("-" * 45)
print(f"\n44h/week based OT would be: {total_weekly_ot:.2f}h")
