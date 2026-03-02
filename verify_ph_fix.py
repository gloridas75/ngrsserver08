"""Verify PH fix: check March 21 and W12 data from production."""
import json, subprocess

result = subprocess.run(
    ["curl", "-s", "https://ngrssolver09.comcentricapps.com/solve/async/33c9c343-e1df-45b4-8ff4-6bec41ed36e6/result"],
    capture_output=True, text=True
)
data = json.loads(result.stdout)
assignments = data.get('assignments', [])

print("=" * 70)
print("VERIFICATION: PH Day Fix (March 21, 2026)")
print("=" * 70)

# Issue 2: Check March 21 shift codes (should be O/OFF_DAY, not PH)
ph_day = [a for a in assignments if a.get('date') == '2026-03-21']
print(f"\n--- March 21 (PH) Assignments ({len(ph_day)} employees) ---")
all_off_day = True
for a in ph_day:
    sc = a.get('shiftCode')
    st = a.get('status')
    is_ok = sc == 'O' and st == 'OFF_DAY'
    if not is_ok:
        all_off_day = False
    print(f"  {a['employeeId']} | shift={sc:3s} | status={st:16s} | {'PASS' if is_ok else 'FAIL - SHOULD BE O/OFF_DAY'}")
print(f"\n  Issue 2 (PH shows as Off Day): {'PASS - ALL CORRECT' if all_off_day else 'FAIL'}")

# Issue 1: Check W12 normal hours (should be 8.80, not 7.33)
emp_id = '00100008'
w12 = [a for a in assignments if a.get('employeeId') == emp_id and '2026-03-16' <= a.get('date', '') <= '2026-03-22']
w12.sort(key=lambda x: x.get('date'))

print(f"\n--- W12 for {emp_id} (Mar 16-22) ---")
work_day_count = 0
normal_correct = True
for a in w12:
    h = a.get('hours', {})
    sc = a.get('shiftCode')
    st = a.get('status')
    normal = h.get('normal', 0)
    ot = h.get('ot', 0)
    gross = h.get('gross', 0)
    
    if sc in ('D', 'N') and st == 'ASSIGNED':
        work_day_count += 1
        if abs(normal - 8.80) > 0.01:
            normal_correct = False
            
    print(f"  {a['date']} | shift={sc:3s} | status={st:16s} | normal={normal:5.2f} | ot={ot:5.2f} | gross={gross:5.2f}")

print(f"\n  Actual work days in W12: {work_day_count}")
if work_day_count > 0:
    print(f"  Expected normal: 44/{work_day_count} = {44.0/work_day_count:.2f}h")
print(f"  Issue 1 (Normal=8.80h, not 7.33h): {'PASS' if normal_correct else 'FAIL'}")

# Cross-check with W11 (no PH)
w11 = [a for a in assignments if a.get('employeeId') == emp_id and '2026-03-09' <= a.get('date', '') <= '2026-03-15']
w11.sort(key=lambda x: x.get('date'))
print(f"\n--- W11 for {emp_id} (Mar 9-15, no PH, reference) ---")
for a in w11:
    h = a.get('hours', {})
    print(f"  {a['date']} | shift={a.get('shiftCode'):3s} | normal={h.get('normal',0):5.2f} | ot={h.get('ot',0):5.2f}")

# Check overall monthly OT
print(f"\n--- Monthly OT Summary ---")
emp_ids = sorted(set(a.get('employeeId') for a in assignments))
for eid in emp_ids:
    emp_a = [a for a in assignments if a.get('employeeId') == eid and a.get('status') == 'ASSIGNED']
    total_ot = sum(a.get('hours', {}).get('ot', 0) for a in emp_a)
    total_normal = sum(a.get('hours', {}).get('normal', 0) for a in emp_a)
    total_gross = sum(a.get('hours', {}).get('gross', 0) for a in emp_a)
    print(f"  {eid}: Normal={total_normal:.2f}h | OT={total_ot:.2f}h | Gross={total_gross:.2f}h | OT<=72: {'PASS' if total_ot <= 72.0 else 'FAIL'}")

print("\n" + "=" * 70)
print("VERIFICATION COMPLETE")
print("=" * 70)
