#!/usr/bin/env python3
"""Debug simulation for pattern offset logic."""
import json
from context.engine import data_loader, slot_builder
from datetime import date

# Load input
with open('input/RST-20260127-DBCCA45D_Solver_Input.json', 'r') as f:
    input_data = json.load(f)

# Build context and slots
ctx = data_loader.load_input(input_data)
slots = slot_builder.build_slots(ctx)

employees = ctx['employees']
slot = slots[0]
slot_base_pattern = slot.rotationSequence

print(f"slot_base_pattern: {slot_base_pattern}")
print(f"slot coverageAnchor: {slot.coverageAnchor}")
print()

# Check first 5 employees
for emp in employees[:5]:
    emp_id = emp['employeeId']
    emp_offset = emp.get('rotationOffset', 0)
    emp_wp = emp.get('workPattern')
    
    # Simulate the comparison logic
    emp_has_custom_rotated_pattern = (
        emp_wp is not None and 
        emp_wp != slot_base_pattern
    )
    effective_offset = 0 if emp_has_custom_rotated_pattern else emp_offset
    
    print(f"{emp_id}:")
    print(f"  rotationOffset: {emp_offset}")
    print(f"  workPattern: {emp_wp}")
    print(f"  workPattern == slot_base_pattern: {emp_wp == slot_base_pattern}")
    print(f"  emp_has_custom_rotated_pattern: {emp_has_custom_rotated_pattern}")
    print(f"  effective_offset: {effective_offset}")
    print()
