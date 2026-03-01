"""C17: Monthly OT cap per employee (HARD).

Canonical model (44h/week threshold - consistent with MOM and output builder):
- Weekly OT = max(0, weekly_gross_hours - 44)
- Monthly OT = sum of all weekly OT within the calendar month
- Monthly OT ≤ monthly OT cap (72h for standard, 112-124h for APGD-D10)

Monthly OT caps (from monthlyHourLimits):
- Standard (non-APO): 72h per month
- APGD-D10 (Scheme A + APO): 112-124h per month (varies by month length)

This constraint enforces monthly OT doesn't exceed the scheme/product-specific limit (HARD).
"""
from collections import defaultdict
from calendar import monthrange
from context.engine.constraint_config import get_monthly_hour_limits


# Weekly normal hours threshold (MOM standard)
WEEKLY_HOURS_THRESHOLD = 44.0


def add_constraints(model, ctx):
    """
    Enforce monthly OT hour cap per employee (HARD).
    
    Strategy: 
    1. Group slots by (employee, ISO week) to calculate weekly gross hours
    2. Weekly OT = max(0, weekly_gross - 44h)
    3. Sum weekly OT for each calendar month
    4. Constraint: monthly OT ≤ monthly_ot_cap
    
    This matches the output builder's OT calculation (44h/week threshold).
    
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
    
    # Pre-calculate gross hours for each slot
    slot_gross_hours = {}
    for slot in slots:
        gross = (slot.end - slot.start).total_seconds() / 3600.0
        slot_gross_hours[slot.slot_id] = gross
    
    # Group slots by (employee, ISO week year, ISO week number)
    # Each slot also knows which calendar month it belongs to
    emp_week_slots = defaultdict(list)  # (emp_id, iso_year, iso_week) -> [slots]
    emp_month_weeks = defaultdict(set)  # (emp_id, cal_year, cal_month) -> set of (iso_year, iso_week)
    
    for slot in slots:
        slot_date = slot.date
        iso_year, iso_week, _ = slot_date.isocalendar()
        cal_month = (slot_date.year, slot_date.month)
        
        for emp in employees:
            emp_id = emp.get('employeeId')
            if (slot.slot_id, emp_id) in x:
                week_key = (emp_id, iso_year, iso_week)
                emp_week_slots[week_key].append(slot)
                emp_month_weeks[(emp_id, cal_month[0], cal_month[1])].add((iso_year, iso_week))
    
    # Create weekly gross hours variables for each (employee, week)
    # weekly_gross[emp_id, iso_year, iso_week] = sum of gross hours for that week
    weekly_gross_vars = {}
    weekly_ot_vars = {}
    
    # Scale factor for integer arithmetic (multiply by 100 for 2 decimal precision)
    SCALE = 100
    weekly_threshold_scaled = int(WEEKLY_HOURS_THRESHOLD * SCALE)
    
    for week_key, week_slots in emp_week_slots.items():
        emp_id, iso_year, iso_week = week_key
        
        # Build sum of gross hours for this week: sum(var * gross_hours)
        gross_terms = []
        for slot in week_slots:
            if (slot.slot_id, emp_id) in x:
                var = x[(slot.slot_id, emp_id)]
                gross = slot_gross_hours.get(slot.slot_id, 0)
                gross_scaled = int(round(gross * SCALE))
                if gross_scaled > 0:
                    gross_terms.append(var * gross_scaled)
        
        if gross_terms:
            # Create variable for weekly gross hours
            max_weekly_gross = int(24 * 7 * SCALE)  # Max possible: 168h/week
            weekly_gross_var = model.NewIntVar(0, max_weekly_gross, f"weekly_gross_{emp_id}_{iso_year}_{iso_week}")
            model.Add(weekly_gross_var == sum(gross_terms))
            weekly_gross_vars[week_key] = weekly_gross_var
            
            # Create variable for weekly OT: max(0, weekly_gross - 44)
            max_weekly_ot = max_weekly_gross - weekly_threshold_scaled
            weekly_ot_var = model.NewIntVar(0, max_weekly_ot, f"weekly_ot_{emp_id}_{iso_year}_{iso_week}")
            
            # weekly_ot = max(0, weekly_gross - 44)
            # This is: weekly_ot >= weekly_gross - 44 AND weekly_ot >= 0
            # We use: weekly_ot = max(0, weekly_gross - threshold)
            diff_var = model.NewIntVar(-max_weekly_gross, max_weekly_gross, f"weekly_diff_{emp_id}_{iso_year}_{iso_week}")
            model.Add(diff_var == weekly_gross_var - weekly_threshold_scaled)
            model.AddMaxEquality(weekly_ot_var, [diff_var, 0])
            
            weekly_ot_vars[week_key] = weekly_ot_var
    
    # Add monthly OT cap constraints AND total hours cap constraints
    monthly_constraints = 0
    total_hours_constraints = 0
    unique_apgd = set()
    
    # Get unique (employee, calendar month) combinations
    emp_months = set()
    for slot in slots:
        slot_date = slot.date
        for emp in employees:
            emp_id = emp.get('employeeId')
            if (slot.slot_id, emp_id) in x:
                emp_months.add((emp_id, slot_date.year, slot_date.month))
    
    for emp_id, cal_year, cal_month in emp_months:
        # Find employee dict
        employee = next((e for e in employees if e.get('employeeId') == emp_id), None)
        if not employee:
            continue
        
        # Get all ISO weeks that have slots in this calendar month for this employee
        weeks_in_month = emp_month_weeks.get((emp_id, cal_year, cal_month), set())
        
        # Collect weekly OT variables for this month
        monthly_ot_terms = []
        for iso_year, iso_week in weeks_in_month:
            week_key = (emp_id, iso_year, iso_week)
            if week_key in weekly_ot_vars:
                monthly_ot_terms.append(weekly_ot_vars[week_key])
        
        if monthly_ot_terms:
            # Get scheme/product-specific monthly OT cap from monthlyHourLimits
            monthly_limits = get_monthly_hour_limits(ctx, employee, cal_year, cal_month)
            monthly_ot_cap = monthly_limits.get('maxOvertimeHours', 72.0)
            monthly_ot_cap_scaled = int(round(monthly_ot_cap * SCALE))
            
            # Track APGD-D10 (APO) employees
            if monthly_ot_cap > 72.0:
                unique_apgd.add(emp_id)
            
            # Constraint 1: sum(weekly_ot) <= monthly_ot_cap
            model.Add(sum(monthly_ot_terms) <= monthly_ot_cap_scaled)
            monthly_constraints += 1
        
        # Constraint 2: Total work hours <= totalMaxHours (if specified)
        # This prevents schedules like 27 days x 12h = 324h when cap is 267h
        total_max_hours = monthly_limits.get('totalMaxHours')
        if total_max_hours:
            # Collect all assigned slots for this employee in this month
            month_slot_terms = []
            for slot in slots:
                if slot.date.year == cal_year and slot.date.month == cal_month:
                    if (slot.slot_id, emp_id) in x:
                        var = x[(slot.slot_id, emp_id)]
                        gross = slot_gross_hours.get(slot.slot_id, 0)
                        gross_scaled = int(round(gross * SCALE))
                        if gross_scaled > 0:
                            month_slot_terms.append(var * gross_scaled)
            
            if month_slot_terms:
                total_max_scaled = int(round(total_max_hours * SCALE))
                model.Add(sum(month_slot_terms) <= total_max_scaled)
                total_hours_constraints += 1
    
    print(f"[C17] Monthly OT Cap Constraint (HARD) - 44h/week threshold")
    print(f"     Employees: {len(employees)}, Slots: {len(slots)}")
    print(f"     Weekly OT = max(0, weekly_gross - 44h)")
    print(f"     Standard OT cap: ≤72h per month")
    if unique_apgd:
        print(f"     APGD-D10 (APO): {len(unique_apgd)} employees with ≤112-124h cap (month-dependent)")
    print(f"     ✓ Added {monthly_constraints} monthly OT constraints")
    print(f"     ✓ Added {total_hours_constraints} total hours cap constraints\n")
