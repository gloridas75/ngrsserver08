"""C16: No overlapping shifts for the same employee.

Implement as: def add_constraints(model, ctx): ...
- Use ctx['employees'], ctx['slots'], ctx['x'] (decision variables)
- Ensure no employee works two overlapping shifts simultaneously.

Input Schema (v0.43):
- employees: [{ employeeId, ... }]
- slots: List of Slot objects with start/end times
"""

def add_constraints(model, ctx):
    """
    Enforce that no employee can be assigned to two overlapping shifts simultaneously.
    
    This constraint ensures that for each employee, if they are assigned to two different slots,
    those slots cannot have overlapping time ranges.
    
    Args:
        model: CP-SAT model from ortools
        ctx: Context dict with 'employees', 'slots', 'x' (decision variables)
    """
    
    employees = ctx.get('employees', [])
    slots = ctx.get('slots', [])
    x = ctx.get('x', {})  # Decision variables: x[(slot_id, emp_id)]
    
    if not slots or not x:
        print(f"[C16] No Overlapping Shifts Constraint")
        print(f"     Skipping: slots or decision variables not available")
        return
    
    # Check if outcomeBased mode - skip overlap check as positions don't overlap by design
    demand_items = ctx.get('demandItems', [])
    is_outcome_based = any(di.get('rosteringBasis') == 'outcomeBased' for di in demand_items)
    
    print(f"[C16] No Overlapping Shifts Constraint")
    print(f"     Total employees: {len(employees)}")
    print(f"     Total slots: {len(slots)}")
    
    if is_outcome_based:
        print(f"[C16] Skipping overlap check for outcomeBased mode (positions don't overlap)")
        print(f"     ✓ Constraint satisfied by design\n")
        return
    
    constraints_added = 0
    
    # For each employee, check all pairs of slots for time conflicts
    for emp in employees:
        emp_id = emp.get('employeeId')
        
        # Get all slots this employee could be assigned to
        emp_slots = [s for s in slots if (s.slot_id, emp_id) in x]
        
        if len(emp_slots) < 2:
            continue
        
        # Check all pairs of slots for overlaps
        for i in range(len(emp_slots)):
            for j in range(i + 1, len(emp_slots)):
                slot1 = emp_slots[i]
                slot2 = emp_slots[j]
                
                # Check if time ranges overlap
                # Overlap occurs if: start1 < end2 AND start2 < end1
                if slot1.start < slot2.end and slot2.start < slot1.end:
                    # Add disjunctive constraint: NOT (x[slot1, emp] AND x[slot2, emp])
                    # Implemented as: x[slot1, emp] + x[slot2, emp] <= 1
                    var1 = x.get((slot1.slot_id, emp_id))
                    var2 = x.get((slot2.slot_id, emp_id))
                    
                    if var1 is not None and var2 is not None:
                        model.Add(var1 + var2 <= 1)
                        constraints_added += 1
    
    print(f"[C16] No Overlapping Shifts Constraint (HARD)")
    print(f"     ✓ Added {constraints_added} no-overlap disjunctive constraints\n")
