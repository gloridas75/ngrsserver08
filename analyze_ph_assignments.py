#!/usr/bin/env python3
"""Analyze why OFF_DAY assignments are created on public holidays."""

import json

# Check the input settings
with open('input/RST-20260130-DC8336C7_Solver_Input.json', 'r') as f:
    input_data = json.load(f)

print("=== INPUT SETTINGS ===")
print(f"Public Holidays: {input_data.get('publicHolidays', [])}")

shifts = input_data.get('demandItems', [{}])[0].get('shifts', [])
if shifts:
    print(f"includePublicHolidays: {shifts[0].get('includePublicHolidays')}")
    print(f"includeEveOfPublicHolidays: {shifts[0].get('includeEveOfPublicHolidays')}")

# Check the output
with open('output/output_3001_1411.json', 'r') as f:
    output = json.load(f)

print("\n=== ASSIGNMENTS ON 2026-03-21 (PH) ===")
ph_assignments = [a for a in output.get('assignments', []) if a.get('date') == '2026-03-21']
print(f"Total assignments: {len(ph_assignments)}")

# Count by shift code
shift_counts = {}
for a in ph_assignments:
    sc = a.get('shiftCode', 'NONE')
    shift_counts[sc] = shift_counts.get(sc, 0) + 1
print(f"By shift code: {shift_counts}")

# Check status
status_counts = {}
for a in ph_assignments:
    st = a.get('status', 'NONE')
    status_counts[st] = status_counts.get(st, 0) + 1
print(f"By status: {status_counts}")

# Sample
if ph_assignments:
    print(f"\nSample assignment on PH:")
    print(json.dumps(ph_assignments[0], indent=2))

# Check what the expected behavior should be
print("\n=== EXPECTED BEHAVIOR ===")
print("When includePublicHolidays=false:")
print("  - No WORK slots should be created on PH dates")
print("  - OFF_DAY assignments are generated for all employees")
print("  - This is CORRECT behavior - employees get day off on PH")
print("")
print("The question is: Should OFF_DAY records even appear in output?")
print("  - Current: YES, all days (work + off) are in assignments array")
print("  - Alternative: Only work days in assignments, OFF in employeeRoster only")
