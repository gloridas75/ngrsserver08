# OFF_DAY Fix Deployment Summary

## Issue Identified
OFF_DAY assignments were **missing from the `assignments` array** but present in `employeeRoster.dailyStatus`:
- ❌ assignments array: 40 OFF_DAYs (missing 8)
- ✅ employeeRoster.dailyStatus: 48 OFF_DAYs (correct)
- ✅ rosterSummary: 48 OFF_DAYs (correct)

**Affected**: Employee 00034833 (and potentially others with no work assignments)

## Root Cause
The `insert_off_day_assignments()` function in `src/output_builder.py` was only being invoked for `demandBased` rosters, but NOT for `outcomeBased` rosters. This caused OFF_DAYs to be missing from the assignments array for outcome-based templates.

## Fix Applied
**File**: `src/output_builder.py` (Line ~720)

**Change**: Remove conditional check that limited OFF_DAY generation to demandBased only

```python
# BEFORE (INCORRECT):
if rostering_basis == 'demandBased':
    all_with_off = insert_off_day_assignments(assignments, input_data, ctx)
    assignments = all_with_off

# AFTER (CORRECT):
all_with_off = insert_off_day_assignments(assignments, input_data, ctx)
assignments = all_with_off
```

## Verification - Local Testing

### Regression Test Results
✅ **5 of 5 core tests PASSED** (2 baseline errors unrelated)

| Test Case | Rostering | Status | Assignments | Roster | Summary |
|-----------|-----------|--------|-------------|--------|---------|
| RST-20260113-C9FE1E08 | outcomeBased | ✅ PASS | 48 | 48 | 48 |
| RST-20260112-4E8B07EE | outcomeBased | ✅ PASS | 230 | 230 | 230 |
| RST-20260112-71DA90DC | outcomeBased | ✅ PASS | 480 | 480 | 480 |
| RST-20260112-D6226DC3 | outcomeBased | ✅ PASS | 0 | 0 | 0 |
| RST-20260113-6C5FEBA6 | demandBased | ✅ PASS | 48 | 48 | 48 |

### Original vs Fixed Comparison
```
Original Output (before fix):
  Assignments OFF_DAYs: 40
  EmployeeRoster OFF_DAYs: 48
  ❌ Discrepancy: 8 missing

Fixed Output (after fix):
  Assignments OFF_DAYs: 48
  EmployeeRoster OFF_DAYs: 48
  ✅ Discrepancy: 0
```

## Production Status
⚠️ **Production API still returns OLD output with the bug**:
- Tested: https://ngrssolver09.comcentricapps.com/solve/async
- Result: Still shows 40 vs 48 discrepancy
- **Action Required**: Deploy fixed code to production

## Deployment Steps Required

1. **Backup current production code** (optional but recommended)
   ```bash
   ssh ubuntu@<ec2-ip>
   cd ~/ngrs-solver
   cp -r . ~/ngrs-solver-backup-$(date +%Y%m%d)
   ```

2. **Deploy fixed code to production**
   ```bash
   # From local machine
   scp src/output_builder.py ubuntu@<ec2-ip>:~/ngrs-solver/src/
   
   # OR sync entire repo
   rsync -av --exclude 'output/' --exclude '*.pyc' \
     . ubuntu@<ec2-ip>:~/ngrs-solver/
   ```

3. **Restart production service**
   ```bash
   ssh ubuntu@<ec2-ip>
   sudo systemctl restart ngrs
   sudo systemctl status ngrs
   ```

4. **Verify production fix**
   ```bash
   # Run API test again
   python test_api_off_days.py
   ```

## Impact Assessment
- **Breaking Change**: NO - This is a bug fix that corrects missing data
- **Backward Compatibility**: YES - Output schema remains v0.95
- **Frontend Impact**: POSITIVE - Frontend will now receive complete OFF_DAY data
- **Performance Impact**: NONE - Same computational complexity

## Files Modified
1. `src/output_builder.py` - Lines 719-728 (removed rostering_basis conditional)

## Testing Checklist
- [x] Local CLI solver tested
- [x] Regression tests (5 test cases)
- [x] outcomeBased rosters verified
- [x] demandBased rosters verified
- [ ] Production API deployment
- [ ] Production API verification

## Related Documentation
- [implementation_docs/FASTAPI_QUICK_REFERENCE.md](implementation_docs/FASTAPI_QUICK_REFERENCE.md)
- [deploy/README.md](deploy/README.md)

---
**Date**: 2026-01-13  
**Priority**: HIGH - Data consistency issue  
**Status**: ✅ Fixed locally, ⏳ Pending production deployment
