# Improved Constraint JSON Format - v0.98

**Design Goal:** Clean, intuitive constraint configuration with minimal redundancy

---

## Design Principles

1. **Simplicity First:** Only specify filters (employeeType, productTypes, ranks) when needed
2. **Default to "All":** If filters omitted, constraint applies to all employees
3. **Scheme-Based Overrides:** Support per-scheme values with fallback to default
4. **Backward Compatible:** Support both old and new formats during migration

---

## Proposed JSON Structure

### Option A: Flat Structure with Scheme Overrides (RECOMMENDED)

```json
{
  "constraintList": [
    {
      "id": "momDailyHoursCap",
      "enforcement": "hard",
      "description": "Maximum daily working hours by scheme",
      "defaultValue": 9,
      "schemeOverrides": {
        "A": 14,
        "B": 13,
        "P": 9
      }
    },
    {
      "id": "maxConsecutiveWorkingDays",
      "enforcement": "hard",
      "description": "Maximum consecutive working days",
      "defaultValue": 12,
      "schemeOverrides": {
        "A": {
          "productTypes": ["APO"],
          "value": 8,
          "description": "APGD-D10 can work 8 consecutive days including off-day"
        }
      }
    },
    {
      "id": "apgdMinRestBetweenShifts",
      "enforcement": "hard",
      "description": "Minimum rest between shifts (hours)",
      "defaultValue": 8,
      "schemeOverrides": {
        "P": {
          "value": 1,
          "description": "Scheme P requires only 1h rest (enables 2 shifts/day)"
        }
      }
    },
    {
      "id": "momWeeklyHoursCap44h",
      "enforcement": "hard",
      "description": "Weekly normal hours cap (same for all schemes)",
      "defaultValue": 44
    },
    {
      "id": "minimumOffDaysPerWeek",
      "enforcement": "hard",
      "description": "Minimum off-days per week (all schemes require 1)",
      "defaultValue": 1
    },
    {
      "id": "momMonthlyOTcap72h",
      "enforcement": "hard",
      "description": "Monthly overtime cap (same for all schemes)",
      "defaultValue": 72
    },
    {
      "id": "momLunchBreak",
      "enforcement": "hard",
      "description": "Meal break deduction (same for all schemes)",
      "defaultValue": 60,
      "params": {
        "deductIfShiftAtLeastMinutes": 480
      }
    },
    {
      "id": "oneShiftPerDay",
      "enforcement": "hard",
      "description": "Maximum shifts per day",
      "defaultValue": 1,
      "schemeOverrides": {
        "P": 2
      }
    },
    {
      "id": "partTimerWeeklyHours",
      "enforcement": "hard",
      "description": "Part-timer weekly hours (Scheme P only)",
      "applicableToSchemes": ["P"],
      "params": {
        "maxHours4Days": 34.98,
        "maxHoursMoreDays": 29.98
      }
    }
  ]
}
```

**Advantages:**
- ✅ Clean and intuitive
- ✅ Easy to see default vs scheme-specific
- ✅ Minimal nesting
- ✅ Handles productType filtering elegantly

---

### Option B: Array-Based Rules (More Flexible)

```json
{
  "constraintList": [
    {
      "id": "momDailyHoursCap",
      "enforcement": "hard",
      "description": "Maximum daily working hours by scheme",
      "rules": [
        {
          "schemes": ["A"],
          "value": 14
        },
        {
          "schemes": ["B"],
          "value": 13
        },
        {
          "schemes": ["P"],
          "value": 9
        },
        {
          "value": 9,
          "description": "Default for all other schemes"
        }
      ]
    },
    {
      "id": "maxConsecutiveWorkingDays",
      "enforcement": "hard",
      "description": "Maximum consecutive working days",
      "rules": [
        {
          "schemes": ["A"],
          "productTypes": ["APO"],
          "value": 8,
          "description": "APGD-D10: 8 days including off-day"
        },
        {
          "schemes": ["A"],
          "value": 12,
          "description": "Scheme A without APO"
        },
        {
          "value": 12,
          "description": "Default"
        }
      ]
    },
    {
      "id": "apgdMinRestBetweenShifts",
      "enforcement": "hard",
      "description": "Minimum rest between shifts (hours)",
      "rules": [
        {
          "schemes": ["P"],
          "value": 1
        },
        {
          "value": 8
        }
      ]
    }
  ]
}
```

**Advantages:**
- ✅ More flexible (can combine multiple filters)
- ✅ Can have multiple rules per scheme with different productTypes
- ✅ Explicit precedence (first match wins)

**Disadvantages:**
- ⚠️ More verbose
- ⚠️ Requires more complex parsing logic

---

## Recommended: Option A with Enhancements

**Hybrid approach combining simplicity of Option A with flexibility:**

```json
{
  "constraintList": [
    {
      "id": "maxConsecutiveWorkingDays",
      "enforcement": "hard",
      "description": "Maximum consecutive working days",
      "defaultValue": 12,
      "schemeOverrides": {
        "A": [
          {
            "productTypes": ["APO"],
            "value": 8,
            "description": "APGD-D10"
          },
          {
            "value": 12,
            "description": "Standard Scheme A"
          }
        ],
        "B": 12,
        "P": 12
      }
    },
    {
      "id": "momDailyHoursCap",
      "enforcement": "hard",
      "description": "Maximum daily working hours",
      "defaultValue": 9,
      "schemeOverrides": {
        "A": 14,
        "B": 13,
        "P": 9
      }
    },
    {
      "id": "apgdMinRestBetweenShifts",
      "enforcement": "hard",
      "description": "Minimum rest between shifts (hours)",
      "defaultValue": 8,
      "schemeOverrides": {
        "P": 1
      }
    },
    {
      "id": "minimumOffDaysPerWeek",
      "enforcement": "hard",
      "description": "Minimum off-days per week",
      "defaultValue": 1,
      "notes": "All schemes require 1 off-day. Scheme A with APO can work on off-day for up to 8 consecutive days."
    },
    {
      "id": "oneShiftPerDay",
      "enforcement": "hard",
      "description": "Maximum shifts per day",
      "defaultValue": 1,
      "schemeOverrides": {
        "P": 2
      }
    },
    {
      "id": "partTimerWeeklyHours",
      "enforcement": "hard",
      "description": "Part-timer weekly hours",
      "applicableToSchemes": ["P"],
      "params": {
        "maxHours4Days": 34.98,
        "maxHoursMoreDays": 29.98
      }
    }
  ]
}
```

**Key Features:**
1. **Simple schemes:** Just a number (e.g., `"A": 14`)
2. **Complex schemes:** Array with filters (e.g., `"A": [{productTypes: ["APO"], value: 8}]`)
3. **Uniform fields:** `defaultValue` + `schemeOverrides`
4. **Optional metadata:** `description`, `notes`, `applicableToSchemes`

---

## Helper Function Update

### Updated `get_constraint_param()` for New Format

```python
def get_constraint_param(ctx: dict, 
                        constraint_id: str, 
                        employee: dict = None,
                        default=None):
    """
    Get constraint value for an employee using improved JSON format.
    
    New format features:
    - defaultValue: Applies to all employees
    - schemeOverrides: Per-scheme values (simple or complex)
    - Complex overrides support productTypes filtering
    
    Args:
        ctx: Context dict with 'constraintList'
        constraint_id: Constraint identifier
        employee: Employee dict (if None, returns defaultValue)
        default: Fallback if constraint not found
    
    Returns:
        Constraint value for this employee
    
    Example JSON:
        {
          "id": "maxConsecutiveWorkingDays",
          "defaultValue": 12,
          "schemeOverrides": {
            "A": [
              {"productTypes": ["APO"], "value": 8},
              {"value": 12}
            ]
          }
        }
    """
    from context.engine.time_utils import normalize_scheme
    
    constraint_list = ctx.get('constraintList', [])
    
    # Find constraint
    constraint = None
    for c in constraint_list:
        if c.get('id') == constraint_id:
            constraint = c
            break
    
    if not constraint:
        return default
    
    # If no employee specified, return default value
    if employee is None:
        return constraint.get('defaultValue', default)
    
    # Extract employee attributes
    scheme = normalize_scheme(employee.get('scheme', 'A'))
    product_types = employee.get('productTypes', [])
    rank = employee.get('rank', '')
    
    # Check scheme overrides
    scheme_overrides = constraint.get('schemeOverrides', {})
    
    if scheme in scheme_overrides:
        override = scheme_overrides[scheme]
        
        # Simple override (just a value)
        if isinstance(override, (int, float, str)):
            return override
        
        # Complex override (array with filters)
        if isinstance(override, list):
            for rule in override:
                # Check if productTypes filter matches
                required_products = rule.get('productTypes', [])
                if required_products:
                    if not all(pt in product_types for pt in required_products):
                        continue  # productTypes don't match, try next rule
                
                # Check if rank filter matches
                required_ranks = rule.get('ranks', [])
                if required_ranks:
                    if rank not in required_ranks:
                        continue  # rank doesn't match, try next rule
                
                # All filters match, return this value
                return rule.get('value')
        
        # Single object override with filters
        if isinstance(override, dict):
            required_products = override.get('productTypes', [])
            if required_products and not all(pt in product_types for pt in required_products):
                # productTypes don't match, fall through to default
                pass
            else:
                return override.get('value')
    
    # No scheme override matched, return default
    return constraint.get('defaultValue', default)
```

---

## Migration Strategy

### Phase 1: Support Both Formats

```python
def get_constraint_param_universal(ctx, constraint_id, employee=None, param_name=None, default=None):
    """
    Universal getter supporting both old and new formats.
    
    Old format (v0.7):
        "params": {"maxDailyHoursA": 14, "maxDailyHoursB": 13}
    
    New format (v0.98):
        "defaultValue": 9, "schemeOverrides": {"A": 14, "B": 13}
    """
    constraint = find_constraint(ctx, constraint_id)
    
    if not constraint:
        return default
    
    # Try new format first
    if 'defaultValue' in constraint or 'schemeOverrides' in constraint:
        return get_constraint_param_new_format(ctx, constraint_id, employee, default)
    
    # Fall back to old format
    if 'params' in constraint and param_name:
        return get_constraint_param_old_format(ctx, constraint_id, param_name, employee, default)
    
    return default
```

---

## Constraint Priority (Implementation Order)

### 🔴 **CRITICAL (Phase 1) - Must implement first:**

1. **momDailyHoursCap** - Daily hours cap
   - Current: Hardcoded A:14, B:13, P:9
   - Impact: Incorrect rosters if wrong
   - Files: C1_mom_daily_hours.py

2. **maxConsecutiveWorkingDays** - Consecutive days limit
   - Current: Hardcoded 12, APGD:8
   - Impact: Fatigue violations, regulatory risk
   - Special handling: Scheme A (APO) = 8 days including off-day flexibility
   - Files: C3_consecutive_days.py

3. **apgdMinRestBetweenShifts** - Minimum rest between shifts
   - Current: Partially configurable (660 min / 480 min)
   - NEW: Scheme P = 1 hour (enables 2 shifts/day)
   - Impact: Schedule feasibility for Scheme P
   - Files: C4_rest_period.py

---

### 🟡 **IMPORTANT (Phase 2) - Implement next:**

4. **minimumOffDaysPerWeek** - Off-day requirements
   - Current: Unknown implementation status
   - Impact: Employee wellbeing, regulatory compliance
   - Special handling: All schemes require 1, but Scheme A (APO) can work on off-day
   - Files: C5_offday_rules.py

5. **momWeeklyHoursCap44h** - Weekly hours cap
   - Current: Hardcoded 44h
   - Impact: Regulatory compliance
   - Files: C2_mom_weekly_hours_pattern_aware.py

---

### 🟢 **STANDARD (Phase 3) - Lower priority:**

6. **momMonthlyOTcap72h** - Monthly OT cap
   - Current: Hardcoded 72h
   - Impact: Long-term compliance
   - Files: C17_ot_monthly_cap.py

7. **momLunchBreak** - Meal break deduction
   - Current: Hardcoded 60 min
   - Impact: Hour calculations
   - Files: time_utils.py

8. **oneShiftPerDay** - Max shifts per day
   - Current: Hardcoded 1
   - NEW: Scheme P = 2 (per Excel)
   - Note: User said keep at 1 for now, revisit later
   - Files: C16_no_overlap.py

9. **partTimerWeeklyHours** - Part-timer limits
   - Current: ✅ Already correct (34.98 / 29.98)
   - Impact: Already working correctly
   - Files: C6_parttimer_limits.py

---

## Special Logic: Scheme A Consecutive Days

**Requirement:** Scheme A (with APO product type) can work 8 consecutive days, including working on their scheduled off-day.

**Current Implementation Issue:**
- C3_consecutive_days.py blocks >8 consecutive working days
- C5_offday_rules.py requires 1 off-day per week
- **Conflict:** If they work on off-day, they violate C5 but should be allowed up to 8 days

**Proposed Solution:**

```python
# C5_offday_rules.py - Update to handle Scheme A flexibility

def add_constraints(model, ctx):
    """
    Enforce minimum off-days per week.
    
    Special handling for Scheme A (APGD-D10):
    - Still requires 1 off-day per week in pattern
    - BUT: Can work on that off-day for up to 8 consecutive days
    - Constraint: If worked off-day, consecutive day count resets within 8 days
    """
    
    for emp in employees:
        scheme = normalize_scheme(emp.get('scheme'))
        product_types = emp.get('productTypes', [])
        
        min_off_days = get_constraint_param(ctx, 'minimumOffDaysPerWeek', emp, default=1)
        
        # Standard enforcement for non-APGD-D10
        if not (scheme == 'A' and 'APO' in product_types):
            # Require min_off_days per week (standard logic)
            enforce_weekly_off_days(model, emp, min_off_days)
        else:
            # Scheme A (APGD-D10): More flexible
            # Allow working on off-day IF consecutive days <= 8
            enforce_apgd_flexible_off_days(model, emp)

def enforce_apgd_flexible_off_days(model, emp):
    """
    APGD-D10 special rule: Can work on off-day within 8-day consecutive window.
    
    Logic:
    1. Pattern defines off-day (e.g., DDDODDD has day 4 as off)
    2. Employee CAN work on day 4 (making it DDDDDDD)
    3. This counts toward consecutive day limit (max 8)
    4. Must have actual rest within 8-day window
    """
    # Implementation: Soft constraint on off-day work, hard cap at 8 consecutive
    pass
```

---

## Summary

### Recommended JSON Format:
**Option A (Flat with Scheme Overrides)** - Best balance of simplicity and flexibility

### Implementation Priority:
1. 🔴 **Phase 1 (3 days):** C1 (daily hours), C3 (consecutive days), C4 (rest period)
2. 🟡 **Phase 2 (2 days):** C5 (off days), C2 (weekly hours)
3. 🟢 **Phase 3 (1 day):** C17 (monthly OT), time_utils (meal break)

### Key Changes:
- ✅ New JSON format: `defaultValue` + `schemeOverrides`
- ✅ Scheme P: 1h rest between shifts (enables split shifts)
- ✅ Scheme A (APO): 8 consecutive days with off-day flexibility
- ✅ Parttimer: Already correct (34.98h / 29.98h)

**Ready to implement Phase 1?**
