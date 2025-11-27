"""C3: Max consecutive working days ≤12 (HARD constraint).

Enforce maximum number of consecutive days an employee can work without a day off.
Global cap: ≤12 consecutive working days per employee.

A "working day" is any day the employee is assigned to at least one shift.
"""
from collections import defaultdict
from datetime import datetime, timedelta


def add_constraints(model, ctx):
    """
    Enforce maximum consecutive working days ≤12 per employee (HARD).
    
    Strategy: 
    1. Create daily indicator variables: day_worked[(emp_id, date)] = 1 if ANY shift assigned
    2. For every 13 consecutive calendar days, ensure sum(day_worked) <= 12
    
    Args:
        model: CP-SAT model
        ctx: Context dict with 'employees', 'slots', 'x'
    """
    
    slots = ctx.get('slots', [])
    employees = ctx.get('employees', [])
    x = ctx.get('x', {})
    
    if not slots or not x or not employees:
        print(f"[C3] Warning: Slots, employees, or decision variables not available")
        return
    
    max_consecutive = 12  # Hard cap: at most 12 consecutive working days
    
    # Check for incremental mode
    incremental_ctx = ctx.get('_incremental')
    locked_consecutive_days = {}
    if incremental_ctx:
        locked_consecutive_days = incremental_ctx.get('lockedConsecutiveDays', {})
        if locked_consecutive_days:
            print(f"[C3] INCREMENTAL MODE: Using locked consecutive days for {len(locked_consecutive_days)} employees")
    
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
    
    # OPTIMIZATION: For incremental solving, check solve window size
    # If solve window < 13 days, constraint is mathematically impossible to violate
    if incremental_ctx:
        temporal_window = incremental_ctx.get('temporalWindow', {})
        if temporal_window:
            from datetime import datetime as dt
            solve_from = dt.fromisoformat(temporal_window.get('solveFromDate')).date()
            solve_to = dt.fromisoformat(temporal_window.get('solveToDate')).date()
            solve_window_days = (solve_to - solve_from).days + 1
            
            if solve_window_days < max_consecutive + 1:
                print(f"[C3] Maximum Consecutive Working Days Constraint (HARD)")
                print(f"     Employees: {len(employees)}, Planning horizon: {len(sorted_dates)} days")
                print(f"     INCREMENTAL MODE: Solve window is {solve_window_days} days (< 13)")
                print(f"     ✓ OPTIMIZATION: Skipping constraint (impossible to violate in <13 day window)\n")
                return
    
    # Regular check for full solve mode
    if len(sorted_dates) < max_consecutive + 1:
        print(f"[C3] Maximum Consecutive Working Days Constraint (HARD)")
        print(f"     Employees: {len(employees)}, Planning horizon: {len(sorted_dates)} days")
        print(f"     No constraints needed (horizon < 13 days)\n")
        return
    
    constraints_added = 0
    
    # For each employee, create day-worked indicator variables and add constraints
    for emp in employees:
        emp_id = emp.get('employeeId')
        
        if emp_id not in emp_slots_by_date:
            continue  # No slots for this employee
        
        # Create indicator variables: day_worked[(emp_id, date)] = 1 if employee works on date
        day_worked = {}
        
        for date_str in sorted_dates:
            if date_str in emp_slots_by_date[emp_id]:
                # This employee has slots on this date
                slot_ids = emp_slots_by_date[emp_id][date_str]
                
                # Create boolean var: day_worked = 1 if ANY slot assigned on this date
                day_var = model.NewBoolVar(f'day_worked_{emp_id}_{date_str}')
                day_worked[date_str] = day_var
                
                # Link day_var to actual slot assignments
                # day_var = 1 if sum(x[(slot_id, emp_id)]) >= 1
                # Equivalent to: day_var <= sum(x) and day_var >= x[i] for any i
                slot_vars = [x[(slot_id, emp_id)] for slot_id in slot_ids]
                
                # If any slot is assigned, day_var must be 1
                for slot_var in slot_vars:
                    model.Add(day_var >= slot_var)
                
                # If day_var is 1, at least one slot must be assigned
                model.Add(sum(slot_vars) >= day_var)
            else:
                # No slots on this date for this employee
                day_worked[date_str] = 0
        
        # Now add constraints: for every 13 consecutive calendar days, sum <= 12
        # INCREMENTAL MODE: Account for locked streak before solve window
        locked_streak = locked_consecutive_days.get(emp_id, 0)
        
        if locked_streak > 0:
            # Employee already worked 'locked_streak' consecutive days before solve window
            # From the first date in solve window, they can only work (12 - locked_streak) more consecutive days
            remaining_allowed = max_consecutive - locked_streak
            
            if remaining_allowed <= 0:
                # Employee already hit max consecutive - cannot work on first days of solve window
                # Must take a break first
                print(f"[C3] Employee {emp_id} already worked {locked_streak} consecutive days (>= {max_consecutive})")
                # Force day off on first date (if this is start of solve window)
                if sorted_dates and sorted_dates[0] in day_worked:
                    var = day_worked[sorted_dates[0]]
                    if not isinstance(var, int):
                        model.Add(var == 0)
                        constraints_added += 1
            else:
                # Employee can work 'remaining_allowed' more consecutive days from start
                consecutive_days_from_start = []
                for date_str in sorted_dates:
                    if date_str in day_worked:
                        var = day_worked[date_str]
                        if not isinstance(var, int):
                            consecutive_days_from_start.append(var)
                    else:
                        # Gap - employee doesn't work this day, so streak resets
                        break
                    
                    # Check if we've collected enough consecutive days
                    if len(consecutive_days_from_start) > remaining_allowed:
                        # Can't work more than remaining_allowed consecutive days from start
                        model.Add(sum(consecutive_days_from_start[:remaining_allowed + 1]) <= remaining_allowed)
                        constraints_added += 1
                        break
        
        for i in range(len(sorted_dates) - max_consecutive):
            window_dates = sorted_dates[i:i + max_consecutive + 1]  # 13 consecutive dates
            
            # Check if these are truly consecutive calendar days
            start_date = window_dates[0]
            end_date = window_dates[-1]
            days_between = (end_date - start_date).days
            
            if days_between == max_consecutive:  # Exactly 12 days apart = 13 calendar days
                # Sum of working days in this window must be <= 12
                day_vars_in_window = []
                for date_str in window_dates:
                    if date_str in day_worked:
                        var = day_worked[date_str]
                        # Only include actual variables (not constant 0)
                        if not isinstance(var, int):
                            day_vars_in_window.append(var)
                
                if len(day_vars_in_window) > max_consecutive:
                    # Only add constraint if there are potentially >12 working days
                    model.Add(sum(day_vars_in_window) <= max_consecutive)
                    constraints_added += 1
    
    print(f"[C3] Maximum Consecutive Working Days Constraint (HARD)")
    print(f"     Employees: {len(employees)}, Planning horizon: {len(sorted_dates)} days")
    print(f"     Max consecutive days allowed: {max_consecutive}")
    print(f"     ✓ Added {constraints_added} rolling window constraints\n")
