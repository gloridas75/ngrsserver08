# NGRS Solver v0.7 - Unassigned Slots Implementation

**Date**: November 15, 2025  
**Change Type**: Core Model Enhancement  
**Status**: ✅ Implemented

---

## 🎯 Overview

Modified the CP-SAT constraint programming model to **always return a solution**, even when some slots cannot be filled without violating hard constraints. The solver now explicitly marks slots as "UNASSIGNED" when no feasible assignment exists.

---

## 📋 Key Changes

### 1. **New Decision Variables: Unassigned Slots**

**Location**: `context/engine/solver_engine.py` - `build_model()` function

**Added**:
```python
# Create Boolean variable for each slot indicating if it's unassigned
unassigned = {}
for slot in slots:
    unassigned[slot.slot_id] = model.NewBoolVar(f"unassigned_slot_{slot.slot_id}")
```

**Purpose**: Allow the solver to explicitly mark slots that cannot be filled.

---

### 2. **Modified Headcount Constraints**

**Location**: `context/engine/solver_engine.py` - `build_model()` function

**Before**:
```python
# Old: Every slot MUST be filled (could cause INFEASIBLE)
model.Add(sum(slot_assignments) == slot.headcount)
```

**After**:
```python
# New: Either fill the slot OR mark it unassigned
model.Add(sum(slot_assignments) + unassigned[slot.slot_id] == slot.headcount)
```

**Impact**: 
- Solver can now find a solution even when constraints prevent filling all slots
- No more INFEASIBLE status due to impossible slot assignments

---

### 3. **Total Unassigned Counter**

**Location**: `context/engine/solver_engine.py` - `build_model()` function

**Added**:
```python
# Aggregate integer variable counting total unassigned slots
total_unassigned = model.NewIntVar(0, len(slots), "total_unassigned")
model.Add(total_unassigned == sum(unassigned[slot.slot_id] for slot in slots))
```

**Purpose**: Track the total number of unassigned slots for optimization objective.

---

### 4. **Updated Objective Function**

**Location**: `context/engine/solver_engine.py` - `build_model()` function

**Before**:
```python
# Old: Maximize assignments (simple feasibility)
model.Maximize(sum(all_assignments))
```

**After**:
```python
# New: PRIMARY objective is to MINIMIZE unassigned slots
BIG_MULTIPLIER = 1_000_000  # Much larger than any soft penalty
model.Minimize(BIG_MULTIPLIER * total_unassigned)
```

**Priority Hierarchy**:
1. **PRIMARY (×1,000,000)**: Minimize unassigned slots
2. **SECONDARY**: Soft constraint penalties (to be added later)

**Impact**: Solver prioritizes filling slots over all other considerations, while respecting hard constraints.

---

### 5. **Enhanced Assignment Extraction**

**Location**: `context/engine/solver_engine.py` - `extract_assignments()` function

**Added**: Logic to extract and report unassigned slots

**Output Format for ASSIGNED slots**:
```json
{
  "assignmentId": "D001-2025-11-15-D-EMP123",
  "demandId": "D001",
  "date": "2025-11-15",
  "employeeId": "EMP123",
  "status": "ASSIGNED",
  ...
}
```

**Output Format for UNASSIGNED slots**:
```json
{
  "assignmentId": "D001-2025-11-15-D-UNASSIGNED",
  "demandId": "D001",
  "date": "2025-11-15",
  "employeeId": null,
  "status": "UNASSIGNED",
  "reason": "No employee could be assigned without violating hard constraints",
  ...
}
```

**Impact**: Users can immediately identify which slots couldn't be filled and why.

---

### 6. **Constraint Validation Updates**

**Location**: `context/engine/solver_engine.py` - `calculate_scores()` function

**Changes**:
- Filter out unassigned slots before checking constraints
- Only validate hard constraints on ASSIGNED slots
- Report unassigned count as informational (not a violation)

**Code**:
```python
# Filter out unassigned slots for constraint checking
assigned_slots = [a for a in assignments if a.get('status') == 'ASSIGNED']

# All constraint checks use assigned_slots instead of assignments
for a in assigned_slots:
    # Check C1, C2, C7, etc. only on assigned slots
```

**Impact**: 
- No false violations on unassigned slots
- Hard constraints remain strict on actual assignments
- Cleaner violation reports

---

### 7. **Enhanced Score Breakdown**

**Location**: `context/engine/solver_engine.py` - `calculate_scores()` function

**Added**: New `unassignedSlots` section in score breakdown

**Output Structure**:
```json
{
  "scoreBreakdown": {
    "hard": {
      "violations": [...]
    },
    "soft": {
      "totalPenalty": 0,
      "details": [...]
    },
    "unassignedSlots": {
      "count": 5,
      "total": 100,
      "percentage": 5.0,
      "slots": [
        {
          "slotId": "D001-2025-11-15-D-abc123",
          "demandId": "D001",
          "date": "2025-11-15",
          "shiftCode": "D",
          "reason": "No feasible assignment"
        }
      ]
    }
  }
}
```

**Impact**: Clear visibility into assignment gaps and their locations.

---

## ✅ Verification Checklist

### Constraint Status

- [x] **C1 (Daily Hours)**: Hard constraint ✓ - Applied only to assigned slots
- [x] **C2 (Weekly Hours)**: Hard constraint ✓ - Applied only to assigned slots
- [x] **C3 (Consecutive Days)**: Hard constraint ✓ - Applied only to assigned slots
- [x] **C4 (Rest Period)**: Hard constraint ✓ - Model-level (prevents assignment)
- [x] **C5 (Off Days)**: Hard constraint ✓ - Applied only to assigned slots
- [x] **C6 (Part-timer Limits)**: Hard constraint ✓ - Applied only to assigned slots
- [x] **C7 (License Validity)**: Hard constraint ✓ - Applied only to assigned slots
- [x] **C8 (PDL Validity)**: Hard constraint ✓ - Applied only to assigned slots
- [x] **C9 (Gender Balance)**: Hard constraint ✓ - Applied only to assigned slots
- [x] **C10 (Skill Match)**: Hard constraint ✓ - Applied only to assigned slots
- [x] **C11 (Rank Match)**: Hard constraint ✓ - Applied only to assigned slots
- [x] **C15 (Qualification Override)**: Hard constraint ✓ - Applied only to assigned slots
- [x] **C16 (No Overlap)**: Hard constraint ✓ - Model-level (prevents overlap)
- [x] **C17 (Monthly OT)**: Hard constraint ✓ - Applied only to assigned slots

### Headcount Constraints

- [x] **Old constraint removed**: No more `model.Add(sum(assignments) == headcount)`
- [x] **New constraint verified**: All use `sum(assignments) + unassigned == headcount`
- [x] **Edge case handled**: Slots with no valid employees automatically marked unassigned

### Variables and Context

- [x] **`unassigned` dictionary**: Created and stored in ctx
- [x] **`total_unassigned` variable**: Created and constrained
- [x] **Context storage**: Both added to `ctx` for extraction phase

### Objective Function

- [x] **Primary objective**: Minimize `total_unassigned` with BIG multiplier (1,000,000)
- [x] **No maximize**: Old `Maximize(sum(assignments))` removed
- [x] **Extensible**: Ready for soft constraint penalties to be added

### Output Format

- [x] **ASSIGNED status**: Added to successful assignments
- [x] **UNASSIGNED status**: Added to unfilled slots
- [x] **employeeId = null**: For unassigned slots
- [x] **reason field**: Explains why slot couldn't be filled
- [x] **scoreBreakdown**: Includes unassignedSlots section

---

## 🔍 Code Locations

### Decision Variables
**File**: `context/engine/solver_engine.py`  
**Function**: `build_model(ctx)`  
**Lines**: ~70-75 (unassigned variables creation)  
**Lines**: ~108-112 (total_unassigned aggregation)

### Modified Constraints
**File**: `context/engine/solver_engine.py`  
**Function**: `build_model(ctx)`  
**Lines**: ~78-95 (headcount constraints with unassigned option)

### Objective Function
**File**: `context/engine/solver_engine.py`  
**Function**: `build_model(ctx)`  
**Lines**: ~114-121 (minimize unassigned objective)

### Assignment Extraction
**File**: `context/engine/solver_engine.py`  
**Function**: `extract_assignments(ctx, solver)`  
**Lines**: ~160-230 (enhanced extraction with unassigned handling)

### Score Calculation
**File**: `context/engine/solver_engine.py`  
**Function**: `calculate_scores(ctx, assignments)`  
**Lines**: ~280-295 (filtering and reporting)  
**Lines**: ~520-545 (enhanced score breakdown)

---

## 🚀 Benefits

### 1. **Always Returns a Solution**
- No more INFEASIBLE status due to impossible constraints
- Users always get actionable results

### 2. **Clear Visibility**
- Explicitly shows which slots couldn't be filled
- Provides reasons for gaps

### 3. **Maintains Integrity**
- All hard constraints remain strict
- No violations introduced to "force" assignments

### 4. **Optimized Assignment**
- Solver prioritizes filling as many slots as possible
- Minimizes unassigned slots first, then optimizes soft preferences

### 5. **Better Decision Making**
- Users can see exactly where staffing gaps exist
- Can make informed decisions about:
  - Hiring additional staff
  - Adjusting shift requirements
  - Relaxing certain whitelist constraints
  - Adding overtime capacity

---

## 📊 Expected Behavior

### Scenario 1: All Slots Can Be Filled
```
Input: 10 slots, sufficient employees with matching skills
Output: 
  - 10 ASSIGNED slots
  - 0 UNASSIGNED slots
  - Status: OPTIMAL
  - Hard violations: 0
```

### Scenario 2: Some Slots Cannot Be Filled
```
Input: 10 slots, insufficient employees or skill mismatches
Output:
  - 7 ASSIGNED slots (maximum possible)
  - 3 UNASSIGNED slots (marked explicitly)
  - Status: OPTIMAL (found best solution)
  - Hard violations: 0 (on assigned slots)
  - unassignedSlots.count: 3
```

### Scenario 3: Constraint Conflicts
```
Input: 10 slots, employees available but PLRD/rest period conflicts
Output:
  - 6 ASSIGNED slots (respecting rest periods)
  - 4 UNASSIGNED slots (cannot assign without violating rest)
  - Status: OPTIMAL
  - Hard violations: 0
```

---

## ⚠️ Important Notes

### What Changed
- ✅ Model now allows unassigned slots
- ✅ Objective prioritizes filling slots
- ✅ Output includes unassigned slot information
- ✅ Constraint checking filters out unassigned slots

### What Stayed the Same
- ✅ All hard constraints remain strict
- ✅ No constraint violations are allowed
- ✅ Whitelist/blacklist still enforced
- ✅ PLRD, MOM, rest periods still mandatory
- ✅ Skill/rank matching still required
- ✅ Soft preferences still optimized (secondary)

### Migration Impact
- **Breaking Change**: Output format includes new fields (`status`, `reason`)
- **Non-Breaking**: Existing assigned slots have same structure
- **Enhancement**: More informative results
- **Action Required**: Update output parsers to handle `status` field

---

## 🧪 Testing Recommendations

### Test Case 1: Normal Operation
```
Input: Balanced workforce, realistic demands
Expected: All slots ASSIGNED, 0 unassigned
```

### Test Case 2: Understaffed
```
Input: More slots than employees
Expected: Some slots UNASSIGNED, explicit list provided
```

### Test Case 3: Skill Mismatch
```
Input: Employees available but lacking required qualifications
Expected: Slots requiring missing skills marked UNASSIGNED
```

### Test Case 4: Rest Period Conflicts
```
Input: Consecutive shifts with <8h gap
Expected: Second shift UNASSIGNED to respect rest period
```

### Test Case 5: Whitelist Constraints
```
Input: All employees blacklisted for certain slots
Expected: Those slots marked UNASSIGNED
```

---

## 📝 Future Enhancements

### Phase 1 (Current)
- ✅ Allow unassigned slots
- ✅ Minimize unassigned as primary objective
- ✅ Report unassigned slots in output

### Phase 2 (Upcoming)
- 🔄 Add soft constraint penalties to objective
- 🔄 Integrate fairness metrics
- 🔄 Add preference scoring

### Phase 3 (Future)
- ⏳ Multi-objective optimization
- ⏳ What-if analysis for unassigned slots
- ⏳ Suggestions for resolving unassigned slots

---

## ✅ Conclusion

The NGRS Solver now **guarantees a solution** while maintaining all hard constraint integrity. Users get clear visibility into staffing gaps and can make informed decisions to improve coverage.

**All hard constraints remain strict. No violations are introduced. The solver simply acknowledges when it cannot find a feasible assignment rather than failing completely.**

---

**Implementation Date**: November 15, 2025  
**Status**: ✅ Complete  
**Tested**: Pending integration testing  
**Version**: 0.7.0
