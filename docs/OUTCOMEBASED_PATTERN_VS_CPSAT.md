# OutcomeBased Rostering - Pattern-Based vs CP-SAT

## Overview

OutcomeBased mode now supports TWO approaches:

### 1. Pattern-Based (DEFAULT) ⚡ FAST
- **No CP-SAT solving** - Pure deterministic pattern following
- **Speed**: ~0.01 seconds (vs 45-60s with CP-SAT)
- **Logic**: Each employee works according to their pattern + rotation offset
- **Constraints**: Validated (weekly caps, consecutive days, etc.) but not optimized
- **Output**: Natural coverage distribution based on rotation offsets

### 2. CP-SAT Optimization (OPTIONAL) 🎯 BALANCED
- **Full CP-SAT solving** - Optimizes workload distribution
- **Speed**: 45-60 seconds
- **Logic**: Creates slots and optimally assigns employees
- **Constraints**: Hard constraints enforced, soft constraints minimized
- **Output**: Balanced workload across employees

---

## Usage

### Pattern-Based (Default)

**Input JSON:**
```json
{
  "demandItems": [{
    "rosteringBasis": "outcomeBased",
    "minStaffThresholdPercentage": 60,
    "requirements": [{
      "workPattern": ["D", "D", "D", "D", "D", "O", "O"],
      "ouOffsets": [
        {"ouId": "ATSU T1 LSU A1", "rotationOffset": 0},
        {"ouId": "ATSU T1 LSU A2", "rotationOffset": 1},
        {"ouId": "ATSU T1 LSU A3", "rotationOffset": 2}
      ]
    }]
  }]
}
```

**Command:**
```bash
python src/run_solver.py --in input.json --time 60
```

**Output:**
```
[CLI] Using pattern-based roster generation (deterministic, no CP-SAT)
[CLI] ✓ Pattern roster generated in 0.01s
[CLI] Status: OPTIMAL
[CLI] Assignments: 2527
[CLI] Coverage: 78-133 employees/day
```

---

### CP-SAT Optimization (Optional)

**Input JSON** (add `optimizeWorkload` flag):
```json
{
  "solverConfig": {
    "optimizeWorkload": true  // ← Enable CP-SAT optimization
  },
  "demandItems": [{
    "rosteringBasis": "outcomeBased",
    "minStaffThresholdPercentage": 60,
    ...
  }]
}
```

**Command:**
```bash
python src/run_solver.py --in input_optimized.json --time 300
```

**Output:**
```
[CLI] Using CP-SAT optimization (optimizeWorkload=true)
[CLI] Starting CP-SAT solver...
[CLI] ✓ CP-SAT completed in 47.23s
[CLI] Status: OPTIMAL
[CLI] Assignments: 2480
```

---

## Comparison

| Feature | Pattern-Based | CP-SAT Optimization |
|---------|---------------|---------------------|
| **Speed** | 0.01s ⚡ | 45-60s |
| **Method** | Deterministic | Constraint optimization |
| **Workload Balance** | Natural | Optimized |
| **Coverage** | Variable by day | Attempts to fill all slots |
| **Constraints** | Validated | Enforced + optimized |
| **Use Case** | Fast roster generation | Balanced workload needed |

---

## How Pattern-Based Works

### Step 1: Employee Selection (Threshold-Based)
```
223 employees × 60% threshold = 134 employees selected

Per-OU distribution:
  OU A1: 73 × 60% = 44 employees
  OU A2: 74 × 60% = 44 employees
  OU A3: 76 × 60% = 46 employees
```

### Step 2: Deterministic Assignment Generation
```python
For each selected employee:
    pattern = ['D', 'D', 'D', 'D', 'D', 'O', 'O']
    offset = employee.rotationOffset
    
    For each date in planning horizon:
        pattern_day = (date_index + offset) % 7
        
        if pattern[pattern_day] == 'D':
            # Check constraints (non-blocking)
            if can_work(employee, date):
                Create assignment
            else:
                Skip (log reason)
```

### Step 3: Constraint Validation
```
Constraints checked (but not optimized):
✓ C2: Weekly 44h cap
✓ C3: Max consecutive days (8 for APGD, 12 for others)
✓ C17: Monthly OT cap (72h)

If constraint would be violated:
  - Assignment skipped
  - Logged to constraint_violations summary
  - Continue to next day/employee
```

### Step 4: Coverage Analysis (Output)
```
Coverage emerges naturally from patterns:
  Monday: 95 employees (all 3 OUs available)
  Tuesday: 82 employees (2 OUs available)
  Wednesday: 133 employees (all working)
  Sunday: 46 employees (1 OU available)
```

---

## Performance Comparison

### Test Case: 223 employees, 31 days, 5-day pattern

**Pattern-Based:**
```
Time: 0.01s
Assignments: 2,527
Employees used: 133/134 selected
Coverage: 78-133 employees/day
Constraint violations: 532 skipped (logged)
```

**CP-SAT Optimization:**
```
Time: 47.23s
Assignments: 2,337
Employees used: 112
Coverage: 73-112 employees/day (attempted to fill 2,480 slots)
Constraint violations: 143 unassigned slots
```

---

## When to Use Each Approach

### Use Pattern-Based When:
- ✅ Speed is critical (<1 second response needed)
- ✅ Natural coverage distribution acceptable
- ✅ Deterministic output preferred
- ✅ Large employee pools (200+)
- ✅ Simple reporting needs

### Use CP-SAT Optimization When:
- 🎯 Workload must be balanced across employees
- 🎯 Need to maximize slot filling
- 🎯 Complex constraints require optimization
- 🎯 Have 5+ minutes for solving
- 🎯 Small employee pools (<50)

---

## Example Outputs

### Pattern-Based Output Structure
```json
{
  "status": "OPTIMAL",
  "assignments": [
    {
      "employeeId": "00054313",
      "date": "2026-01-21",
      "startDateTime": "2026-01-21T08:00:00",
      "endDateTime": "2026-01-21T20:00:00",
      "grossHours": 12.0,
      "normalHours": 8.8,
      "overtimeHours": 2.2,
      "isUnassigned": false
    }
  ],
  "metadata": {
    "method": "pattern_based",
    "optimization": false,
    "pattern_stats": {
      "total_assignments": 2527,
      "employees_used": 133,
      "coverage_min": 78,
      "coverage_max": 133,
      "coverage_avg": 81.5,
      "constraint_violations": {
        "C2_weekly_44h_cap": 444,
        "C17_monthly_216h_cap": 88
      }
    }
  }
}
```

---

## Constraint Violation Handling

### Pattern-Based Approach
When an assignment would violate a constraint:
1. Assignment is **skipped** (not created)
2. Reason is **logged** to `constraint_violations` summary
3. Solver **continues** to next opportunity
4. Final output includes violation counts in metadata

**Example Log:**
```
[PatternRoster] Constraint violations summary:
  - C2_weekly_44h_cap: 444 skipped assignments
  - C17_monthly_216h_cap: 88 skipped assignments
```

This is **NOT an error** - it's the natural outcome of respecting constraints without optimization.

### CP-SAT Approach
When an assignment would violate a constraint:
1. CP-SAT **tries alternative** assignments
2. Uses **backtracking** to find valid solution
3. May leave slots **unassigned** if no valid solution exists
4. Returns "INFEASIBLE" if constraints are impossible

---

## Migration Guide

### From Slot-Based to Pattern-Based

**Old Input (Slot-Based):**
```json
{
  "demandItems": [{
    "rosteringBasis": "outcomeBased",
    "shifts": [{
      "headcount": 80  // ← Creates 80 slots per day
    }]
  }]
}
```

**New Input (Pattern-Based):**
```json
{
  "demandItems": [{
    "rosteringBasis": "outcomeBased",
    "minStaffThresholdPercentage": 60,  // ← Select 60% of employees
    // headcount is IGNORED in pattern-based mode
    "requirements": [{
      "workPattern": ["D","D","D","D","D","O","O"]  // ← Pattern drives assignments
    }]
  }]
}
```

**Key Changes:**
- ❌ `headcount` is ignored (coverage emerges from patterns)
- ✅ `minStaffThresholdPercentage` selects employees
- ✅ `workPattern` + `rotationOffset` drive assignments
- ✅ Coverage is OUTPUT, not INPUT

---

## Troubleshooting

### Issue: Too Many Constraint Violations
```
constraint_violations: {
  "C2_weekly_44h_cap": 1000+ skipped
}
```

**Solutions:**
1. Reduce `minStaffThresholdPercentage` (use fewer employees)
2. Check work pattern has enough rest days (O)
3. Enable CP-SAT optimization: `"optimizeWorkload": true`

### Issue: Low Coverage on Certain Days
```
Coverage: 30-120 employees/day (large variance)
```

**Solutions:**
1. Adjust rotation offsets for better distribution
2. Use consecutive offsets (0,1,2) instead of spaced (0,2,4)
3. Add more OUs with different offsets

### Issue: Need Exact Coverage Numbers
**Problem**: Pattern-based generates natural coverage, not target numbers

**Solution**: Use CP-SAT optimization with explicit slot counts:
```json
{
  "solverConfig": {"optimizeWorkload": true},
  "demandItems": [{
    "shifts": [{"headcount": 80}]  // ← CP-SAT will try to fill 80/day
  }]
}
```

---

## Best Practices

### 1. Start with Pattern-Based
- Test quickly (~0.01s)
- Understand natural coverage distribution
- Validate constraint violations are acceptable

### 2. Switch to CP-SAT if Needed
- Add `"optimizeWorkload": true` flag
- Increase timeout to 300+ seconds
- Compare results with pattern-based

### 3. Rotation Offset Design
- Consecutive offsets (0,1,2,...) provide even coverage
- Spaced offsets (0,2,4,...) increase variation but create bottlenecks
- More OUs = smoother coverage curve

### 4. Threshold Selection
- Start with 50-60% for exploration
- Increase if too many constraint violations
- Decrease if coverage is too high

---

## Technical Implementation

Pattern-based roster is implemented in:
- **Module**: `context/engine/pattern_roster.py`
- **Integration**: `src/solver.py` (Phase 3: Roster Generation)
- **Decision**: Based on `optimizeWorkload` flag

**Code Flow:**
```
solver.py::solve_problem()
  ↓
  if outcomeBased and not optimizeWorkload:
    pattern_roster.generate_pattern_based_roster()
      ↓
      1. Select employees (threshold)
      2. For each employee × date:
         - Check pattern[date % pattern_length]
         - Validate constraints
         - Create assignment or skip
      3. Return assignments + stats
  else:
    solver_engine.solve()  # Traditional CP-SAT
```

