# CRITICAL ISSUE: Rotation Offsets Not Applied to CP-SAT

## Problem Summary

ICPMP v3.0 preprocessing correctly calculates and assigns rotation offsets to employees, BUT the CP-SAT solver is NOT using them because **`fixedRotationOffset` flag is missing or false** in the input.

---

## Root Cause

### How Rotation Offsets Work in the System

The solver has TWO modes for handling rotation offsets:

#### Mode 1: **Dynamic Offsets** (`fixedRotationOffset=false` or missing)
- CP-SAT solver **optimizes** rotation offsets itself
- Employee `rotationOffset` values in input are **IGNORED**
- Solver decides best offset for each employee
- Used when no preprocessing is done

#### Mode 2: **Fixed Offsets** (`fixedRotationOffset=true`)
- CP-SAT solver **MUST USE** the `rotationOffset` from employee objects
- Offsets are pre-calculated (by ICPMP or manually set)
- Solver builds constraints based on these fixed offsets
- Used when preprocessing provides optimal offsets

### The Bug

**ICPMP v3.0 preprocessing:**
1. ✅ Calculates optimal offsets (0-11 for 12-day pattern)
2. ✅ Assigns `employee['rotationOffset'] = offset`
3. ✅ Returns filtered employees with offsets set
4. ❌ **BUT does NOT set `input_data['fixedRotationOffset'] = True`**

**Result:**
- CP-SAT solver receives 15 employees with rotation offsets 0-11
- But sees `fixedRotationOffset=false` (or missing)
- **Ignores all the ICPMP-calculated offsets**
- Tries to optimize offsets itself
- Fails because:
  * Only 15 employees available (normally needs 26)
  * Constraints designed for preprocessed offsets
  * Optimization space too constrained
  * Times out after 600 seconds

---

## Evidence

### Code Analysis

**File: `src/offset_manager.py` (Line 65-68)**
```python
def should_stagger_offsets(input_data: Dict[str, Any]) -> bool:
    # Check fixedRotationOffset
    if not input_data.get('fixedRotationOffset', False):
        logger.info("fixedRotationOffset is false - no staggering needed (solver will optimize)")
        return False
```

**File: `src/preprocessing/icpmp_integration.py` (Line 267)**
```python
# Sets rotation offset on employee object
emp['rotationOffset'] = offset
```

**File: `src/redis_worker.py` (Line 92)**
```python
# Replaces employees but doesn't set fixedRotationOffset flag
input_data['employees'] = preprocessing_result['filtered_employees']
```

### Production Logs

The logs show:
- ✅ "Selected 15 employees (utilization: 57.7%)"
- ✅ "Starting CP-SAT solver for job 79b0a7d6"
- ❌ No log showing "fixedRotationOffset is true"
- ❌ Solver runs 600 seconds and fails

### Result File

`output/output_1012_1745.json` shows:
- ✅ `icpmp_preprocessing.offset_distribution` present
- ❌ `status: "UNKNOWN"`
- ❌ `assignments: []`

---

## The Fix

### Required Change in `redis_worker.py`

**Location:** After ICPMP preprocessing, before CP-SAT execution

**Current Code (Line 92):**
```python
input_data['employees'] = preprocessing_result['filtered_employees']
```

**Fixed Code:**
```python
input_data['employees'] = preprocessing_result['filtered_employees']
input_data['fixedRotationOffset'] = True  # ← ADD THIS LINE
```

### Why This Works

1. ICPMP preprocessing calculates optimal offsets
2. Offsets are assigned to employee objects (`emp['rotationOffset']`)
3. **NEW:** Set global flag telling CP-SAT to use these offsets
4. CP-SAT builds constraints using fixed offsets
5. Solver finds solution quickly (not optimizing offsets anymore)

---

## Verification Steps

After applying the fix:

1. **Check Log Output:**
   ```
   [WORKER-1] ICPMP preprocessing completed
   [WORKER-1] Set fixedRotationOffset=True for CP-SAT
   ```

2. **Check Solver Behavior:**
   - Should solve in < 60 seconds (not 600s timeout)
   - Should return OPTIMAL or FEASIBLE status
   - Should generate 310 assignments

3. **Check Result Quality:**
   - Coverage rate should match ICPMP prediction (~100%)
   - Employees should work according to their assigned offsets
   - No constraint violations

---

## Impact Assessment

### Before Fix (Current State)
- ❌ ICPMP offsets calculated but ignored
- ❌ CP-SAT tries to optimize 15-employee problem
- ❌ Solver times out (600s)
- ❌ 0 assignments generated
- ❌ System unusable

### After Fix (Expected)
- ✅ ICPMP offsets used by CP-SAT
- ✅ Solver works with fixed offsets
- ✅ Fast solve time (< 60s)
- ✅ Optimal solution found
- ✅ 100% coverage achieved

---

## Additional Consideration

### Alternative Approach: Offset Manager Integration

The system has an `offset_manager.py` module that can automatically stagger offsets. However:

**Offset Manager:**
- Distributes offsets evenly (0, 1, 2, 3... up to pattern length)
- Simple round-robin distribution
- Doesn't consider employee utilization or U-slot minimization

**ICPMP v3.0:**
- ✅ Calculates **OPTIMAL** offset distribution
- ✅ Minimizes U-slots
- ✅ Considers employee working hours for fairness
- ✅ Proven minimal U-slot count

**Conclusion:** We should use ICPMP offsets, not offset_manager.

---

## Next Steps

1. ⚡ **IMMEDIATE:** Add `input_data['fixedRotationOffset'] = True` in redis_worker.py
2. 🧪 Test locally with `test_icpmp_integration.py`
3. 🚀 Commit and deploy to EC2
4. ✅ Rerun job RST-20251210-0870DE6A
5. 📊 Verify solution found in < 60 seconds

---

**Priority:** CRITICAL  
**Impact:** Blocking - System cannot generate solutions  
**Effort:** 5 minutes (1-line fix)  
**Risk:** Low - Adding missing configuration flag
