# Bug Analysis Summary - Scheme Normalization

## Issue
False "rank mismatch" and "exceeds scheme limits" errors appear in both outcomeBased and demandBased modes.

## Root Causes (2 Different Bugs!)

### Bug 1: DemandBased Mode - C1 Constraint Not Normalizing Scheme
**File**: `context/constraints/C1_mom_daily_hours.py`
**Line**: 62, 105

```python
# WRONG - reads raw scheme like "Scheme A"
scheme = emp.get('scheme', 'A')
employee_scheme[emp_id] = scheme
```

**Impact**: When checking if an employee can work a 12h shift:
- Employee has `scheme: "Scheme A"` in JSON
- Code reads `"Scheme A"` (string)
- Later tries to use it with constraint config expecting `'A'` (single letter)
- Logic fails, employee filtered out incorrectly

**Fix**: Import and use `normalize_scheme()`:
```python
from context.engine.time_utils import normalize_scheme

# CORRECT
scheme_raw = emp.get('scheme', 'A')
scheme = normalize_scheme(scheme_raw)
employee_scheme[emp_id] = scheme
```

---

### Bug 2: OutcomeBased Mode - ICPMP Filtering Out All Employees
**Observed in**: Test with RST-20260108-F6866C6B input

**Debug Log Evidence**:
```
[CLI] ✓ Filtered: 12 → 0 employees
[CLI] ⚠️  No employees selected! Automatic fallback disabled.
Problem size: 155 slots × 0 employees
```

**Root Cause**: ICPMP calculates:
- Need 16 employees (headcount=5, ratio=2.2, buffer=50%: 5×2.2×1.5=16.5)
- Only 12 employees available
- Raises ValueError
- Error handler sets employees list to EMPTY
- Template generator runs with 0 employees
- All slots become UNASSIGNED
- Post-solve explanation tries to explain with 0 employees → false "rank mismatch"

**Location**: Need to find where ICPMP ValueError is caught and employees list is cleared

---

## Fix Priority

1. **IMMEDIATE**: Fix C1 constraint (demandBased mode)
2. **NEXT**: Fix ICPMP graceful degradation (outcomeBased mode) 
3. **VERIFY**: Post-solve explanation logic (already fixed at line 1168)

---

## Files To Fix

1. `context/constraints/C1_mom_daily_hours.py` - Add normalize_scheme()
2. `src/unified_solver.py` or ICPMP caller - Handle ValueError gracefully
3. Verify: `context/engine/solver_engine.py` line 1168 (already fixed)

