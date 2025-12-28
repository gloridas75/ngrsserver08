# Incremental Solver Production Test Files

## Overview
This directory contains test files for testing the incremental solver on the production server.

**Server**: `https://ngrssolver09.comcentricapps.com`  
**Endpoint**: `POST /solve/incremental`  
**Last Updated**: December 28, 2025

---

## Test Files

### 1. Test Script
**File**: [`test_incremental_production.py`](../test_incremental_production.py)

Main test runner that:
- Checks server health
- Tests demandBased incremental solving
- Tests outcomeBased incremental solving (with headcount=0)
- Saves results to `output/` directory

**Usage**:
```bash
python3 test_incremental_production.py
```

---

### 2. Test Input Files

#### demandBased Mode Test
**File**: [`test_incremental_demand_based.json`](test_incremental_demand_based.json)

Tests traditional pattern-based incremental solving:
- **Rostering Basis**: `demandBased`
- **Headcount**: 2 (standard mode)
- **Temporal Window**: 
  - Cutoff: 2026-01-15 (lock before this date)
  - Solve: 2026-01-16 to 2026-01-31 (only solve this range)
- **Previous Assignments**: 3 locked assignments
- **Employees**: 2 employees (EMP001, EMP002)
- **Work Pattern**: 5 days on, 2 days off (D-D-D-D-D-O-O)

**What it tests**:
- Locked assignments remain unchanged before cutoff date
- New assignments only generated for solve window
- Pattern-based locked context calculations (weekly hours, consecutive days)

---

#### outcomeBased Mode Test
**File**: [`test_incremental_outcome_based.json`](test_incremental_outcome_based.json)

Tests template-based incremental solving with headcount=0:
- **Rostering Basis**: `outcomeBased`
- **Headcount**: 0 (template mode - should be allowed)
- **Min Staff Threshold**: 100%
- **Temporal Window**:
  - Cutoff: 2026-01-15
  - Solve: 2026-01-16 to 2026-01-31
- **Previous Assignments**: 4 locked assignments
- **Employees**: 3 employees (EMP001, EMP002, EMP003)
- **Work Pattern**: 5 days on, 2 days off (D-D-D-D-D-O-O)

**What it tests**:
- Headcount=0 validation passes for outcomeBased mode (recent fix)
- Template-based validation without pattern constraints
- Locked context calculations conditional on rostering basis
- Schema version 0.95 support

---

## Key Features Tested

### ✅ Recent Updates (Deployed Dec 28, 2025)

1. **Input Validation** (Commit: a111591)
   - `_validate_incremental_request()` validates request structure
   - Clear error messages for missing/invalid fields
   
2. **Rostering Basis Support** (Commit: a111591)
   - `_detect_rostering_basis()` auto-detects mode
   - Conditional locked context calculations
   - Pattern-based locked hours only for demandBased mode
   
3. **Headcount=0 Support** (Commit: 09be8f8)
   - Allows `headcount: 0` specifically for outcomeBased mode
   - Rejects for demandBased mode as expected
   
4. **Schema Version Update** (Commit: a111591)
   - Schema version updated from 0.80 to 0.95
   - Supports 0.95 and 0.98 versions

5. **Targeted Validation Fix** (Commit: 5933fd0)
   - Fixed validation to skip employee checks (derived from previousOutput)
   - Validates only demandItems and planningHorizon structures

---

## Expected Results

### Successful Response Structure
```json
{
  "assignments": [
    {
      "assignmentId": "...",
      "employeeId": "...",
      "date": "2026-01-XX",
      "shiftCode": "D",
      "status": "LOCKED",  // or "ASSIGNED"
      "hours": { ... }
    }
  ],
  "solverRun": {
    "status": "OPTIMAL",
    "solveTime": 5.2
  }
}
```

### Assignment Status Meanings
- **LOCKED**: Assignment before cutoff date (from previousOutput)
- **ASSIGNED**: Newly generated assignment in solve window

---

## Troubleshooting

### Common Issues

1. **"employees array cannot be empty"**
   - **Cause**: Old code tried to validate with empty employees array
   - **Fixed**: Commit 5933fd0 (targeted validation)
   - **Solution**: Deploy latest code to server

2. **"headcount must be greater than 0"**
   - **Cause**: Validation didn't account for outcomeBased mode
   - **Fixed**: Commit 09be8f8
   - **Solution**: Deploy validation fix

3. **"Missing required fields: planningReference"**
   - **Cause**: Request missing required fields
   - **Solution**: Check test input includes all required fields (see _validate_incremental_request)

### Required Fields Checklist
- ✅ `schemaVersion`
- ✅ `planningReference`
- ✅ `temporalWindow` (cutoffDate, solveFromDate, solveToDate)
- ✅ `previousOutput` (with assignments array)
- ✅ `employeeChanges` (newJoiners, notAvailableFrom, longLeave)
- ✅ `demandItems`
- ✅ `planningHorizon`

---

## Output Files

Test results are saved to: `output/incremental_*_prod_*.json`

Format: `incremental_{mode}_prod_{timestamp}.json`

Examples:
- `incremental_demand_based_prod_20251228_174612.json`
- `incremental_outcome_based_prod_20251228_174650.json`

---

## Running Tests After Deployment

1. **Deploy to server**:
   ```bash
   ssh ubuntu@<ec2-ip>
   cd ~/ngrs-solver
   git pull origin main
   sudo systemctl restart ngrs
   ```

2. **Run tests locally** (against production):
   ```bash
   python3 test_incremental_production.py
   ```

3. **Check results**:
   - Console output shows pass/fail status
   - Output files contain full solver responses
   - Review locked vs new assignments

---

## Related Documentation

- [Incremental Solver Updates Required](../INCREMENTAL_SOLVER_UPDATES_REQUIRED.md) - Implementation guide
- [Local Test Suite](../test_incremental_updates.py) - Unit tests for incremental changes
- [FastAPI Quick Reference](../implementation_docs/FASTAPI_QUICK_REFERENCE.md) - API endpoint docs

---

## Git History

```bash
5933fd0  fix(incremental): Use targeted validation
a111591  feat(incremental): Add input validation and rostering basis support
09be8f8  Allow headcount=0 for outcomeBased mode
```

---

## Contact

For issues or questions about incremental solving:
1. Check logs: `sudo journalctl -u ngrs -n 100 -f`
2. Review validation errors in API response
3. Verify all required fields present in request
