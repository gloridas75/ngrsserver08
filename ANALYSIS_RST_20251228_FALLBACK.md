# Analysis: RST-20251228-1A2210A7 Unexpected Output

**Date**: December 28, 2025  
**Input**: RST-20251228-1A2210A7_Solver_Input.json  
**Issue**: demandBased roster with headcount=2 produced unexpected results

---

## Summary

✅ **ROOT CAUSE IDENTIFIED**: The solver **fell back from demandBased to outcomeBased mode**, which explains why the output doesn't match expected demandBased behavior.

---

## Input Configuration

```json
{
  "rosteringBasis": "demandBased",
  "headcount": 2,
  "workPattern": ["D", "D", "D", "D", "D", "O", "O"],
  "employees": 5,
  "fallbackToOutcomeBased": true,  // ← KEY SETTING
  "enableOtAwareIcpmp": true
}
```

---

## Expected vs Actual Behavior

### Expected (demandBased with headcount=2):
- ✓ Only 2 employees used (matching headcount)
- ✓ Strict 5-days-on, 2-days-off rotation (D-D-D-D-D-O-O)
- ✓ Employees staggered by rotation offset
- ✓ Pattern repeats consistently across month

### Actual (Fell back to outcomeBased):
- ✗ All 5 employees used (headcount ignored)
- ✗ Pattern used as template, not rotation
- ✗ Each employee gets 23 assignments (distributed evenly)
- ✗ Gaps indicate template-based coverage, not rotation

---

## Evidence of Fallback

1. **Employee Count**:
   ```
   Expected: 2 employees (per headcount)
   Actual:   5 employees (all available)
   ```

2. **Assignment Distribution**:
   ```
   00032093: 23 assignments
   00033182: 23 assignments  
   00033261: 23 assignments
   00033642: 23 assignments
   00034833: 23 assignments
   ```
   → All employees equally distributed (outcomeBased behavior)

3. **Pattern Analysis**:
   ```
   Actual: D D D D D O O D D D D D O O D D D D D O O
   ```
   → Gaps of 2 days (O O) appear regularly, but this is per-employee template, not rotation

4. **Solve Time**: 0.000s
   → Instant completion suggests template validation rather than CP-SAT solve

5. **Solver Status**: FEASIBLE (not OPTIMAL)
   → Template validation produces "FEASIBLE", not "OPTIMAL"

---

## Why Fallback Occurred

### Possible Reasons:

1. **fallbackToOutcomeBased: true** (in input)
   - Solver configured to automatically fall back if ICPMP preprocessing fails
   
2. **ICPMP Preprocessing Failure**:
   - `enableOtAwareIcpmp: true` with `headcount: 2`
   - ICPMP might not have found a valid configuration for:
     - 2 employees
     - 5-days-on 2-days-off pattern
     - 31-day month with scheme/constraint requirements
   
3. **Constraint Conflicts**:
   - MOM constraints (44h weekly cap, daily caps, etc.)
   - Consecutive days limits (8 days for Scheme A + APO)
   - Rest day requirements
   - May have made demandBased infeasible with only 2 employees

---

## Solution Options

### Option 1: Disable Automatic Fallback
```json
{
  "fallbackToOutcomeBased": false
}
```
**Result**: Solver will fail if demandBased is infeasible, showing clear error

### Option 2: Increase Headcount
```json
{
  "headcount": 3
}
```
**Result**: More employees in rotation may satisfy constraints

### Option 3: Disable OT-Aware ICPMP
```json
{
  "enableOtAwareIcpmp": false
}
```
**Result**: Use simpler ICPMP that may find solution

### Option 4: Adjust Work Pattern
```json
{
  "workPattern": ["D", "D", "D", "D", "O", "O", "O"]  // 4 on, 3 off
}
```
**Result**: More rest days may satisfy constraints

---

## Testing Recommendations

### Test 1: Without Fallback
- Set `"fallbackToOutcomeBased": false`
- Check if demandBased fails or succeeds
- Review error message if it fails

### Test 2: With More Employees
- Change `"headcount": 3`
- See if demandBased succeeds with 3-employee rotation

### Test 3: Without OT-Aware ICPMP
- Set `"enableOtAwareIcpmp": false`
- Use standard ICPMP preprocessing

---

## Key Insights

1. **The solver is working correctly** - fallback is by design when `fallbackToOutcomeBased: true`

2. **outcomeBased mode ignores headcount** - uses all available employees for coverage

3. **To get true demandBased behavior**:
   - Either disable fallback and fix constraint conflicts
   - OR increase headcount to make rotation feasible
   - OR adjust pattern to be less demanding

4. **The solve() metadata should record**:
   - `rosteringBasis` actually used
   - `fallbackReason` if fallback occurred
   - Currently these are missing from output

---

## Recommendation

**Immediate**: Test with `"fallbackToOutcomeBased": false` to see the actual constraint conflict error, then address the root cause rather than relying on fallback.

**Long-term**: Enhance solver output to clearly indicate when fallback occurs and why, so users understand the difference between requested vs actual rostering mode.

---

## Files

- **Input**: `/Users/glori/Downloads/RST-20251228-1A2210A7_Solver_Input.json`
- **Output**: `output/rst_prod_132724.json`
- **Test Script**: Create test with fallback disabled

