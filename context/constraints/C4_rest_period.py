"""C4: Minimum rest between shifts (HARD constraint).

Enforce minimum rest period between consecutive shifts for the same employee.
Default: 11 hours = 660 minutes minimum rest between shift end and next shift start.
APGD-D10: 8 hours = 480 minutes minimum rest.
"""
from collections import defaultdict
from datetime import timedelta


def add_constraints(model, ctx):
    """
    Enforce minimum rest period between consecutive shifts (HARD).
    Standard: 11 hours minimum rest.
    APGD-D10: 8 hours minimum rest.
    
    Strategy: For each employee, identify shift pairs that violate the min rest requirement.
    Add disjunctive constraints: NOT (both shifts assigned).
    
    Args:
        model: CP-SAT model
        ctx: Context dict with 'slots', 'employees', 'x', 'constraintList'
    """
    from context.engine.time_utils import is_apgd_d10_employee
    
    slots = ctx.get('slots', [])
    employees = ctx.get('employees', [])
    x = ctx.get('x', {})
    constraint_list = ctx.get('constraintList', [])
    
    if not slots or not x or not employees:
        print(f"[C4] Warning: Slots, employees, or decision variables not available")
        return
    
    # Build requirement map for APGD-D10 detection
    req_map = {}
    for demand in ctx.get('demandItems', []):
        for req in demand.get('requirements', []):
            req_map[req['requirementId']] = req
    
    # Identify APGD-D10 employees
    apgd_employees = set()
    for emp in employees:
        emp_id = emp.get('employeeId')
        product = emp.get('productTypeId', '')
        for req_id, req in req_map.items():
            if req.get('productTypeId', '') == product:
                if is_apgd_d10_employee(emp, req):
                    apgd_employees.add(emp_id)
                    break
    
    # Import constraint config helper
    from context.engine.constraint_config import get_constraint_param
    
    if apgd_employees:
        print(f"[C4] APGD-D10 detected: {len(apgd_employees)} employees with configured minimum rest")
    
    # Read min rest hours from constraintList (per employee, scheme-specific)
    # NEW format: defaultValue + schemeOverrides (e.g., P: 1 hour)
    # OLD format: params.minRestMinutes (backward compatible)
    min_rest_by_employee = {}  # emp_id -> min_rest_minutes
    
    for emp in employees:
        emp_id = emp.get('employeeId')
        
        # Read from constraintList (returns HOURS)
        min_rest_hours = get_constraint_param(
            ctx,
            'apgdMinRestBetweenShifts',
            employee=emp,
            param_name='minRestHours',  # NEW format uses hours
            default=8
        )
        
        # Try OLD format if NEW format returns default (backward compatibility)
        if min_rest_hours == 8:  # Default value, might be from OLD format
            # Check OLD format with minRestMinutes
            for constraint in constraint_list:
                if constraint.get('id') == 'apgdMinRestBetweenShifts':
                    params = constraint.get('params', {})
                    if 'minRestMinutes' in params:
                        # OLD format uses minutes directly
                        min_rest_by_employee[emp_id] = params['minRestMinutes']
                        break
            else:
                # No OLD format found, use NEW format hours → minutes
                min_rest_by_employee[emp_id] = int(min_rest_hours * 60)
        else:
            # NEW format: convert hours to minutes
            min_rest_by_employee[emp_id] = int(min_rest_hours * 60)
    
    # Check for incremental mode
    incremental_ctx = ctx.get('_incremental')
    last_locked_shift_end = {}
    
    if incremental_ctx:
        # Calculate last shift end time before solve window for each employee
        locked_assignments = incremental_ctx.get('lockedAssignments', [])
        from datetime import datetime as dt
        
        for assignment in locked_assignments:
            emp_id = assignment.get('employeeId')
            if not emp_id:
                continue
            
            end_dt_str = assignment.get('endDateTime')
            if end_dt_str:
                try:
                    end_dt = dt.fromisoformat(end_dt_str.replace('Z', '+00:00'))
                    
                    # Track the latest end time for this employee
                    if emp_id not in last_locked_shift_end or end_dt > last_locked_shift_end[emp_id]:
                        last_locked_shift_end[emp_id] = end_dt
                except Exception:
                    pass
        
        if last_locked_shift_end:
            print(f"[C4] INCREMENTAL MODE: Tracking last locked shift end for {len(last_locked_shift_end)} employees")
    
    constraints_added = 0
    
    # For each employee, check all shift pairs
    for emp in employees:
        emp_id = emp.get('employeeId')
        
        # Get employee-specific minimum rest from configuration
        emp_min_rest_minutes = min_rest_by_employee.get(emp_id, 480)
        min_rest_delta = timedelta(minutes=emp_min_rest_minutes)
        
        # Get all slots this employee could be assigned to
        emp_slots = [s for s in slots if (s.slot_id, emp_id) in x]
        
        if len(emp_slots) < 1:
            continue
        
        # INCREMENTAL MODE: Check if first new shift has sufficient rest from last locked shift
        if incremental_ctx and emp_id in last_locked_shift_end:
            last_end = last_locked_shift_end[emp_id]
            
            # Sort slots by start time
            sorted_by_start = sorted(emp_slots, key=lambda s: (s.date, s.start))
            
            # Check first slot in solve window
            if sorted_by_start:
                first_slot = sorted_by_start[0]
                rest_from_locked = first_slot.start - last_end
                
                if rest_from_locked < min_rest_delta:
                    # Insufficient rest from last locked shift - cannot assign to first slot
                    var = x[(first_slot.slot_id, emp_id)]
                    model.Add(var == 0)
                    constraints_added += 1
        
        if len(emp_slots) < 2:
            continue
        
        # Sort by end time (date + end datetime)
        sorted_slots = sorted(emp_slots, key=lambda s: (s.date, s.end))
        
        # Check ALL pairs where slot1 ends before slot2 starts
        # and there's insufficient rest between them
        for i in range(len(sorted_slots)):
            slot1 = sorted_slots[i]
            
            # Check all subsequent slots that might violate rest period
            for j in range(i + 1, len(sorted_slots)):
                slot2 = sorted_slots[j]
                
                # Skip if slot2 starts before slot1 ends (impossible overlap)
                if slot2.start < slot1.end:
                    continue
                
                # Calculate rest time between slot1 end and slot2 start
                rest_available = slot2.start - slot1.end
                
                # If rest is insufficient, add disjunctive constraint
                if rest_available < min_rest_delta:
                    var1 = x[(slot1.slot_id, emp_id)]
                    var2 = x[(slot2.slot_id, emp_id)]
                    
                    # Constraint: NOT (var1 AND var2)
                    # Implemented as: var1 + var2 <= 1
                    model.Add(var1 + var2 <= 1)
                    constraints_added += 1
                # NOTE: Removed early break - must check ALL pairs because different shift types
                # on the same day can have different rest periods (e.g., D->D vs D->N)
    
    # Calculate summary statistics for logging
    unique_rest_values = set(min_rest_by_employee.values())
    min_rest_summary = f"{min(unique_rest_values)//60}h-{max(unique_rest_values)//60}h" if unique_rest_values else "8h"
    
    print(f"[C4] Minimum Rest Between Shifts Constraint (HARD)")
    print(f"     Employees: {len(employees)}, Slots: {len(slots)}")
    print(f"     Rest requirements: {min_rest_summary} (scheme-specific)")
    print(f"     Unique rest values: {sorted([v//60 for v in unique_rest_values])}h")
    print(f"     ✓ Added {constraints_added} rest period disjunctive constraints\n")
