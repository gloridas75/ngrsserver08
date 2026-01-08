# NGRS Solver - Rostering Modes Workflow Analysis

## Entry Points

### API Entry (`src/api_server.py`)
1. POST `/solve` (sync) or `/solve/async` (async)
2. Calls `solve_problem(input_data)` from `src/unified_solver.py`

### CLI Entry (`src/run_solver.py`)
1. `python src/run_solver.py --in input.json`
2. Also calls `solve_problem(input_data)` from `src/unified_solver.py`

---

## Main Workflow: `src/unified_solver.py` - `solve_problem()`

This is the **SINGLE ENTRY POINT** for both modes. Let me trace through this function:

```python
def solve_problem(input_data, max_time_seconds=300, ...):
    # Step 1: Determine rostering mode
    rostering_mode = determine_rostering_mode(input_data)
    # Returns: "outcomeBased" or "demandBased"
    
    # Step 2: Mode-specific preprocessing
    if rostering_mode == "outcomeBased":
        # Path A: Outcome-Based Mode
        return solve_outcome_based(input_data, ...)
    else:
        # Path B: Demand-Based Mode
        return solve_demand_based(input_data, ...)
```

---

## PATH A: Outcome-Based Mode

### File: `src/unified_solver.py` - `solve_outcome_based()`

```
┌─────────────────────────────────────────────────────────────┐
│ 1. PREPROCESSING                                            │
│    • Load input JSON                                        │
│    • Check templateGenerationMode (cpsat/incremental/auto)  │
│    • Apply rotation offsets                                 │
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

### File: `src/unified_solver.py` - `solve_demand_based()`

```
┌─────────────────────────────────────────────────────────────┐
│ 1. PREPROCESSING                                            │
│    • Load input JSON                                        │
│    • Build slots from demandItems                           │
│    • Run ICPMP if autoOptimize=true                        │
│    • Filter employees                                       │
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

