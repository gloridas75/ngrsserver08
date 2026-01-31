#!/usr/bin/env python3
"""Debug CP-SAT model for Mar 1-2 unassigned slots.

This script creates a minimal model to test if the constraints allow
all 205 slots to be assigned.
"""
import json
from datetime import datetime, timedelta
from collections import defaultdict
from ortools.sat.python import cp_model

with open('/Users/glori/Downloads/RST-20260128-69B55E12_Solver_Input.json') as f:
    data = json.load(f)

pattern = ['D','D','D','D','O','D','D','D','D','D','O']  # 11-day cycle
start_date = datetime.fromisoformat(data['planningHorizon']['startDate'].replace('Z','')).date()
end_date = datetime.fromisoformat(data['planningHorizon']['endDate'].replace('Z','')).date()

# Build slots
slots = []
emp_slots = defaultdict(list)  # emp_id -> list of (date, slot_idx)
employees = data['employees']

for emp in employees:
    emp_id = emp['employeeId']
    offset = emp.get('rotationOffset', 0)
    
    for i in range(31):  # March has 31 days
        day = start_date + timedelta(days=i)
        pattern_idx = (i + offset) % 11
        if pattern[pattern_idx] == 'D':
            slot_idx = len(slots)
            slots.append({'emp_id': emp_id, 'date': day, 'idx': slot_idx})
            emp_slots[emp_id].append((day, slot_idx))

print(f"Total slots: {len(slots)}")
print(f"Employees: {len(employees)}")

# Create minimal CP-SAT model
model = cp_model.CpModel()

# Decision variables: x[slot_idx] = 1 if slot is assigned (to its target employee)
x = {}
for slot in slots:
    x[slot['idx']] = model.NewBoolVar(f"x_{slot['idx']}")

# Unassigned variables
unassigned = {}
for slot in slots:
    unassigned[slot['idx']] = model.NewBoolVar(f"unassigned_{slot['idx']}")

# Constraint 1: Each slot is either assigned or unassigned
for slot in slots:
    model.Add(x[slot['idx']] + unassigned[slot['idx']] == 1)

# Constraint 2: C5 - At most 6 work days per 7-day window per employee
print("\nAdding C5 constraints...")
c5_count = 0
for emp_id, emp_slot_list in emp_slots.items():
    # Group by date
    emp_dates = [d for d, _ in emp_slot_list]
    emp_slot_by_date = {d: idx for d, idx in emp_slot_list}
    
    # For each 7-day window
    for window_start_offset in range(25):  # 31 - 6 = 25 possible windows
        window_start = start_date + timedelta(days=window_start_offset)
        window_end = window_start + timedelta(days=6)
        
        # Get slots in this window
        slots_in_window = []
        for day, slot_idx in emp_slot_list:
            if window_start <= day <= window_end:
                slots_in_window.append(x[slot_idx])
        
        if slots_in_window:
            model.Add(sum(slots_in_window) <= 6)
            c5_count += 1

print(f"Added {c5_count} C5 constraints")

# Constraint 3: C2 - Weekly normal hours <= 44h
# For simplicity, assume 12h shift → 12h × 10 = 120 (scaled integer)
# Weekly cap = 44h × 10 = 440 (scaled integer)
print("\nAdding C2 weekly hours constraints...")
c2_count = 0

# Group slots by employee and ISO week
emp_week_slots = defaultdict(lambda: defaultdict(list))
for slot in slots:
    emp_id = slot['emp_id']
    day = slot['date']
    iso_year, iso_week, _ = day.isocalendar()
    week_key = f"{iso_year}-W{iso_week:02d}"
    emp_week_slots[emp_id][week_key].append(slot['idx'])

for emp_id, weeks in emp_week_slots.items():
    for week_key, slot_indices in weeks.items():
        # Week-specific normal hours calculation
        work_days_this_week = len(slot_indices)
        # Normal hours per shift = 44 / work_days (MOM compliant)
        normal_per_shift = 44.0 / work_days_this_week
        # For 12h shift, normal = min(normal_per_shift, 12)
        actual_normal = min(normal_per_shift, 12.0)
        
        # Sum of normal hours for this week
        # Each slot contributes actual_normal if assigned
        scaled_normal = int(round(actual_normal * 10))  # Scale by 10 for integer
        weekly_cap_scaled = 440  # 44h × 10
        
        slot_vars = [x[idx] for idx in slot_indices]
        # sum(slot_vars) * scaled_normal <= weekly_cap_scaled
        model.Add(sum(slot_vars) * scaled_normal <= weekly_cap_scaled)
        c2_count += 1

print(f"Added {c2_count} C2 weekly constraints")

# Constraint 4: C17 - Monthly OT cap <= 72h
# OT = max(0, gross - 9h) per shift
# For 12h shift: OT = 12 - 9 = 3h
print("\nAdding C17 monthly OT constraints...")
c17_count = 0

# Group slots by employee (all slots are in March 2026)
for emp_id, emp_slot_list in emp_slots.items():
    # All slots have 3h OT (12h - 9h)
    ot_per_slot = 3.0
    scaled_ot = int(round(ot_per_slot * 10))  # 30
    monthly_cap_scaled = 720  # 72h × 10
    
    slot_vars = [x[slot_idx] for _, slot_idx in emp_slot_list]
    if slot_vars:
        # sum(slot_vars) * scaled_ot <= monthly_cap_scaled
        model.Add(sum(slot_vars) * scaled_ot <= monthly_cap_scaled)
        c17_count += 1

print(f"Added {c17_count} C17 monthly OT constraints")
print(f"  Each employee: max {monthly_cap_scaled // scaled_ot} work days to stay under 72h OT")

# Objective: Minimize unassigned
total_unassigned = sum(unassigned.values())
model.Minimize(total_unassigned)

# Solve
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 30
status = solver.Solve(model)

print(f"\nSolver status: {solver.StatusName(status)}")
print(f"Unassigned count: {solver.Value(total_unassigned)}")

# Show which slots are unassigned
if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
    unassigned_slots = []
    for slot in slots:
        if solver.Value(unassigned[slot['idx']]) == 1:
            unassigned_slots.append(slot)
    
    print(f"\nUnassigned slots ({len(unassigned_slots)}):")
    for slot in unassigned_slots:
        print(f"  {slot['date']} - {slot['emp_id']}")
