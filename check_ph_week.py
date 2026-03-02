"""Check PH week data from production output."""
import json, subprocess, sys

result = subprocess.run(
    ["curl", "-s", "https://ngrssolver09.comcentricapps.com/solve/async/889cd582-b95c-409e-b0ad-9ebb169aa74b/result"],
    capture_output=True, text=True
)
data = json.loads(result.stdout)
assignments = data.get('assignments', [])
emp_id = '00100008'

# Full week W12 (March 16-22)
w12 = [a for a in assignments if a.get('employeeId') == emp_id and '2026-03-16' <= a.get('date', '') <= '2026-03-22']
w12.sort(key=lambda x: x.get('date'))
print(f"=== W12 for {emp_id} (Mar 16-22, Mon-Sun) ===")
for a in w12:
    h = a.get('hours', {})
    print(f"  {a['date']} | shift={a.get('shiftCode'):3s} | status={a.get('status'):16s} | normal={h.get('normal',0):5.2f} | ot={h.get('ot',0):5.2f} | gross={h.get('gross',0):5.2f}")

# Count work days
work_days = [a for a in w12 if a.get('shiftCode') not in ('O', None)]
print(f"\nShifts != O in W12: {len(work_days)}")
for w in work_days:
    print(f"  {w['date']} shift={w.get('shiftCode')}")

# Non-PH week W11 (Mar 9-15)
w11 = [a for a in assignments if a.get('employeeId') == emp_id and '2026-03-09' <= a.get('date', '') <= '2026-03-15']
w11.sort(key=lambda x: x.get('date'))
print(f"\n=== W11 for {emp_id} (Mar 9-15, no PH) ===")
for a in w11:
    h = a.get('hours', {})
    print(f"  {a['date']} | shift={a.get('shiftCode'):3s} | status={a.get('status'):16s} | normal={h.get('normal',0):5.2f} | ot={h.get('ot',0):5.2f} | gross={h.get('gross',0):5.2f}")

# Summary for all employees on March 21
print(f"\n=== All employees on March 21 ===")
ph_day = [a for a in assignments if a.get('date') == '2026-03-21']
for a in ph_day:
    print(f"  {a['employeeId']} | shift={a.get('shiftCode'):3s} | status={a.get('status')}")
