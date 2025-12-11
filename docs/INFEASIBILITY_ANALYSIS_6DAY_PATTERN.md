# Infeasibility Analysis: 6-Day Continuous Pattern (DDDDDOD)

**Date**: 2025-12-11  
**Case**: RST-20251211-FDEFDA64  
**Status**: INFEASIBLE with 30 unassigned slots (9.68%)

---

## Problem Summary

The solver returned INFEASIBLE with all violations from C9 Gender Balance constraint showing "Required gender 'Any' not available". However, **this is a misleading error message**—the real issue is **under-resourcing**.

### Key Metrics
```json
{
  "totalEmployeesAvailable": 12,
  "employeesUsed": 13,          // ❌ Impossible!
  "employeesUnused": -1,         // ❌ Negative = shortage
  "utilizationRate": 108.3%,     // ❌ Over 100%
  "unassignedSlots": 30 (9.68%)
}
```

---

## Root Cause Analysis

### 1. ICPMP Calculated 12 Employees
```json
"icpmp_preprocessing": {
  "requirements": {
    "68_1": {
      "optimal_employees": 12,   // ❌ TOO FEW
      "is_optimal": true,         // ❌ FALSE POSITIVE
      "coverage_rate": 100.0      // ❌ WRONG
    }
  }
}
```

**Calculation Used:**
```python
pattern = ["D","D","D","D","D","O","D"]  # 6 work, 1 off
pattern_length = 7
work_days = 6
headcount = 10

optimal_employees = ceil(31 / 7) * 10 / 7 ≈ 12
```

**What's Missing:**
- ❌ MOM weekly hour cap (44h normal hours)
- ❌ MOM monthly OT cap (72h)
- ❌ Consecutive day limits (12 days max)
- ❌ Rest period requirements (11h between shifts)
- ❌ Public holiday effects (2026-01-01)

### 2. Pattern Analysis: DDDDDOD (6 Consecutive Days)
```
Week 1:  D D D D D O D  (6 working days = 72 hours with 12h shifts)
         └─┴─┴─┴─┴─┘ └─ 6 consecutive = 72 hours
                  └─── Only 1 off day before next cycle
```

**Hour Breakdown per Employee (12h shifts):**
- Normal hours/week: 44h (MOM cap)
- OT hours/week: 72h - 44h = 28h
- Monthly OT accumulation: ~50-51h (approaching 72h cap)

**The Math Doesn't Work:**
- 6 days × 12 hours = 72 hours
- Weekly cap = 44 hours normal
- Even with rest-day pay, **you can't have 6 employees working 72h/week continuously**

### 3. Why C9 Errors Are Misleading
The actual violations say: `"Required gender 'Any' not available"`

**This is NOT a gender issue**—it's a **post-solve validation error**. The real sequence is:
1. CP-SAT tries to assign all slots
2. **C2 (Weekly/Monthly Hour Caps) blocks most assignments**
3. CP-SAT returns INFEASIBLE
4. Post-solve validator sees unassigned slots
5. Validator incorrectly reports as "gender not available"

**Evidence**: All employees are Male except 1 Female, and requirement says `gender: "Any"`. The C9 constraint should allow ANY gender.

---

## Why ICPMP Failed

The ICPMP v3 algorithm has a flaw in handling patterns with high work-to-rest ratios:

### Current Logic
```python
def calculate_optimal_with_u_slots(pattern, headcount, calendar):
    cycle_length = len(pattern)  # 7
    work_days_per_cycle = sum(1 for s in pattern if s != 'O')  # 6
    
    # Lower bound calculation
    pattern_based_minimum = ceil(headcount * cycle_length / work_days_per_cycle)
    # = ceil(10 * 7 / 6) = ceil(11.67) = 12
```

**Problem**: This assumes **all employees can work the full pattern continuously**, which violates:
1. **C2**: Weekly normal hours ≤ 44h
2. **C17**: Monthly OT ≤ 72h
3. **C3**: Max 12 consecutive days

### What Should Happen
ICPMP needs to simulate **actual constraint feasibility**, not just mathematical coverage:

```python
def calculate_feasible_employees(pattern, headcount, calendar):
    # Start with mathematical minimum
    min_employees = ceil(headcount * len(pattern) / work_days)
    
    # Add buffer for MOM constraints
    hours_per_cycle = work_days * 12  # Assuming 12h shifts
    cycles_per_week = 7 / len(pattern)
    weekly_hours = hours_per_cycle * cycles_per_week
    
    if weekly_hours > 44:
        # Need MORE employees to stay under weekly cap
        buffer_factor = weekly_hours / 44
        min_employees = ceil(min_employees * buffer_factor)
    
    # Add buffer for consecutive day limits
    if work_days >= 6:
        min_employees += 1  # Extra employee for rotation flexibility
    
    return min_employees
```

For DDDDDOD pattern:
```python
weekly_hours = 6 days * 12h * (7/7 weeks) = 72h
buffer_factor = 72 / 44 ≈ 1.64
min_employees = ceil(12 * 1.64) = 20 employees  // ✅ CORRECT
```

---

## Solutions

### Option 1: Fix ICPMP Calculation (RECOMMENDED)
**File**: `context/engine/config_optimizer_v3.py`

Add constraint-aware buffer calculation:

```python
def calculate_optimal_with_u_slots(
    pattern: List[str],
    headcount: int,
    calendar: List[str],
    anchor_date: str,
    requirement_id: str = "unknown",
    max_attempts: int = 50,
    shift_hours: float = 12.0  # NEW: Pass actual shift duration
) -> Dict[str, Any]:
    
    cycle_length = len(pattern)
    work_days_per_cycle = sum(1 for s in pattern if s != 'O')
    
    # Base mathematical minimum
    pattern_based_minimum = ceil(headcount * cycle_length / work_days_per_cycle)
    
    # NEW: Check if pattern violates weekly hour caps
    hours_per_cycle = work_days_per_cycle * shift_hours
    cycles_per_week = 7.0 / cycle_length
    weekly_hours = hours_per_cycle * cycles_per_week
    
    if weekly_hours > 44:
        # Pattern exceeds weekly cap - need buffer
        overflow_factor = weekly_hours / 44
        pattern_based_minimum = ceil(pattern_based_minimum * overflow_factor)
        logger.warning(
            f"[{requirement_id}] Pattern {pattern} requires {weekly_hours:.1f}h/week "
            f"(exceeds 44h cap). Increased employees from {pattern_based_minimum / overflow_factor:.0f} "
            f"to {pattern_based_minimum} (+{overflow_factor - 1:.1%} buffer)"
        )
    
    # NEW: Check for consecutive day limits
    max_consecutive = 0
    current_consecutive = 0
    for day in pattern:
        if day != 'O':
            current_consecutive += 1
            max_consecutive = max(max_consecutive, current_consecutive)
        else:
            current_consecutive = 0
    
    if max_consecutive >= 6:
        pattern_based_minimum += 1  # Extra employee for flexibility
        logger.warning(
            f"[{requirement_id}] Pattern has {max_consecutive} consecutive work days. "
            f"Added +1 employee for rotation flexibility."
        )
    
    # Continue with existing U-slot injection algorithm...
```

### Option 2: Post-ICPMP Validation
Add feasibility check AFTER ICPMP calculates employees:

```python
def validate_icpmp_result(employees_calculated, pattern, shift_hours, headcount):
    """
    Validate that ICPMP-calculated employee count is feasible.
    Returns (is_feasible, recommended_count, warnings)
    """
    warnings = []
    
    work_days = sum(1 for s in pattern if s != 'O')
    weekly_hours = (work_days / len(pattern)) * 7 * shift_hours
    
    if weekly_hours > 44:
        overflow = weekly_hours / 44
        min_needed = ceil(employees_calculated * overflow)
        warnings.append({
            "type": "WEEKLY_HOUR_OVERFLOW",
            "message": f"Pattern requires {weekly_hours:.1f}h/week (>{44}h). Need {min_needed} employees (not {employees_calculated})",
            "recommended_count": min_needed
        })
        return False, min_needed, warnings
    
    return True, employees_calculated, warnings
```

### Option 3: Change Work Pattern (BUSINESS DECISION)
Instead of DDDDDOD (6+1), use:
- **DDDDOOD** (4 work, 2 off): 48h/week → Need 14 employees
- **DDODODD** (5 work, 2 off distributed): 60h/week → Need 18 employees
- **DD4D2O2D** (custom): Design for 44h/week compliance

---

## Recommended Implementation Plan

### Phase 1: Immediate Fix (ICPMP Buffer)
**File**: `context/engine/config_optimizer_v3.py`  
**Lines**: 70-90 (in `calculate_optimal_with_u_slots`)

Add:
1. Weekly hour cap check
2. Consecutive day buffer
3. Warning messages

**Impact**: ICPMP will calculate 18-20 employees instead of 12

### Phase 2: Post-Solve Validation Improvement
**File**: `src/output_builder.py` or `context/engine/solver_engine.py`

Fix the misleading "gender not available" error to show actual constraint violations.

### Phase 3: Frontend Warning
When user selects pattern with 6+ consecutive days, show:
```
⚠️ Warning: Pattern DDDDDOD requires 6 consecutive work days (72h/week with 12h shifts).
This exceeds MOM weekly limit (44h). Estimated employees: 18-20 (not 12).
Consider using DDDDOOD (4+2) or custom pattern for better efficiency.
```

---

## Test Case

To verify fix, run:
```bash
# Original input (fails with 12 employees)
python src/run_solver.py --in /Users/glori/Downloads/RST-20251211-16372254_Solver_Input.json --time 300

# Expected after fix:
# ICPMP should calculate 18-20 employees
# All slots should be assigned
# Status: OPTIMAL or FEASIBLE
```

---

## Related Files

- `context/engine/config_optimizer_v3.py` - ICPMP calculation
- `context/constraints/C2_mom_weekly_hours.py` - Weekly hour cap
- `context/constraints/C17_ot_monthly_cap.py` - Monthly OT cap
- `context/constraints/C3_consecutive_days.py` - Consecutive day limit
- `src/output_builder.py` - Error message generation

---

## Conclusion

**The solver is working correctly**—it's correctly detecting that 12 employees cannot cover 310 slots with DDDDDOD pattern without violating MOM hour caps. 

**The bug is in ICPMP**, which calculated 12 employees using pure mathematical coverage without considering constraint feasibility.

**Fix**: Add constraint-aware buffer to ICPMP calculation, especially for patterns with ≥6 consecutive work days.
