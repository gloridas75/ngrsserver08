# C17 totalMaxHours Enforcement Implementation Summary

## Problem
The C17 monthly OT cap constraint was only enforcing `maxOvertimeHours` but not `totalMaxHours`, allowing schedules with excessive total work hours (e.g., 27 days × 12h = 324h) that exceeded the `totalMaxHours` cap (267h for 31-day months).

## Solution
Added `totalMaxHours` enforcement to both C17 constraint implementations:
1. **Template Generator** (`context/engine/cpsat_template_generator.py`)
2. **Standard CP-SAT Model** (`context/constraints/C17_ot_monthly_cap.py`)

## Files Modified

### 1. context/constraints/C17_ot_monthly_cap.py
**Changes:**
- Added Constraint 2: Total work hours <= totalMaxHours
- Reads `totalMaxHours` from `get_monthly_hour_limits()`
- Prevents solver from assigning work beyond monthly cap
- Works alongside existing weekly OT cap constraint

**Key Code:**
```python
# Constraint 2: Total work hours <= totalMaxHours (if specified)
total_max_hours = monthly_limits.get('totalMaxHours')
if total_max_hours:
    month_slot_terms = [x[(slot.slot_id, emp_id)] * gross_scaled 
                        for slot in month_slots]
    model.Add(sum(month_slot_terms) <= total_max_scaled)
    total_hours_constraints += 1
```

### 2. context/engine/cpsat_template_generator.py
**Changes:**
- Added same totalMaxHours constraint to template generation
- Moved `get_monthly_hour_limits()` call outside conditional block
- Applied constraint to all dates in calendar month

**Key Code:**
```python
# Constraint 2: Total work hours <= totalMaxHours
total_max_hours = monthly_limits.get('totalMaxHours')
if total_max_hours:
    month_indices = [i for i, date in enumerate(dates) 
                     if i in x and date.year == year and date.month == month]
    if month_indices:
        month_work_terms = [x[i] * gross_scaled for i in month_indices]
        model.Add(sum(month_work_terms) <= total_max_scaled)
```

### 3. context/engine/constraint_config.py
**Changes:**
- Fixed `matches_monthly_limit_filters()` to support `productTypeId` (single string)
- Added handling for `ranks: ['All']` as wildcard matching any rank
- Previously only supported `productTypes` (list)

**Bug Fixes:**
```python
# Support both productTypeId (single) and productTypes (list)
emp_product_id = employee.get('productTypeId', '')
emp_products = employee.get('productTypes', [emp_product_id] if emp_product_id else [])

# 'All' in ranks list acts as wildcard
if 'All' not in allowed_ranks:
    if emp_rank not in allowed_ranks:
        return False
```

### 4. input/RST-20260227-8804A876_Solver_Input.json
**Changes:**
- Added `totalMaxHours` values to SO_A monthlyHourLimits entry
- Already had values in SO_B entry

## Test Results

### Before Fix (Violation)
```
00100008 (Sch B): 27 work days, total=297.00h ⚠️  EXCEEDS 267h cap by 30h
00100011 (Sch B): 27 work days, total=297.00h ⚠️  EXCEEDS 267h cap by 30h
00100012 (Sch A): 27 work days, total=297.00h ⚠️  EXCEEDS 267h cap by 30h
00100014 (Sch A): 27 work days, total=297.00h ⚠️  EXCEEDS 267h cap by 30h
```

### After Fix (Compliant)
```
00100008 (Sch B): 22 work days, total=242.00h ✅ Within 267h cap (25h headroom)
00100011 (Sch B): 22 work days, total=242.00h ✅ Within 267h cap (25h headroom)
00100012 (Sch A): 22 work days, total=242.00h ✅ Within 267h cap (25h headroom)
00100014 (Sch A): 22 work days, total=242.00h ✅ Within 267h cap (25h headroom)
```

## How It Works

### Monthly Hour Limits Schema
```json
{
  "id": "SO_B",
  "hourCalculationMethod": "dailyContractual",
  "applicableTo": {
    "schemes": ["B"],
    "productTypes": ["SO"]
  },
  "valuesByMonthLength": {
    "31": {
      "maxOvertimeHours": 72,
      "minimumContractualHours": 195,
      "totalMaxHours": 267  ← THIS VALUE NOW ENFORCED
    }
  }
}
```

### Constraint Enforcement Flow
1. Solver reads `totalMaxHours` from matched monthlyHourLimits rule
2. C17 adds CP-SAT constraint: `sum(work_hours) <= totalMaxHours * 100`
3. Solver reduces work days (27 → 22) to satisfy constraint
4. Output shows compliant schedules with proper hour breakdowns

## Benefits
- **Prevents MOM Violations**: Ensures total work hours never exceed regulatory limits
- **Configurable**: Different limits for different schemes/products via monthlyHourLimits
- **Early Detection**: Constraint violations caught during solving, not post-processing
- **Flexible**: Works with both template and standard CP-SAT modes

## Related
- Enhanced hourCalculationMethod field (Phase 2)
- Daily contractual hours calculation (Phase 1)
- MOM compliance hour routing (output_builder.py)

## Commit
Commit: [pending]
Date: 2025-01-27
Feature: C17 totalMaxHours enforcement + productTypeId/ranks wildcard fixes
