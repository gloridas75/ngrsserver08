#!/usr/bin/env python3
"""Check slot rotation sequence vs employee workPattern."""
import json
from context.engine import data_loader, slot_builder
from datetime import date

# Load input
with open('input/RST-20260127-DBCCA45D_Solver_Input.json', 'r') as f:
    input_data = json.load(f)

# Build context and slots
ctx = data_loader.load_input(input_data)
slots = slot_builder.build_slots(ctx)

# Check first slot's rotationSequence
print(f"Number of slots: {len(slots)}")
if slots:
    slot = slots[0]
    print(f"\nFirst slot:")
    print(f"  slot_id: {slot.slot_id}")
    print(f"  rotationSequence: {slot.rotationSequence}")
    print(f"  rotationSequence type: {type(slot.rotationSequence)}")
    
    # Compare with employee workPattern
    emp_pattern = ctx['employees'][0].get('workPattern')
    print(f"\nEmployee[0] workPattern: {emp_pattern}")
    print(f"  workPattern type: {type(emp_pattern)}")
    
    # Check equality
    print(f"\nEquality checks:")
    print(f"  slot.rotationSequence == emp_pattern: {slot.rotationSequence == emp_pattern}")
    if slot.rotationSequence:
        print(f"  list(slot.rotationSequence) == emp_pattern: {list(slot.rotationSequence) == emp_pattern}")
