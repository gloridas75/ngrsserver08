#!/usr/bin/env python
"""Test C2 constraint loading on production"""
import sys
sys.path.insert(0, "/opt/ngrs-solver")

from context.constraints import C2_mom_weekly_hours_pattern_aware
from ortools.sat.python import cp_model

print("Testing C2 pattern-aware constraint...")
print(f"Has add_constraints: {hasattr(C2_mom_weekly_hours_pattern_aware, 'add_constraints')}")

model = cp_model.CpModel()
ctx = {
    "employees": [],
    "slots": [],
    "x": {},
    "demandItems": []
}

try:
    C2_mom_weekly_hours_pattern_aware.add_constraints(model, ctx)
    print("✓ SUCCESS: C2 constraint loaded and applied")
except Exception as e:
    print(f"✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
