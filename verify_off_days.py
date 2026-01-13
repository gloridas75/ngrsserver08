import json

# Load output file
with open('RST-20260113-C9FE1E08_Solver_Output.json', 'r') as f:
    output = json.load(f)

print("="*80)
print("OFF_DAYS VERIFICATION REPORT")
print("="*80)

# Check assignments block
off_day_assignments = [a for a in output['assignments'] if a['status'] == 'OFF_DAY']
print(f"\n1. ASSIGNMENTS BLOCK:")
print(f"   Total OFF_DAY entries: {len(off_day_assignments)}")
print(f"   Sample OFF_DAY assignment:")
if off_day_assignments:
    sample = off_day_assignments[0]
    print(f"   - Date: {sample['date']}")
    print(f"   - EmployeeId: {sample['employeeId']}")
    print(f"   - Status: {sample['status']}")
    print(f"   - ShiftCode: {sample['shiftCode']}")
    print(f"   - Hours: {sample['hours']}")

# Check employeeRoster block
total_off_days_in_roster = 0
for emp in output['employeeRoster']:
    off_days = [d for d in emp['dailyStatus'] if d['status'] == 'OFF_DAY']
    total_off_days_in_roster += len(off_days)

print(f"\n2. EMPLOYEE ROSTER BLOCK:")
print(f"   Total OFF_DAY entries: {total_off_days_in_roster}")
print(f"   Sample from first employee:")
first_emp = output['employeeRoster'][0]
off_days = [d for d in first_emp['dailyStatus'] if d['status'] == 'OFF_DAY']
if off_days:
    sample = off_days[0]
    print(f"   - Employee: {first_emp['employeeId']}")
    print(f"   - Date: {sample['date']}")
    print(f"   - Status: {sample['status']}")
    print(f"   - ShiftCode: {sample['shiftCode']}")
    print(f"   - PatternDay: {sample['patternDay']}")

# Check roster summary
print(f"\n3. ROSTER SUMMARY:")
print(f"   By Status: {output['rosterSummary']['byStatus']}")

# Verify consistency
print(f"\n4. CONSISTENCY CHECK:")
print(f"   OFF_DAYs in assignments: {len(off_day_assignments)}")
print(f"   OFF_DAYs in employeeRoster: {total_off_days_in_roster}")
print(f"   OFF_DAYs in rosterSummary: {output['rosterSummary']['byStatus']['OFF_DAY']}")

discrepancy = len(off_day_assignments) != total_off_days_in_roster
if discrepancy:
    print(f"\n   ⚠️  DISCREPANCY DETECTED:")
    print(f"   assignments has {len(off_day_assignments)} OFF_DAYs")
    print(f"   employeeRoster has {total_off_days_in_roster} OFF_DAYs")
    print(f"   Difference: {abs(len(off_day_assignments) - total_off_days_in_roster)}")
else:
    print(f"\n   ✅ All counts match!")

print("\n" + "="*80)
