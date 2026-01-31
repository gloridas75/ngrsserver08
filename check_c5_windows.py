#!/usr/bin/env python3
"""Check C5 constraint windows for Mar 1-2."""
from datetime import date, timedelta

pattern = ['D','D','D','D','O','D','D','D','D','D','O']
base_date = date(2026, 3, 1)

# Employee 00007901 has offset=1
offset = 1

# Check 7-day windows that include Mar 1
print('Employee 00007901 (offset=1) - 7-day windows:')
for window_start in range(-6, 2):  # Windows that include Mar 1
    work_days = 0
    window_dates = []
    for i in range(7):
        day = base_date + timedelta(days=window_start + i)
        days_from_base = (day - base_date).days
        pattern_idx = (days_from_base + offset) % len(pattern)
        status = pattern[pattern_idx]
        window_dates.append(f'{day.day:02d}/{status}')
        if status == 'D':
            work_days += 1
    start_day = (base_date + timedelta(days=window_start)).day
    end_day = (base_date + timedelta(days=window_start + 6)).day
    print(f'  Feb{start_day:02d}-Mar{end_day:02d}: {work_days} work days - {window_dates}')

# Check the planning horizon issue: planning starts Mar 1
# So the solver has no visibility into Feb days
print()
print('BUT: Planning horizon starts Mar 1!')
print('The solver only has Mar 1-31, not Feb days.')
print('So C5 cannot create constraints involving Feb dates.')
