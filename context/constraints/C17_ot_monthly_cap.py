"""C17: Monthly OT cap ≤72h per employee (HARD).

Canonical model:
- ot_hours = max(0, gross_hours - 9.0) per shift
- Sum of ot_hours per employee per calendar month ≤ 72h

This constraint enforces monthly OT doesn't exceed 72 hours (HARD).

Integrated with C2 for consistency: both use same hour calculation.
"""
from collections import defaultdict
from context.engine.constraint_config import get_constraint_param


def add_constraints(model, ctx):
    """
    Enforce monthly OT hour cap (72h per employee) (HARD).
    
    Strategy: Group slots by (employee, calendar month).
    For each month, sum OT hours weighted by assignments.
    Constraint: sum(var * scaled_ot) <= 720 (72h in tenths).
    
    Args:
        model: CP-SAT model
        ctx: Context dict with 'employees', 'slots', 'x'
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
    
    # Group slots by (employee, calendar month)
    emp_month_slots = defaultdict(list)
    
    for slot in slots:
        slot_date = slot.date
        month_key = f"{slot_date.year}-{slot_date.month:02d}"
        
        for emp in employees:
            emp_id = emp.get('employeeId')
            if (slot.slot_id, emp_id) in x:
                emp_month_slots[(emp_id, month_key)].append(slot)
    
    # Add monthly OT cap constraints
    monthly_constraints = 0
    for (emp_id, month_key), month_slots in emp_month_slots.items():
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
            # Read monthly OT cap from JSON with fallback to 72h
            employee_dict = {'employeeId': emp_id}
            monthly_ot_cap = get_constraint_param(
                ctx, 'momMonthlyOTcap72h', employee_dict, default=72.0
            )
            monthly_ot_cap_int = int(round(monthly_ot_cap * 10))  # Convert to tenths
            
            # Constraint: sum(var * scaled_ot) <= monthly_ot_cap
            model.Add(sum(terms) <= monthly_ot_cap_int)
            monthly_constraints += 1
    
    print(f"[C17] Monthly OT Cap Constraint (HARD)")
    print(f"     Employees: {len(employees)}, Slots: {len(slots)}")
    print(f"     Monthly OT cap: ≤72h per employee per calendar month")
    print(f"     ✓ Added {monthly_constraints} monthly OT constraints\n")
