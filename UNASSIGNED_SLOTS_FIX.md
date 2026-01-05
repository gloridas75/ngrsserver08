# UNASSIGNED Slots Fix - employeeId Must Be Null

## Issue Description
UNASSIGNED slots in the output JSON were incorrectly showing `employeeId` values instead of `null`. This occurred when employees failed qualification checks during template replication.

### Example of Bug:
```json
{
  "assignmentId": "DI-2601031507-75610560-2026-06-01-D-00087506-UNASSIGNED",
  "employeeId": "00087506",  // ❌ BUG: Should be null
  "status": "UNASSIGNED",
  "reason": "C7: No valid qualification from group G2"
}
```

### Correct Format:
```json
{
  "assignmentId": "DI-2601031507-75610560-2026-06-01-D-UNASSIGNED",
  "employeeId": null,  // ✅ CORRECT
  "status": "UNASSIGNED",
  "reason": "C7: No valid qualification from group G2"
}
```

## Root Cause
In `context/engine/template_roster.py` (lines 755-777), when replicating a validated template pattern to individual employees, the code created UNASSIGNED slots with the employee's ID populated:

```python
# OLD CODE (BUG):
assignment = {
    'assignmentId': f"{demand_id}-{date_str}-D-{emp_id}-UNASSIGNED",
    'employeeId': emp_id,  # ❌ Wrong: UNASSIGNED should have null
    'status': 'UNASSIGNED',
    'reason': day_info['reason']
}
```

This happened when:
1. Template validation identified a work day
2. Employee failed qualification checks for that day
3. Slot was marked UNASSIGNED but still retained employeeId

## Solution

### File 1: context/engine/template_roster.py (Line 771)
**Changed**: UNASSIGNED slots now correctly have `employeeId: None`

```python
# NEW CODE (FIXED):
assignment = {
    'assignmentId': f"{demand_id}-{date_str}-D-UNASSIGNED",
    'employeeId': None,  # ✅ UNASSIGNED slots must have null employeeId
    'status': 'UNASSIGNED',
    'reason': day_info['reason']
}
```

### File 2: src/output_builder.py (Line 310)
**Changed**: Employee counting now excludes None values from UNASSIGNED slots

```python
# OLD CODE:
employee_counts = Counter(a['employeeId'] for a in assignments)

# NEW CODE (FIXED):
employee_counts = Counter(a['employeeId'] for a in assignments if a.get('employeeId') is not None)
```

This prevents None values from being counted as employees in statistics.

## Testing

### Test Case: June 2026 with Qualification Mismatch
**Input**: 6 employees, 1 requirement needing BOTH G1 AND G2 qualifications
**Scenario**: Employee 00087506 only has G1 (missing G2)
**Expected**: 132 UNASSIGNED slots with `employeeId: null`

**Results**:
- Before fix: 132 UNASSIGNED with `employeeId: "00087506"` ❌
- After fix: 132 UNASSIGNED with `employeeId: null` ✅

### Verification Output:
```
UNASSIGNED Slots Check:
  With employeeId (BUG): 0
  Without employeeId (CORRECT): 132

Sample UNASSIGNED Entry:
  assignmentId: DI-2601031507-75610560-2026-06-01-D-UNASSIGNED
  employeeId: None
  status: UNASSIGNED
  reason: C7: No valid qualification from group G2
```

## Impact Analysis

### What Changed:
✅ UNASSIGNED slots now have `employeeId: null` (correct JSON format)
✅ Employee statistics exclude UNASSIGNED slots (correct counting)
✅ No conflicts between assignments and employeeRoster blocks

### What Stayed the Same:
- Constraint validation logic (C1-C17)
- Qualification checking (C7)
- Blacklist filtering (v0.70+ date ranges)
- Template generation and validation
- All other assignment processing

### Affected Scenarios:
- outcomeBased mode when employees fail qualification checks
- outcomeBased mode when employees are blacklisted for specific dates
- Any scenario where template validation marks work days as UNASSIGNED

### Not Affected:
- demandBased mode (uses different code path in solver_engine.py which was already correct)
- ASSIGNED slots (still have employeeId values)
- Empty slots (still created correctly with employeeId: None)

## Related Files

### Modified:
- `context/engine/template_roster.py` - Fixed UNASSIGNED slot creation (line 771)
- `src/output_builder.py` - Fixed employee counting (line 310)

### Verified Correct (No Changes Needed):
- `context/engine/solver_engine.py` - extract_assignments() already creates UNASSIGNED with `employeeId: None`
- `context/engine/outcome_based_with_slots.py` - Already creates UNASSIGNED with `employeeId: None`
- `src/redis_worker.py` - No UNASSIGNED slot creation logic
- `src/api_server.py` - No UNASSIGNED slot creation logic

## Commit Message

```
fix: UNASSIGNED slots must have employeeId: null

Fixed template_roster.py to correctly set employeeId: None for UNASSIGNED slots
when employees fail qualification checks during template replication.

Also updated output_builder.py to exclude None values when counting employee usage.

Before: UNASSIGNED slots had employeeId: "00087506" (incorrect)
After: UNASSIGNED slots have employeeId: null (correct)

Fixes issue where UNASSIGNED slots appeared to be assigned to specific employees
in the output JSON, causing confusion about actual staffing.
```

## Deployment Notes

### Production Impact: LOW
- This is a bug fix for output formatting only
- Does not change solver logic or constraint behavior
- No API schema changes
- No database migrations needed

### Rollback Plan:
If issues arise, revert commits:
1. Revert `context/engine/template_roster.py` line 771
2. Revert `src/output_builder.py` line 310

### Monitoring:
After deployment, verify:
- UNASSIGNED slots have `employeeId: null`
- Employee statistics are accurate
- No errors in employee roster generation
- Frontend correctly handles null employeeId values

## Future Improvements

Consider adding:
1. Unit tests for UNASSIGNED slot creation
2. Schema validation to enforce employeeId: null for UNASSIGNED status
3. Linting rule to catch employeeId assignment in UNASSIGNED contexts
4. Documentation of UNASSIGNED slot format in schema docs
