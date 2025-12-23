# Constraint Configuration Analysis & Redesign Proposal

**Date:** 2025-12-22  
**Issue:** Scheme-specific constraint values are hardcoded  
**Goal:** Read constraint values from input JSON with scheme-specific support

---

## 1. Current State Analysis

### ✅ Constraints Currently Implemented

Based on code analysis, here's what's implemented:

| # | Constraint | Excel Name | Code File | Current Status |
|---|------------|------------|-----------|----------------|
| 1 | **Max Consecutive Working Days** | maxConsecutiveWorkingDays | C3_consecutive_days.py | ⚠️ **HARDCODED** - General: 12, APGD: 8 |
| 2 | **Max Consecutive Night Shifts** | maxConsecutiveNights | ❌ **NOT IMPLEMENTED** | ❌ Missing |
| 3 | **Daily Working Hours Cap** | momDailyHoursCap | C1_mom_daily_hours.py | ⚠️ **HARDCODED** - A: 14h, B: 13h, P: 9h |
| 4 | **Weekly Working Hours Cap** | momWeeklyHoursCap44h | C2_mom_weekly_hours_pattern_aware.py | ⚠️ **HARDCODED** - All schemes: 44h |
| 5 | **One Off Day Per Week** | minimumOffDaysPerWeek | C5_offday_rules.py | ⚠️ **PARTIALLY** - General: 1, APGD: 0 |
| 6 | **Monthly Overtime Cap** | momMonthlyOTcap72h | C17_ot_monthly_cap.py | ⚠️ **HARDCODED** - All schemes: 72h |
| 7 | **Daily Meal Break** | momLunchBreak | (time_utils.py) | ⚠️ **HARDCODED** - All: 60 min |
| 8 | **Minimum Rest Between Shifts** | apgdMinRestBetweenShifts | C4_rest_period.py | ✅ **PARTIALLY CONFIGURABLE** - Reads from constraintList |
| 9 | **Maximum shifts per day** | oneShiftPerDay | C16_no_overlap.py | ⚠️ **IMPLICIT** - Always 1 shift |
| 10 | **Parttimers Weekly Hours** | partTimerWeeklyHours | C6_parttimer_limits.py | ⚠️ **HARDCODED** - ≤4 days: 34.98h, >4 days: 29.98h |

---

## 2. Critical Findings

### ❌ **NOT IMPLEMENTED:**
1. **Max Consecutive Night Shifts** (Row 2 in Excel)
   - Excel shows: General: 12, A: 12, B: 6, P: 12
   - No constraint file exists for this
   - **Action Required:** Create C18_consecutive_nights.py

### ⚠️ **HARDCODED VALUES:**

#### C1_mom_daily_hours.py (Line 60-62)
```python
max_gross_by_scheme = {
    'A': 14.0,  # Scheme A: max 14 hours per day
    'B': 13.0,  # Scheme B: max 13 hours per day
    'P': 9.0    # Scheme P: max 9 hours per day
}
```
**Issue:** Should support scheme-specific values from input JSON

#### C3_consecutive_days.py (Line 57-58)
```python
max_consecutive = 12  # Default: at most 12 consecutive working days
apgd_max_consecutive = 8  # APGD-D10: at most 8 consecutive working days
```
**Issue:** Excel shows Scheme B should be 6 days, not 12!

#### C6_parttimer_limits.py
```python
# Hardcoded values for Scheme P
max_hours_4_days = 34.98
max_hours_more_days = 29.98
```
**Issue:** Excel shows 24.98 and 29.98 (not 34.98!)

---

## 3. Excel vs Current Implementation - DISCREPANCIES

### 🚨 **CRITICAL MISMATCHES:**

| Constraint | Scheme | Excel Value | Current Code | Status |
|------------|--------|-------------|--------------|--------|
| Max Consecutive Days | **B** | **6 days** | **12 days** | ❌ **WRONG!** |
| Min Off Days Per Week | **A** | **0 days** | **1 day** | ⚠️ **APGD-D10 only** |
| Parttimers Weekly (≤4 days) | **P** | **24.98h** | **34.98h** | ❌ **WRONG!** |
| Max Shifts Per Day | **P** | **2 shifts** | **1 shift** | ❌ **WRONG!** |
| Min Rest Between Shifts | **P** | **1 hour** | **8 hours** | ❌ **WRONG!** |

**IMPACT:** Current code may be producing incorrect rosters for Scheme B and Scheme P employees!

---

## 4. Proposed Solution Architecture

### Design Principles

1. **Backward Compatibility:** Support existing input format
2. **Scheme-Specific:** Allow per-scheme override of constraint values
3. **Default Values:** Fall back to hardcoded defaults if not specified
4. **Validation:** Validate constraint parameters at input stage

### Proposed JSON Schema

```json
{
  "schemaVersion": "0.98",
  "constraintList": [
    {
      "id": "momDailyHoursCap",
      "enforcement": "hard",
      "description": "Max daily hours by scheme",
      "params": {
        "maxDailyHoursGeneral": 9,    // Default for unspecified schemes
        "maxDailyHoursA": 14,          // Scheme A specific
        "maxDailyHoursB": 13,          // Scheme B specific
        "maxDailyHoursP": 9            // Scheme P specific
      }
    },
    {
      "id": "maxConsecutiveWorkingDays",
      "enforcement": "hard",
      "description": "Max consecutive working days",
      "params": {
        "maxConsecutiveDaysGeneral": 12,  // Default
        "maxConsecutiveDaysA": 12,        // Scheme A
        "maxConsecutiveDaysB": 6,         // Scheme B (IMPORTANT!)
        "maxConsecutiveDaysP": 12         // Scheme P
      }
    },
    {
      "id": "maxConsecutiveNights",
      "enforcement": "hard",
      "description": "Max consecutive night shifts",
      "params": {
        "maxConsecutiveNightsGeneral": 12,
        "maxConsecutiveNightsA": 12,
        "maxConsecutiveNightsB": 6,
        "maxConsecutiveNightsP": 12
      }
    },
    {
      "id": "minimumOffDaysPerWeek",
      "enforcement": "hard",
      "description": "Minimum off-days per week",
      "params": {
        "minOffDaysPerWeekGeneral": 1,
        "minOffDaysPerWeekA": 0,      // APGD-D10 can be 0
        "minOffDaysPerWeekB": 1,
        "minOffDaysPerWeekP": 1
      }
    },
    {
      "id": "apgdMinRestBetweenShifts",
      "enforcement": "hard",
      "description": "Minimum rest between shifts (hours)",
      "params": {
        "minRestHoursGeneral": 8,
        "minRestHoursA": 8,
        "minRestHoursB": 8,
        "minRestHoursP": 1           // P: Only 1 hour! (2 shifts per day)
      }
    },
    {
      "id": "oneShiftPerDay",
      "enforcement": "hard",
      "description": "Maximum shifts per day",
      "params": {
        "maxShiftsPerDayGeneral": 1,
        "maxShiftsPerDayA": 1,
        "maxShiftsPerDayB": 1,
        "maxShiftsPerDayP": 2        // P can work 2 shifts!
      }
    },
    {
      "id": "partTimerWeeklyHours",
      "enforcement": "hard",
      "description": "Part-timer weekly hour limits",
      "params": {
        "maxHours4Days": 24.98,      // CORRECTED from 34.98
        "maxHoursMoreDays": 29.98
      }
    },
    {
      "id": "momWeeklyHoursCap44h",
      "enforcement": "hard",
      "description": "Weekly normal hours cap",
      "params": {
        "maxWeeklyHours": 44         // Same for all schemes
      }
    },
    {
      "id": "momMonthlyOTcap72h",
      "enforcement": "hard",
      "description": "Monthly OT cap",
      "params": {
        "maxMonthlyOtHours": 72      // Same for all schemes
      }
    },
    {
      "id": "momLunchBreak",
      "enforcement": "hard",
      "description": "Meal break deduction",
      "params": {
        "deductMinutes": 60,
        "deductIfShiftAtLeastMinutes": 480  // 8 hours
      }
    }
  ]
}
```

---

## 5. Implementation Strategy

### Phase 1: Create Helper Function (NEW)

Create `context/engine/constraint_config.py`:

```python
def get_constraint_value(ctx: dict, constraint_id: str, param_name: str, 
                        scheme: str = None, default=None):
    """
    Get constraint parameter value with scheme-specific override support.
    
    Args:
        ctx: Context dict with 'constraintList'
        constraint_id: Constraint identifier (e.g., 'momDailyHoursCap')
        param_name: Base parameter name (e.g., 'maxDailyHours')
        scheme: Employee scheme ('A', 'B', 'P', or None for general)
        default: Default value if not found
    
    Returns:
        Parameter value (scheme-specific if available, else general, else default)
    
    Examples:
        # Get daily hours cap for Scheme A
        max_hours = get_constraint_value(ctx, 'momDailyHoursCap', 
                                        'maxDailyHours', scheme='A')
        # Returns value from 'maxDailyHoursA' if present, else 'maxDailyHoursGeneral', else default
    """
    constraint_list = ctx.get('constraintList', [])
    
    for constraint in constraint_list:
        if constraint.get('id') != constraint_id:
            continue
        
        params = constraint.get('params', {})
        
        # Priority 1: Scheme-specific parameter
        if scheme:
            scheme_param_name = f"{param_name}{scheme}"
            if scheme_param_name in params:
                return params[scheme_param_name]
        
        # Priority 2: General parameter
        general_param_name = f"{param_name}General"
        if general_param_name in params:
            return params[general_param_name]
        
        # Priority 3: Base parameter (backward compatible)
        if param_name in params:
            return params[param_name]
    
    # Priority 4: Default value
    return default
```

### Phase 2: Update Constraint Files

#### C1_mom_daily_hours.py
```python
# OLD (lines 59-63):
max_gross_by_scheme = {
    'A': 14.0,
    'B': 13.0,
    'P': 9.0
}

# NEW:
from context.engine.constraint_config import get_constraint_value

max_gross_by_scheme = {
    'A': get_constraint_value(ctx, 'momDailyHoursCap', 'maxDailyHours', 'A', default=14.0),
    'B': get_constraint_value(ctx, 'momDailyHoursCap', 'maxDailyHours', 'B', default=13.0),
    'P': get_constraint_value(ctx, 'momDailyHoursCap', 'maxDailyHours', 'P', default=9.0)
}
```

#### C3_consecutive_days.py
```python
# OLD (lines 57-58):
max_consecutive = 12
apgd_max_consecutive = 8

# NEW:
from context.engine.constraint_config import get_constraint_value

# Per-scheme consecutive day limits
max_consecutive_by_scheme = {
    'A': get_constraint_value(ctx, 'maxConsecutiveWorkingDays', 'maxConsecutiveDays', 'A', default=12),
    'B': get_constraint_value(ctx, 'maxConsecutiveWorkingDays', 'maxConsecutiveDays', 'B', default=6),  # CORRECTED!
    'P': get_constraint_value(ctx, 'maxConsecutiveWorkingDays', 'maxConsecutiveDays', 'P', default=12)
}

# Get employee scheme and apply limit
for emp in employees:
    emp_scheme = normalize_scheme(emp.get('scheme', 'A'))
    emp_max_consecutive = max_consecutive_by_scheme.get(emp_scheme, 12)
    
    # APGD-D10 override (if applicable)
    if is_apgd_d10_employee(emp):
        emp_max_consecutive = 8  # APGD-D10 always 8 days
```

#### C16_no_overlap.py → Update for Scheme P (2 shifts per day)
```python
# NEW: Check if employee scheme allows multiple shifts per day
from context.engine.constraint_config import get_constraint_value

emp_scheme = normalize_scheme(emp.get('scheme', 'A'))
max_shifts_per_day = get_constraint_value(ctx, 'oneShiftPerDay', 'maxShiftsPerDay', 
                                         emp_scheme, default=1)

if max_shifts_per_day == 1:
    # Standard: Only 1 shift per day
    # (existing overlap prevention logic)
else:
    # Scheme P: Allow 2 shifts per day (with min 1h rest between)
    # Check rest period instead of full overlap
```

---

## 6. Migration Plan

### Week 1: Foundation
- [ ] Create `constraint_config.py` helper module
- [ ] Add unit tests for get_constraint_value()
- [ ] Update input_validator.py to validate new parameter format

### Week 2: Update Constraints
- [ ] Update C1 (daily hours) - scheme-specific
- [ ] Update C3 (consecutive days) - **FIX Scheme B to 6 days!**
- [ ] Update C4 (rest period) - Scheme P to 1 hour
- [ ] Update C6 (parttimer) - **FIX to 24.98h!**
- [ ] Update C16 (overlap) - Allow 2 shifts for Scheme P

### Week 3: New Constraints
- [ ] Create C18_consecutive_nights.py (missing constraint)
- [ ] Update C5 (off days) - Scheme A can be 0 for APGD-D10

### Week 4: Testing & Deployment
- [ ] Create test inputs with all scheme variations
- [ ] Run regression tests
- [ ] Update documentation
- [ ] Deploy to production

---

## 7. Benefits

### ✅ **Correctness**
- Fix Scheme B consecutive days (12 → 6 days)
- Fix Scheme P parttimer hours (34.98 → 24.98)
- Support Scheme P 2-shift capability

### ✅ **Flexibility**
- Operations can adjust constraint values without code changes
- Scheme-specific overrides for special cases
- Easy to test different regulatory scenarios

### ✅ **Maintainability**
- Single source of truth (input JSON)
- No more hardcoded magic numbers
- Clear mapping between Excel rules and implementation

### ✅ **Compliance**
- Accurate MOM regulation implementation
- Audit trail of constraint configurations
- Easy to verify against regulatory documents

---

## 8. Risks & Mitigations

### Risk 1: Breaking Existing Inputs
**Mitigation:** Maintain backward compatibility with default values

### Risk 2: Performance Impact
**Mitigation:** Cache constraint values at initialization

### Risk 3: Invalid Configurations
**Mitigation:** Strict validation in input_validator.py

---

## 9. Open Questions

1. **APGD-D10 Logic:** Should consecutive day limits respect both scheme AND APGD-D10?
   - Current: APGD-D10 overrides scheme (always 8 days)
   - Proposed: APGD-D10 is override for Scheme A only
   
2. **Scheme P Two-Shift Logic:** How to handle shift spacing?
   - Option A: Minimum 1-hour rest between shifts
   - Option B: Allow split shifts (AM + PM pattern)
   
3. **Night Shift Definition:** What constitutes a "night shift"?
   - Proposal: Any shift with >= 4 hours between 22:00-06:00

---

## 10. Recommendation

**PRIORITY: HIGH**

1. **Immediate Actions:**
   - Fix Scheme B consecutive days (12 → 6) - **CRITICAL BUG**
   - Fix Scheme P parttimer hours (34.98 → 24.98)
   - Implement Scheme P 2-shift capability

2. **Short-Term (2 weeks):**
   - Create constraint_config.py helper
   - Update all hardcoded constraints to read from JSON
   - Add scheme-specific parameter support

3. **Medium-Term (1 month):**
   - Implement C18_consecutive_nights.py
   - Full regression testing with scheme variations
   - Update all documentation

**Estimated Effort:** 2-3 weeks full implementation

---

**Ready to proceed?** We can start with Phase 1 (helper function) or fix the critical bugs first.
