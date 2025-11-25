"""C2: Weekly <=44h (normal hours only) and Monthly OT <=72h - HARD constraints.

C2: Weekly <=44h (normal hours only, exclude lunch & OT); Monthly OT <=72h.

Canonical model:
- normal_hours = min(gross, 9.0) - lunch (for 44h weekly cap)
- ot_hours = max(0, gross - 9.0) (for 72h monthly cap)

This constraint enforces:
1. Sum of normal_hours per employee per week <= 44h (HARD)
2. Sum of ot_hours per employee per month <= 72h (HARD)

All constraints added via model.Add() for hard enforcement.

Input Schema (v0.43):
- employees: [{ employeeId, scheme, ... }]
- demandItems: [{ demandId, shiftStartDate, shifts: [{ shiftDetails, rotationSequence }] }]
- planningHorizon: { startDate, endDate }
"""
from datetime import datetime, timedelta
from context.engine.time_utils import split_shift_hours
from collections import defaultdict


def add_constraints(model, ctx):
    """
    Enforce weekly normal-hours cap (44h) and monthly OT cap (72h) - HARD constraints.
    
    HARD constraints - solution must not violate these.
    
    Normal hours = gross - lunch (per shift)
    OT hours = max(0, gross - 9.0) (per shift)
    
    Constraints added to CP-SAT model:
        - For each employee-week: sum(normal_hours) <= 44h
        - For each employee-month: sum(ot_hours) <= 72h
    
    Args:
        model: CP-SAT model
        ctx: Context dict with 'employees', 'demandItems', 'slots', 'x'
    """
    
    employees = ctx.get('employees', [])
    demand_items = ctx.get('demandItems', [])
    slots = ctx.get('slots', [])
    x = ctx.get('x', {})
    
    if not slots or not x:
        print(f"[C2] Warning: Slots or decision variables not available")
        return
    
    # Extract shift information by demand and shift code
    shift_info = {}
    for demand in demand_items:
        demand_id = demand.get('demandId')
        
        for shift_group in demand.get('shifts', []):
            shift_details_list = shift_group.get('shiftDetails', [])
            
            for sd in shift_details_list:
                shift_code = sd.get('shiftCode', '?')
                start_str = sd.get('start')
                end_str = sd.get('end')
                
                try:
                    start_time = datetime.strptime(start_str, '%H:%M').time() if start_str else None
                    end_time = datetime.strptime(end_str, '%H:%M').time() if end_str else None
                    
                    if start_time and end_time:
                        dummy_date = datetime(2025, 1, 1)
                        start_dt = datetime.combine(dummy_date.date(), start_time)
                        end_dt = datetime.combine(dummy_date.date(), end_time)
                        
                        if end_dt < start_dt:
                            end_dt = end_dt + timedelta(days=1)
                        
                        hours_breakdown = split_shift_hours(start_dt, end_dt)
                        key = f"{demand_id}-{shift_code}"
                        shift_info[key] = hours_breakdown
                except Exception:
                    pass
    
    # Build employee-week and employee-month groupings of slots
    emp_week_slots = defaultdict(lambda: defaultdict(list))  # emp_id -> week_key -> [slots]
    emp_month_slots = defaultdict(lambda: defaultdict(list))  # emp_id -> month_key -> [slots]
    
    for slot in slots:
        slot_date = slot.date
        iso_week = slot_date.isocalendar()[1]
        iso_year = slot_date.isocalendar()[0]
        week_key = f"{iso_year}-W{iso_week:02d}"
        month_key = f"{slot_date.year}-{slot_date.month:02d}"
        
        for emp in employees:
            emp_id = emp.get('employeeId')
            if (slot.slot_id, emp_id) in x:
                emp_week_slots[emp_id][week_key].append(slot)
                emp_month_slots[emp_id][month_key].append(slot)
    
    # ===== ADD CONSTRAINTS FOR WEEKLY NORMAL HOURS <= 44H =====
    weekly_constraints = 0
    for emp_id, weeks in emp_week_slots.items():
        for week_key, week_slots in weeks.items():
            # For each slot in this week, get normal hours and create weighted sum
            weighted_assignments = []
            for slot in week_slots:
                if (slot.slot_id, emp_id) not in x:
                    continue
                
                # Try to find shift info from demand_items first
                slot_key = f"{slot.demandId}-{slot.shiftCode}"
                hours_data = shift_info.get(slot_key)
                
                # FALLBACK: If shift_info lookup fails, calculate directly from slot times
                if not hours_data:
                    try:
                        hours_data = split_shift_hours(slot.start, slot.end)
                    except Exception:
                        continue
                
                if hours_data:
                    normal_hours = hours_data.get('normal', 0)
                    var = x[(slot.slot_id, emp_id)]
                    
                    # Only include if there are actual normal hours
                    if normal_hours > 0:
                        # Scale to integer (multiply by 10 for tenths of hours)
                        int_hours = int(round(normal_hours * 10))
                        weighted_assignments.append((var, int_hours))
            
            if weighted_assignments:
                # Create constraint: sum(var_i * normal_hours_i) <= 44 * 10 = 440 (in tenths)
                constraint_expr = sum(var * hours for var, hours in weighted_assignments)
                model.Add(constraint_expr <= 440)  # 44 hours = 440 tenths
                weekly_constraints += 1
    
    # ===== ADD CONSTRAINTS FOR MONTHLY OT HOURS <= 72H =====
    monthly_constraints = 0
    for emp_id, months in emp_month_slots.items():
        for month_key, month_slots in months.items():
            # For each slot in this month, get OT hours and create weighted sum
            weighted_assignments = []
            for slot in month_slots:
                if (slot.slot_id, emp_id) not in x:
                    continue
                
                # Try to find shift info from demand_items first
                slot_key = f"{slot.demandId}-{slot.shiftCode}"
                hours_data = shift_info.get(slot_key)
                
                # FALLBACK: If shift_info lookup fails, calculate directly from slot times
                if not hours_data:
                    try:
                        hours_data = split_shift_hours(slot.start, slot.end)
                    except Exception:
                        continue
                
                if hours_data:
                    ot_hours = hours_data.get('ot', 0)
                    var = x[(slot.slot_id, emp_id)]
                    
                    # Only include if there are actual OT hours
                    if ot_hours > 0:
                        # Scale to integer (multiply by 10 for tenths of hours)
                        int_hours = int(round(ot_hours * 10))
                        weighted_assignments.append((var, int_hours))
            
            if weighted_assignments:
                # Create constraint: sum(var_i * ot_hours_i) <= 72 * 10 = 720 (in tenths)
                constraint_expr = sum(var * hours for var, hours in weighted_assignments)
                model.Add(constraint_expr <= 720)  # 72 hours = 720 tenths
                monthly_constraints += 1
    
    print(f"[C2] Weekly & Monthly Hours Constraints (HARD)")
    print(f"     Employees: {len(employees)}, Slots: {len(slots)}")
    print(f"     Weekly normal hours cap: <=44h per employee per ISO week")
    print(f"     Monthly OT hours cap: <=72h per employee per calendar month")
    print(f"     ✓ Added {weekly_constraints} weekly normal hours constraints (HARD)")
    print(f"     ✓ Added {monthly_constraints} monthly OT hours constraints (HARD)\n")
