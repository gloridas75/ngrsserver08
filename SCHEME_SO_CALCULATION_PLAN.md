# Scheme SO Hour Calculation Implementation Plan

## Problem Statement
Need to differentiate OT calculation for Scheme A + SO vs Scheme B + SO:

**Scheme B + SO**: Use `calculationMethod: "daily"` - prorate minimumContractualHours across work days
**Scheme A + SO**: Use `calculationMethod: "monthly"` - but calculate OT **daily** using 44h/week threshold (NOT APGD-D10 monthly threshold)

## Current Behavior
- Both Scheme A + SO and Scheme B + SO use `calculate_mom_compliant_hours()` (44h/week threshold)
- Only Scheme A + APO uses `calculate_apgd_d10_hours()` (monthly threshold)

## Required Changes

### 1. New Function: `calculate_daily_contractual_hours()`
Location: `context/engine/time_utils.py`

```python
def calculate_daily_contractual_hours(
    start_dt, end_dt, employee_id, assignment_date_obj,
    all_assignments, cumulative_normal_hours,
    minimumContractualHours, totalMaxHours, work_days_in_month
) -> dict:
    """
    Calculate hours using daily proration of minimumContractualHours.
    
    Logic:
    - Normal hours per day = minimumContractualHours / work_days_in_month
    - Each assignment allocates up to this daily normal cap
    - Once monthly cumulative exceeds minimumContractualHours, all becomes OT
    - Hard cap: total hours cannot exceed totalMaxHours
    
    Example (31-day month, 27 work days, 195h minimum, 267h total max):
    - Daily normal cap = 195 / 27 = 7.22h
    - Days 1-27: 7.22h normal, 4.78h OT (for 12h shift)
    - Monthly total: 195h normal + 129h OT = 324h > 267h → VIOLATION
    
    Returns: {gross, lunch, normal, ot, restDayPay, paid}
    """
```

### 2. Update `output_builder.py` Routing Logic
Replace current routing (lines 990-1050) with:

```python
# Get monthly hour limits for this employee
month_length = calendar.monthrange(date_obj.year, date_obj.month)[1]
hour_limits = get_monthly_hour_limits(month_length, employee, input_data)
calculation_method = hour_limits['calculationMethod']
minimumContractualHours = hour_limits['minimumContractualHours']
totalMaxHours = hour_limits['totalMaxHours']

if calculation_method == 'daily':
    # Scheme B + SO: Daily proration of minimumContractualHours
    work_days_in_month = count_work_days_for_employee_in_month(...)
    cumulative = daily_cumulative.get(emp_id, 0.0)
    
    hours_dict = calculate_daily_contractual_hours(
        start_dt, end_dt, emp_id, date_obj, assignments,
        cumulative, minimumContractualHours, totalMaxHours, work_days_in_month
    )
    
    daily_cumulative[emp_id] += hours_dict['normal']

elif calculation_method == 'monthly':
    # Scheme A (APO or SO): Check product type
    product_type = employee.get('productTypeId', '').upper()
    
    if product_type == 'APO':
        # Scheme A + APO: APGD-D10 monthly threshold
        cumulative = apgd_cumulative.get(emp_id, 0.0)
        hours_dict = calculate_apgd_d10_hours(...)
        apgd_cumulative[emp_id] += hours_dict['normal']
    else:
        # Scheme A + SO: Daily 44h/week threshold
        hours_dict = calculate_mom_compliant_hours(...)
```

### 3. Validation
- Scheme B + SO should show ~7.22h normal per day (195h / 27 days)
- Scheme A + SO should show ~8.8h normal per day (44h / 5 days)
- Monthly OT should not exceed 72h for either
- Total hours should not exceed totalMaxHours

## Implementation Steps
1. ✅ Create this plan document
2. ⬜ Implement `calculate_daily_contractual_hours()` in time_utils.py
3. ⬜ Add `count_work_days_for_employee_in_month()` helper
4. ⬜ Update output_builder.py routing logic
5. ⬜ Test with RST-20260227-8804A876 input
6. ⬜ Validate hour totals match expectations
7. ⬜ Deploy to production
