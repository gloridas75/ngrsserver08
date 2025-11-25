# Input Files Index

## Overview
This document provides a complete index of all input scenario files available for NGRSSolver testing.

## Primary Test Scenarios

### ✅ RECOMMENDED FOR TESTING

#### 1. **input_1211_optimized.json** (15 KB) - SIMPLE BASELINE
- **Status**: ✅ OPTIMAL (110 assignments, 0 violations)
- **Employees**: 14 across 3 teams
- **Demands**: 3 (Frisking, Detention, XRay)
- **Slots**: ~150
- **Use**: Quick validation, baseline performance
- **Test Time**: <20ms

#### 2. **input_complex_scenario.json** (20 KB) - COMPLEX MULTI-TEAM ⭐
- **Status**: ✅ OPTIMAL (281 assignments, 66.9% coverage)
- **Employees**: 18 across 3 teams (ALPHA, BETA, GAMMA)
- **Demands**: 8 (Patrol Day/Night, Frisking, Detention Day/Night, XRay Day/Night, Community)
- **Slots**: ~420
- **Use**: Realistic operations, multi-team coordination
- **Test Time**: ~40ms
- **Features**: Mixed shifts, licenses, skills, gender balance

## Other Available Scenarios

### Historical/Test Files

| File | Size | Purpose | Status |
|------|------|---------|--------|
| input_1211_1400.json | 8.2K | Early version | Legacy |
| input_1211_1400_v2.json | 9.4K | Early version v2 | Legacy |
| input_enhanced.json | 11K | Enhanced features test | Legacy |
| input_realistic.json | 8.6K | Realistic scenario | Legacy |
| input_monthly_ot_test.json | 2.3K | OT validation | Minimal |
| input_violation_test.json | 2.3K | Violation testing | Minimal |
| input_complex_roster.json | 17K | Initial complex attempt | Legacy |
| wrapped.json | 16K | Wrapped format test | Format test |

## Recommended Usage Path

### Phase 1: Validation (10 min)
```bash
# Test simple scenario
python test_scripts/General/debug_solver.py input/input_1211_optimized.json

# Expected: OPTIMAL, 110 assignments, 0 violations
```

### Phase 2: Complex Testing (15 min)
```bash
# Test complex scenario
python test_scripts/General/debug_solver.py input/input_complex_scenario.json

# Expected: OPTIMAL, 281 assignments, 66.9% coverage
```

### Phase 3: API Testing (20 min)
```bash
# Start API server
python -m uvicorn src.api_server:app --host 127.0.0.1 --port 8080

# In another terminal, test with API
curl -X POST http://localhost:8080/solve \
  -H 'Content-Type: application/json' \
  -d @input/input_complex_scenario.json

# Response saved to: output/output_complex_DDMM_HHMM.json
```

## File Structure Comparison

### input_1211_optimized.json Structure
```
{
  "schemaVersion": "0.43",
  "planningReference": "NGRS_OPTIMAL_MINIMAL_VIOLATIONS",
  "timezone": "Asia/Singapore",
  "planningHorizon": {"startDate": "2025-11-01", "endDate": "2025-11-30"},
  "publicHolidays": [],
  "solverRunTime": {"maxSeconds": 600},
  "schemeMap": {"A": "SchemeA", "B": "SchemeB", "P": "SchemeP"},
  "constraintList": [...],
  "solverScoreConfig": {...},
  "demandItems": [...],
  "employees": [...]
}
```

### input_complex_scenario.json Structure
Same structure as above with:
- More employees (18 vs 14)
- More demands (8 vs 3)
- More constraints configured
- Enhanced team structure
- Multiple license types
- Cross-team skill distribution

## Testing Commands Quick Reference

### CLI Tests
```bash
cd /Users/glori/1\ Anthony_Workspace/My\ Developments/NGRS/ngrs-solver-v0.5/ngrssolver

# Simple scenario
python test_scripts/General/debug_solver.py input/input_1211_optimized.json

# Complex scenario
python test_scripts/General/debug_solver.py input/input_complex_scenario.json

# With output file
python test_scripts/General/debug_solver.py input/input_complex_scenario.json > /tmp/results.txt
```

### API Tests
```bash
# Start server (if not running)
python -m uvicorn src.api_server:app --host 127.0.0.1 --port 8080

# Test simple
curl -X POST http://localhost:8080/solve \
  -H 'Content-Type: application/json' \
  -d @input/input_1211_optimized.json

# Test complex
curl -X POST http://localhost:8080/solve \
  -H 'Content-Type: application/json' \
  -d @input/input_complex_scenario.json

# With timeout
curl -X POST http://localhost:8080/solve \
  -H 'Content-Type: application/json' \
  -d @input/input_complex_scenario.json?time_limit=30
```

### Python Direct
```bash
cd /Users/glori/1\ Anthony_Workspace/My\ Developments/NGRS/ngrs-solver-v0.5/ngrssolver

python << 'EOF'
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from context.engine.data_loader import load_input
from context.engine.solver_engine import solve
from src.output_builder import build_output

# Load
with open('input/input_complex_scenario.json') as f:
    data = json.load(f)

# Solve
ctx = load_input(data)
status, result, assignments, violations = solve(ctx)

# Output
output = build_output(data, ctx, status, result, assignments, violations)
print(f"Status: {output['solverRun']['status']}")
print(f"Assignments: {len(assignments)}")
print(f"Duration: {output['solverRun']['durationSeconds']}s")
EOF
```

## Expected Output

### For input_1211_optimized.json
```
Status: OPTIMAL
Assignments: 110
Hard violations: 0
Soft violations: 0
Duration: 0.017s
Output file: output/output_1211_HHMM.json (65 KB)
```

### For input_complex_scenario.json
```
Status: OPTIMAL
Assignments: 281
Coverage: 66.9% (281/420 slots)
Hard violations: 0
Soft violations: 0
Duration: 0.037s
Output file: output/output_complex_HHMM.json (180 KB)
```

## Documentation Reference

| Document | Purpose | Location |
|----------|---------|----------|
| COMPLEX_SCENARIO_README.md | Detailed complex scenario breakdown | implementation_docs/ |
| INPUT_SCENARIOS_COMPARISON.md | Side-by-side comparison | implementation_docs/ |
| OUTPUT_FILE_GENERATION.md | Output file features | implementation_docs/ |
| API_QUICK_REFERENCE.md | API endpoint reference | implementation_docs/ |

## Modifying Input Scenarios

To create variations:

1. **Copy existing file**:
   ```bash
   cp input/input_complex_scenario.json input/input_custom.json
   ```

2. **Edit JSON**:
   - Increase `headcount` in demands
   - Add new employee entries
   - Modify rotation patterns
   - Adjust constraint weights

3. **Test**:
   ```bash
   python test_scripts/General/debug_solver.py input/input_custom.json
   ```

## Performance Benchmarks

| Scenario | Solver Time | Assignments | Complexity |
|----------|------------|-------------|-----------|
| input_1211_optimized.json | 17ms | 110 | ⭐ |
| input_complex_scenario.json | 37ms | 281 | ⭐⭐⭐ |
| input_realistic.json | 22ms | ~90 | ⭐⭐ |

## Troubleshooting

### File Not Found
```bash
ls -la input/input_complex_scenario.json
```

### Schema Validation Error
Check that planningHorizon has `startDate` and `endDate` (not `start`/`end`)

### Solver Timeout
Increase `solverRunTime.maxSeconds` or reduce headcount

### No Assignments
Check licenses aren't expired, skills match demands

## Next Steps

1. ✅ Test simple scenario → `input_1211_optimized.json`
2. ✅ Test complex scenario → `input_complex_scenario.json`
3. Create variations for specific use cases
4. Add public holidays to planningHorizon
5. Include employee unavailability data

---

**Last Updated**: Nov 13, 2025
**Total Input Files**: 10
**Recommended Files**: 2 (simple + complex)
