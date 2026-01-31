#!/usr/bin/env python3
"""Debug why Mar 1-2 slots are UNASSIGNED."""
import json
import sys
sys.path.insert(0, '/Users/glori/1 Anthony_Workspace/My Developments/NGRS/ngrs-solver-v0.7/ngrssolver')

from context.engine.data_loader import load_input
from context.engine.slot_builder import build_slots, Slot
from datetime import date

# Load input
with open('/Users/glori/Downloads/RST-20260128-69B55E12_Solver_Input.json') as f:
    input_data = json.load(f)

ctx = load_input(input_data)

# Get employees
employees = ctx.get('employees', [])
print(f"Employees: {len(employees)}")
for emp in employees:
    print(f"  {emp['employeeId']}: offset={emp.get('rotationOffset', 0)}")

# Build employee-based slots - need to add employees to input
input_data['_eligible_employees'] = employees
slots = build_slots(input_data)
ctx['slots'] = slots

print(f"\nTotal slots: {len(slots)}")

# Filter to Mar 1 and Mar 2
mar1_slots = [s for s in slots if s.date == date(2026, 3, 1)]
mar2_slots = [s for s in slots if s.date == date(2026, 3, 2)]

print(f"\nMar 1 slots: {len(mar1_slots)}")
for s in mar1_slots:
    target = getattr(s, 'targetEmployeeId', None)
    print(f"  {s.slot_id}: targetEmployeeId={target}")

print(f"\nMar 2 slots: {len(mar2_slots)}")
for s in mar2_slots:
    target = getattr(s, 'targetEmployeeId', None)
    print(f"  {s.slot_id}: targetEmployeeId={target}")

# Now simulate decision variable creation
print("\n=== DECISION VARIABLE CHECK ===")
from ortools.sat.python import cp_model
model = cp_model.CpModel()
x = {}

for slot in mar1_slots + mar2_slots:
    for emp in employees:
        emp_id = emp.get('employeeId')
        
        # Check targetEmployeeId filter
        if hasattr(slot, 'targetEmployeeId') and slot.targetEmployeeId is not None:
            if emp_id != slot.targetEmployeeId:
                continue  # Skip
        
        # Create variable
        var_key = (slot.slot_id, emp_id)
        x[var_key] = model.NewBoolVar(f"x_{slot.slot_id}_{emp_id}")
        print(f"  Created var: {slot.date} - slot={slot.slot_id[:40]}... - emp={emp_id}")

print(f"\nTotal vars created for Mar 1-2: {len(x)}")
