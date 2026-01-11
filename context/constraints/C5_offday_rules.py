"""C5: Minimum off-days per week ≥1 day off per 7-day window (HARD constraint).

Enforce minimum number of off-days: each employee must have at least 1 day off
per every 7 consecutive calendar days.

APGD-D10: EXEMPT from weekly rest day requirement (can work 7 days/week).
"""
from collections import defaultdict
from datetime import datetime, timedelta
from context.engine.constraint_config import get_constraint_param


def add_constraints(model, ctx):
    """
    Enforce minimum off-days: ≥1 day off per 7 days (HARD).
    APGD-D10 employees: EXEMPT (can work 7 days/week).
    
    Strategy: 
    1. Create daily indicator variables: day_worked[(emp_id, date)] = 1 if ANY shift assigned
    2. For every 7 consecutive calendar days, ensure sum(day_worked) <= 6
    3. Skip constraint for APGD-D10 employees
    
    Args:
        model: CP-SAT model
        ctx: Context dict with 'slots', 'employees', 'x'
    """
    from context.engine.time_utils import is_apgd_d10_employee
    
    slots = ctx.get('slots', [])
    employees = ctx.get('employees', [])
    x = ctx.get('x', {})
    
    if not slots or not x or not employees:
        print(f"[C5] Warning: Slots, employees, or decision variables not available")
        return
    
    # Build requirement map for APGD-D10 detection
    req_map = {}
    for demand in ctx.get('demandItems', []):
        for req in demand.get('requirements', []):
            req_map[req['requirementId']] = req
    
    # Identify APGD-D10 employees (exempt from weekly rest day)
    apgd_employees = set()
    for emp in employees:
        emp_id = emp.get('employeeId')
        product = emp.get('productTypeId', '')
        for req_id, req in req_map.items():
            if req.get('productTypeId', '') == product:
                if is_apgd_d10_employee(emp, req):
                    apgd_employees.add(emp_id)
                    break
    
    if apgd_employees:
        print(f"[C5] APGD-D10 detected: {len(apgd_employees)} employees EXEMPT from weekly rest day")
    
    # Group slots by employee and date
    emp_slots_by_date = defaultdict(lambda: defaultdict(list))  # emp_id -> date_str -> [slot_ids]
    all_dates = set()
    
    for slot in slots:
        date_str = slot.date  # Keep as string for consistency
        all_dates.add(date_str)
        for emp in employees:
            emp_id = emp.get('employeeId')
            if (slot.slot_id, emp_id) in x:
                emp_slots_by_date[emp_id][date_str].append(slot.slot_id)
    
    # Convert dates to sorted list (slot.date is already a date object, not string)
    sorted_dates = sorted(list(all_dates))
    
    if len(sorted_dates) < 7:
        print(f"[C5] Minimum Off-Days Per Week Constraint (HARD)")
        print(f"     Employees: {len(employees)}, Planning horizon: {len(sorted_dates)} days")
        print(f"     No constraints needed (horizon < 7 days)\n")
        return
    
    constraints_added = 0
    
    # Read minimum off-days from JSON with fallback to 1
    # This applies globally, but could be made employee-specific if needed
    min_off_days = get_constraint_param(
        ctx, 'minimumOffDaysPerWeek', default=1
    )
    
    # For each employee, create day-worked indicator variables and add constraints
    for emp in employees:
        emp_id = emp.get('employeeId')
        emp_scheme = emp.get('scheme', 'Unknown')
        
        # Skip APGD-D10 employees (exempt from weekly rest day)
        if emp_id in apgd_employees:
            print(f"     ✓ Skipping {emp_id} (Scheme {emp_scheme}): APGD-D10 EXEMPT from weekly rest")
            continue
        
        if emp_id not in emp_slots_by_date:
            continue  # No slots for this employee
        
        print(f"     → Adding C5 constraints for {emp_id} (Scheme {emp_scheme})")
        
        # Create indicator variables: day_worked[(emp_id, date)] = 1 if employee works on date
        day_worked = {}
        
        for date_str in sorted_dates:
            if date_str in emp_slots_by_date[emp_id]:
                # This employee has slots on this date
                slot_ids = emp_slots_by_date[emp_id][date_str]
                
                # Create boolean var: day_worked = 1 if ANY slot assigned on this date
                day_var = model.NewBoolVar(f'day_worked_c5_{emp_id}_{date_str}')
                day_worked[date_str] = day_var
                
                # Link day_var to actual slot assignments
                slot_vars = [x[(slot_id, emp_id)] for slot_id in slot_ids]
                
                # If any slot is assigned, day_var must be 1
                for slot_var in slot_vars:
                    model.Add(day_var >= slot_var)
                
                # If day_var is 1, at least one slot must be assigned
                model.Add(sum(slot_vars) >= day_var)
            else:
                # No slots on this date for this employee
                day_worked[date_str] = 0
        
        # Now add constraints: for every 7 consecutive calendar days, at most 6 working days
        for i in range(len(sorted_dates) - 6):
            window_dates = sorted_dates[i:i + 7]  # 7 consecutive dates
            
            # Check if these are truly consecutive calendar days
            start_date = window_dates[0]
            end_date = window_dates[-1]
            days_between = (end_date - start_date).days
            
            if days_between == 6:  # Exactly 6 days apart = 7 calendar days
                # Sum of working days in this window must be <= 6 (at least 1 off-day)
                day_vars_in_window = []
                for date_str in window_dates:
                    if date_str in day_worked:
                        var = day_worked[date_str]
                        # Only include actual variables (not constant 0)
                        if not isinstance(var, int):
                            day_vars_in_window.append(var)
                
                if len(day_vars_in_window) >= 7:
                    # Only add constraint if all 7 days have potential assignments
                    model.Add(sum(day_vars_in_window) <= 6)
                    constraints_added += 1
    
    print(f"[C5] Minimum Off-Days Per Week Constraint (HARD)")
    print(f"     Employees: {len(employees)}, Planning horizon: {len(sorted_dates)} days")
    print(f"     Minimum off-days: ≥{min_off_days} per 7-day window")
    print(f"     ✓ Added {constraints_added} rolling window constraints\n")
