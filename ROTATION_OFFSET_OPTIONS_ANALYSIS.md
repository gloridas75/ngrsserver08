# Rotation Offset Handling - Options Analysis

## Problem Statement

In **outcomeBased mode** with **single OU** and **multiple employees with different rotation offsets**:
- Current approach: Generate template for 1 employee, replicate with date-shifting
- **Issue**: Date-shifting breaks with:
  - Public holidays (wrong shifts on holiday dates)
  - Employee availability/leave (shifts assigned when unavailable)
  - Complex constraint interactions (MOM rules violated)

## Current Architecture

### Template Generation Mode (outcomeBased)
```
1. Pick ONE employee as template (first in OU)
2. Run CP-SAT mini-solver for template employee
   - Apply C1-C17 constraints
   - Generate optimal schedule
3. Replicate to other employees by shifting dates
   - offset_diff = emp_offset - template_offset
   - new_date = template_date + offset_diff days
4. Problem: Date shifting doesn't respect constraints!
```

**Key Issue**: Replication happens AFTER CP-SAT, so constraints only validated for template.

### DemandBased Mode (Full CP-SAT)
```
1. Generate slots for ALL demand items
2. Create decision variables: x[(slot, employee)] for EVERY employee
3. Apply C1-C17 constraints to ALL employees simultaneously
4. CP-SAT solver finds optimal assignment
5. Result: Each employee's schedule respects ALL constraints
```

**Advantage**: CP-SAT sees the full problem and enforces constraints for every employee.

---

## Option 1: Full CP-SAT for Single OU (Recommended)

### Approach
**Treat single OU + multiple offsets like demandBased mode**

```python
if rostering_basis == 'outcomeBased':
    # Check if single OU with individual employee offsets
    unique_ous = set(emp.get('ouId') for emp in employees)
    has_employee_offsets = any('rotationOffset' in emp for emp in employees)
    is_single_ou = len(unique_ous) == 1
    
    if is_single_ou and has_employee_offsets:
        # Use full CP-SAT solver instead of template generation
        print("[SOLVER] Single OU with rotation offsets → Using full CP-SAT")
        status_code, solver_result, assignments, violations = solve(ctx)
    else:
        # Use template generation for multiple OUs
        assignments = generate_template_validated_roster(ctx, ...)
```

### What Changes
1. **Slot Generation**: Build slots for ALL employees (not just template)
   - Each employee gets slots based on their work pattern + offset
   - Pattern repeats: `(offset + day_index) % pattern_length`

2. **Decision Variables**: Create `x[(slot, emp)]` for all employee-slot pairs
   - Same as demandBased mode
   - ~10 employees × 31 days × pattern = ~200-300 variables

3. **Constraint Application**: C1-C17 applied to ALL employees
   - Public holidays respected for each employee
   - Availability/leave checked individually
   - MOM rules (weekly rest, OT caps, etc.) per employee

4. **Solving**: CP-SAT finds optimal assignment
   - Rotation offsets enforced via C2 (pattern adherence)
   - Each employee gets their own schedule

### Pros
✅ **Correct**: Respects ALL constraints for ALL employees  
✅ **Handles holidays**: CP-SAT knows about public holidays  
✅ **Handles availability**: Checks employee-specific constraints  
✅ **Clean architecture**: Reuses existing demandBased solver  
✅ **Moderate complexity**: 10 employees is feasible for CP-SAT  

### Cons
⚠️ **Slower**: O(employees × days) vs O(1 template × days)  
⚠️ **May not scale**: >50 employees might be slow  
⚠️ **More variables**: 200-300 vs 31 for template  

### Performance Estimate
- **10 employees × 31 days = 310 variables**
- Similar to small demandBased problem
- Expected solve time: **5-30 seconds** (vs 0.1s template)
- Still acceptable for single OU use case

---

## Option 2: Template per Offset (Middle Ground)

### Approach
**Generate one template per unique rotation offset**

```python
# Group employees by rotation offset
offset_groups = defaultdict(list)
for emp in employees:
    offset = emp.get('rotationOffset', 0)
    offset_groups[offset].append(emp)

# Generate template for each offset
for offset, emp_group in offset_groups.items():
    template = generate_template_with_cpsat(
        ctx, requirement, [emp_group[0]], date_range
    )
    # Replicate to other employees with SAME offset (no date shifting)
    for emp in emp_group:
        assignments.extend(replicate_template(template, emp))
```

### Pros
✅ **Partially correct**: Each offset group gets valid template  
✅ **Faster**: Only N templates where N = unique offsets  
✅ **No date shifting**: Employees with same offset get identical schedule  

### Cons
❌ **Still breaks with availability**: If emp1 unavailable on Feb 1, template might assign it  
❌ **Doesn't handle individual constraints**: Only template employee validated  
❌ **Complex code**: Need offset grouping logic  

### Verdict
**Not recommended** - Still has the same fundamental issues as current approach.

---

## Option 3: Hybrid (Template + Validation)

### Approach
**Generate template, then validate each employee with CP-SAT**

```python
# 1. Generate template with CP-SAT
template = generate_template_with_cpsat(ctx, [first_employee], ...)

# 2. For each employee, validate and adjust
for emp in all_employees:
    # Replicate template with date shifting
    candidate_schedule = replicate_with_offset(template, emp)
    
    # Run mini CP-SAT to check feasibility
    is_valid, adjusted_schedule = validate_with_cpsat(
        emp, candidate_schedule, ctx
    )
    
    if is_valid:
        assignments.extend(adjusted_schedule)
    else:
        # Regenerate from scratch for this employee
        assignments.extend(generate_individual_schedule(emp, ctx))
```

### Pros
✅ **Correct**: Each employee validated individually  
✅ **Optimized**: Most employees use template (fast)  
✅ **Fallback**: Problematic employees get custom schedule  

### Cons
⚠️ **Complex**: Two-phase solving (template + validation)  
⚠️ **Unpredictable performance**: Depends on how many need regeneration  
⚠️ **Code complexity**: Validation logic + fallback handling  

---

## Recommendation: Option 1 (Full CP-SAT)

### Rationale
1. **Correctness > Speed**: 5-30 seconds is acceptable for 10 employees
2. **Simplest implementation**: Reuse existing demandBased path
3. **No edge cases**: All constraints enforced uniformly
4. **Proven approach**: DemandBased mode already works this way

### Implementation Plan

#### Step 1: Add Single OU Detection
```python
# In src/solver.py, around line 330
if rostering_basis == 'outcomeBased':
    unique_ous = set(emp.get('ouId') for emp in employees)
    has_employee_offsets = any('rotationOffset' in emp for emp in employees)
    is_single_ou = len(unique_ous) == 1
    
    if is_single_ou and has_employee_offsets and len(employees) <= 50:
        # Override to demandBased mode for this case
        print(f"{log_prefix} Single OU with {len(employees)} employees having individual offsets")
        print(f"{log_prefix} Using full CP-SAT solver instead of template generation")
        rostering_basis = 'demandBased'  # Switch mode
```

#### Step 2: Ensure Slots Generated Correctly
```python
# In context/engine/slot_builder.py
# build_slots() already handles rotation offsets via C2 constraint
# Just ensure employees have rotationOffset field populated
```

#### Step 3: Pattern Adherence (C2)
```python
# context/constraints/C2_rotation_pattern_adherence.py
# Already handles rotation offsets correctly
# Enforces: assignment on date D follows pattern[(offset + D) % len(pattern)]
```

#### Step 4: Test with E082FFB0 Input
```bash
python src/run_solver.py --in RST-20260108-E082FFB0_Solver_Input.json --time 60
```

Expected result: **10 unique schedules**, each respecting:
- Rotation offset (different work dates)
- Public holidays (no assignments on PH)
- MOM constraints (weekly rest, OT caps, etc.)

---

## Comparison Table

| Aspect | Current Template | Option 1: Full CP-SAT | Option 2: Template/Offset | Option 3: Hybrid |
|--------|-----------------|----------------------|--------------------------|------------------|
| **Correctness** | ❌ Breaks | ✅ Perfect | ❌ Still breaks | ✅ Perfect |
| **Speed (10 emp)** | ⚡ 0.1s | 🐢 5-30s | ⚡ 1s | 🐌 10-60s |
| **Scalability** | ✅ 100+ emp | ⚠️ <50 emp | ⚠️ <50 emp | ⚠️ <50 emp |
| **Holidays** | ❌ Ignored | ✅ Respected | ❌ Ignored | ✅ Respected |
| **Availability** | ❌ Ignored | ✅ Respected | ❌ Ignored | ✅ Respected |
| **Code Complexity** | ✅ Simple | ✅ Simple | ⚠️ Moderate | ❌ Complex |
| **Implementation** | - | ✅ 20 lines | ⚠️ 100 lines | ❌ 200+ lines |

---

## Alternative: Scope Limits

If performance is critical, consider:

### Option 4: Documentation + Limits
```json
{
  "documentation": "For single OU with rotation offsets, use demandBased mode instead",
  "validation": {
    "if": "rosteringBasis == 'outcomeBased' AND single OU AND employee offsets",
    "then": "Employee count must be <= 20 OR use demandBased mode"
  }
}
```

User can explicitly choose:
- **outcomeBased + templateGenerationMode**: Fast but ignores individual offsets (all same schedule)
- **demandBased**: Slower but respects individual offsets (unique schedules)

---

## Decision Matrix

**Choose Option 1 (Full CP-SAT) if:**
- ✅ Employee count <= 50
- ✅ Correctness is critical (MOM compliance)
- ✅ 30-60 second solve time is acceptable

**Choose Option 4 (Documentation) if:**
- ✅ Need fast response (<5 seconds)
- ✅ Willing to use demandBased mode for this case
- ✅ Can educate users about mode selection

**Current Recommendation: Option 1**
- Simple to implement (20 lines)
- Reuses proven demandBased path
- Correct for all edge cases
- Performance acceptable for typical use case (10-20 employees)
