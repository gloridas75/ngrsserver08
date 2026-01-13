import json

with open('RST-20260113-C9FE1E08_Solver_Output.json', 'r') as f:
    output = json.load(f)

# Get all OFF_DAYs from employeeRoster
roster_off_days = set()
for emp in output['employeeRoster']:
    for day in emp['dailyStatus']:
        if day['status'] == 'OFF_DAY':
            key = f"{emp['employeeId']}_{day['date']}"
            roster_off_days.add(key)

# Get all OFF_DAYs from assignments
assignment_off_days = set()
for a in output['assignments']:
    if a['status'] == 'OFF_DAY':
        key = f"{a['employeeId']}_{a['date']}"
        assignment_off_days.add(key)

# Find missing
missing = roster_off_days - assignment_off_days

print(f"OFF_DAYs in employeeRoster but NOT in assignments:")
print(f"Total missing: {len(missing)}\n")

# Group by employee
from collections import defaultdict
missing_by_emp = defaultdict(list)
for emp in output['employeeRoster']:
    for day in emp['dailyStatus']:
        if day['status'] == 'OFF_DAY':
            key = f"{emp['employeeId']}_{day['date']}"
            if key in missing:
                missing_by_emp[emp['employeeId']].append(day['date'])

for emp_id, dates in sorted(missing_by_emp.items()):
    print(f"Employee {emp_id}: {len(dates)} missing OFF_DAYs")
    for date in sorted(dates):
        print(f"  - {date}")
