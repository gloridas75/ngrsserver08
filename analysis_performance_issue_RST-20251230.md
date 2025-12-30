# Performance Issue Analysis: RST-20251230-CE17BA91

## Problem
Solver times out after 6+ minutes on production (360s limit), used to complete in ~2 minutes.

## Input Characteristics
- **Problem**: demandBased rostering
- **Employees provided**: 91
- **Requirement**: 20 positions/shift, pattern [D,D,N,N,O,O]
- **Planning period**: 31 days (Jan 2026)
- **Shifts**: Day (08:00-20:00) + Night (20:00-08:00)

## Root Cause Analysis

### Theoretical Employee Requirement
```
Pattern: [D, D, N, N, O, O]
- Pattern length: 6 days
- Work days: 4 days (2D + 2N)
- Headcount per shift: 20 positions

Calculation:
  Employees needed = 20 positions × 6 days / 4 work days
                   = 30 employees (optimal)
```

### What ICPMP Actually Did
```
ICPMP v3.0 preprocessing:
  Input: 91 employees
  
  Step 1: Calculate optimal
    → 60 employees needed (for BOTH D and N shifts!)
  
  Step 2: Apply buffer
    Buffer = 30% (from icpmpBufferPercentage field)
    60 × 1.30 = 78 employees
  
  Output: 91 → 78 employees
```

### Why This Is Wrong

**The ICPMP calculation is CORRECT for coverage:**
- Day shift needs: ~30 employees
- Night shift needs: ~30 employees  
- Total: ~60 employees for both shifts

**But the 30% buffer is UNNECESSARY:**
- Input has 91 employees (sufficient)
- Buffer meant for understaffing scenarios
- Creates 30% overhead: 60 → 78 employees

### Performance Impact

**Decision Variables:**
```
Slots: 1240 (20 Day positions × 31 days + 20 Night positions × 31 days)
Employees: 78 (after ICPMP filtering)
Variables: 1240 × 78 = 96,720 decision variables
```

**C4 Constraint (Minimum Rest Between Shifts):**
```python
# Current implementation checks ALL pairs O(n²)
for i in range(len(sorted_slots)):
    for j in range(i + 1, len(sorted_slots)):
        if rest_insufficient(slot_i, slot_j):
            add_constraint()

# With 78 employees, ~16 slots each:
# 78 employees × 16² comparisons = ~20,000 constraint checks
# Takes 2-3 minutes just to build constraints!
```

**Solver Phase:**
- CP-SAT must search through 96,720 variables
- With 78 employees instead of 60: **30% more search space**
- Timeout after 6+ minutes

## Solutions Implemented

### 1. C4 Constraint Optimization (DONE)
Added early termination when rest_available > 24 hours:

```python
# NEW: Early break for performance
if rest_available > timedelta(hours=24):
    break  # All subsequent slots have even more rest
```

**Impact**: Reduces O(n²) to O(n×k) where k is slots within 24h window

### 2. ICPMP Buffer Adjustment (RECOMMENDED)

**Option A: Remove buffer when sufficient employees**
```python
# In icpmp_integration.py
available_employees = len(self._filter_eligible_employees(requirement, demand_item))
buffer_percentage = requirement.get('icpmpBufferPercentage', 20)

# Skip buffer if we have enough employees
if available_employees >= optimal_count_raw * 1.5:
    buffer_percentage = 0
    logger.info(f"Sufficient employees ({available_employees}), skipping buffer")
```

**Option B: Cap buffer at sensible maximum**
```python
# Never add more than 20% buffer
buffer_percentage = min(requirement.get('icpmpBufferPercentage', 20), 20)
```

**Option C: Remove default buffer entirely**
```python
# Make buffer opt-in, not automatic
buffer_percentage = requirement.get('icpmpBufferPercentage', 0)  # Changed from 20
```

## Recommendations

**Immediate (Fix C4 constraint):**
✅ DONE - Added early termination in C4_rest_period.py

**Short-term (Fix ICPMP buffer logic):**
1. Implement Option A: Skip buffer when sufficient employees
2. Add logging to show buffer decision reasoning
3. Update ICPMP documentation

**Long-term (Smarter buffering):**
1. Calculate buffer based on constraint tightness
2. Different defaults for different scenarios:
   - Tight consecutive day limits → 20-30% buffer
   - Flexible patterns → 0-10% buffer
3. Adaptive: Start with no buffer, add if infeasible

## Expected Performance After Fixes

**With C4 optimization only:**
- Model build: 2-3 min → ~30-60 sec
- Solve: 3-4 min → ~1-2 min
- **Total: ~2-3 minutes**

**With C4 + reduced buffer (60 employees instead of 78):**
- Variables: 96,720 → 74,400 (23% reduction)
- Model build: ~30 sec
- Solve: ~60 sec
- **Total: ~90 seconds** ← Back to historical performance!

## Test Plan

1. ✅ Test C4 fix locally with current input
2. ⬜ Deploy C4 fix to production
3. ⬜ Implement Option A (skip buffer when sufficient)
4. ⬜ Test with buffer=0 on this input
5. ⬜ Compare solve times: 30% vs 0% buffer

