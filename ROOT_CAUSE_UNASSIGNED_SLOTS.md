# ROOT CAUSE ANALYSIS: Unassigned Slots Instead of OFF Days

## The Problem

Your screenshot shows employees with pattern `DDNNOO` displaying:
- ❌ Yellow "Unassigned (N)" on days 3-4 (where pattern expects N shifts)
- ✅ Green shifts on days 5-6 (where pattern expects OFF but solver assigned work)

**Expected**: Days 5-6 should show gray "Off Day" cells.

---

## Root Cause

### **NO HARD CONSTRAINT FOR PATTERN ADHERENCE**

The CP-SAT solver has:
- ✅ Hard constraints: MOM hours, rest days, consecutive work
- ❌ **NO constraint forcing employees to follow work patterns**
- ✅ Soft constraint (S1): Scores violations but doesn't enforce

### What's Happening:

```
Pattern: ['D', 'D', 'N', 'N', 'O', 'O']  (Expected cycle)

CP-SAT Solver Decision:
  Day 1-2: Assign employee to N shifts (ignore pattern says D)
  Day 3-4: Don't assign (insufficient demand for N shifts)
  Day 5-6: Assign employee to D shifts (ignore pattern says O)

Result in employeeRoster:
  Day 1-2: status="ASSIGNED"   (OK - working)
  Day 3-4: status="UNASSIGNED" (❌ WRONG - should check pattern)
  Day 5-6: status="ASSIGNED"   (OK - working, even on OFF days)
```

### Why Patterns Aren't Being Followed:

1. **Slots are generated for D/N only** - not for specific employees
2. **Solver assigns ANY employee to ANY compatible slot** - no pattern matching
3. **No constraint says "Employee X must work D on day 1, D on day 2, etc."**
4. **Only soft penalty** - solver ignores it to maximize demand coverage

---

## Historical Behavior ("It Used to Work")

You're right that DDNNOO patterns worked before. Here's what changed:

### Before (Working):
- Pattern adherence was likely enforced through:
  - Template-based allocation (not pure CP-SAT optimization)
  - Hard constraint forcing continuous pattern cycles
  - Or strictAdherenceRatio parameter controlling flexibility

### Recent Changes That Broke It:
1. **Commit bf10221**: Removed OFF_DAY from assignments array
   - Intent: Clean up Demand Coverage tab
   - Side effect: employeeRoster can't find OFF_DAY assignments

2. **Commit 94efa2a**: Pattern-based OFF day detection
   - Intent: Use pattern to determine OFF days
   - Side effect: Only works if employees follow patterns (they don't!)

---

## The Solution

### Option 1: Add Hard Constraint for Continuous Adherence (Recommended)

Create `C18_continuous_adherence.py`:

```python
def add_constraints(model, ctx):
    """
    Enforce that IF an employee is assigned ANY shift,
    THEN they must work their full pattern cycle.
    
    For pattern ['D','D','N','N','O','O']:
      - If assigned on any day, must work ALL D and N days in cycle
      - OFF days (O) remain as rest days
    """
    
    employees = ctx.get('employees', [])
    slots = ctx.get('slots', [])
    x = ctx.get('x', {})
    
    for emp in employees:
        emp_id = emp['employeeId']
        emp_pattern = calculate_employee_work_pattern(base_pattern, emp_offset)
        
        # Group slots by pattern cycle position
        for cycle_start_date in cycle_dates:
            work_slots_in_cycle = []
            
            for day_offset, expected_shift in enumerate(emp_pattern):
                if expected_shift != 'O':  # Work day (D or N)
                    date = cycle_start_date + timedelta(days=day_offset)
                    slots_on_date = [s for s in slots if s.date == date and s.shift_code == expected_shift]
                    
                    for slot in slots_on_date:
                        work_slots_in_cycle.append(x[(slot.id, emp_id)])
            
            # If employee works ANY day in cycle, they work ALL work days in cycle
            if work_slots_in_cycle:
                # Either all work days assigned OR none assigned
                model.Add(sum(work_slots_in_cycle) == len(work_slots_in_cycle))
                             .OnlyEnforceIf(work_slots_in_cycle[0])
```

**Effect**: Employees either work full pattern cycles OR not at all. No partial assignments.

### Option 2: Use strictAdherenceRatio (Existing Parameter)

If this parameter is supposed to control pattern flexibility:

```python
def apply_adherence_ratio(ctx):
    """
    strictAdherenceRatio = 1.0: Full pattern adherence (100%)
    strictAdherenceRatio = 0.8: Allow 20% flexibility
    strictAdherenceRatio = 0.0: No pattern enforcement
    """
    
    ratio = ctx.get('strictAdherenceRatio', 1.0)
    
    if ratio == 1.0:
        # Add hard constraint for full adherence
        enforce_continuous_pattern(model, ctx)
    elif ratio > 0:
        # Add soft constraint with weight based on ratio
        weight = int(ratio * 100)  # 0.8 → weight 80
        # Solver tries to match pattern but can deviate
    else:
        # No pattern enforcement - full flexibility
        pass
```

### Option 3: Template-Based Pattern Assignment (Simplest)

Instead of letting CP-SAT choose freely:

```python
def pre_assign_employees_to_cycles(ctx):
    """
    BEFORE CP-SAT solving:
    1. Calculate how many employees needed
    2. Assign employees to work patterns
    3. Generate slots ONLY for assigned employees' work days
    4. CP-SAT just fills pre-determined slots
    """
    
    for emp in employees[:employees_needed]:
        emp_pattern = calculate_pattern(emp)
        
        for date in date_range:
            pattern_day = calculate_pattern_day(date, emp_offset)
            expected_shift = emp_pattern[pattern_day]
            
            if expected_shift != 'O':
                # Create slot specifically for this employee
                slot = Slot(
                    emp_id=emp_id,  # ← Pre-assigned!
                    shift_code=expected_shift,
                    date=date
                )
```

**Effect**: CP-SAT just confirms feasibility, doesn't choose which employees work which days.

---

## Immediate Fix for Your Case

Since you need this working NOW, here's the quickest fix:

### Update `insert_off_day_assignments()` to NOT filter employees

```python
# Line 544-545 in output_builder.py
# BEFORE:
if emp_id not in assignments_by_emp_date:
    continue

# AFTER:
# Generate OFF days for ALL employees, regardless of whether they have work
```

AND

### Update `build_employee_roster()` to ALWAYS use pattern first

```python
# For each date:
pattern_day = calculate_pattern_day(date, offset, pattern_length)
expected_shift = emp_pattern[pattern_day]

if expected_shift == 'O':
    # Pattern says OFF → always mark as OFF_DAY
    daily_status.append({"status": "OFF_DAY", "shiftCode": "O"})
elif assignment_exists:
    # Has work assignment → mark as ASSIGNED
    daily_status.append({"status": "ASSIGNED", ...})
else:
    # Pattern says work but no assignment → mark as UNASSIGNED
    daily_status.append({"status": "UNASSIGNED", ...})
```

**But this still won't fix the underlying issue**: Solver is assigning work on OFF days because there's no constraint preventing it!

---

## Recommended Action Plan

1. **Immediate** (today): Verify that current code correctly identifies OFF days based on pattern
2. **Short-term** (this week): Add C18_continuous_adherence.py hard constraint
3. **Medium-term** (next sprint): Implement strictAdherenceRatio parameter properly
4. **Long-term**: Document expected behavior for demandBased vs outcomeBased

Do you want me to implement Option 1 (Hard Constraint) now?
