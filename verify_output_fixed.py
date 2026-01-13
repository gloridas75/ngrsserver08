import json

with open('output/output_fixed.json', 'r') as f:
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

print(f"assignments OFF_DAYs: {len(assignment_off_days)}")
print(f"employeeRoster OFF_DAYs: {len(roster_off_days)}")
print(f"Missing from assignments: {len(missing)}")

if missing:
    from collections import defaultdict
    missing_by_emp = defaultdict(list)
    for emp in output['employeeRoster']:
        for day in emp['dailyStatus']:
            if day['status'] == 'OFF_DAY':
                key = f"{emp['employeeId']}_{day['date']}"
                if key in missing:
                    missing_by_emp[emp['employeeId']].append(day['date'])
    
    print("\nMissing OFF_DAYs by employee:")
    for emp_id, dates in sorted(missing_by_emp.items()):
        print(f"  {emp_id}: {len(dates)} missing")
else:
    print("\n✅ ALL OFF_DAYs present in both places!")
