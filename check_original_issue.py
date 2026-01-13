import json

print("="*80)
print("COMPARISON: ORIGINAL OUTPUT vs FIXED OUTPUT")
print("="*80)
print()

# Check original output (the one user provided)
print("ORIGINAL OUTPUT (RST-20260113-C9FE1E08_Solver_Output.json):")
print("─"*80)
try:
    with open('RST-20260113-C9FE1E08_Solver_Output.json', 'r') as f:
        original = json.load(f)
    
    orig_assignments_off = len([a for a in original['assignments'] if a.get('status') == 'OFF_DAY'])
    orig_roster_off = sum(len([d for d in emp['dailyStatus'] if d.get('status') == 'OFF_DAY']) 
                          for emp in original['employeeRoster'])
    orig_summary_off = original['rosterSummary']['byStatus']['OFF_DAY']
    
    print(f"  Assignments OFF_DAYs: {orig_assignments_off}")
    print(f"  EmployeeRoster OFF_DAYs: {orig_roster_off}")
    print(f"  RosterSummary OFF_DAYs: {orig_summary_off}")
    print(f"  Discrepancy: {abs(orig_assignments_off - orig_roster_off)}")
    
    if orig_assignments_off != orig_roster_off:
        print(f"  ❌ ISSUE CONFIRMED: Missing {orig_roster_off - orig_assignments_off} OFF_DAYs in assignments")
    else:
        print(f"  ✅ No discrepancy")
except Exception as e:
    print(f"  Error: {e}")

print()
print("FIXED OUTPUT (output/output_clean.json):")
print("─"*80)
try:
    with open('output/output_clean.json', 'r') as f:
        fixed = json.load(f)
    
    fixed_assignments_off = len([a for a in fixed['assignments'] if a.get('status') == 'OFF_DAY'])
    fixed_roster_off = sum(len([d for d in emp['dailyStatus'] if d.get('status') == 'OFF_DAY']) 
                           for emp in fixed['employeeRoster'])
    fixed_summary_off = fixed['rosterSummary']['byStatus']['OFF_DAY']
    
    print(f"  Assignments OFF_DAYs: {fixed_assignments_off}")
    print(f"  EmployeeRoster OFF_DAYs: {fixed_roster_off}")
    print(f"  RosterSummary OFF_DAYs: {fixed_summary_off}")
    print(f"  Discrepancy: {abs(fixed_assignments_off - fixed_roster_off)}")
    
    if fixed_assignments_off == fixed_roster_off:
        print(f"  ✅ FIXED: All OFF_DAYs are now consistent!")
    else:
        print(f"  ❌ Still has issues")
except Exception as e:
    print(f"  Error: {e}")

print()
print("="*80)
print("SUMMARY:")
print("="*80)
print(f"Original had {orig_assignments_off} OFF_DAYs in assignments")
print(f"Fixed now has {fixed_assignments_off} OFF_DAYs in assignments")
print(f"Improvement: +{fixed_assignments_off - orig_assignments_off} OFF_DAYs added")
print("="*80)
