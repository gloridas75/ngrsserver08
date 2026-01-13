# Scheme P Demand-Based Rostering Analysis
**Input**: RST-20260113-AECA74BF_Solver_Input.json  
**Output**: RST-20260113-AECA74BF_Solver_Output.json  
**Date**: 2026-01-13  
**Status**: INFEASIBLE (124 hard constraint violations)

---

## Executive Summary

The solver is configured with 6 Scheme P employees and 3 shift requirements (N, D, E patterns). While **all shift types ARE being created**, only N shifts can be assigned—D and E shifts remain UNASSIGNED due to **conflicting hard constraints**. The root cause is that **Scheme P weekly hour limits are NOT being properly enforced**, leading to infeasibility.

---

## Issues Identified

### ✅ Issue 1: "Not all 3 shifts (N, D, E) had slots created"
**Status**: **NOT AN ISSUE** - All 3 shift types ARE being created

**Evidence**:
```
Assignments by shift type:
  - N (ASSIGNED):    62 slots ✅
  - D (UNASSIGNED):  62 slots ❌
  - E (UNASSIGNED):  62 slots ❌
  - O (OFF_DAY):     120 slots ✅
  - UNASSIGNED:      22 slots
```

All shift types are created correctly based on the 3 requirements:
- **Requirement 270_1**: N-N-N-N-O-O pattern (headcount 2) → 62 N slots
- **Requirement 270_2**: D-D-D-D-O-O pattern (headcount 2) → 62 D slots  
- **Requirement 270_3**: E-E-E-E-O-O pattern (headcount 2) → 62 E slots

The problem is **assignment**, not **slot creation**.

---

### ❌ Issue 2: D and E shifts cannot be assigned (INFEASIBLE)
**Status**: **CRITICAL BUG**

**Symptoms**:
- Status: `INFEASIBLE`
- All 62 D slots: `UNASSIGNED`
- All 62 E slots: `UNASSIGNED`
- Only N shifts assigned successfully
- Reason: "No employee could be assigned without violating hard constraints"

**Root Cause Analysis**:

The solver is applying **CONFLICTING hard constraints**:

1. **C2_mom_weekly_hours.py** - Enforces 44h weekly normal hours cap for ALL employees
2. **C6_parttimer_limits.py** - Should enforce 34.98h or 29.98h for Scheme P employees

**The Problem**:

Scheme P employees are subject to **BOTH** constraints:
- C2 says: "You can work up to 44h normal hours per week"
- C6 says: "You can only work 34.98h or 29.98h normal hours per week"

Since C6's limit (34.98h) is MORE RESTRICTIVE than C2's limit (44h), the solver should respect C6. However, **C2 is treating Scheme P the same as Scheme A/B**.

---

### ❌ Issue 3: Scheme P weekly hour limits not properly enforced
**Status**: **CRITICAL BUG**

**Expected Behavior** (from input JSON):
```json
{
  "id": "partTimerWeeklyHours",
  "enforcement": "hard",
  "params": {
    "maxHours4Days": 34.98,
    "maxHoursMoreDays": 29.98
  },
  "applicableToSchemes": ["P"]
}
```

**Current Behavior**:
- C6_parttimer_limits.py DOES implement Scheme P logic
- BUT C2_mom_weekly_hours.py enforces 44h for ALL employees INCLUDING Scheme P
- This creates a **constraint conflict**

**Evidence from Code**:

[context/constraints/C2_mom_weekly_hours.py](context/constraints/C2_mom_weekly_hours.py) line 334:
```python
max_weekly_normal_hours = get_constraint_param(
    ctx, 'momWeeklyHoursCap44h', employee_dict, default=44.0
)
```

This applies 44h to **all employees** including Scheme P. There is **no scheme-specific override** for Scheme P's 34.98h/29.98h limits.

**Fix Required**:
C2 must **exempt Scheme P employees** from the 44h cap since they are already handled by C6.

---

### ⚠️ Issue 4: Rest period constraint configuration
**Status**: **CORRECTLY CONFIGURED** - but may contribute to infeasibility

**Configuration**:
```json
{
  "id": "apgdMinRestBetweenShifts",
  "enforcement": "hard",
  "defaultValue": 8,
  "schemeOverrides": {
    "P": 1  // ← Scheme P requires only 1 hour rest
  }
}
```

**Implementation**:
- [context/constraints/C4_rest_period.py](context/constraints/C4_rest_period.py) correctly reads `schemeOverrides`
- Scheme P employees get 1-hour rest between shifts (enables split-shift patterns)
- Other schemes get 8-hour rest

This is **working as designed**. However, with only 1 hour rest, the solver may struggle to find feasible schedules when combined with the 44h weekly cap issue.

---

## Why Only N Shifts Are Assigned

**Hypothesis**: N shifts (00:00-08:00) are the **first shifts of the day** and have fewer conflicts:
- No prior shifts to conflict with (rest period constraint)
- Fall early in the daily schedule
- Rotation offsets spread N shifts across different employees

D shifts (08:00-16:00) and E shifts (16:00-00:00 next day) may create conflicts due to:
1. **Sequential nature**: D comes after N, E comes after D
2. **Cumulative weekly hours**: By the time the solver tries to assign D/E shifts, weekly hours are approaching limits
3. **44h cap too high for Scheme P**: The solver thinks it has 44h available but C6 restricts to 34.98h

---

## Input Configuration Summary

### Employees (6 total, all Scheme P):
```
00173519 - Scheme P, Offset 0
00173565 - Scheme P, Offset 1
00173697 - Scheme P, Offset 2
00174052 - Scheme P, Offset 3
00174056 - Scheme P, Offset 4
00174104 - Scheme P, Offset 0
```

### Demand Requirements:
| Requirement | Pattern      | Headcount | Shift Times |
|-------------|--------------|-----------|-------------|
| 270_1       | N-N-N-N-O-O  | 2         | 00:00-08:00 |
| 270_2       | D-D-D-D-O-O  | 2         | 08:00-16:00 |
| 270_3       | E-E-E-E-O-O  | 2         | 16:00-00:00 next day |

### Relevant Constraints:
1. **partTimerWeeklyHours** (HARD):
   - ≤4 work days/week: Max 34.98h
   - >4 work days/week: Max 29.98h

2. **momWeeklyHoursCap44h** (HARD):
   - **BUG**: Applies 44h to ALL schemes including P

3. **apgdMinRestBetweenShifts** (HARD):
   - Default: 8 hours
   - Scheme P override: 1 hour ✅

4. **oneShiftPerDay** (HARD):
   - 1 shift per day for all schemes

5. **momDailyHoursCap** (HARD):
   - Scheme P: 9 hours daily

---

## Solution Strategy

### 1. Fix C2_mom_weekly_hours.py to Exempt Scheme P

**Current Code** (line 334):
```python
max_weekly_normal_hours = get_constraint_param(
    ctx, 'momWeeklyHoursCap44h', employee_dict, default=44.0
)
```

**Proposed Fix**:
```python
# Scheme P employees are handled by C6_parttimer_limits.py
# Skip 44h cap for Scheme P to avoid constraint conflicts
scheme_normalized = normalize_scheme(emp_schemes.get(emp_id, 'A'))
if scheme_normalized == 'P':
    continue  # Scheme P weekly hours enforced by C6

max_weekly_normal_hours = get_constraint_param(
    ctx, 'momWeeklyHoursCap44h', employee_dict, default=44.0
)
```

**Impact**:
- Scheme P employees will be governed ONLY by C6's 34.98h/29.98h limits
- Removes conflicting 44h constraint
- Should resolve INFEASIBLE status

---

### 2. Verify C6_parttimer_limits.py Logic

**Current Implementation**:
- ✅ Identifies Scheme P employees correctly
- ✅ Reads `maxHours4Days` and `maxHoursMoreDays` from JSON
- ✅ Counts work days in pattern
- ✅ Applies correct threshold:
  - ≤4 work days → 34.98h
  - >4 work days → 29.98h

**Verification Needed**:
- Ensure work day counting includes D/N shifts but excludes O days
- Ensure pattern-aware hour calculation matches time_utils.py
- Test with actual Scheme P patterns (N-N-N-N-O-O, D-D-D-D-O-O, E-E-E-E-O-O)

---

### 3. Test After Fix

**Test Case**: RST-20260113-AECA74BF_Solver_Input.json

**Expected Results**:
- Status: `OPTIMAL` or `FEASIBLE`
- N shifts: 62 assigned ✅
- D shifts: 62 assigned (currently 0)
- E shifts: 62 assigned (currently 0)
- Weekly hours per employee: ≤34.98h (4-day patterns)

**Validation**:
```python
# For each employee with Scheme P
for emp in output['employeeRoster']:
    if 'Scheme P' in emp['scheme']:
        # Check weekly hours
        for week in employee_weeks:
            normal_hours = sum(a['hours']['normal'] for a in week_assignments)
            work_days = count(a for a in week_assignments if shiftCode in ['N','D','E'])
            
            if work_days <= 4:
                assert normal_hours <= 34.98, f"Week {week}: {normal_hours}h exceeds 34.98h"
            else:
                assert normal_hours <= 29.98, f"Week {week}: {normal_hours}h exceeds 29.98h"
```

---

## Other Findings

### ✅ Slot Generation Working Correctly
- ICPMP preprocessing created all required slots
- Rotation offsets applied (0-5)
- Patterns correctly expanded (N-N-N-N-O-O → daily N slots with O slots)

### ✅ OFF_DAY Slots Generated
- 120 OFF_DAY slots created (matches patterns: 2 O days per employee per week × 6 employees × ~5 weeks)

### ✅ Hour Calculations
- N shift: 8h gross → 7.25h normal (after 0.75h lunch) ✅
- Hour breakdowns include: gross, lunch, normal, ot, restDayPay, paid

### ⚠️ UNASSIGNED Status
- 22 slots marked `UNASSIGNED` (in addition to 62 D + 62 E = 124 total unassigned)
- May represent pattern days that couldn't be assigned due to constraint violations

---

## Implementation Priority

### Priority 1 (CRITICAL): Fix C2 Constraint Conflict
- **File**: `context/constraints/C2_mom_weekly_hours.py`
- **Change**: Exempt Scheme P employees from 44h cap
- **Testing**: Resolve INFEASIBLE status for RST-20260113-AECA74BF

### Priority 2 (VERIFICATION): Test C6 Logic
- **File**: `context/constraints/C6_parttimer_limits.py`
- **Action**: Add debug logging for Scheme P constraint application
- **Testing**: Verify 34.98h/29.98h limits are enforced correctly

### Priority 3 (ENHANCEMENT): Improve Error Messages
- **File**: `context/engine/solver_engine.py`
- **Action**: When INFEASIBLE, identify which constraints conflict
- **Benefit**: Faster debugging of constraint issues

---

## References

### Key Files:
- Input: `input/RST-20260113-AECA74BF_Solver_Input.json`
- Output: `input/RST-20260113-AECA74BF_Solver_Output.json`
- C2 Constraint: `context/constraints/C2_mom_weekly_hours.py`
- C6 Constraint: `context/constraints/C6_parttimer_limits.py`
- C4 Rest Period: `context/constraints/C4_rest_period.py`

### Documentation:
- [context/glossary.md](context/glossary.md) - Scheme definitions
- [implementation_docs/CONSTRAINT_ARCHITECTURE.md](implementation_docs/CONSTRAINT_ARCHITECTURE.md)
- [docs/RATIO_CACHING_GUIDE.md](docs/RATIO_CACHING_GUIDE.md)
