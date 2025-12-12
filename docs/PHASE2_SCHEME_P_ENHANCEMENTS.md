# Phase 2: Scheme P Enhancements - TODO

## Status: NOT YET IMPLEMENTED
**Phase 1** (current commit) implements basic Scheme P support for 8h shifts.  
**Phase 2** (this document) describes required enhancements before production use with variable shift lengths.

---

## Issue 1: ICPMP Shift-Duration Awareness

### Problem
ICPMP currently uses **fixed 4 days/week** for all Scheme P employees, regardless of shift duration.

```python
# Current implementation:
SCHEME_P_CONSTRAINTS = {
    'max_days_per_week': 4,  # ← FIXED for all shifts
}
```

### Required Behavior
Scheme P capacity should vary by shift duration to comply with C6 weekly hour limits:

| Shift Duration (gross) | Max Days/Week | Max Weekly Hours | Calculation |
|------------------------|---------------|------------------|-------------|
| 8h (9h gross) | 4 days | 34.98h | 4 days × 8.745h |
| 6h gross | 5 days | 29.98h | 5 days × 5.996h |
| 5h gross | 6 days | 29.98h | 6 days × 4.996h |
| 4h gross | 7 days | 29.98h | 7 days × 4.283h |

### Impact
- ICPMP will **underestimate** required employees for patterns with shorter shifts
- Example: 6h shift pattern should allow 5 days/week (not 4)
  - Current: Calculates ~27 employees (4 days capacity)
  - Correct: Should calculate ~22 employees (5 days capacity)

### Implementation Plan

#### Step 1: Pass Shift Duration to ICPMP
**File**: `src/preprocessing/icpmp_integration.py`

```python
# Extract shift duration from requirement
def _run_icpmp_for_requirement(req: dict) -> dict:
    scheme = req.get('scheme', 'A')
    
    # NEW: Extract typical shift duration from demand items
    shift_duration = _extract_typical_shift_duration(req)
    
    icpmp_result = calculate_optimal_with_u_slots(
        ...,
        scheme=scheme,
        shift_duration_hours=shift_duration  # ← NEW parameter
    )
```

#### Step 2: Dynamic Max Days Calculation
**File**: `context/engine/config_optimizer_v3.py`

```python
def calculate_scheme_p_max_days(shift_duration_hours: float) -> int:
    """
    Calculate max work days per week for Scheme P based on shift duration.
    
    Args:
        shift_duration_hours: Typical gross shift duration (includes lunch)
    
    Returns:
        Maximum work days per week
    
    Examples:
        8-9h shifts → 4 days/week (34.98h max)
        6-7h shifts → 5 days/week (29.98h max)
        5-5.99h shifts → 6 days/week (29.98h max)
        ≤4h shifts → 7 days/week (29.98h max)
    """
    if shift_duration_hours >= 8:
        return 4
    elif shift_duration_hours >= 6:
        return 5
    elif shift_duration_hours >= 5:
        return 6
    else:
        return 7
```

#### Step 3: Update ICPMP Calculation
**File**: `context/engine/config_optimizer_v3.py`

```python
def calculate_optimal_with_u_slots(
    ...,
    scheme: str = 'A',
    shift_duration_hours: float = 8.0  # NEW parameter
) -> dict:
    
    # Calculate scheme-specific max days
    if scheme == 'P':
        scheme_max_days_per_week = calculate_scheme_p_max_days(shift_duration_hours)
    else:
        scheme_max_days_per_week = calculate_scheme_max_days_per_week(scheme)
    
    # Rest of logic unchanged...
```

### Testing Requirements
- Test ICPMP with 8h shifts: Should return 4 days capacity (existing behavior)
- Test ICPMP with 6h shifts: Should return 5 days capacity (new behavior)
- Test ICPMP with 5h shifts: Should return 6 days capacity (new behavior)
- Test ICPMP with 4h shifts: Should return 7 days capacity (new behavior)

### Affected Files
- `context/engine/config_optimizer_v3.py` - Add dynamic calculation
- `src/preprocessing/icpmp_integration.py` - Pass shift duration
- Tests: `test_icpmp_v3.py` - Add shift-duration test cases

---

## Issue 2: Scheme P 1-Hour Gap Between Same-Day Shifts

### Problem
**No constraint exists** to enforce minimum gap between multiple shifts on the same day for Scheme P employees.

### Required Behavior
Scheme P employees can work multiple shifts per day, but there **MUST be at least 1 hour gap** between shifts.

**Example** (Valid):
```
Shift 1: 09:00-13:00 (4h)
Gap:     13:00-14:00 (1h) ← REQUIRED
Shift 2: 14:00-18:00 (4h)
Total: 8h worked, complies with C6
```

**Example** (Invalid):
```
Shift 1: 09:00-13:00 (4h)
Shift 2: 13:00-17:00 (4h) ← NO GAP! Violates requirement
```

### Distinction from Existing Constraints
| Constraint | Scope | Min Gap | Applies To |
|------------|-------|---------|------------|
| **C4** | Day-to-day | 8 hours | All schemes |
| **S4** | Day-to-day | 8 hours (soft) | All schemes |
| **C7** (NEW) | Same-day | 1 hour | **Scheme P only** |

### Implementation Plan

#### Step 1: Create New Constraint
**File**: `context/constraints/C7_scheme_p_same_day_gap.py`

```python
"""C7: Minimum 1h gap between same-day shifts for Scheme P (HARD constraint).

Scheme P employees can work multiple shifts per day, but must have at least
1 hour gap between shifts on the same calendar day.

This is separate from C4 (8h rest between consecutive days).
"""
from datetime import timedelta
from collections import defaultdict


def add_constraints(model, ctx):
    """
    Enforce 1h minimum gap between same-day shifts for Scheme P employees.
    
    Strategy:
    1. Identify Scheme P employees
    2. Group slots by (employee, date)
    3. For each pair of slots on same date:
       - If both assigned and they overlap or gap < 1h
       - Add constraint: NOT (both assigned)
    
    Args:
        model: CP-SAT model
        ctx: Context dict with 'slots', 'employees', 'x'
    """
    
    slots = ctx.get('slots', [])
    employees = ctx.get('employees', [])
    x = ctx.get('x', {})
    
    # Identify Scheme P employees
    scheme_p_employees = [
        emp.get('employeeId') 
        for emp in employees 
        if emp.get('scheme') == 'P'
    ]
    
    if not scheme_p_employees:
        print(f"[C7] Scheme P Same-Day Gap Constraint (HARD)")
        print(f"     No Scheme P employees found\n")
        return
    
    min_gap = timedelta(hours=1)
    constraints_added = 0
    
    # Group slots by (emp_id, date)
    emp_date_slots = defaultdict(list)
    for slot in slots:
        for emp_id in scheme_p_employees:
            if (slot.slot_id, emp_id) in x:
                emp_date_slots[(emp_id, slot.date)].append(slot)
    
    # Check each employee-date combination
    for (emp_id, date), day_slots in emp_date_slots.items():
        if len(day_slots) < 2:
            continue
        
        # Sort slots by start time
        day_slots.sort(key=lambda s: s.start)
        
        # Check all pairs
        for i in range(len(day_slots)):
            for j in range(i + 1, len(day_slots)):
                slot1 = day_slots[i]
                slot2 = day_slots[j]
                
                # Calculate gap between shifts
                gap = slot2.start - slot1.end
                
                # If gap is less than 1h, they can't both be assigned
                if gap < min_gap:
                    var1 = x[(slot1.slot_id, emp_id)]
                    var2 = x[(slot2.slot_id, emp_id)]
                    
                    # Add constraint: NOT (both assigned)
                    # Equivalent to: var1 + var2 <= 1
                    model.Add(var1 + var2 <= 1)
                    constraints_added += 1
    
    print(f"[C7] Scheme P Same-Day Gap Constraint (HARD)")
    print(f"     Scheme P employees: {len(scheme_p_employees)}")
    print(f"     Min gap between same-day shifts: 1 hour")
    print(f"     ✓ Added {constraints_added} gap constraints\n")
```

#### Step 2: Register Constraint
Ensure constraint is loaded by the solver (auto-loaded via `pkgutil` in `solver_engine.py`).

#### Step 3: Update SCHEME_P_CONSTRAINTS
**File**: `context/engine/config_optimizer_v3.py`

```python
SCHEME_P_CONSTRAINTS = {
    # ... existing fields ...
    
    # Same-day shift rules (C7 constraint)
    'min_gap_between_same_day_shifts_hours': 1.0,
    'allow_multiple_shifts_per_day': True,
}
```

### Testing Requirements
- Test 1: Scheme P with 2 shifts on same day, 1h gap → Should be feasible
- Test 2: Scheme P with 2 shifts on same day, 30min gap → Should be infeasible
- Test 3: Scheme P with 2 shifts on different days, any gap → C4 applies (8h), not C7
- Test 4: Scheme A/B with tight same-day shifts → Should work (C7 doesn't apply)

### Affected Files
- `context/constraints/C7_scheme_p_same_day_gap.py` - NEW constraint
- `context/engine/config_optimizer_v3.py` - Add gap parameter
- Tests: `tests/test_scheme_p_gap.py` - NEW test file

---

## Implementation Priority

### High Priority (Before Production)
✅ **Issue 1**: ICPMP shift-duration awareness  
- Required for correct employee count with variable shifts
- Affects capacity planning and cost estimates

### Medium Priority
✅ **Issue 2**: Same-day gap constraint  
- Required for operational compliance
- But can be validated post-solve if needed (manual check)

---

## Acceptance Criteria

### Issue 1: ICPMP Shift-Duration Awareness
- [ ] ICPMP accepts `shift_duration_hours` parameter
- [ ] 8h shifts → 4 days capacity (existing behavior preserved)
- [ ] 6h shifts → 5 days capacity (new behavior)
- [ ] 5h shifts → 6 days capacity (new behavior)
- [ ] 4h shifts → 7 days capacity (new behavior)
- [ ] All ICPMP tests pass with updated logic
- [ ] Employee count calculations verified for each shift length

### Issue 2: Same-Day Gap Constraint
- [ ] C7 constraint created and registered
- [ ] Scheme P employees cannot be assigned shifts with <1h gap on same day
- [ ] Scheme A/B employees unaffected
- [ ] Constraint works with C4 (day-to-day rest) without conflict
- [ ] Test suite covers all gap scenarios
- [ ] No false positives (valid patterns not blocked)

---

## Testing Strategy

### Phase 2 Test Suite
Create comprehensive test file: `tests/test_scheme_p_phase2.py`

**Test Cases**:
1. ICPMP with 8h shifts (baseline - should match Phase 1)
2. ICPMP with 6h shifts (should increase capacity to 5 days)
3. ICPMP with 5h shifts (should increase capacity to 6 days)
4. ICPMP with 4h shifts (should increase capacity to 7 days)
5. Same-day gap: Valid (1h gap between shifts)
6. Same-day gap: Invalid (<1h gap between shifts)
7. Multi-shift pattern: 3 shifts per day with proper gaps
8. Edge case: Midnight-crossing shifts
9. Integration: C7 + C4 working together
10. Regression: Scheme A/B unaffected by C7

---

## Deployment Plan

### Phase 1 (Current Commit) ✅
- Basic Scheme P support with 8h shifts
- Hour calculation fixes
- ICPMP basic support (4 days/week)
- Safe for production with 8h patterns

### Phase 2 (Next Sprint)
1. **Week 1**: Implement Issue 1 (ICPMP shift-duration)
2. **Week 2**: Implement Issue 2 (Same-day gap constraint)
3. **Week 3**: Integration testing
4. **Week 4**: Production deployment with full Scheme P support

### Rollback Plan
If Phase 2 issues discovered:
- Revert to Phase 1 (8h shifts only)
- Block 6h/5h/4h shift patterns in input validation
- Fix issues and redeploy

---

## Documentation Updates Needed

After Phase 2 implementation:
- [ ] Update [.github/copilot-instructions.md](.github/copilot-instructions.md)
- [ ] Update [docs/SCHEME_P_IMPLEMENTATION_SUMMARY.md](docs/SCHEME_P_IMPLEMENTATION_SUMMARY.md)
- [ ] Update [context/glossary.md](context/glossary.md) with C7 constraint
- [ ] Update [implementation_docs/CONSTRAINT_ARCHITECTURE.md](implementation_docs/CONSTRAINT_ARCHITECTURE.md)
- [ ] Add C7 to constraint reference docs

---

## Notes
- Phase 1 is **production-ready** for 8h Scheme P shifts
- Phase 2 required before supporting variable shift lengths
- Both phases maintain backward compatibility with Scheme A/B
- Gap constraint (C7) is complementary to existing rest constraints (C4)

---

*Created: 2025-12-12*  
*Status: Pending Implementation*  
*Target: Next Sprint*
