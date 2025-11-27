# Incremental Solver Implementation Guide (v0.80)

## Overview

The Incremental Solver handles mid-month scheduling scenarios where the roster needs adjustment without disturbing already-committed assignments.

## Implementation Status

### ✅ Completed (Phase 1)

1. **Pydantic Models** (`src/models.py`)
   - `IncrementalSolveRequest`: Main request model
   - `TemporalWindow`: Cutoff and solve date ranges
   - `EmployeeChanges`: New joiners, departures, long leave
   - `AssignmentAuditInfo`: Audit trail for assignments
   - `NewJoiner`, `NotAvailableEmployee`, `LongLeave`: Supporting models

2. **Core Module** (`src/incremental_solver.py`)
   - `validate_temporal_window()`: Validates cutoff < solveFrom <= solveTo
   - `classify_slots()`: Partitions assignments into LOCKED vs SOLVABLE
   - `build_employee_pool()`: Merges previous + new - departed employees
   - `calculate_locked_weekly_hours()`: Tracks hours worked before cutoff
   - `calculate_locked_consecutive_days()`: Counts consecutive days leading to cutoff
   - `solve_incremental()`: Main orchestrator

3. **API Endpoint** (`src/api_server.py`)
   - `POST /solve/incremental`: RESTful endpoint with full docs
   - Error handling for temporal validation
   - Request/response logging

4. **JSON Schema** (`context/schemas/incremental_input_schema_v0.80.json`)
   - Complete validation schema for incremental requests
   - Compliant with JSON Schema draft-07

### ⚠️ Pending (Phase 2) - Constraint Integration

The following components require modification to support incremental mode:

#### 1. Solver Engine (`context/engine/solver_engine.py`)

**Current State:** Regular solve() function doesn't handle incremental context

**Required Changes:**
```python
def solve(input_data, time_limit_sec=15):
    """
    Enhanced to support both regular and incremental modes.
    """
    # Detect incremental mode
    incremental_ctx = input_data.get('_incremental')
    
    if incremental_ctx:
        # Extract incremental-specific context
        locked_assignments = incremental_ctx['lockedAssignments']
        solvable_slots = incremental_ctx['solvableSlots']
        locked_weekly_hours = incremental_ctx['lockedWeeklyHours']
        locked_consecutive_days = incremental_ctx['lockedConsecutiveDays']
        temporal_window = incremental_ctx['temporalWindow']
        
        # Build slots ONLY from solvable_slots (not full demands)
        slots = build_slots_from_solvable(solvable_slots)
        
        # Build decision variables only for solvable slots
        x = {}
        for emp in employees:
            for slot in slots:
                # Check employee availability constraints
                if not is_employee_available(emp, slot, temporal_window, incremental_ctx):
                    continue
                x[(emp['employeeId'], slot.slot_id)] = model.NewBoolVar(...)
        
        # Add pre-assignment constraints for locked assignments
        for locked in locked_assignments:
            emp_id = locked.get('employeeId')
            # These are NOT in the model, but we track them for constraint context
            
        # Pass incremental context to constraint builders
        ctx['_incremental'] = incremental_ctx
        ctx['_mode'] = 'incremental'
    else:
        # Regular mode - existing logic
        ...
```

#### 2. Constraint Modules

Each constraint module needs enhancement to handle locked context:

**C2: Weekly/Monthly Hours** (`context/constraints/C2_mom_weekly_hours.py`)

```python
def add_constraints(model, ctx):
    """
    Weekly <= 44h (normal), Monthly OT <= 72h
    
    INCREMENTAL MODE ENHANCEMENT:
    - Read locked_weekly_hours from ctx['_incremental']['lockedWeeklyHours']
    - For each employee-week constraint:
        locked_hours = ctx['_incremental']['lockedWeeklyHours'].get(emp_id, {}).get(week_key, 0.0)
        remaining_capacity = 44.0 - locked_hours
        model.Add(sum(new_assignment_hours) <= remaining_capacity)
    """
    
    incremental_ctx = ctx.get('_incremental')
    
    if incremental_ctx:
        locked_weekly_hours = incremental_ctx.get('lockedWeeklyHours', {})
        
        for emp_id in employees:
            for week_key in weeks:
                locked_hours = locked_weekly_hours.get(emp_id, {}).get(week_key, 0.0)
                remaining = 44.0 - locked_hours
                
                # Add constraint with adjusted capacity
                model.Add(sum(normal_hours_vars) <= remaining)
    else:
        # Regular mode - existing logic
        model.Add(sum(normal_hours_vars) <= 44.0)
```

**C3: Max Consecutive Days** (`context/constraints/C3_max_consecutive_days.py`)

```python
def add_constraints(model, ctx):
    """
    Max 12 consecutive working days
    
    INCREMENTAL MODE ENHANCEMENT:
    - Read locked_consecutive_days from ctx['_incremental']['lockedConsecutiveDays']
    - For each employee:
        locked_streak = ctx['_incremental']['lockedConsecutiveDays'].get(emp_id, 0)
        remaining_allowed = 12 - locked_streak
        
        # Apply constraint starting from solveFromDate
        # Employee already worked 'locked_streak' days before cutoff
        # Can only work 'remaining_allowed' more consecutive days
    """
    
    incremental_ctx = ctx.get('_incremental')
    
    if incremental_ctx:
        locked_consecutive = incremental_ctx.get('lockedConsecutiveDays', {})
        solve_from_date = parse_date(incremental_ctx['temporalWindow']['solveFromDate'])
        
        for emp_id in employees:
            locked_streak = locked_consecutive.get(emp_id, 0)
            remaining = 12 - locked_streak
            
            # Build rolling window constraints starting from solve_from_date
            # accounting for locked_streak
            ...
```

**C4: Minimum Rest Between Shifts**

```python
def add_constraints(model, ctx):
    """
    Min 480 minutes (8h) rest between shifts
    
    INCREMENTAL MODE ENHANCEMENT:
    - Get last shift end time before cutoff from locked assignments
    - For first assignment >= solveFromDate:
        last_locked_end = get_last_shift_end_before_cutoff(emp_id, locked_assignments)
        first_new_start = assignment.startDateTime
        
        # Ensure rest period respected
        model.Add((first_new_start - last_locked_end) >= 480 minutes)
    """
```

**Other Constraints (C1, C5-C17)**

Most other constraints work without modification because:
- They're slot-level or date-specific (not cumulative across time)
- They only consider variables in the model (solvable slots)
- Example: Gender balance, rank matching, license validity, etc.

#### 3. Slot Builder (`context/engine/slot_builder.py`)

**Current State:** Builds slots from demands for entire planning horizon

**Required Changes:**
```python
def build_slots_from_solvable(solvable_slots_data):
    """
    Build slot objects only from pre-classified solvable slots.
    
    In incremental mode, we don't expand demands again.
    We use the solvable_slots from classify_slots().
    """
    slots = []
    for slot_data in solvable_slots_data:
        slot = Slot(
            slot_id=slot_data['slotId'],
            date=parse_date(slot_data['date']),
            demand_id=slot_data['demandId'],
            shift_code=slot_data['shiftCode'],
            ...
        )
        slots.append(slot)
    return slots
```

#### 4. Output Builder (`src/output_builder.py`)

**Current State:** Builds output from solver solution

**Required Changes:**
```python
def build_incremental_output(
    locked_assignments,
    new_assignments,
    incremental_ctx,
    solver_metadata
):
    """
    Merge locked + new assignments with audit trail.
    
    Returns:
        {
            "assignments": [
                {
                    ...assignment_data...,
                    "auditInfo": {
                        "solverRunId": "...",
                        "source": "locked" | "incremental",
                        "timestamp": "...",
                        "inputHash": "...",
                        "previousJobId": "..."
                    }
                },
                ...
            ],
            "incrementalSolve": {
                "cutoffDate": "...",
                "solveFromDate": "...",
                "solveToDate": "...",
                "lockedAssignmentsCount": 100,
                "newAssignmentsCount": 50,
                "solvableSlots": 55,
                "unassignedSlots": 5
            }
        }
    """
```

### 🔄 Integration Steps (Phase 2)

1. **Modify `solver_engine.py`**
   - Add incremental mode detection
   - Pass `_incremental` context to constraints
   - Build slots from solvable_slots instead of expanding demands

2. **Enhance Constraint Modules**
   - C2: Weekly/monthly hours with locked hours
   - C3: Consecutive days with locked streak
   - C4: Rest periods with last locked shift
   - Test each constraint individually

3. **Update Slot Builder**
   - Add `build_slots_from_solvable()` function
   - Skip demand expansion in incremental mode

4. **Enhance Output Builder**
   - Merge locked + new assignments
   - Add audit trail to each assignment
   - Include `incrementalSolve` metadata

5. **End-to-End Testing**
   - Test Case 1: New joiner mid-month
   - Test Case 2: Employee departure
   - Test Case 3: Long leave
   - Test Case 4: Combined scenario

### 📋 Testing Plan

Create test files in `input/incremental/`:

**Test 1: New Joiner**
```json
{
  "schemaVersion": "0.80",
  "temporalWindow": {
    "cutoffDate": "2025-12-15",
    "solveFromDate": "2025-12-16",
    "solveToDate": "2025-12-31"
  },
  "employeeChanges": {
    "newJoiners": [{
      "employee": {...},
      "availableFrom": "2025-12-16"
    }]
  },
  "previousOutput": { /* from output_2611_1800.json */ }
}
```

**Test 2: Employee Departure**
```json
{
  "employeeChanges": {
    "notAvailableFrom": [{
      "employeeId": "EMP123",
      "notAvailableFrom": "2025-12-15"
    }]
  }
}
```

**Test 3: Long Leave**
```json
{
  "employeeChanges": {
    "longLeave": [{
      "employeeId": "EMP456",
      "leaveFrom": "2025-12-20",
      "leaveTo": "2025-12-25"
    }]
  }
}
```

### 📊 Expected Behavior

**Input:** Previous output with 155 assigned slots (Dec 1-31)
**Scenario:** Employee EMP001 departs on Dec 15, new employee NEW001 joins Dec 16
**Temporal Window:** Cutoff=Dec 15, Solve=Dec 16-31

**Processing:**
1. Classify: 75 slots locked (Dec 1-15), 80 solvable (Dec 16-31)
2. Freed slots: 16 slots from EMP001 (Dec 16-31)
3. Employee pool: 21 previous (minus EMP001) + 1 new (NEW001) = 22 total
4. Solve: Assign 16 freed slots + any previously unassigned
5. Output: 155 total (75 locked + 80 new)

**Validation:**
- EMP001 has no assignments >= Dec 16 ✓
- NEW001 only assigned >= Dec 16 ✓
- All locked assignments unchanged ✓
- Weekly hours respect locked hours ✓
- Audit trail present on all assignments ✓

### 🚀 Next Steps

1. **Complete Phase 2 Integration** (constraint modifications)
2. **Create Test Scenarios** (3-4 test files)
3. **Run End-to-End Tests** (verify output)
4. **Update Documentation** (README, Postman)
5. **Commit & Deploy** (Git push to main)

### 📝 API Usage Example

```bash
curl -X POST http://localhost:8000/solve/incremental \
  -H "Content-Type: application/json" \
  -d @input/incremental/test_new_joiner.json
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "assignments": [...],
    "score": {...},
    "incrementalSolve": {
      "status": "completed",
      "lockedAssignments": 75,
      "newAssignments": 80,
      "solvableSlots": 80,
      "unassignedSlots": 0
    }
  },
  "meta": {
    "requestId": "...",
    "runId": "incr-...",
    "timestamp": "2025-11-27T...",
    "schemaVersion": "0.80"
  }
}
```

### ⚠️ Known Limitations

1. **Employee Data Recovery**: `previousOutput` should ideally include full input data for employee reconstruction. Currently assumes employee IDs can be derived from assignments.

2. **Constraint Context Propagation**: All constraint modules must be updated to check for `_incremental` context.

3. **Rotation Re-baseline**: Currently allows fresh rotation patterns from solveFromDate. May need option to continue existing patterns.

4. **Performance**: Incremental solving still builds full CP-SAT model. Future optimization: only model solvable slots.

### 🎯 Success Criteria

- [x] Models defined (v0.80)
- [x] Core module implemented
- [x] API endpoint added
- [x] JSON schema created
- [ ] Solver engine enhanced
- [ ] Constraints updated
- [ ] Tests passing
- [ ] Documentation complete

---

**Version:** 0.80  
**Date:** 2025-11-27  
**Status:** Phase 1 Complete, Phase 2 Pending
