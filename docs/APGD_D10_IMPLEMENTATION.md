# APGD-D10 Implementation Summary

## Overview
Successfully implemented APGD-D10 (MOM Special Approval) special group support for Scheme A + APO employees. This allows employees with MOM approval number "APGD - D10" to work 6-7 days per week with monthly hour caps instead of standard weekly limits.

## Implementation Date
14 December 2024

## What is APGD-D10?
APGD-D10 is a MOM special approval that allows Scheme A + APO employees to:
- Work up to 7 days per week (exempt from weekly rest day requirement)
- Follow monthly hour caps instead of strict weekly limits
- Receive rest day pay for 6th and 7th days in a work week
- Work max 8 consecutive days (vs standard 12)
- Have minimum 8-hour rest between shifts (vs standard 11)

## Activation
Add `"enableAPGD-D10": true` to the requirement in input JSON:

```json
{
  "requirements": [{
    "requirementId": "R1",
    "productTypeId": "APO",
    "scheme": "Global",
    "enableAPGD-D10": true,  // ← Enable APGD-D10 mode
    "workPattern": ["D","D","D","D","D","D","O"]
  }]
}
```

## Detection Criteria
An employee qualifies for APGD-D10 treatment when ALL conditions are met:
1. **Scheme**: A (normalized from "Scheme A")
2. **Product**: APO (employee.productTypeId matches requirement)
3. **Flag**: `requirement.enableAPGD-D10 = true`

## Hour Caps & Rules

### Monthly Total Hour Caps (C19)
Varies by days in month and employee category:

| Days in Month | Standard (Locals + Non-CPL/SGT) | Foreign CPL/SGT |
|---------------|--------------------------------|-----------------|
| 28 days       | 224h                          | 244h           |
| 29 days       | 231h                          | 252h           |
| 30 days       | 238h                          | 260h           |
| 31 days       | 246h                          | 268h           |

**Category Determination**:
- `foreign_cpl_sgt`: Foreign employees (local=0) with rankId='CPL' or 'SGT'
- `standard`: All others (locals or non-CPL/SGT ranks)

### Weekly Normal Hour Cap
- **44h per week** (same as standard Scheme A)
- Extra hours beyond 44h/week are paid as overtime + rest day pay

### Work Pattern Hour Breakdown
**4 days/week**: 11.0h normal each
- Total: 44h normal, 0h OT, 0 RDP

**5 days/week**: 8.8h normal + 2.2h OT each
- Total: 44h normal, 11h OT, 0 RDP

**6 days/week**:
- Days 1-5: 8.8h normal + 2.2h OT each
- Day 6: 0h normal + 3h OT + 8h RDP
- Total: 44h normal, 14h OT, 1 RDP

**7 days/week**:
- Days 1-5: 8.8h normal + 2.2h OT each
- Days 6-7: 0h normal + 3h OT + 8h RDP each
- Total: 44h normal, 17h OT, 2 RDP

## Special Rules vs Standard Scheme A

| Rule | Standard Scheme A | APGD-D10 | Implementation |
|------|------------------|----------|----------------|
| Max consecutive days | 12 days | **8 days** | C3 constraint |
| Min rest between shifts | 11 hours | **8 hours** | C4 constraint |
| Weekly rest day | Required | **Exempt** | C5 constraint (skipped) |
| Max days/week | 6 days | **7 days** | C5 exemption |
| Weekly normal cap | 44h | 44h (same) | C2 constraint |
| Monthly total cap | ~319h | **246h-268h** | C19 constraint (NEW) |
| Rest Day Pay | 1 RDP (6th day) | **1-2 RDP (6th & 7th)** | time_utils calculation |

## Files Modified/Created

### Phase 1: Detection Functions (time_utils.py)
**File**: `context/engine/time_utils.py`

Added 4 new functions:

```python
def normalize_rank(rank_str: str) -> str:
    """Normalize rank to uppercase (CPL, SGT, SER)."""

def is_apgd_d10_employee(employee: dict, requirement: dict = None) -> bool:
    """Check if employee qualifies for APGD-D10 treatment."""

def get_apgd_d10_category(employee: dict) -> str:
    """Return 'foreign_cpl_sgt' or 'standard' for monthly cap calculation."""

def calculate_apgd_d10_hours(
    start_dt, end_dt, employee_id, assignment_date_obj, 
    all_assignments, employee_dict
) -> dict:
    """Calculate APGD-D10 compliant work hours with rest day pay."""
```

**Test Results**: ✅ All detection tests passed
- Scheme A + APO + flag=true → Detected
- Scheme B + APO + flag=true → Not detected (correct)
- Scheme A + APO + flag=false → Not detected (correct)
- Foreign CPL → Category: foreign_cpl_sgt (268h cap)
- Local CPL → Category: standard (246h cap)
- Foreign SER → Category: standard (246h cap)

### Phase 2: C3 - Max Consecutive Days
**File**: `context/constraints/C3_consecutive_days.py`

**Changes**:
- Added APGD-D10 employee detection at constraint start
- Set `emp_max_consecutive = 8` for APGD-D10, `12` for standard
- Applied employee-specific limit in rolling window constraints
- Updated constraint descriptions and logging

**Impact**: APGD-D10 employees limited to 8 consecutive work days (vs 12 standard)

### Phase 3: C5 - Weekly Rest Day
**File**: `context/constraints/C5_offday_rules.py`

**Changes**:
- Added APGD-D10 employee detection
- Skip weekly rest day constraint for APGD-D10 employees
- Updated constraint descriptions to note exemption

**Impact**: APGD-D10 employees can work 7 days/week (exempt from weekly rest day requirement)

### Phase 4: C4 - Minimum Rest Period
**File**: `context/constraints/C4_rest_period.py`

**Changes**:
- Added APGD-D10 employee detection
- Set `emp_min_rest = 8h` for APGD-D10, `11h` for standard
- Applied employee-specific rest period in disjunctive constraints
- Updated default from 8h to 11h (standard MOM)

**Impact**: APGD-D10 employees require only 8-hour gaps (vs 11h standard)

### Phase 5: C19 - APGD-D10 Monthly Cap (NEW)
**File**: `context/constraints/C19_apgd_d10_monthly_cap.py` (NEW FILE)

**Features**:
- Detects APGD-D10 employees and categorizes them
- Groups slots by (employee, month)
- Calculates net hours per slot (gross - lunch)
- Enforces monthly caps: 224-246h (standard) or 244-268h (foreign CPL/SGT)
- Scales caps by days in month (28/29/30/31)
- Uses integer minutes for CP-SAT compatibility

**Cap Table**:
```python
MONTHLY_CAPS = {
    (28, 'standard'): 224,
    (28, 'foreign_cpl_sgt'): 244,
    (29, 'standard'): 231,
    (29, 'foreign_cpl_sgt'): 252,
    (30, 'standard'): 238,
    (30, 'foreign_cpl_sgt'): 260,
    (31, 'standard'): 246,
    (31, 'foreign_cpl_sgt'): 268,
}
```

## Testing

### Test Input Prepared
**File**: `input/RST-20251214-APGD-D10_Test.json`
- 86 employees (54 Scheme A, 32 Scheme B)
- All productTypeId = "APO"
- All rankId = "SER" (standard category, 246h cap)
- All local = 0 (foreigners)
- Pattern: ["D","D","D","D","D","O","O"] (5-day pattern)
- **Modified**: Added `"enableAPGD-D10": true` to requirement

### Expected Outcomes
When solver runs with APGD-D10 enabled:

1. **C3 Constraint**: Max 8 consecutive days per employee (not 12)
2. **C4 Constraint**: 8-hour minimum rest between shifts (not 11h)
3. **C5 Constraint**: No weekly rest day requirement (can work 7 days)
4. **C19 Constraint**: Monthly hours ≤ 246h per employee (31-day month)
5. **Hour Breakdown**: 
   - 5-day weeks: 44h normal + 11h OT per week
   - No rest day pay (only 5 days, not 6+)
6. **Employee Count**: Potentially lower than standard (can work more days)

### Test Commands

**Quick syntax check** (PASSED ✅):
```bash
python -c "from context.engine.time_utils import is_apgd_d10_employee; print('OK')"
```

**Detection logic test** (PASSED ✅):
```bash
python -c "
from context.engine.time_utils import is_apgd_d10_employee, get_apgd_d10_category
emp = {'scheme': 'Scheme A', 'productTypeId': 'APO'}
req = {'enableAPGD-D10': True}
print('Detected:', is_apgd_d10_employee(emp, req))  # True
emp2 = {'local': 0, 'rankId': 'CPL'}
print('Category:', get_apgd_d10_category(emp2))  # foreign_cpl_sgt
"
```

**Full solver test**:
```bash
python src/run_solver.py --in input/RST-20251214-APGD-D10_Test.json --time 60
```

### Test Checklist
- [ ] Constraint imports work (C3, C4, C5, C19)
- [ ] APGD-D10 employees detected correctly
- [ ] C3 enforces 8-day consecutive limit
- [ ] C5 allows 7-day work weeks
- [ ] C4 enforces 8-hour rest gaps
- [ ] C19 enforces 246h monthly cap
- [ ] Rest day pay calculated for 6/7-day patterns
- [ ] Output includes correct normal/OT/RDP breakdown

## Integration Points

### Constraint Loading
Constraints auto-load via `pkgutil` in `solver_engine.py`. C19 will be automatically discovered and loaded when constraint module is scanned.

### Output Builder (Phase 6 - TODO)
Need to integrate `calculate_apgd_d10_hours()` into output builder:
- Check if employee is APGD-D10 before calling standard `calculate_mom_compliant_hours()`
- Use `calculate_apgd_d10_hours()` for APGD-D10 employees
- Returns same structure: `{gross, lunch, normal, ot, restDayPay, paid}`

**File to modify**: `src/output_builder.py` (async) or `src/run_solver.py` (CLI)

### ICPMP Integration (Optional Enhancement)
Could enhance `config_optimizer_v3.py` to calculate APGD-D10 capacity:
```python
if enable_apgd_d10 and scheme == 'A':
    # 246h ÷ 4.33 weeks ÷ 11h/shift = 5.18 shifts/week
    effective_days_per_week = 246.0 / 4.33 / 11.0
```

## Known Limitations

1. **Output Builder**: Not yet integrated with `calculate_apgd_d10_hours()` - still uses standard calculation
2. **Pattern Generation**: ICPMP doesn't optimize for APGD-D10 capacity yet
3. **Mixed Schedules**: If one requirement has APGD-D10 and another doesn't, employees can only be assigned to one type
4. **Incremental Solving**: Locked consecutive days logic not yet tested with 8-day limit

## Deployment Steps

1. **Test locally** with prepared input:
   ```bash
   python src/run_solver.py --in input/RST-20251214-APGD-D10_Test.json --time 60
   ```

2. **Verify constraints** in solver logs:
   ```
   [C3] APGD-D10 detected: X employees with 8-day consecutive limit
   [C4] APGD-D10 detected: X employees with 8-hour minimum rest
   [C5] APGD-D10 detected: X employees EXEMPT from weekly rest day
   [C19] APGD-D10 Monthly Hour Cap: X employees
   ```

3. **Check output** for correct hour breakdown:
   - `normalHours` ≤ 44h per week
   - `overtimeHours` calculated correctly
   - `restDayPay` = 0, 1, or 2 based on days worked

4. **Commit changes**:
   ```bash
   git add context/engine/time_utils.py
   git add context/constraints/C3_consecutive_days.py
   git add context/constraints/C4_rest_period.py
   git add context/constraints/C5_offday_rules.py
   git add context/constraints/C19_apgd_d10_monthly_cap.py
   git commit -m "feat: Add APGD-D10 special group support (8-day limit, 7-day weeks, monthly caps)"
   ```

5. **Deploy to production**:
   ```bash
   ./scripts/deploy_update.sh
   ```

## Success Metrics

- ✅ All 4 detection functions implemented and tested
- ✅ C3 modified for 8-day consecutive limit
- ✅ C4 modified for 8-hour rest periods
- ✅ C5 modified to exempt APGD-D10 from weekly rest
- ✅ C19 created for monthly hour caps
- ✅ Test input prepared with enableAPGD-D10 flag
- ✅ Syntax checks passed
- ✅ Detection logic tests passed
- ⏳ Full solver test pending
- ⏳ Output builder integration pending

## Next Steps (Phase 6)

1. **Integrate hour calculation** into output builder:
   - Modify `src/output_builder.py` (async API)
   - Modify `src/run_solver.py` (CLI solver)
   - Use `calculate_apgd_d10_hours()` for APGD-D10 employees

2. **Test with full solve**:
   - Run 60s test with prepared input
   - Verify all constraint logs appear
   - Check output hour breakdown accuracy

3. **Update documentation**:
   - Add APGD-D10 to [README.md](README.md)
   - Update [FASTAPI_QUICK_REFERENCE.md](implementation_docs/FASTAPI_QUICK_REFERENCE.md)
   - Document in [CONSTRAINT_ARCHITECTURE.md](implementation_docs/CONSTRAINT_ARCHITECTURE.md)

4. **Production deployment**:
   - Test on staging environment
   - Deploy to production EC2
   - Monitor first production use

## References

- **MOM Approval**: APGD - D10
- **Spreadsheet**: APGD-D10 hour breakdown calculations
- **Screenshot**: Weekly hour patterns (4/5/6/7 days)
- **Input**: RST-20251214-FF942E24 (86 employees)
- **Context**: [.github/copilot-instructions.md](.github/copilot-instructions.md)
