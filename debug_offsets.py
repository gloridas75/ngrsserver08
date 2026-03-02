"""Check optimized offsets and pattern for each employee around March 21."""
import json, subprocess

result = subprocess.run(
    ["curl", "-s", "https://ngrssolver09.comcentricapps.com/solve/async/33c9c343-e1df-45b4-8ff4-6bec41ed36e6/result"],
    capture_output=True, text=True
)
data = json.loads(result.stdout)
assignments = data.get('assignments', [])

# Check each employee's assignments around March 19-22
emp_ids = sorted(set(a.get('employeeId') for a in assignments))

for emp_id in emp_ids:
    print(f"\n=== Employee {emp_id} ===")
    days = [a for a in assignments if a.get('employeeId') == emp_id and '2026-03-15' <= a.get('date', '') <= '2026-03-22']
    days.sort(key=lambda x: x.get('date'))
    for a in days:
        from datetime import datetime
        d = datetime.fromisoformat(a['date']).date()
        day_name = d.strftime('%a')
        print(f"  {a['date']} ({day_name}) | shift={a.get('shiftCode'):3s} | status={a.get('status'):16s} | offset={a.get('newRotationOffset', '?')}")

# Check if any employee has a D or N shift on any Saturday or Sunday
print("\n=== Weekend assignments check ===")
for emp_id in emp_ids:
    weekends = [a for a in assignments if a.get('employeeId') == emp_id]
    for a in weekends:
        from datetime import datetime
        d = datetime.fromisoformat(a['date']).date()
        if d.weekday() >= 5 and a.get('shiftCode') in ('D', 'N'):
            print(f"  {emp_id}: {a['date']} ({d.strftime('%a')}) shift={a.get('shiftCode')}")
