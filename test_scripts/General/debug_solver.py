"""Debug script to identify model issues."""
import sys
sys.path.insert(0, '.')

from context.engine.data_loader import load_input
from context.engine.solver_engine import build_model, apply_constraints
from ortools.sat.python import cp_model

# Load input from command line argument or default
input_file = sys.argv[1] if len(sys.argv) > 1 else "input.json"
print(f"Loading input from: {input_file}")
ctx = load_input(input_file)

# Build model
print("Building model...")
model = build_model(ctx)

print("\nApplying constraints...")
apply_constraints(model, ctx)

print("\nModel Statistics:")
print(f"  Variables: {model.Proto().variables.__len__()}")
print(f"  Constraints: {len(model.Proto().constraints)}")
print(f"  Objectives: {len(model.Proto().objective.vars)}")

print("\nValidating model...")
solver = cp_model.CpSolver()

# Try to solve with debug output
solver.parameters.log_search_progress = True
solver.parameters.max_time_in_seconds = 5

print("\nSolving...")
status = solver.Solve(model)

# Map status (correct OR-Tools constants)
status_map = {
    0: "UNKNOWN",
    1: "MODEL_INVALID",
    2: "FEASIBLE",
    3: "INFEASIBLE",
    4: "OPTIMAL"
}

print(f"\nSolver Status: {status_map.get(status, 'UNKNOWN')} (code {status})")

# Print solution statistics
if status in [1, 2]:  # OPTIMAL or FEASIBLE
    print(f"Objective value: {solver.ObjectiveValue()}")
    print(f"Solution found!")

# Check if there's a proto error
try:
    model.Proto()
    print("\n✓ Model proto is valid")
except Exception as e:
    print(f"\n✗ Model proto error: {e}")
