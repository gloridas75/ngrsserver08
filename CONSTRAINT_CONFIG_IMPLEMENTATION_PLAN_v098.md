# Constraint Configuration Implementation Plan v0.98

**Date:** 2025-12-22  
**Goal:** Make ALL constraint parameters configurable via input JSON (scheme-specific)  
**Status:** Ready for implementation

---

## 1. User Clarifications & Corrections

### ✅ **Parttimer Hours - ALREADY CORRECT**
Current implementation:
```python
# solver_engine.py line 1409
limit = 34.98 if working_days <= 4 else 29.98
```
**Status:** ✅ No changes needed! Logic matches Excel (34.98h for ≤4 days, 29.98h for >4 days)

### ✅ **APGD-D10 = Scheme A + APO**
- APGD-D10 is simply: **Scheme A employees with Product Type = APO**
- No need for separate "APGD-D10" handling in constraints
- Excel now captures this as Scheme A values
- **Already handled in v0.96 implementation!** (automatic detection via `is_apgd_d10_employee()`)

### ✅ **Scheme P - Keep 1 Shift Per Day**
- No need to implement 2-shift logic now
- Will revisit later when needed
- **Status:** No changes needed

---

## 2. Updated Constraint Matrix (From Excel Screenshot)

| # | Constraint | Code | General | A | B | P | Notes |
|---|------------|------|---------|---|---|---|-------|
| 1 | **Max Consecutive Working Days** | maxConsecutiveWorkingDays | 12 | **8** | 12 | 12 | A=8 is APGD-D10 (A+APO) |
| 2 | **Daily Working Hours Cap** | momDailyHoursCap | 9 | 14 | 13 | 9 | Scheme-specific |
| 3 | **Weekly Working Hours Cap** | momWeeklyHoursCap44h | 44 | 44 | 44 | 44 | Same for all |
| 4 | **One Off Day Per Week** | minimumOffDaysPerWeek | 1 | **0** | 1 | 1 | A=0 is APGD-D10 (A+APO) |
| 5 | **Monthly Overtime Cap** | momMonthlyOTcap72h | 72 | 72 | 72 | 72 | Same for all |
| 6 | **Daily Meal Break** | momLunchBreak | 60 | 60 | 60 | 60 | Same for all (minutes) |
| 7 | **Minimum Rest Between Shifts** | apgdMinRestBetweenShifts | 8 | 8 | 8 | **1** | P=1h (allows split shifts) |
| 8 | **Maximum Shifts Per Day** | oneShiftPerDay | 1 | 1 | 1 | 1 | Keep simple for now |
| 9 | **Parttimers Weekly Hours** | partTimerWeeklyHours | - | - | - | 34.98/29.98 | ✅ Already correct! |

**Key Insights:**
- **No Scheme B exceptions** (B follows general rules: 12 days, 1 off-day)
- **Scheme A variations** are all APGD-D10 (A+APO): 8 consecutive days, 0 off-days
- **Scheme P variations:** 1h rest only (allows 2 shifts with gap)

---

## 3. Current Implementation Status

### ✅ **Already Correct:**
1. ✅ **Parttimer limits** - 34.98h (≤4 days), 29.98h (>4 days) in [solver_engine.py](context/engine/solver_engine.py#L1409)
2. ✅ **APGD-D10 detection** - via `is_apgd_d10_employee()` in [time_utils.py](context/engine/time_utils.py) (v0.96)
3. ✅ **Scheme normalization** - via `normalize_schemes()` in [time_utils.py](context/engine/time_utils.py) (v0.96)

### ⚠️ **HARDCODED (Need to make configurable):**

1. **C1_mom_daily_hours.py** (Lines 60-62)
   ```python
   max_gross_by_scheme = {
       'A': 14.0,
       'B': 13.0,
       'P': 9.0
   }
   ```
   **Issue:** Hardcoded, should read from JSON

2. **C3_consecutive_days.py** (Lines 57-58)
   ```python
   max_consecutive = 12  # General
   apgd_max_consecutive = 8  # APGD-D10 (Scheme A + APO)
   ```
   **Issue:** Hardcoded, should read from JSON with scheme support

3. **C2_mom_weekly_hours_pattern_aware.py**
   ```python
   max_weekly_hours = 44  # Hardcoded
   ```
   **Issue:** Hardcoded, should read from JSON

4. **C4_rest_period.py** (Lines 52-53)
   ```python
   default_min_rest_minutes = 660  # 11 hours (standard MOM)
   apgd_min_rest_minutes = 480  # 8 hours (APGD-D10)
   ```
   **Issue:** Partially reads from JSON (line 60-63), but needs scheme-specific support
   **Excel shows:** General/A/B=8h, **P=1h** (NOT IMPLEMENTED!)

5. **C5_offday_rules.py**
   - Need to verify implementation
   - Should support: General/B/P=1 off-day, **A (APGD-D10)=0 off-days**

6. **C17_ot_monthly_cap.py**
   ```python
   max_monthly_ot = 72  # Hardcoded
   ```
   **Issue:** Hardcoded, should read from JSON

7. **time_utils.py - Meal break deduction**
   ```python
   lunch_deduct_minutes = 60  # Hardcoded
   ```
   **Issue:** Hardcoded, should read from JSON

---

## 4. Proposed Solution: Helper Function Pattern

### Design Philosophy
1. **Centralized helper function** for reading constraint params
2. **Scheme-specific overrides** with fallback to general
3. **Backward compatible** with current hardcoded defaults
4. **Product-type aware** (for APGD-D10 = A + APO)

### Core Helper Function

```python
# context/engine/constraint_config.py (NEW FILE)

def get_constraint_param(ctx: dict, 
                        constraint_id: str, 
                        param_name: str, 
                        scheme: str = None,
                        product_types: list = None,
                        default=None):
    """
    Get constraint parameter with scheme-specific and product-type-specific support.
    
    Priority order:
    1. Scheme + product-type specific (e.g., 'A' + 'APO' → APGD-D10 rules)
    2. Scheme-specific (e.g., 'maxConsecutiveDaysA')
    3. General parameter (e.g., 'maxConsecutiveDaysGeneral')
    4. Base parameter (e.g., 'maxConsecutiveDays') - backward compatibility
    5. Default value (hardcoded fallback)
    
    Args:
        ctx: Context dict with 'constraintList'
        constraint_id: Constraint identifier (e.g., 'momDailyHoursCap')
        param_name: Base parameter name (e.g., 'maxDailyHours')
        scheme: Employee scheme ('A', 'B', 'P', or None)
        product_types: Employee product types (e.g., ['APO'] for APGD-D10)
        default: Default value if not found
    
    Returns:
        Parameter value (scheme-specific > general > default)
    
    Examples:
        # Daily hours for Scheme A
        max_hours = get_constraint_param(ctx, 'momDailyHoursCap', 
                                        'maxDailyHours', scheme='A', default=14.0)
        
        # Consecutive days for Scheme A + APO (APGD-D10)
        max_days = get_constraint_param(ctx, 'maxConsecutiveWorkingDays',
                                       'maxConsecutiveDays', 
                                       scheme='A', product_types=['APO'], default=8)
    """
    from context.engine.time_utils import is_apgd_d10_employee
    
    constraint_list = ctx.get('constraintList', [])
    
    # Find the constraint
    for constraint in constraint_list:
        if constraint.get('id') != constraint_id:
            continue
        
        params = constraint.get('params', {})
        
        # Priority 1: APGD-D10 specific (Scheme A + APO product type)
        if scheme == 'A' and product_types and 'APO' in product_types:
            # For APGD-D10, use Scheme A values (already captured in Excel)
            # No special handling needed - will fall through to scheme-specific
            pass
        
        # Priority 2: Scheme-specific parameter (e.g., 'maxDailyHoursA')
        if scheme:
            scheme_param_name = f"{param_name}{scheme}"
            if scheme_param_name in params:
                return params[scheme_param_name]
        
        # Priority 3: General parameter (e.g., 'maxDailyHoursGeneral')
        general_param_name = f"{param_name}General"
        if general_param_name in params:
            return params[general_param_name]
        
        # Priority 4: Base parameter (backward compatibility)
        if param_name in params:
            return params[param_name]
    
    # Priority 5: Default value
    return default


def get_scheme_param(ctx: dict, constraint_id: str, param_name: str, 
                    employee: dict, default=None):
    """
    Convenience wrapper - get constraint param for a specific employee.
    
    Automatically extracts scheme and product types from employee dict.
    
    Args:
        ctx: Context dict
        constraint_id: Constraint ID
        param_name: Parameter name
        employee: Employee dict with 'scheme' and 'productTypes'
        default: Default value
    
    Returns:
        Parameter value for this employee's scheme
    """
    from context.engine.time_utils import normalize_scheme
    
    scheme_raw = employee.get('scheme', 'A')
    scheme = normalize_scheme(scheme_raw)
    product_types = employee.get('productTypes', [])
    
    return get_constraint_param(ctx, constraint_id, param_name, 
                               scheme=scheme, product_types=product_types, 
                               default=default)
```

---

## 5. Implementation Plan

### Phase 1: Create Helper Module (1 day)

**Tasks:**
- [ ] Create `context/engine/constraint_config.py`
- [ ] Implement `get_constraint_param()` function
- [ ] Implement `get_scheme_param()` convenience function
- [ ] Add unit tests for helper functions

**Test Coverage:**
```python
# Test scheme-specific
assert get_constraint_param(ctx, 'momDailyHoursCap', 'maxDailyHours', 'A') == 14
assert get_constraint_param(ctx, 'momDailyHoursCap', 'maxDailyHours', 'B') == 13

# Test APGD-D10 (A + APO)
assert get_constraint_param(ctx, 'maxConsecutiveWorkingDays', 
                           'maxConsecutiveDays', 'A', ['APO']) == 8

# Test fallback to general
assert get_constraint_param(ctx, 'momWeeklyHoursCap44h', 
                           'maxWeeklyHours', 'A') == 44

# Test default fallback
assert get_constraint_param(ctx, 'unknownConstraint', 'param', default=99) == 99
```

---

### Phase 2: Update Constraint Files (2 days)

#### **2.1 C1_mom_daily_hours.py - Daily Hours Cap**

**Current (Lines 59-63):**
```python
# Hardcoded scheme-specific limits
max_gross_by_scheme = {
    'A': 14.0,  # Scheme A: max 14 hours per day
    'B': 13.0,  # Scheme B: max 13 hours per day
    'P': 9.0    # Scheme P: max 9 hours per day
}
```

**New Implementation:**
```python
from context.engine.constraint_config import get_constraint_param

# Read from constraintList with scheme-specific support
max_gross_by_scheme = {
    'A': get_constraint_param(ctx, 'momDailyHoursCap', 'maxDailyHours', 'A', default=14.0),
    'B': get_constraint_param(ctx, 'momDailyHoursCap', 'maxDailyHours', 'B', default=13.0),
    'P': get_constraint_param(ctx, 'momDailyHoursCap', 'maxDailyHours', 'P', default=9.0)
}
```

---

#### **2.2 C3_consecutive_days.py - Consecutive Working Days**

**Current (Lines 57-58):**
```python
max_consecutive = 12  # Default: at most 12 consecutive working days
apgd_max_consecutive = 8  # APGD-D10: at most 8 consecutive working days
```

**New Implementation:**
```python
from context.engine.constraint_config import get_constraint_param
from context.engine.time_utils import is_apgd_d10_employee, normalize_scheme

# Per-employee consecutive day limits
for emp in employees:
    emp_id = emp.get('employeeId')
    scheme = normalize_scheme(emp.get('scheme', 'A'))
    product_types = emp.get('productTypes', [])
    
    # Check if APGD-D10 (Scheme A + APO)
    if is_apgd_d10_employee(emp):
        # APGD-D10 uses Scheme A value (should be 8 in Excel)
        max_consecutive = get_constraint_param(ctx, 'maxConsecutiveWorkingDays',
                                             'maxConsecutiveDays', 'A', 
                                             product_types, default=8)
    else:
        # Standard scheme limits
        max_consecutive = get_constraint_param(ctx, 'maxConsecutiveWorkingDays',
                                             'maxConsecutiveDays', scheme, 
                                             default=12)
    
    # Apply constraint with employee-specific limit...
```

**Alternative (Simpler):**
```python
from context.engine.constraint_config import get_scheme_param

# Direct lookup per employee
for emp in employees:
    max_consecutive = get_scheme_param(ctx, 'maxConsecutiveWorkingDays',
                                      'maxConsecutiveDays', emp, default=12)
    # This automatically handles APGD-D10 (A+APO → uses Scheme A value)
```

---

#### **2.3 C4_rest_period.py - Minimum Rest Between Shifts**

**Current Issue:** Reads from JSON but doesn't support scheme-specific (especially **Scheme P = 1 hour**)

**Current (Lines 52-63):**
```python
default_min_rest_minutes = 660  # Default: 11 hours (standard MOM)
apgd_min_rest_minutes = 480  # APGD-D10: 8 hours

# Read from constraintList
constraint_list = ctx.get('constraintList', [])
for constraint in constraint_list:
    if constraint.get('id') == 'apgdMinRestBetweenShifts':
        default_min_rest_minutes = constraint.get('params', {}).get('minRestMinutes', 660)
```

**New Implementation:**
```python
from context.engine.constraint_config import get_scheme_param

# Per-employee rest period (supports Scheme P = 1 hour!)
for emp in employees:
    # Default is 8 hours (480 min), but Scheme P can be 1 hour (60 min)
    min_rest_hours = get_scheme_param(ctx, 'apgdMinRestBetweenShifts',
                                     'minRestHours', emp, default=8)
    min_rest_minutes = min_rest_hours * 60
    
    # Apply constraint...
```

**CRITICAL:** This enables Scheme P with 1-hour rest (allows 2 shifts per day pattern)

---

#### **2.4 C2_mom_weekly_hours_pattern_aware.py - Weekly Hours Cap**

**Current:**
```python
max_weekly_hours = 44  # Hardcoded
```

**New:**
```python
from context.engine.constraint_config import get_constraint_param

max_weekly_hours = get_constraint_param(ctx, 'momWeeklyHoursCap44h',
                                       'maxWeeklyHours', default=44)
```

---

#### **2.5 C5_offday_rules.py - Minimum Off Days Per Week**

**Need to verify:** Does it handle APGD-D10 (Scheme A + APO) = 0 off-days?

**New Implementation:**
```python
from context.engine.constraint_config import get_scheme_param

for emp in employees:
    # APGD-D10 (A+APO) should get 0, others get 1
    min_off_days = get_scheme_param(ctx, 'minimumOffDaysPerWeek',
                                   'minOffDaysPerWeek', emp, default=1)
    
    # Apply constraint...
```

---

#### **2.6 C17_ot_monthly_cap.py - Monthly OT Cap**

**Current:**
```python
max_monthly_ot = 72  # Hardcoded
```

**New:**
```python
from context.engine.constraint_config import get_constraint_param

max_monthly_ot = get_constraint_param(ctx, 'momMonthlyOTcap72h',
                                     'maxMonthlyOtHours', default=72)
```

---

#### **2.7 time_utils.py - Meal Break Deduction**

**Current (multiple locations):**
```python
lunch_deduct_minutes = 60  # Hardcoded
```

**New:**
```python
from context.engine.constraint_config import get_constraint_param

lunch_deduct_minutes = get_constraint_param(ctx, 'momLunchBreak',
                                           'deductMinutes', default=60)
```

---

### Phase 3: Update Input JSON Schema (1 day)

**Create updated input template with all configurable params:**

```json
{
  "schemaVersion": "0.98",
  "constraintList": [
    {
      "id": "maxConsecutiveWorkingDays",
      "enforcement": "hard",
      "description": "Max consecutive working days (scheme-specific)",
      "params": {
        "maxConsecutiveDaysGeneral": 12,
        "maxConsecutiveDaysA": 8,
        "maxConsecutiveDaysB": 12,
        "maxConsecutiveDaysP": 12
      }
    },
    {
      "id": "momDailyHoursCap",
      "enforcement": "hard",
      "description": "Max daily hours (scheme-specific)",
      "params": {
        "maxDailyHoursGeneral": 9,
        "maxDailyHoursA": 14,
        "maxDailyHoursB": 13,
        "maxDailyHoursP": 9
      }
    },
    {
      "id": "momWeeklyHoursCap44h",
      "enforcement": "hard",
      "description": "Weekly normal hours cap",
      "params": {
        "maxWeeklyHours": 44
      }
    },
    {
      "id": "minimumOffDaysPerWeek",
      "enforcement": "hard",
      "description": "Minimum off-days per week (scheme-specific)",
      "params": {
        "minOffDaysPerWeekGeneral": 1,
        "minOffDaysPerWeekA": 0,
        "minOffDaysPerWeekB": 1,
        "minOffDaysPerWeekP": 1
      }
    },
    {
      "id": "momMonthlyOTcap72h",
      "enforcement": "hard",
      "description": "Monthly OT hours cap",
      "params": {
        "maxMonthlyOtHours": 72
      }
    },
    {
      "id": "momLunchBreak",
      "enforcement": "hard",
      "description": "Meal break deduction",
      "params": {
        "deductMinutes": 60,
        "deductIfShiftAtLeastMinutes": 480
      }
    },
    {
      "id": "apgdMinRestBetweenShifts",
      "enforcement": "hard",
      "description": "Minimum rest between shifts (hours, scheme-specific)",
      "params": {
        "minRestHoursGeneral": 8,
        "minRestHoursA": 8,
        "minRestHoursB": 8,
        "minRestHoursP": 1
      }
    },
    {
      "id": "oneShiftPerDay",
      "enforcement": "hard",
      "description": "Maximum shifts per day",
      "params": {
        "maxShiftsPerDay": 1
      }
    },
    {
      "id": "partTimerWeeklyHours",
      "enforcement": "hard",
      "description": "Part-timer weekly normal hour limits",
      "params": {
        "maxHours4Days": 34.98,
        "maxHoursMoreDays": 29.98
      }
    }
  ]
}
```

---

### Phase 4: Testing (1 day)

**Test Cases:**

1. **Scheme-Specific Constraints:**
   - [ ] Scheme A with APO (APGD-D10): 8 consecutive days, 0 off-days
   - [ ] Scheme A without APO: 12 consecutive days, 1 off-day
   - [ ] Scheme B: 13h daily, 12 consecutive days, 1 off-day
   - [ ] Scheme P: 9h daily, 1h rest, 34.98h/29.98h weekly

2. **Backward Compatibility:**
   - [ ] Old input format (without scheme-specific params) uses defaults
   - [ ] Constraints still enforce correctly with fallback values

3. **Edge Cases:**
   - [ ] Missing constraintList → uses hardcoded defaults
   - [ ] Partial constraint params → falls back to general/default
   - [ ] Invalid schemes → falls back to general

**Test Files:**
```bash
# Create test inputs
input/test_scheme_a_apgd.json       # A + APO employee
input/test_scheme_b_config.json     # B with 13h daily cap
input/test_scheme_p_rest.json       # P with 1h rest
input/test_backward_compat.json     # Old format without scheme params

# Run tests
pytest tests/test_constraint_configuration.py -v
pytest tests/test_scheme_specific_constraints.py -v
```

---

## 6. Summary of Changes

### Files to CREATE:
1. ✅ `context/engine/constraint_config.py` - Helper functions
2. ✅ `tests/test_constraint_configuration.py` - Test suite
3. ✅ `input/input_v098_template.json` - Updated input template

### Files to MODIFY:
1. ✅ `context/constraints/C1_mom_daily_hours.py` - Read daily hours from JSON
2. ✅ `context/constraints/C3_consecutive_days.py` - Read consecutive days from JSON
3. ✅ `context/constraints/C4_rest_period.py` - Add scheme-specific rest (P=1h!)
4. ✅ `context/constraints/C2_mom_weekly_hours_pattern_aware.py` - Read weekly cap
5. ✅ `context/constraints/C5_offday_rules.py` - Support A (APGD-D10) = 0 off-days
6. ✅ `context/constraints/C17_ot_monthly_cap.py` - Read monthly cap
7. ✅ `context/engine/time_utils.py` - Read meal break minutes
8. ✅ `context/schemas/input_schema_v098.json` - Update schema

### Files to DOCUMENT:
1. ✅ Update [CONSTRAINT_ARCHITECTURE.md](implementation_docs/CONSTRAINT_ARCHITECTURE.md)
2. ✅ Update [README.md](README.md) - v0.98 features
3. ✅ Create `CONSTRAINT_CONFIG_GUIDE.md` - How to configure constraints

---

## 7. Timeline Estimate

| Phase | Duration | Deliverables |
|-------|----------|-------------|
| Phase 1: Helper Module | 1 day | `constraint_config.py` + unit tests |
| Phase 2: Update Constraints | 2 days | 7 constraint files updated |
| Phase 3: Schema & Docs | 1 day | Input template + documentation |
| Phase 4: Testing | 1 day | Test suite + regression tests |
| **TOTAL** | **5 days** | v0.98 release ready |

---

## 8. Risk Assessment

### ✅ LOW RISK:
- Helper function is non-invasive (adds capability, doesn't break existing)
- Backward compatible (defaults maintain current behavior)
- APGD-D10 logic already tested (v0.96)
- Parttimer logic already correct

### ⚠️ MEDIUM RISK:
- Scheme P with 1h rest is NEW behavior (needs careful testing)
- Multiple constraint files changing simultaneously (need thorough regression)

### Mitigation:
- Implement one constraint at a time
- Test each constraint independently before moving to next
- Keep hardcoded defaults as fallback

---

## 9. Success Criteria

- [ ] All 9 constraints read parameters from input JSON
- [ ] Scheme-specific overrides work correctly (A/B/P)
- [ ] APGD-D10 (A+APO) uses Scheme A values automatically
- [ ] Scheme P with 1h rest functions correctly
- [ ] Backward compatibility maintained (old inputs still work)
- [ ] All tests passing (unit + integration)
- [ ] Documentation updated

---

## 10. Next Steps

**Ready to proceed with implementation?**

**Recommended Approach:**
1. Start with Phase 1 (helper module) - foundation
2. Test helper module thoroughly
3. Update constraints one-by-one (C1 → C3 → C4 → etc.)
4. Test after each constraint update
5. Full regression test at end

**Let me know if you'd like to:**
- ✅ Proceed with implementation (Phase 1 first)
- ❓ Discuss any specific constraint behavior
- ❓ Review the helper function design
- ❓ Adjust the implementation order

---

**Questions for clarification:**

1. **Scheme P Rest Period:** Excel shows P=1h. Should this apply to ALL Scheme P employees, or only when they work 2 shifts per day pattern?

2. **APGD-D10 Off Days:** Excel shows A=0 off-days. Should this apply to ALL Scheme A, or only A+APO (APGD-D10)?

3. **Implementation Priority:** Any specific constraint that's more urgent than others?
