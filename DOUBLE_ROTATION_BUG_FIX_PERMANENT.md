# Double Rotation Bug - PERMANENT FIX

## Date: 2025-12-20

## Issue Summary
Employee rotation offsets were being applied TWICE, causing consecutive OFF days to show as UNASSIGNED.

## Root Cause
The codebase has a helper function `calculate_employee_work_pattern(base_pattern, offset)` that rotates a pattern by an offset:
- Base pattern: `['D', 'D', 'N', 'N', 'O', 'O']`
- Employee offset: 1
- Employee pattern: `['D', 'N', 'N', 'O', 'O', 'D']` (already rotated)

Then when calculating which day of the pattern a date falls on, we were calling:
```python
pattern_day = calculate_pattern_day(
    assignment_date=current_date,
    employee_offset=emp_offset,  # ❌ WRONG - offset applied again!
    ...
)
```

This caused the pattern_day to be offset by 1 extra position, mapping to the wrong day in the pattern.

## Example of the Bug
Employee 00016678, Offset: 1, Pattern: `['D', 'N', 'N', 'O', 'O', 'D']`

**Before Fix:**
- May 5: pattern_day=5 → 'D' (wrong!) → Shows UNASSIGNED
- Should be: pattern_day=4 → 'O' (correct!) → Shows OFF_DAY

**After Fix:**
- May 5: pattern_day=4 → 'O' (correct!) → Shows OFF_DAY ✓

## All Locations Fixed

### Location 1: `build_employee_roster_async()` - Line 124
**File:** `src/output_builder.py`
**Function:** Main roster building for async API

**Before:**
```python
pattern_day = calculate_pattern_day(
    assignment_date=current_date,
    pattern_start_date=pattern_start_date_obj,
    employee_offset=emp_offset,  # ❌ Wrong
    pattern_length=len(base_pattern)
)
```

**After:**
```python
pattern_day = calculate_pattern_day(
    assignment_date=current_date,
    pattern_start_date=pattern_start_date_obj,
    employee_offset=0,  # ✓ Correct - pattern already rotated
    pattern_length=len(base_pattern),
    coverage_days=coverage_days  # ✓ Also added coverage_days support
)
```

### Location 2: `insert_off_day_assignments()` - Line 584
**File:** `src/output_builder.py`
**Function:** Generates OFF day assignments

**Before:**
```python
pattern_day = calculate_pattern_day(
    assignment_date=current_date,
    pattern_start_date=pattern_start_date_obj,
    employee_offset=emp_offset,  # ❌ Wrong
    pattern_length=pattern_length
)
```

**After:**
```python
pattern_day = calculate_pattern_day(
    assignment_date=current_date,
    pattern_start_date=pattern_start_date_obj,
    employee_offset=0,  # ✓ Correct - pattern already rotated
    pattern_length=pattern_length,
    coverage_days=coverage_days  # ✓ Also added coverage_days support
)
```

## Additional Fixes Applied

### Coverage Days Support
Both functions now properly extract and pass `coverage_days` from the requirement:
```python
coverage_days = reqs[0].get('coverageDays', None)
```

This ensures correct pattern day calculation for Mon-Fri patterns that should skip weekends.

## Verification

### Code Search Verification
✓ Searched entire codebase for `calculate_pattern_day` calls
✓ Only 2 locations in `output_builder.py` use `calculate_employee_work_pattern` + `calculate_pattern_day`
✓ Both locations are now fixed

### Test Results
```
✓ Total employees with work: 15
✓ Total unassigned days (employees with work): 0

Employee 00016678:
  - Work days: 21
  - OFF days: 10 (was 5 before)
  - Unassigned: 0 (was 5 before)
  - Pattern: ['D', 'N', 'N', 'O', 'O', 'D']
```

## Why This Bug Kept Reoccurring
1. There are TWO separate functions in `output_builder.py` that build roster data
2. Initial fix only addressed one function (`build_employee_roster_async`)
3. The second function (`insert_off_day_assignments`) was missed

## Guarantee of Permanent Fix

### 1. All Usage Locations Fixed
- ✓ `build_employee_roster_async()` - Line 124
- ✓ `insert_off_day_assignments()` - Line 584
- ✓ No other locations use this pattern combination

### 2. Added Explanatory Comments
Both locations now have this comment:
```python
# NOTE: We pass employee_offset=0 because emp_pattern is already rotated
```

This prevents future developers from "fixing" it back to the wrong behavior.

### 3. Pattern Established
**RULE:** When using `calculate_employee_work_pattern()` to get a rotated pattern, ALWAYS pass `employee_offset=0` to `calculate_pattern_day()`.

**Why:** The pattern is already rotated. Passing the offset again would double-rotate.

## Code Review Checklist
When reviewing code that uses rotation patterns:

- [ ] Is `calculate_employee_work_pattern()` used to get a rotated pattern?
- [ ] Is `calculate_pattern_day()` called with that rotated pattern?
- [ ] If yes to both, verify `employee_offset=0` is passed to `calculate_pattern_day()`
- [ ] Verify `coverage_days` is extracted from requirement and passed through

## Test Coverage
- ✓ Tested with 6-day pattern `['D', 'D', 'N', 'N', 'O', 'O']`
- ✓ Tested with multiple employee offsets (0, 1, 2, etc.)
- ✓ Tested with consecutive OFF days in pattern
- ✓ Verified all 15 employees with work have 0 unassigned days

## Files Modified
1. `src/output_builder.py`
   - Line 77: Added `coverage_days = None`
   - Line 84: Extract coverage_days from requirement
   - Line 124: Fixed double rotation (employee_offset=0)
   - Line 129: Pass coverage_days parameter
   - Line 541: Added `coverage_days = None`
   - Line 547: Extract coverage_days from requirement
   - Line 584: Fixed double rotation (employee_offset=0)
   - Line 589: Pass coverage_days parameter

## Commit Message Template
```
Fix: Permanent fix for double rotation offset bug

- Fixed two locations in output_builder.py where employee rotation 
  offset was applied twice
- Added coverage_days support to both functions
- Added explanatory comments to prevent regression
- All employees with work assignments now have 0 unassigned days

Locations fixed:
1. build_employee_roster_async() - Line 124
2. insert_off_day_assignments() - Line 584

Test: Employee 00016678 now shows 10 OFF days (was 5 OFF + 5 UNASSIGNED)
```
