"""C17: Monthly OT cap per employee (HARD).

Canonical model:
- ot_hours = max(0, gross_hours - 9.0) per shift
- Sum of ot_hours per employee per calendar month ≤ monthly OT cap

Monthly OT caps (from monthlyHourLimits):
- Standard (non-APO): 72h per month
- APGD-D10 (Scheme A + APO): 112-124h per month (varies by month length)

This constraint enforces monthly OT doesn't exceed the scheme/product-specific limit (HARD).
"""
from collections import defaultdict
from calendar import monthrange
from context.engine.constraint_config import get_monthly_hour_limits


def add_constraints(model, ctx):
    """
    Enforce monthly OT hour cap per employee (HARD).
    
    Strategy: Group slots by (employee, calendar month).
    For each month, sum OT hours weighted by assignments.
    Constraint: sum(var * scaled_ot) <= monthly_ot_cap
    
    Monthly OT caps (from monthlyHourLimits):
    - Standard: 72h
    - APGD-D10 (APO): 112-124h depending on month length (28-31 days)
    
    Args:
        model: CP-SAT model
        ctx: Context dict with 'employees', 'slots', 'x', 'monthlyHourLimits'
    """
    
    slots = ctx.get('slots', [])
    employees = ctx.get('employees', [])
    x = ctx.get('x', {})
    
    if not slots or not x or not employees:
        print(f"[C17] Warning: Slots, employees, or decision variables not available")
        return
    
    # Calculate OT hours for each slot (same logic as C2)
    slot_ot_hours = {}
    for slot in slots:
        gross = (slot.end - slot.start).total_seconds() / 3600.0
        # OT = hours beyond 9h daily threshold
        ot_hours = max(0, gross - 9.0)
        slot_ot_hours[slot.slot_id] = ot_hours
    
    # Group slots by (employee, calendar month, year)
    emp_month_slots = defaultdict(list)
    
    for slot in slots:
        slot_date = slot.date
        month_key = (slot_date.year, slot_date.month)
        
        for emp in employees:
            emp_id = emp.get('employeeId')
            if (slot.slot_id, emp_id) in x:
                emp_month_slots[(emp_id, month_key)].append(slot)
    
    # Add monthly OT cap constraints
    monthly_constraints = 0
    apgd_employees = 0
    
    for (emp_id, month_key), month_slots in emp_month_slots.items():
        year, month = month_key
        
        # Find employee dict for this employee
        employee = next((e for e in employees if e.get('employeeId') == emp_id), None)
        if not employee:
            continue
        
        # Build weighted sum: sum(var * ot_hours_scaled)
        terms = []
        for slot in month_slots:
            if (slot.slot_id, emp_id) in x:
                var = x[(slot.slot_id, emp_id)]
                ot_hours = slot_ot_hours.get(slot.slot_id, 0)
                
                if ot_hours > 0:
                    # Scale to integer tenths (multiply by 10)
                    int_hours = int(round(ot_hours * 10))
                    terms.append(var * int_hours)
        
        if terms:
            # Get scheme/product-specific monthly OT cap from monthlyHourLimits
            monthly_limits = get_monthly_hour_limits(ctx, employee, year, month)
            monthly_ot_cap = monthly_limits.get('maxOvertimeHours', 72.0)
            monthly_ot_cap_int = int(round(monthly_ot_cap * 10))  # Convert to tenths
            
            # Track APGD-D10 (APO) employees
            if monthly_ot_cap > 72.0:
                apgd_employees += 1
            
            # Constraint: sum(var * scaled_ot) <= monthly_ot_cap
            model.Add(sum(terms) <= monthly_ot_cap_int)
            monthly_constraints += 1
    
    # Calculate unique APO employees (avoid double counting across months)
    unique_apgd = set()
    for (emp_id, month_key), _ in emp_month_slots.items():
        year, month = month_key
        employee = next((e for e in employees if e.get('employeeId') == emp_id), None)
        if employee:
            monthly_limits = get_monthly_hour_limits(ctx, employee, year, month)
            if monthly_limits.get('maxOvertimeHours', 72.0) > 72.0:
                unique_apgd.add(emp_id)
    
    print(f"[C17] Monthly OT Cap Constraint (HARD)")
    print(f"     Employees: {len(employees)}, Slots: {len(slots)}")
    print(f"     Standard OT cap: ≤72h per month")
    if unique_apgd:
        print(f"     APGD-D10 (APO): {len(unique_apgd)} employees with ≤112-124h cap (month-dependent)")
    print(f"     ✓ Added {monthly_constraints} monthly OT constraints\n")
