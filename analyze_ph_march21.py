#!/usr/bin/env python3
"""Analyze PH application on March 21, 2026."""
import json
from collections import Counter

with open("input/RST-20260130-5B7971B2_Solver_Input.json") as f:
    input_data = json.load(f)

with open("input/RST-20260130-5B7971B2_Solver_Output.json") as f:
    output_data = json.load(f)

print("=== INPUT ANALYSIS ===")
print("Public Holidays:", input_data.get("publicHolidays"))
print("Work Pattern:", input_data["demandItems"][0]["requirements"][0]["workPattern"])
print("includePublicHolidays:", input_data["demandItems"][0]["shifts"][0].get("includePublicHolidays"))
print()

# Group employees by offset
offsets = {}
for emp in input_data["employees"]:
    offset = emp.get("rotationOffset", 0)
    if offset not in offsets:
        offsets[offset] = []
    offsets[offset].append(emp["employeeId"])

print("=== EMPLOYEES BY ROTATION OFFSET ===")
for offset in sorted(offsets.keys()):
    print(f"Offset {offset}: {offsets[offset]}")
print()

# Check March 21 assignments
ph_date = "2026-03-21"
march21_assignments = [a for a in output_data.get("assignments", []) if a.get("date") == ph_date]
statuses = Counter(a.get("status") for a in march21_assignments)
print("=== MARCH 21 (PH) ASSIGNMENTS ===")
print("Status counts:", dict(statuses))
print()

# Per-employee status
emp_offsets = {e["employeeId"]: e["rotationOffset"] for e in input_data["employees"]}
print("=== PER-EMPLOYEE STATUS ON MARCH 21 ===")
for a in sorted(march21_assignments, key=lambda x: x.get("employeeId", "")):
    emp_id = a.get("employeeId")
    status = a.get("status")
    shift = a.get("shiftCode")
    offset = emp_offsets.get(emp_id, "?")
    print(f"{emp_id}: offset={offset}, status={status}, shiftCode={shift}")

# Calculate expected pattern day for March 21
print("\n=== EXPECTED PATTERN DAY FOR MARCH 21 ===")
from datetime import date
pattern = input_data["demandItems"][0]["requirements"][0]["workPattern"]
start_date = date(2026, 3, 1)
ph_date_obj = date(2026, 3, 21)
days_from_start = (ph_date_obj - start_date).days  # 20 days

print(f"Pattern: {pattern} (length={len(pattern)})")
print(f"Days from March 1: {days_from_start}")
for offset in sorted(offsets.keys()):
    pattern_idx = (days_from_start + offset) % len(pattern)
    expected_shift = pattern[pattern_idx]
    print(f"Offset {offset}: pattern_idx={(days_from_start + offset)} % {len(pattern)} = {pattern_idx} → {expected_shift}")
