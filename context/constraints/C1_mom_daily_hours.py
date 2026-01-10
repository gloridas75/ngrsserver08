"""C1: Daily hours cap by scheme (gross hours = normal + lunch, not OT).

HARD Constraint - enforced via model.Add():
- Scheme A: ≤ 14 hours per day (gross)
- Scheme B: ≤ 13 hours per day (gross)
- Scheme P: ≤ 9 hours per day (gross)

Note: Gross hours = total shift duration (includes lunch break).
For 44-hour weekly cap, see C2 (normal hours only).
For 72-hour monthly OT cap, see C17 (ot hours only).

Per-shift constraints: Each individual shift must not exceed scheme max.

Input Schema (v0.70):
- employees: [{ employeeId, scheme, ... }]
- Slot objects have start and end datetime fields
"""
from collections import defaultdict
from datetime import datetime, timedelta
from context.engine.time_utils import split_shift_hours, normalize_scheme


def add_constraints(model, ctx):
    """
    Enforce maximum daily gross working hours by employee scheme.
    
    HARD Constraint: Each shift must not exceed gross hours limit for employee's scheme.
    - Scheme A: ≤ 14 hours per shift
    - Scheme B: ≤ 13 hours per shift
    - Scheme P: ≤ 9 hours per shift
    
    Gross hours = total shift duration including lunch break.
    v0.70: Use slot.start and slot.end directly.
    
    Strategy: For each slot, check its gross hours against scheme limits.
    If any slot exceeds the limit for an employee's scheme, block assignment via model.Add(var == 0).
    
    Args:
        model: CP-SAT model
        ctx: Context dict with 'employees', 'slots', 'x'
    """
    
    employees = ctx.get('employees', [])
    slots = ctx.get('slots', [])
    x = ctx.get('x', {})
    
    if not slots or not x:
        print(f"[C1] Warning: Slots or decision variables not available")
        return
    
    # Import constraint config helper
    from context.engine.constraint_config import get_constraint_param
    
    # Build employee scheme map and max hours per employee
    employee_scheme = {}
    max_gross_by_employee = {}  # emp_id -> max_gross_hours
    
    for emp in employees:
        emp_id = emp.get('employeeId')
        scheme_raw = emp.get('scheme', 'A')
        scheme = normalize_scheme(scheme_raw)  # Normalize "Scheme A" → 'A'
        employee_scheme[emp_id] = scheme
        
        # Read max daily hours from constraintList (scheme-specific)
        # Supports both NEW format (defaultValue + schemeOverrides) and OLD format (params)
        max_gross = get_constraint_param(
            ctx, 
            'momDailyHoursCap', 
            employee=emp, 
            param_name='maxDailyHours',  # For OLD format compatibility
            default=14.0 if scheme == 'A' else 13.0 if scheme == 'B' else 9.0
        )
        max_gross_by_employee[emp_id] = float(max_gross)
    
    # Build scheme-wise summary for logging
    max_gross_by_scheme = {}
    for scheme in ['A', 'B', 'P']:
        # Compare with normalized scheme
        emp_of_scheme = [e for e in employees if normalize_scheme(e.get('scheme', 'A')) == scheme]
        if emp_of_scheme:
            max_gross_by_scheme[scheme] = max_gross_by_employee.get(emp_of_scheme[0]['employeeId'], 14.0)
    
    # Build shift hour map from slots
    shift_hours = {}  # (demandId, shiftCode) -> gross_hours
    for slot in slots:
        key = (slot.demandId, slot.shiftCode)
        if key not in shift_hours:
            gross = (slot.end - slot.start).total_seconds() / 3600.0
            shift_hours[key] = gross
    
    # Add constraints: For each slot-employee pair, check if shift exceeds scheme limit
    constraints_added = 0
    blocks_by_employee = {}  # Track blocks per employee for debugging
    
    for slot in slots:
        slot_key = (slot.demandId, slot.shiftCode)
        gross_hours = shift_hours.get(slot_key, 0)
        
        for emp in employees:
            emp_id = emp.get('employeeId')
            
            if (slot.slot_id, emp_id) not in x:
                continue
            
            scheme = employee_scheme.get(emp_id, 'A')
            max_gross = max_gross_by_employee.get(emp_id, 14.0)
            
            # If shift exceeds employee's daily limit, block assignment
            if gross_hours > max_gross:
                var = x[(slot.slot_id, emp_id)]
                model.Add(var == 0)
                constraints_added += 1
                blocks_by_employee[emp_id] = blocks_by_employee.get(emp_id, 0) + 1
    
    print(f"[C1] Daily Gross Hours Constraint (HARD - by Scheme)")
    print(f"     Total employees: {len(employees)}")
    print(f"     Total slots: {len(slots)}")
    print(f"     Unique shifts: {len(shift_hours)}")
    print(f"     Scheme limits: A≤{max_gross_by_scheme.get('A', 14)}h, B≤{max_gross_by_scheme.get('B', 13)}h, P≤{max_gross_by_scheme.get('P', 9)}h")
    
    if blocks_by_employee:
        print(f"     Blocks by employee:")
        for emp_id, count in blocks_by_employee.items():
            emp_scheme = employee_scheme.get(emp_id, 'Unknown')
            emp_limit = max_gross_by_employee.get(emp_id, 0)
            print(f"       {emp_id} (Scheme {emp_scheme}, {emp_limit}h limit): {count} blocks")
    
    print(f"     ✓ Added {constraints_added} per-shift scheme violations blocks\n")
