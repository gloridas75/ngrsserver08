# Regression Testing Guide

## Quick Start

### 1. Establish Baselines (First Time Setup)
```bash
# Run all tests and save their outputs as baselines
python test_regression.py --update-baselines
```

This creates `test_baselines/` folder with expected results for each test input.

### 2. Run Tests Before Committing
```bash
# Run all regression tests
python test_regression.py
```

**Expected Output:**
```
================================================================================
NGRS SOLVER - REGRESSION TEST SUITE
================================================================================
Timestamp: 2026-01-12T10:30:00

Found 5 test input(s)

✓ RST-20260110-64276C3D_Solver_Input: PASS (0.68s)
✓ RST-20260111-52038D2B_Solver_Input: PASS (0.71s)
✓ RST-20260112-9654BC37_Solver_Input: PASS (0.72s)
...

================================================================================
SUMMARY
================================================================================
Total tests: 5
Passed: 5
Total time: 3.50s

ALL TESTS PASSED - SAFE TO COMMIT
```

### 3. If Tests Fail
```
✗ RST-20260112-9654BC37_Solver_Input: FAIL (0.72s)
    Status changed: OPTIMAL → INFEASIBLE
    Hard violations changed: 0 → 8

================================================================================
SUMMARY
================================================================================
Total tests: 5
Passed: 4
Failed: 1

REGRESSION DETECTED - DO NOT COMMIT
Review failures above and fix issues before pushing.
```

**Action:** Fix the code issue before committing!

## Advanced Usage

### Filter Tests
```bash
# Run only tests matching pattern
python test_regression.py --filter "RST-2026"
python test_regression.py --filter "APGD"
```

### Update Specific Baselines
```bash
# Update only filtered tests
python test_regression.py --filter "RST-20260112" --update-baselines
```

### Increase Timeout
```bash
# For slower tests (default: 120s)
python test_regression.py --timeout 300
```

### Verbose Mode
```bash
# Show detailed solver output
python test_regression.py --verbose
```

## What Gets Checked

### Critical (Test Fails If Different):
- ✅ **Solver Status**: OPTIMAL/FEASIBLE/INFEASIBLE
- ✅ **Hard Violations**: Count of hard constraint violations

### Warning (Logged But Test Passes):
- ⚠️  **Assignment Count**: Number of assigned slots
- ⚠️  **Employees Used**: Number of employees rostered

## Workflow

### Before Making Code Changes
```bash
# Ensure all baselines exist
python test_regression.py --update-baselines
```

### During Development
```bash
# Run tests frequently
python test_regression.py

# Or run specific tests you're working on
python test_regression.py --filter "your-test-name"
```

### Before Committing
```bash
# Final check - ALL tests must pass
python test_regression.py

# If all pass:
git add -A
git commit -m "Your changes"
git push origin main
```

### After Intentional Behavior Changes
If you intentionally changed solver behavior (e.g., fixed a bug that changes results):

```bash
# Review changes carefully
python test_regression.py

# If changes are expected and correct, update baselines
python test_regression.py --update-baselines

# Commit both code AND updated baselines
git add -A
git commit -m "Fix XYZ - updated test baselines"
git push origin main
```

## Directory Structure

```
ngrssolver/
├── input/                              # Test input JSONs
│   ├── RST-20260110-64276C3D_Solver_Input.json
│   ├── RST-20260111-52038D2B_Solver_Input.json
│   └── RST-20260112-9654BC37_Solver_Input.json
│
├── test_baselines/                     # Expected results (auto-created)
│   ├── RST-20260110-64276C3D_Solver_Input.json
│   ├── RST-20260111-52038D2B_Solver_Input.json
│   └── RST-20260112-9654BC37_Solver_Input.json
│
├── output/                             # Test outputs (temporary)
│   └── test_regression_*.json
│
└── test_regression.py                  # Test runner script
```

## Adding New Test Cases

1. **Add input JSON to `input/` folder**
   ```bash
   cp my_new_test.json input/
   ```

2. **Run once to create baseline**
   ```bash
   python test_regression.py --filter "my_new_test" --update-baselines
   ```

3. **Future runs will validate against this baseline**
   ```bash
   python test_regression.py
   ```

## CI/CD Integration (Optional)

### Pre-Commit Hook
Create `.git/hooks/pre-commit`:
```bash
#!/bin/bash
echo "Running regression tests..."
python test_regression.py

if [ $? -ne 0 ]; then
    echo "Tests failed! Commit blocked."
    exit 1
fi

echo "All tests passed!"
```

Make it executable:
```bash
chmod +x .git/hooks/pre-commit
```

Now tests run automatically before every commit!

### Makefile Target
Add to `Makefile`:
```makefile
.PHONY: test
test:
	python test_regression.py

.PHONY: test-update
test-update:
	python test_regression.py --update-baselines
```

Usage:
```bash
make test              # Run tests
make test-update       # Update baselines
```

## Troubleshooting

### "No test inputs found"
- Ensure you have JSON files in `input/` folder
- Check filter pattern if using `--filter`

### "No baseline" warning
- Run with `--update-baselines` to create baselines
- This happens for new test cases

### Tests timeout
- Increase timeout: `--timeout 300`
- Or check if solver is hanging on that input

### All tests show as "new"
- You need to run with `--update-baselines` first
- This establishes what "correct" looks like

## Best Practices

1. **Always run tests before committing**
   ```bash
   python test_regression.py && git push origin main
   ```

2. **Keep test inputs diverse**
   - Different schemes (A, B, P)
   - Different modes (demandBased, outcomeBased)
   - Different patterns (5-day, 6-day, APGD-D10)
   - Edge cases (small/large, simple/complex)

3. **Update baselines intentionally**
   - Only use `--update-baselines` when you KNOW the new behavior is correct
   - Review the diff first
   - Document why baselines changed in commit message

4. **Add test for every bug fix**
   - When you fix a bug, add the failing case as a test input
   - This prevents regression of that specific bug

## Example: Complete Workflow

```bash
# 1. Make code changes
vim context/constraints/C2_mom_weekly_hours_pattern_aware.py

# 2. Run regression tests
python test_regression.py

# Output shows 1 failure - investigate
✗ RST-20260112-9654BC37_Solver_Input: FAIL (0.72s)
    Hard violations changed: 0 → 8

# 3. Fix the bug
vim context/constraints/C2_mom_weekly_hours_pattern_aware.py

# 4. Re-run tests
python test_regression.py

# Output: All pass!
✓ RST-20260112-9654BC37_Solver_Input: PASS (0.72s)
ALL TESTS PASSED - SAFE TO COMMIT

# 5. Commit and push
git add -A
git commit -m "Fix C2 constraint issue"
git push origin main
```

Success! No regressions introduced.
