# DemandBased Rostering Workflow - Complete Trace

## Overview
demandBased rostering uses **CP-SAT constraint programming** to find optimal assignments matching demand requirements with available employees.

---

## Step-by-Step Flow

### 1. INPUT LOADING (`src/redis_worker.py` or `src/run_solver.py`)
```
Input JSON (RST-20251220-46FCA2BA_Solver_Input.json)
  ├─ rosteringBasis: "demandBased"
  ├─ demandItems[] 
  │   └─ requirements[]
  │       ├─ workPattern: ['D', 'D', 'N', 'N', 'O', 'O']
  │       ├─ productTypeId: "25"
  │       └─ slotCount: 10 per day
  └─ employees[] (86 employees)
      ├─ employeeId
      ├─ rotationOffset: 0-5
      └─ productTypeId: "25"
```

**Key Point**: Employees DON'T have workPattern - they inherit it from matching requirement based on productTypeId.

---

### 2. ICPMP PREPROCESSING (`context/engine/config_optimizer_v3.py`)
```
Filter employees by:
  - Match productTypeId between employee and requirement
  - Apply per-requirement auto-optimization (if enabled)
  - Result: 86 → 23 employees selected
```

**Output**: Filtered employee list with rotationOffsets assigned.

---

### 3. DATA LOADING (`context/engine/data_loader.py`)
```python
def load_input(input_data):
    # Build ctx dictionary
    ctx = {
        'employees': [...],          # 23 employees after ICPMP
        'demandItems': [...],         # Demand requirements
        'slots': [],                  # Will be generated next
        'x': {},                      # Decision variables (later)
        'model': CpModel(),           # OR-Tools model
        'constraintList': [...],      # Constraint configs
        'planningReference': {...}    # Metadata
    }
```

---

### 4. SLOT GENERATION (`context/engine/slot_builder.py`)
```python
def build_slots(ctx):
    # For each demand requirement, create slots for each day
    # Slot = one shift opening (D or N) at specific time
    
    for demand in demandItems:
        for req in demand.requirements:
            work_pattern = req['workPattern']  # ['D', 'D', 'N', 'N', 'O', 'O']
            
            for date in date_range:
                # Calculate pattern position for this date
                pattern_day = (date - start_date + 0) % len(work_pattern)
                expected_shift = work_pattern[pattern_day]
                
                if expected_shift != 'O':  # Skip OFF days
                    # Create slot for D or N shift
                    slot = Slot(
                        slot_id=f"SLOT-{date}-{shift_code}-{i}",
                        demand_id=demand_id,
                        date=date,
                        shift_code=expected_shift,
                        start_time="08:00" or "20:00",
                        end_time="20:00" or "08:00",
                        pattern_day=pattern_day
                    )
                    ctx['slots'].append(slot)
```

**CRITICAL**: Slots are only created for 'D' and 'N' days in the pattern. 'O' days have NO slots.

**Result**: ~300 slots created (10 per work day × 30 days × 1 requirement)

---

### 5. CP-SAT MODEL BUILDING (`context/engine/solver_engine.py`)
```python
def build_model(ctx):
    model = CpModel()
    slots = ctx['slots']
    employees = ctx['employees']
    
    # CREATE DECISION VARIABLES
    x = {}  # x[(slot_id, emp_id)] = BoolVar
    for slot in slots:
        for emp in employees:
            x[(slot.slot_id, emp.id)] = model.NewBoolVar(f"x_{slot}_{emp}")
    
    ctx['x'] = x
    ctx['model'] = model
```

**Key**: Decision variables only exist for ACTUAL SLOTS (work shifts D, N).
**NO variables for OFF days** - they don't exist in the problem!

---

### 6. CONSTRAINT APPLICATION (`context/constraints/*.py`)
```python
# Hard constraints applied:
C1_mom_daily_hours.apply(model, ctx, slots, x)      # Max 12h/day
C2_mom_weekly_hours.apply(model, ctx, slots, x)     # Max 44h/week normal
C3_mom_monthly_ot.apply(model, ctx, slots, x)       # Max 72h/month OT
C4_one_shift_per_day.apply(model, ctx, slots, x)    # Max 1 shift/day
C5_rest_between_shifts.apply(model, ctx, slots, x)  # 11h rest
C6_weekly_rest.apply(model, ctx, slots, x)          # 24h/week rest
# ... more constraints

# Each constraint adds clauses like:
model.Add(sum(x[(slot, emp)] * hours for slot in day_slots) <= 12)
```

**IMPORTANT**: Constraints operate on SLOTS (work shifts). OFF days are implicit - they're days without assignments.

---

### 7. CP-SAT SOLVING
```python
solver = cp_model.CpSolver()
solver.parameters.num_search_workers = 4
solver.parameters.max_time_in_seconds = 300
status = solver.Solve(model)

# Extract solution
for (slot_id, emp_id), var in x.items():
    if solver.Value(var) == 1:
        # Employee emp_id is assigned to slot_id
        assignments.append({
            'slotId': slot_id,
            'employeeId': emp_id,
            'shiftCode': slot.shift_code,  # 'D' or 'N'
            'date': slot.date
        })
```

**Result**: 300 assignments (work shifts D, N) extracted from solver solution.
**Note**: OFF days are NOT in assignments - they were never variables!

---

### 8. OUTPUT BUILDING (`src/output_builder.py`)

#### Step 8A: Insert OFF Day Assignments
```python
def insert_off_day_assignments(assignments, input_data, ctx):
    """Generate OFF_DAY records for pattern OFF days"""
    
    for emp in employees:
        emp_pattern = calculate_employee_work_pattern(base_pattern, emp_offset)
        # emp_pattern = ['D', 'D', 'N', 'N', 'O', 'O'] rotated by offset
        
        for date in date_range:
            pattern_day = calculate_pattern_day(date, pattern_start, emp_offset, len(pattern))
            expected_shift = emp_pattern[pattern_day]
            
            if expected_shift == 'O':
                # Pattern says OFF day - create OFF_DAY assignment
                off_assignment = {
                    'employeeId': emp_id,
                    'date': date,
                    'shiftCode': 'O',
                    'status': 'OFF_DAY',
                    'startDateTime': '08:00-20:00',  # Default times
                    'hours': {all zeros}
                }
                off_day_assignments.append(off_assignment)
    
    # Return work assignments + OFF day assignments
    return assignments + off_day_assignments
```

**ISSUE IDENTIFIED**: This function generates OFF_DAY assignments based on pattern.

**BUT**: Recent code change (commit bf10221) **removes OFF_DAY from final assignments array**!

#### Step 8B: Build Employee Roster
```python
def build_employee_roster(input_data, ctx, assignments, off_day_assignments):
    """Build employeeRoster with dailyStatus for each employee"""
    
    # Merge assignments for internal use
    all_assignments_for_roster = assignments + off_day_assignments
    
    for emp in employees:
        emp_pattern = calculate_employee_work_pattern(base_pattern, emp_offset)
        
        for date in date_range:
            assignment = find_assignment(emp, date)
            pattern_day = calculate_pattern_day(date, ...)
            expected_shift = emp_pattern[pattern_day]
            
            # CURRENT LOGIC (commit 94efa2a):
            if expected_shift == 'O' and not (assignment with D/N shift):
                dailyStatus = 'OFF_DAY'  # Pattern says OFF, no work
            elif assignment with D/N:
                dailyStatus = 'ASSIGNED'  # Working
            else:
                dailyStatus = 'UNASSIGNED'  # Pattern says work, but not assigned
```

#### Step 8C: Final Output
```json
{
  "assignments": [
    // ONLY work shifts (D, N) - 300 entries
    // NO OFF_DAY entries here!
  ],
  "employeeRoster": [
    {
      "employeeId": "00011502",
      "workPattern": ['D', 'D', 'N', 'N', 'O', 'O'],
      "rotationOffset": 0,
      "dailyStatus": [
        {"date": "2026-04-01", "status": "ASSIGNED", "shiftCode": "N"},
        {"date": "2026-04-02", "status": "ASSIGNED", "shiftCode": "N"},
        {"date": "2026-04-03", "status": "UNASSIGNED"},  // ← PROBLEM!
        {"date": "2026-04-04", "status": "UNASSIGNED"},  // ← PROBLEM!
        {"date": "2026-04-05", "status": "ASSIGNED", "shiftCode": "D"},
        {"date": "2026-04-06", "status": "ASSIGNED", "shiftCode": "D"}
      ]
    }
  ]
}
```

---

## THE PROBLEM

### Root Cause Analysis:

1. **Solver assigns employees to slots** → 300 work assignments
2. **insert_off_day_assignments()** generates OFF_DAY records based on pattern
3. **BUT**: We're now filtering OUT OFF_DAY from assignments array (commit bf10221)
4. **build_employee_roster()** checks if OFF_DAY assignments exist
5. **If employee has NO OFF_DAY assignment for a date**, it checks pattern
6. **Pattern calculation is WRONG** for some employees!

### Why Employee 00011502 Shows UNASSIGNED:

```
Employee 00011502:
  Pattern: ['D', 'D', 'N', 'N', 'O', 'O']
  Offset: 0

Apr 1 (day 0): Pattern position 0 → 'D', but solver assigned 'N' → Shows ASSIGNED ✅
Apr 2 (day 1): Pattern position 1 → 'D', but solver assigned 'N' → Shows ASSIGNED ✅
Apr 3 (day 2): Pattern position 2 → 'N', no assignment → Shows UNASSIGNED ❌
Apr 4 (day 3): Pattern position 3 → 'N', no assignment → Shows UNASSIGNED ❌
Apr 5 (day 4): Pattern position 4 → 'O', solver assigned 'D' → Shows ASSIGNED ✅
Apr 6 (day 5): Pattern position 5 → 'O', solver assigned 'D' → Shows ASSIGNED ✅
```

**The solver is NOT respecting the work pattern!**

### Why is the solver ignoring patterns?

**ANSWER**: There's NO CONSTRAINT enforcing pattern adherence!

Let me check if continuous adherence constraint exists and is enabled...

---

## Expected Behavior (Historical)

Before recent changes, DDNNOO pattern rosters worked because:
1. CP-SAT solver had constraints enforcing pattern cycles
2. OFF days were automatically generated and included in output
3. employeeRoster.dailyStatus correctly showed OFF_DAY for pattern 'O' days

## Current Behavior (Broken)

Now:
1. ❌ Solver assigns employees without respecting patterns
2. ❌ OFF_DAY assignments generated but removed from output
3. ❌ employeeRoster.dailyStatus shows UNASSIGNED where pattern says work but no assignment

---

## Next Steps to Fix

1. **Check constraint files** for pattern adherence enforcement
2. **Verify continuous adherence constraint** is enabled and working
3. **Fix insert_off_day_assignments()** to generate OFF days correctly
4. **Update build_employee_roster()** to use pattern-first logic consistently
