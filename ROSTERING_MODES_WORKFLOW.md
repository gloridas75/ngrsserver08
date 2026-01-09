# NGRS Solver - Rostering Modes Workflow Analysis

## Entry Points

### API Entry (`src/api_server.py`)
1. POST `/solve` (sync) or `/solve/async` (async)
2. Validates input JSON schema
3. **Calls `solve_problem(input_data)` from `src/solver.py`** (unified entry point)
4. **NO preprocessing of rotation offsets** - handled inside `solve_problem()`

### CLI Entry (`src/run_solver.py`)
1. `python src/run_solver.py --in input.json`
2. Loads raw input JSON
3. **Calls `solve_problem(input_data)` from `src/solver.py`** (unified entry point)
4. **NO preprocessing of rotation offsets** - handled inside `solve_problem()`

### ⚠️ CRITICAL: Unified Code Path
Both API and CLI use **IDENTICAL** preprocessing logic inside `src/solver.py`.
This ensures rotation offsets, mode detection, and ICPMP handling work the same way for both entry points.

---

## Main Workflow: `src/solver.py` - `solve_problem()`

This is the **SINGLE ENTRY POINT** for both API and CLI. All preprocessing happens here.

```python
def solve_problem(input_data, max_time_seconds=300, ...):
    # ═══════════════════════════════════════════════════════════
    # PHASE 1: INTELLIGENT PREPROCESSING
    # ═══════════════════════════════════════════════════════════
    
    # Step 1: Analyze input structure
    employees = input_data.get('employees', [])
    employees_with_patterns = sum(1 for emp in employees if emp.get('workPattern'))
    fixed_rotation_offset_mode = input_data.get('fixedRotationOffset')
    
    # Step 2: Rotation Offset Handling (src/offset_manager.py)
    # ──────────────────────────────────────────────────────────
    # SCENARIO A: outcomeBased mode → Apply OU offsets or auto-stagger
    if fixed_rotation_offset_mode == 'ouOffsets':
        # Call ensure_staggered_offsets() which internally:
        # 1. Checks if employees have VARIED individual offsets
        # 2. If YES → PRESERVE them (don't override with OU offsets)
        # 3. If NO → Apply OU-level offsets from ouOffsets array
        input_data = ensure_staggered_offsets(input_data)
    
    elif fixed_rotation_offset_mode == 'auto':
        # Auto-stagger offsets unless ICPMP assigned them
        if not icpmp_assigned_offsets:
            input_data = ensure_staggered_offsets(input_data)
    
    # Step 3: Single OU Detection & Mode Switching
    # ──────────────────────────────────────────────────────────
    # If all employees in ONE OU have INDIVIDUAL varied offsets:
    # → Switch from outcomeBased to demandBased mode
    # → Use full CP-SAT solver to generate unique schedules per employee
    
    unique_ous = set(emp.get('ouId') for emp in employees)
    employee_offsets = [emp.get('rotationOffset') for emp in employees]
    has_individual_offsets = len(set(employee_offsets)) > 1
    is_single_ou = len(unique_ous) == 1
    
    if is_single_ou and has_individual_offsets and len(employees) <= 50:
        # OVERRIDE mode: Switch to demandBased
        rostering_basis = 'demandBased'
        print("SINGLE OU WITH INDIVIDUAL ROTATION OFFSETS DETECTED")
        print("Switching to demandBased CP-SAT solver...")
    
    # Step 4: Mode-specific solving
    if rostering_basis == "outcomeBased":
        return solve_outcome_based(input_data, ctx)
    else:
        return solve_demand_based(input_data, ctx)
```

### Key Preprocessing Features

1. **Rotation Offset Preservation** (`src/offset_manager.py`):
   - Detects when employees have VARIED individual offsets (e.g., 0, 1, 2, 3...)
   - Preserves these offsets even if `ouOffsets` specifies OU-level offset
   - Only applies OU offsets when all employees have SAME offset (typically 0)

2. **Automatic Mode Switching**:
   - Single OU + individual offsets → Switch to demandBased mode
   - Enables unique schedules per employee based on rotation offsets
   - Limited to ≤50 employees for performance

3. **ICPMP Integration**:
   - If ICPMP assigned offsets, skip auto-staggering
   - Preserves ICPMP's optimal offset distribution

---

## PATH A: Outcome-Based Mode

### File: `src/solver.py` - `solve_outcome_based()`

**CRITICAL CHANGE**: When single OU with individual offsets is detected, this path is SKIPPED and demandBased is used instead!

```
┌─────────────────────────────────────────────────────────────┐
│ 1. PREPROCESSING (done in solve_problem before this!)     │
│    • Rotation offsets already applied by offset_manager    │
│    • Mode already determined (may have switched to demand) │
│    • Filter employees by rank (if specified)                │
│    ⚠️  NEVER runs ICPMP - already has workPattern          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. TEMPLATE GENERATION                                      │
│    Decision: templateGenerationMode = ?                     │
│    • "cpsat" → generate_cpsat_template()                   │
│    • "incremental" → generate_incremental_template()        │
│    • "auto" → Try CP-SAT first, fallback to incremental    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. CP-SAT TEMPLATE GENERATION (if cpsat mode)              │
│    File: context/engine/cpsat_template_generator.py         │
│                                                             │
│    For each OU (organizational unit):                       │
│    a) Pick ONE template employee                            │
│    b) Build CP-SAT model with constraints:                 │
│       - C1: MOM daily hours (checks scheme limits HERE!)   │
│       - C2: Rotation pattern adherence                      │
│       - C3: Weekly rest days                                │
│       - C4: Consecutive work days                           │
│       - C5-C17: Other MOM constraints                       │
│    c) Solve for ONE feasible template                      │
│    d) Create assignments array:                             │
│       • ASSIGNED: When pattern + constraints OK            │
│       • UNASSIGNED: When pattern conflicts with constraint │
│       • OFF_DAY: When pattern says off day                  │
│    e) Replicate template to ALL employees in same OU       │
│                                                             │
│    ⚠️  KEY: Template is built for 1 employee, then         │
│        replicated. NO per-employee checking during solve.  │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. POST-SOLVE SCORING (for both templates types)           │
│    File: context/engine/solver_engine.py                    │
│    Function: calculate_scores(ctx, assignments)             │
│                                                             │
│    For each UNASSIGNED slot:                                │
│    • Try to explain WHY it's unassigned                     │
│    • Check what prevented assignment:                       │
│      - C11: Rank mismatch?                                  │
│      - C1: Scheme hours exceeded?                           │
│      - C9: Gender requirement?                              │
│      - Pattern conflicts?                                   │
│                                                             │
│    ⚠️  THIS IS WHERE MY FIX WAS (line 1168)               │
│        But this is EXPLANATION only, not enforcement!      │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. OUTPUT FORMATTING                                        │
│    • Calculate hours breakdown                              │
│    • Build final JSON output                                │
│    • Return result                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## PATH B: Demand-Based Mode

### File: `src/solver.py` - `solve_demand_based()`

**IMPORTANT**: This path is used for:
- Normal demandBased inputs with demandItems
- **outcomeBased inputs with single OU + individual employee offsets** (auto-switched)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. PREPROCESSING (done in solve_problem before this!)     │
│    • Load input JSON                                        │
│    • Build slots from demandItems                           │
│    • Run ICPMP if autoOptimize=true                        │
│    • Filter employees                                       │
│    • Rotation offsets already applied by offset_manager    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. SLOT BUILDING                                            │
│    File: context/engine/slot_builder.py                     │
│    • Create Slot objects from requirements                  │
│    • Each slot has: date, shift, rank requirements, etc.   │
│    • Generate decision variables: x[(slot_id, emp_id)]     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. BUILD CP-SAT MODEL                                       │
│    File: context/engine/solver_engine.py                    │
│    Function: build_model(ctx)                               │
│                                                             │
│    Load all constraint modules:                             │
│    • C1_mom_daily_hours.py                                  │
│    • C2_rotation_pattern_adherence.py                       │
│    • C3_weekly_rest_day.py                                  │
│    • ... (C4-C17 hard constraints)                          │
│    • S1-S16 (soft constraints)                              │
│                                                             │
│    For each constraint module:                              │
│    • Call apply(model, ctx, slots, assignments)            │
│    • Constraint adds OR-Tools constraints to model          │
│                                                             │
│    ⚠️  THIS IS WHERE CONSTRAINTS ARE ENFORCED              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. SOLVE CP-SAT MODEL                                       │
│    • OR-Tools finds optimal assignment                      │
│    • Result: x[(slot_id, emp_id)] = 0 or 1                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. POST-SOLVE SCORING (same as outcome-based!)            │
│    File: context/engine/solver_engine.py                    │
│    Function: calculate_scores(ctx, assignments)             │
│                                                             │
│    For soft constraints:                                    │
│    • Call score_violations(ctx, assignments, score_book)   │
│    • Calculate penalties for soft constraint violations    │
│                                                             │
│    For UNASSIGNED slots:                                    │
│    • Explain why (same logic as outcome-based)             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. OUTPUT FORMATTING (same as outcome-based)               │
└─────────────────────────────────────────────────────────────┘
```

---

## Rotation Offset Handling - Deep Dive

### The Problem We Solved
**Original Issue**: In outcomeBased mode with `fixedRotationOffset: "ouOffsets"`, the OU-level offset was overwriting individual employee rotation offsets, causing all employees to have identical schedules.

**Example**:
```json
{
  "fixedRotationOffset": "ouOffsets",
  "ouOffsets": [{"ouId": "ATSU T1 LSU A1", "rotationOffset": 0}],
  "employees": [
    {"employeeId": "001", "ouId": "ATSU T1 LSU A1", "rotationOffset": 3},
    {"employeeId": "002", "ouId": "ATSU T1 LSU A1", "rotationOffset": 2},
    {"employeeId": "003", "ouId": "ATSU T1 LSU A1", "rotationOffset": 7}
  ]
}
```
**Before Fix**: All 3 employees got offset 0 (from ouOffsets) → identical schedules
**After Fix**: Employees keep offsets 3, 2, 7 → unique staggered schedules

### The Solution (3-Part Fix)

#### 1. Smart Offset Preservation (`src/offset_manager.py` line 239-246)
```python
def apply_ou_offsets(input_data):
    # Check if employees have varied individual offsets
    employee_offsets = [emp.get('rotationOffset') for emp in employees]
    has_varied_offsets = len(set(employee_offsets)) > 1
    
    # If employees have varied offsets, PRESERVE them (don't override)
    if has_varied_offsets:
        return 0  # No updates - preserve existing offsets
    
    # Otherwise, apply OU-level offsets
    for emp in employees:
        emp['rotationOffset'] = ou_offset_map.get(emp['ouId'])
```

#### 2. Automatic Mode Switching (`src/solver.py` line 364-388)
```python
# Detect single OU with individual employee offsets
unique_ous = set(emp.get('ouId') for emp in employees)
employee_offsets = [emp.get('rotationOffset') for emp in employees]
has_individual_offsets = len(set(employee_offsets)) > 1
is_single_ou = len(unique_ous) == 1

if is_single_ou and has_individual_offsets and len(employees) <= 50:
    # Switch from outcomeBased to demandBased mode
    rostering_basis = 'demandBased'
    # This enables CP-SAT solver to generate unique schedules per employee
```

#### 3. Unified Code Path (removed duplication)
- **Before**: `api_server.py` called `ensure_staggered_offsets()` before `solve_problem()`
- **After**: Only `solver.py` calls `ensure_staggered_offsets()` (lines 248, 256, 271)
- **Result**: API and CLI use identical preprocessing logic

### When Rotation Offsets Are Applied

| Scenario | Offset Source | Logic |
|----------|---------------|-------|
| **ouOffsets + varied employee offsets** | Individual employee offsets | ✅ **PRESERVED** (offset_manager detects variation) |
| **ouOffsets + uniform employee offsets (all 0)** | OU-level offsets | Applied from ouOffsets array |
| **auto mode + no ICPMP** | Auto-staggered | Generated by ensure_staggered_offsets() |
| **auto mode + ICPMP assigned** | ICPMP-optimized | Preserved, no auto-staggering |
| **demandBased + patterns** | Employee offsets | Preserved or auto-staggered if all 0 |

### Critical Files Modified

1. **`src/offset_manager.py`** (commit 9b06326)
   - Lines 239-246: Detect varied offsets and preserve them
   - **Applies to ALL scenarios**, regardless of OU count

2. **`src/solver.py`** (commit 51133b3, d3f5a0d)
   - Lines 364-388: Single OU detection and mode switching
   - Lines 288-317: Offset preservation logic (now redundant with offset_manager fix)

3. **`src/api_server.py`** (commit 667592b)
   - Line 1054: **REMOVED** duplicate `ensure_staggered_offsets()` call
   - Now relies on solver.py for all preprocessing

---

## Key Differences Between Modes

| Aspect | Outcome-Based | Demand-Based |
|--------|---------------|--------------|
| **Input Structure** | `requirements` with `workPattern` | `demandItems` with `shifts` and `requirements` with `workPattern` |
| **WorkPattern Usage** | Used for template generation | Used for ICPMP optimization or employee preferences |
| **TemplateGenerationMode** | Can specify: "cpsat", "incremental", "auto", "off" | Field is IGNORED - always uses CP-SAT slot-based solver |
| **ICPMP** | NEVER runs - already has work patterns | Runs if autoOptimize=true and no pre-assigned patterns |
| **Constraint Enforcement** | During template generation (cpsat_template_generator.py) | During model building (constraint modules) |
| **Assignment Granularity** | Template per OU, replicated to all employees | Individual slot-to-employee assignment |
| **Employee Selection** | All employees in OU use same template | Solver assigns specific employees to specific slots |
| **UNASSIGNED Creation** | Created when pattern conflicts with constraints | Created when no feasible assignment exists |
| **Rotation Offsets** | ⚠️ **Auto-switches to demandBased if single OU + individual offsets** | Offsets applied per employee, enables unique schedules |

---

## Common Pitfalls & Solutions

### ❌ Problem: Individual Employee Offsets Not Working
**Symptom**: All employees get identical schedules despite having different `rotationOffset` values

**Root Cause**: OU-level offsets in `ouOffsets` array overriding individual employee offsets

**Solution**: ✅ **Fixed in commit 9b06326**
- `offset_manager.py` now detects varied employee offsets
- Preserves individual offsets instead of overriding with OU offset
- Works regardless of single vs multiple OUs

### ❌ Problem: Offset Values ≥ Pattern Length
**Symptom**: Pattern length is 7, but employees have offsets 7, 8, 9 → duplicate schedules

**Example**:
- Pattern: `['D','D','D','D','D','O','O']` (length 7)
- Offset 7: `(0 + 7) % 7 = 0` → Same as offset 0
- Offset 8: `(0 + 8) % 7 = 1` → Same as offset 1

**Current Behavior**: ✅ **Allowed as-is (no normalization)**
- Solver doesn't validate or normalize offsets
- User responsible for ensuring offsets are < pattern_length
- Future: Could add normalization `offset = offset % pattern_length`

### ❌ Problem: Local Works But Production Doesn't
**Root Cause**: Different preprocessing paths between API and CLI

**Solution**: ✅ **Fixed in commit 667592b**
- Removed duplicate `ensure_staggered_offsets()` call from `api_server.py`
- Both API and CLI now use identical code path through `solver.py`
- Rotation offset logic centralized in one place

---

## Where Scheme Checking Happens

### Outcome-Based Mode:
1. **During Template Generation** (context/engine/cpsat_template_generator.py):
   - Line 278: `normalize_scheme(employee.get('scheme'))` ✅ CORRECT
   - Checks if shift duration fits within scheme daily limits
   - If violated, creates UNASSIGNED assignment

2. **During Post-Solve Explanation** (context/engine/solver_engine.py):
   - Line 1168: `employee_schemes = {emp_id: normalize_scheme(...)}` ✅ MY FIX
   - Explains why UNASSIGNED slots couldn't be filled

### Demand-Based Mode:
1. **During Constraint Enforcement** (context/constraints/C1_mom_daily_hours.py):
   - Constraint module enforces scheme limits during solve
   - Need to check if normalize_scheme() is used HERE!

2. **During Post-Solve Explanation** (same as outcome-based)

---

## The Bug Location

Based on this workflow, the bug must be in **ONE OF THESE PLACES**:

1. ❌ **Post-solve scoring** (solver_engine.py line 1168) - ALREADY FIXED
2. ❓ **Demand-based constraint** (C1_mom_daily_hours.py) - Need to check
3. ❓ **Outcome-based template generation** (cpsat_template_generator.py line 278) - Claims to be correct
4. ❓ **Employee preprocessing** - Maybe employees are filtered out before reaching solver?

---

## Next Steps

1. Check C1_mom_daily_hours.py constraint module
2. Verify cpsat_template_generator.py actually normalizes correctly
3. Check if employee list is empty when reaching solver
4. Add debug logging to see where employees disappear

