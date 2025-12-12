"""S18: Minimize Gaps (U-slots) - SOFT constraint with CP-SAT objective integration.

Penalizes gaps (unassigned "D" days) between work days in employee schedules.
Unlike other soft constraints, S18 creates gap tracking variables DURING model building
and adds them to the CP-SAT objective, ensuring gaps are minimized during solving.

For pattern DDDDDOD:
- Employees should work continuously on their scheduled "D" days
- Gaps (U-slots on "D" days) are heavily penalized in CP-SAT objective
- Pattern "O" days are NOT penalized (they're intentional rest days)

This encourages continuous work blocks and reduces roster fragmentation.
"""

def add_constraints(model, ctx):
    """
    Create gap tracking variables and add to CP-SAT objective.
    
    For each employee's pattern work days:
    - Create boolean "gap" variable = 1 if day should be worked but isn't
    - Add gap variables to model objective with heavy penalty
    
    This makes CP-SAT actively minimize gaps during solving.
    """
    from datetime import datetime, timedelta
    
    employees = ctx.get('employees', [])
    slots = ctx.get('slots', [])
    x = ctx.get('x', {})
    
    if not employees or not slots:
        print(f"[S18] Minimize Gaps (SOFT) - skipped (no data)\n")
        return
    
    # Get planning horizon
    planning_horizon = ctx.get('planningHorizon', {})
    start_date_str = planning_horizon.get('startDate')
    end_date_str = planning_horizon.get('endDate')
    
    if not start_date_str or not end_date_str:
        print(f"[S18] Minimize Gaps (SOFT) - skipped (no planning horizon)\n")
        return
    
    start_date = datetime.fromisoformat(start_date_str).date()
    end_date = datetime.fromisoformat(end_date_str).date()
    
    # Get base work pattern
    demands = ctx.get('demandItems', [])
    if not demands:
        print(f"[S18] Minimize Gaps (SOFT) - skipped (no demands)\n")
        return
    
    reqs = demands[0].get('requirements', [])
    if not reqs:
        print(f"[S18] Minimize Gaps (SOFT) - skipped (no requirements)\n")
        return
    
    base_pattern = reqs[0].get('workPattern', [])
    if not base_pattern:
        print(f"[S18] Minimize Gaps (SOFT) - skipped (no work pattern)\n")
        return
    
    pattern_length = len(base_pattern)
    pattern_start_date_str = demands[0].get('shiftStartDate', start_date_str)
    pattern_start_date = datetime.fromisoformat(pattern_start_date_str).date()
    
    # Build date-to-slots mapping
    date_to_slots = {}
    current_date = start_date
    while current_date <= end_date:
        date_to_slots[current_date] = [s for s in slots if s.date == current_date]
        current_date += timedelta(days=1)
    
    # Create gap tracking variables for each employee
    gap_vars = []
    gap_count = 0
    
    for emp in employees:
        emp_id = emp.get('employeeId')
        emp_offset = emp.get('rotationOffset', 0)
        
        # Track first and last assignment for this employee
        # We'll create "potential gap" variables between consecutive work pattern days
        
        # Get employee's pattern work dates
        emp_work_dates = []
        current_date = start_date
        while current_date <= end_date:
            days_from_start = (current_date - pattern_start_date).days
            pattern_day = (days_from_start + emp_offset) % pattern_length
            expected_shift = base_pattern[pattern_day]
            
            if expected_shift in ['D', 'N']:
                emp_work_dates.append(current_date)
            
            current_date += timedelta(days=1)
        
        # For consecutive pattern work days, create gap tracking
        for i in range(len(emp_work_dates) - 1):
            work_date1 = emp_work_dates[i]
            work_date2 = emp_work_dates[i + 1]
            
            # Get slots for these dates
            slots_date1 = [x[(s.slot_id, emp_id)] for s in date_to_slots.get(work_date1, []) if (s.slot_id, emp_id) in x]
            slots_date2 = [x[(s.slot_id, emp_id)] for s in date_to_slots.get(work_date2, []) if (s.slot_id, emp_id) in x]
            
            if not slots_date1 or not slots_date2:
                continue
            
            # Create gap detection variable
            # gap = 1 if employee works on date1 but NOT on date2
            gap_var = model.NewBoolVar(f'gap_{emp_id}_{work_date2}')
            
            # Indicators for working on each date
            worked_date1 = model.NewBoolVar(f'worked_{emp_id}_{work_date1}_{i}')
            worked_date2 = model.NewBoolVar(f'worked_{emp_id}_{work_date2}_{i}')
            
            # Set indicators
            model.Add(sum(slots_date1) > 0).OnlyEnforceIf(worked_date1)
            model.Add(sum(slots_date1) == 0).OnlyEnforceIf(worked_date1.Not())
            
            model.Add(sum(slots_date2) > 0).OnlyEnforceIf(worked_date2)
            model.Add(sum(slots_date2) == 0).OnlyEnforceIf(worked_date2.Not())
            
            # gap = worked_date1 AND (NOT worked_date2)
            # Using: gap >= worked_date1 - worked_date2
            model.Add(gap_var >= worked_date1 - worked_date2)
            model.Add(gap_var <= worked_date1)
            model.Add(gap_var <= 1 - worked_date2)
            
            gap_vars.append(gap_var)
            gap_count += 1
    
    # Store gap variables in context for objective function
    ctx['gap_penalty_vars'] = gap_vars
    
    print(f"[S18] Minimize Gaps: Created {gap_count} gap tracking variables")
    print(f"      Pattern: {base_pattern}, will be added to CP-SAT objective\n")


def score_violations(ctx, assignments, score_book):
    """
    Calculate actual gap violations for reporting.
    (Gap minimization already handled by CP-SAT objective during solve)
    """
    from datetime import datetime, timedelta
    from collections import defaultdict
    
    # Get planning data
    planning_horizon = ctx.get('planningHorizon', {})
    start_date_str = planning_horizon.get('startDate')
    end_date_str = planning_horizon.get('endDate')
    
    if not start_date_str or not end_date_str:
        return 0
    
    start_date = datetime.fromisoformat(start_date_str).date()
    end_date = datetime.fromisoformat(end_date_str).date()
    
    # Get work pattern
    demands = ctx.get('demandItems', [])
    if not demands:
        return 0
    
    reqs = demands[0].get('requirements', [])
    if not reqs:
        return 0
    
    base_pattern = reqs[0].get('workPattern', [])
    if not base_pattern:
        return 0
    
    pattern_length = len(base_pattern)
    pattern_start_date_str = demands[0].get('shiftStartDate', start_date_str)
    pattern_start_date = datetime.fromisoformat(pattern_start_date_str).date()
    
    employees = ctx.get('employees', [])
    
    # Build employee work calendar
    employee_work_dates = defaultdict(set)
    for a in assignments:
        emp_id = a.get('employeeId')
        date_str = a.get('date')
        shift_code = a.get('shiftCode', '')
        status = a.get('status')
        
        if emp_id and date_str and shift_code not in ['O', None] and status != 'UNASSIGNED':
            date_obj = datetime.fromisoformat(date_str).date()
            employee_work_dates[emp_id].add(date_obj)
    
    total_gap_days = 0
    gap_penalty_per_day = 1000  # Match CP-SAT objective weight
    
    # For each employee, check for gaps
    for emp in employees:
        emp_id = emp.get('employeeId')
        emp_offset = emp.get('rotationOffset', 0)
        
        work_dates = sorted(employee_work_dates.get(emp_id, []))
        if len(work_dates) < 2:
            continue
        
        first_work = work_dates[0]
        last_work = work_dates[-1]
        
        # Check each date between first and last work dates
        current_date = first_work
        while current_date <= last_work:
            days_from_start = (current_date - pattern_start_date).days
            pattern_day = (days_from_start + emp_offset) % pattern_length
            expected_shift = base_pattern[pattern_day]
            
            if expected_shift in ['D', 'N'] and current_date not in work_dates:
                score_book.soft(
                    "S18",
                    f"{emp_id} on {current_date}: Gap (U-slot on pattern work day)",
                    gap_penalty_per_day
                )
                total_gap_days += 1
            
            current_date += timedelta(days=1)
    
    return total_gap_days

