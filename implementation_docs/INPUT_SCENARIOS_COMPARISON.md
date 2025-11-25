# Input Files Summary

## Available Test Scenarios

### 1. **input_1211_optimized.json** (ORIGINAL - SIMPLE)
- **Employees**: 14 (6 Frisking + 5 Detention + 3 XRay)
- **Teams**: 3 (TEAM-1, TEAM-2, TEAM-3)
- **Demands**: 3 (Frisking, Detention, XRay - Day only)
- **Headcount**: 5 total (2+2+1)
- **Planning**: Nov 1-30, 2025
- **Complexity**: Low - single shift types per demand
- **Test Result**: OPTIMAL - 110 assignments, 0 violations
- **Output Size**: ~65 KB
- **Use Case**: Simple validation, quick testing

### 2. **input_complex_scenario.json** (NEW - COMPLEX)
- **Employees**: 18 (6 per team with cross-skills)
- **Teams**: 3 (TEAM-ALPHA, TEAM-BETA, TEAM-GAMMA)
- **Demands**: 8 (Patrol Day, Patrol Night, Frisking, Detention, XRay, Community)
- **Headcount**: 14 total (3+2+2+2+2+1+1+1)
- **Planning**: Nov 1-30, 2025
- **Complexity**: High - multi-team, multi-shift, mixed licenses
- **Test Result**: OPTIMAL - 281 assignments, 66.9% coverage
- **Output Size**: ~180 KB
- **Skills**: 5 (patrol, frisking, detention, xray, community)
- **Licenses**: 3 (Frisking, XRay, Detention)
- **Use Case**: Realistic operations, performance testing, advanced scenarios

## Quick Comparison

| Aspect | Simple | Complex |
|--------|--------|---------|
| Employees | 14 | 18 |
| Teams | 3 | 3 |
| Demands | 3 | 8 |
| Total Shifts | 3 | 8 |
| Total Slots | ~150 | ~420 |
| Skills Required | 3 | 5 |
| Licenses | 2 | 3 |
| Ranks | APO, AVSO | APO, AVSO |
| Schemes | A | A, B |
| Gender Balance | Yes | Yes |
| Solver Time | <20ms | ~40ms |
| Assignments | 110 | 281 |
| Coverage | 73% | 67% |
| Complexity | ⭐ | ⭐⭐⭐ |

## Running Tests

### Option 1: CLI
```bash
# Simple scenario
python test_scripts/General/debug_solver.py input/input_1211_optimized.json

# Complex scenario
python test_scripts/General/debug_solver.py input/input_complex_scenario.json
```

### Option 2: API (when running)
```bash
# Make sure API is running on port 8080
python -m uvicorn src.api_server:app --host 127.0.0.1 --port 8080

# Then POST input
curl -X POST http://localhost:8080/solve \
  -H 'Content-Type: application/json' \
  -d @input/input_complex_scenario.json
```

### Option 3: Python Direct
```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from context.engine.data_loader import load_input
from context.engine.solver_engine import solve
from src.output_builder import build_output

# Load scenario
with open('input/input_complex_scenario.json') as f:
    input_data = json.load(f)

# Solve
ctx = load_input(input_data)
status, result, assignments, violations = solve(ctx)

# Build output
output = build_output(input_data, ctx, status, result, assignments, violations)
print(f"Status: {output['solverRun']['status']}")
print(f"Assignments: {len(assignments)}")
```

## Output Files Generated

Both scenarios create timestamped output files:
- `output/output_1211_HHMM.json` (simple)
- `output/output_complex_HHMM.json` (complex)

Each contains:
- Complete solution with all assignments
- Constraint violation analysis
- Solver performance metrics
- Request metadata and timing

## Recommendations

**Use Simple Scenario When:**
- Quick validation needed
- Testing basic functionality
- Learning the format
- Performance benchmarking baseline

**Use Complex Scenario When:**
- Testing realistic operations
- Multi-team coordination needed
- Advanced constraint handling required
- Production readiness validation
- Performance testing under load
- Cross-skill team dynamics

## Next Steps

1. **Modify Complex Scenario**:
   - Add more employees (increase per-team from 6 to 10)
   - Add more demands (add cleaning, admin roles)
   - Add public holidays
   - Add unavailability constraints

2. **Extend Simple Scenario**:
   - Convert to complex format
   - Add night shifts
   - Add more teams
   - Include community engagement

3. **Create New Scenarios**:
   - Monthly rotating crews
   - Seasonal variations
   - Emergency coverage
   - Training rotations

## File Locations

- Simple: `input/input_1211_optimized.json` (23 KB)
- Complex: `input/input_complex_scenario.json` (20 KB)
- Documentation: `implementation_docs/COMPLEX_SCENARIO_README.md`
