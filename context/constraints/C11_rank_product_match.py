"""C11: Match AVSO/CVSO/APO to requirement product type.

Enforce rank/product alignment: employee's rank must match requirement's product type.
AVSO→AVSO, CVSO→CVSO, APO→APO (no cross-rank assignments).

Input Schema (v0.70):
- employees: [{ employeeId, rankId: 'AVSO'|'CVSO'|'APO', ... }]
- Slot objects have productTypeId from requirements
- planningHorizon: { startDate, endDate }
"""
from collections import defaultdict


def add_constraints(model, ctx):
    """
    Enforce rank/product type alignment for assignments (HARD constraint).
    
    This constraint ensures:
    1. Employee rank matches requirement product type
    2. No AVSO officer can work APO shift
    3. No CVSO officer can work APO shift
    4. Maintains operational role separation
    
    Rank hierarchy:
    - AVSO: Airport VSO (aviation security)
    - CVSO: Civil VSO (non-aviation)
    - APO: Airport Police Officer (law enforcement)
    
    Args:
        model: CP-SAT model from ortools
        ctx: Context dict with planning data
    """
    
    employees = ctx.get('employees', [])
    slots = ctx.get('slots', [])
    x = ctx.get('x', {})
    
    if not slots or not x:
        print(f"[C11] Warning: Slots or decision variables not available")
        return
    
    # Build a map of employee to rank
    employee_rank_map = {}
    for emp in employees:
        emp_id = emp.get('employeeId')
        rank = emp.get('rankId', 'UNKNOWN')
        employee_rank_map[emp_id] = rank
    
    # Add constraints: for each slot-employee pair, enforce rank matching
    rank_match_constraints = 0
    for slot in slots:
        # v0.95: rankIds is a list (OR logic - employee must match ANY rank in the list)
        slot_ranks = getattr(slot, 'rankIds', [])
        if not slot_ranks:
            # Fallback to singular rankId for backward compatibility
            slot_rank = getattr(slot, 'rankId', None)
            slot_ranks = [slot_rank] if slot_rank else []
        
        for emp in employees:
            emp_id = emp.get('employeeId')
            emp_rank = employee_rank_map.get(emp_id, 'UNKNOWN')
            
            if (slot.slot_id, emp_id) not in x:
                continue
            
            # If employee's rank is NOT in the slot's accepted ranks, block assignment
            # This implements OR logic: employee must have at least one matching rank
            if slot_ranks and emp_rank not in slot_ranks:
                var = x[(slot.slot_id, emp_id)]
                # Add constraint: var must be 0 (not assigned)
                model.Add(var == 0)
                rank_match_constraints += 1
    
    # Count by rank
    rank_counts = defaultdict(int)
    for emp in employees:
        rank = emp.get('rankId', 'UNKNOWN')
        rank_counts[rank] += 1
    
    # Count by product type from slots
    product_counts = defaultdict(int)
    for slot in slots:
        product = getattr(slot, 'productTypeId', 'UNKNOWN')
        product_counts[product] += 1
    
    # Count by rankIds from slots (combine all ranks)
    slot_rank_counts = defaultdict(int)
    for slot in slots:
        ranks = getattr(slot, 'rankIds', [])
        if not ranks:
            # Fallback to singular rankId
            rank = getattr(slot, 'rankId', 'UNKNOWN')
            ranks = [rank] if rank else ['UNKNOWN']
        for rank in ranks:
            slot_rank_counts[rank] += 1
    
    print(f"[C11] Rank/Product Type Match Constraint (HARD)")
    print(f"     Total employees: {len(employees)}")
    print(f"     Employee ranks: {dict(rank_counts)}")
    print(f"     Total slots: {len(slots)}")
    print(f"     Slot product types: {dict(product_counts)}")
    print(f"     Slot rankIds (OR logic): {dict(slot_rank_counts)}")
    print(f"     ✓ Added {rank_match_constraints} rank mismatch constraints (HARD)\n")
