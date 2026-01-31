#!/usr/bin/env python3
"""Debug outcomeBased slot generation."""
import json
import math

with open('output/RST-20260127-838E64D9_Solver_Input.json', 'r') as f:
    input_data = json.load(f)

# Get key parameters
employees = input_data.get('employees', [])
demand = input_data.get('demandItems', [{}])[0]
req = demand.get('requirements', [{}])[0]

print("=== INPUT PARAMETERS ===")
print(f"Rostering basis: {demand.get('rosteringBasis')}")
print(f"Headcount in requirement: {req.get('headcount')}")
print(f"Total employees: {len(employees)}")
print(f"minStaffThresholdPercentage: {demand.get('minStaffThresholdPercentage', 100)}%")

work_pattern = req.get('workPattern', [])
print(f"Work pattern: {work_pattern}")
print(f"Pattern length: {len(work_pattern)}")

work_days = sum(1 for d in work_pattern if d != 'O')
print(f"Work days in pattern: {work_days}")
workable_ratio = work_days / len(work_pattern) if work_pattern else 1.0
print(f"Workable ratio: {workable_ratio:.2%}")

# Calculate what slot_builder should create
min_threshold = demand.get('minStaffThresholdPercentage', 100)
positions_per_day = len(employees) * (min_threshold / 100) * workable_ratio
print(f"\nPositions per day calculation:")
print(f"  {len(employees)} employees × {min_threshold}% × {workable_ratio:.2%} = {positions_per_day:.2f}")
print(f"  Rounded: {int(math.floor(positions_per_day))}")

# Expected total slots
days_in_month = 28
total_d_slots = int(math.floor(positions_per_day)) * days_in_month
total_o_slots = (21 - int(math.floor(positions_per_day))) * days_in_month  # Approx
print(f"\nExpected D slots over 28 days: {int(math.floor(positions_per_day))} × 28 = {total_d_slots}")

# The PROBLEM: outcomeBased should be employee-centric, NOT position-centric
# Each employee follows THEIR pattern - we shouldn't create position slots at all
print("\n=== THE ISSUE ===")
print("outcomeBased mode is creating position-based slots (P0, P1, P2...)")
print("But it should be creating EMPLOYEE-based slots where each employee")
print("follows their own rotated work pattern.")
print(f"\nWith 21 employees × 28 days = 588 total slots")
print(f"  - 21 employees × 8/11 work ratio ≈ 428 D-slots")
print(f"  - 21 employees × 3/11 off ratio ≈ 160 O-slots")
print(f"  - Total: 588 slots")
print(f"\nActual output: 425 ASSIGNED + 163 UNASSIGNED + 160 OFF_DAY = 748")
print("The extra 163 UNASSIGNED are position-based slots that shouldn't exist!")
