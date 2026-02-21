#!/usr/bin/env python3
"""Test v2 slot builder features."""
import json
from context.engine.slot_builder_v2 import build_slots_v2

with open('input/RST-20260210-008E178F_Solver_Input.json') as f:
    data = json.load(f)

# Mark as v2
data['_apiVersion'] = 'v2'
data['_hasDailyHeadcount'] = True

slots = build_slots_v2(data)

# Check first slot attributes
if slots:
    s = slots[0]
    print(f'Total slots: {len(slots)}')
    print(f'First slot:')
    print(f'  productTypeId: {s.productTypeId}')
    print(f'  _productTypeIds: {getattr(s, "_productTypeIds", "NOT SET")}')
    print(f'  _dayType: {getattr(s, "_dayType", "NOT SET")}')
    print(f'  _hasTimeOverride: {getattr(s, "_hasTimeOverride", "NOT SET")}')
    print(f'  start: {s.start}')
    print(f'  end: {s.end}')
    
    # Find slot for Feb 15 (has time override)
    feb15_slots = [slot for slot in slots if slot.date.day == 15 and slot.date.month == 2]
    if feb15_slots:
        s15 = feb15_slots[0]
        print(f'\nFeb 15 slot (time override):')
        print(f'  start: {s15.start}')
        print(f'  end: {s15.end}')
        print(f'  _hasTimeOverride: {getattr(s15, "_hasTimeOverride", "NOT SET")}')
        
    # Find normal slot
    feb10_slots = [slot for slot in slots if slot.date.day == 10 and slot.date.month == 2]
    if feb10_slots:
        s10 = feb10_slots[0]
        print(f'\nFeb 10 slot (no override):')
        print(f'  start: {s10.start}')
        print(f'  end: {s10.end}')
        print(f'  _hasTimeOverride: {getattr(s10, "_hasTimeOverride", "NOT SET")}')
