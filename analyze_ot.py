"""Analyze OT calculation - after C17 fix."""
import json
from collections import defaultdict
from datetime import datetime

with open('/tmp/result3.json') as f:
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
output_ot = 0
output_normal = 0

for a in assigns:
    h = a.get('hours', {})
    gross = h.get('gross', 0)
    total_gross += gross
    output_ot += h.get('ot', 0)
    output_normal += h.get('normal', 0)

print("=== Employee", eid, "===")
print("Total gross hours:", round(total_gross, 2))
print("Output normal hours:", round(output_normal, 2))
print("Output OT hours:", round(output_ot, 2))

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
print("Week   Days   Gross      Normal     OT         Weekly_OT_calc")
print("-" * 65)
total_weekly_ot = 0
for wk in sorted(weeks.keys()):
    w = weeks[wk]
    weekly_ot_calc = max(0, w['gross'] - 44)
    total_weekly_ot += weekly_ot_calc
    print("{:<6} {:<6} {:<10.2f} {:<10.2f} {:<10.2f} {:<10.2f}".format(
        wk, w['days'], w['gross'], w['normal'], w['ot'], weekly_ot_calc))

print("-" * 65)
print("Sum of weekly OT (gross-44 per week):", round(total_weekly_ot, 2))
print("\nOT is within 72h limit:", "YES" if output_ot <= 72 else "NO")
