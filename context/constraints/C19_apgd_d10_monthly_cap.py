"""C19: APGD-D10 Monthly Hour Cap ≤246h or ≤268h (HARD constraint).

Enforce monthly total hour caps for APGD-D10 employees:
- Standard (locals + non-CPL/SGT): ≤246h for 31-day months
- Foreign CPL/SGT: ≤268h for 31-day months

Monthly caps scale by days in month:
- 28 days: 224h (standard) / 244h (foreign CPL/SGT)
- 29 days: 231h (standard) / 252h (foreign CPL/SGT)
- 30 days: 238h (standard) / 260h (foreign CPL/SGT)
- 31 days: 246h (standard) / 268h (foreign CPL/SGT)

Hours calculated as: gross_hours - lunch_hours per shift.
"""
from collections import defaultdict
from datetime import datetime


def add_constraints(model, ctx):
    """
    Enforce APGD-D10 monthly total hour caps (HARD).
    
    Only applies to APGD-D10 employees (Scheme A + APO + enableAPGD-D10=true).
    
    Strategy:
    1. Identify APGD-D10 employees and their category
    2. Group slots by (employee, month)
    3. Calculate net hours per slot (gross - lunch)
    4. Add constraint: sum(net_hours) <= monthly_cap
    
    Args:
        model: CP-SAT model
        ctx: Context dict with 'slots', 'employees', 'x'
    """
    from context.engine.time_utils import (
        is_apgd_d10_employee, 
        get_apgd_d10_category,
        span_hours,
        lunch_hours
    )
    
    slots = ctx.get('slots', [])
    employees = ctx.get('employees', [])
    x = ctx.get('x', {})
    
    if not slots or not x or not employees:
        print(f"[C19] Warning: Slots, employees, or decision variables not available")
        return
    
    # Build requirement map for APGD-D10 detection
    req_map = {}
    for demand in ctx.get('demandItems', []):
        for req in demand.get('requirements', []):
            req_map[req['requirementId']] = req
    
    # Identify APGD-D10 employees and their categories
    apgd_employees = {}  # emp_id -> category ('standard' or 'foreign_cpl_sgt')
    
    for emp in employees:
        emp_id = emp.get('employeeId')
        product = emp.get('productTypeId', '')
        
        # Check if APGD-D10 eligible
        is_apgd = False
        for req_id, req in req_map.items():
            if req.get('productTypeId', '') == product:
                if is_apgd_d10_employee(emp, req):
                    is_apgd = True
                    break
        
        if is_apgd:
            category = get_apgd_d10_category(emp)
            apgd_employees[emp_id] = category
    
    if not apgd_employees:
        print(f"[C19] APGD-D10 Monthly Hour Cap (HARD)")
        print(f"     No APGD-D10 employees detected - skipping constraint\n")
        return
    
    print(f"[C19] APGD-D10 Monthly Hour Cap: {len(apgd_employees)} employees")
    
    # Monthly cap lookup: (days_in_month, category) -> max_hours
    MONTHLY_CAPS = {
        (28, 'standard'): 224,
        (28, 'foreign_cpl_sgt'): 244,
        (29, 'standard'): 231,
        (29, 'foreign_cpl_sgt'): 252,
        (30, 'standard'): 238,
        (30, 'foreign_cpl_sgt'): 260,
        (31, 'standard'): 246,
        (31, 'foreign_cpl_sgt'): 268,
    }
    
    # Group slots by (employee, month)
    emp_month_slots = defaultdict(list)  # (emp_id, year_month) -> [slots]
    
    for slot in slots:
        for emp_id, category in apgd_employees.items():
            if (slot.slot_id, emp_id) in x:
                # Extract year-month from slot date
                year_month = (slot.date.year, slot.date.month)
                emp_month_slots[(emp_id, year_month)].append(slot)
    
    constraints_added = 0
    
    # Add constraint for each (employee, month) combination
    for (emp_id, year_month), month_slots in emp_month_slots.items():
        year, month = year_month
        category = apgd_employees[emp_id]
        
        # Determine days in this month
        if month in [1, 3, 5, 7, 8, 10, 12]:
            days_in_month = 31
        elif month in [4, 6, 9, 11]:
            days_in_month = 30
        elif month == 2:
            # Check leap year
            if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
                days_in_month = 29
            else:
                days_in_month = 28
        else:
            days_in_month = 31  # Fallback
        
        # Get monthly cap for this category
        monthly_cap = MONTHLY_CAPS.get((days_in_month, category), 246)
        
        # Calculate net hours for each slot (gross - lunch)
        # We'll use integer minutes to avoid floating point issues in CP-SAT
        slot_net_minutes = []
        slot_vars = []
        
        for slot in month_slots:
            # Calculate gross hours
            gross = span_hours(slot.start, slot.end)
            
            # Calculate lunch hours
            lunch = lunch_hours(gross)
            
            # Net hours = gross - lunch
            net_hours = gross - lunch
            
            # Convert to minutes (integer for CP-SAT)
            net_minutes = int(round(net_hours * 60))
            
            # Get decision variable
            var = x[(slot.slot_id, emp_id)]
            
            slot_net_minutes.append(net_minutes)
            slot_vars.append(var)
        
        if not slot_vars:
            continue
        
        # Add constraint: sum(var[i] * net_minutes[i]) <= monthly_cap_minutes
        monthly_cap_minutes = monthly_cap * 60
        
        # Build weighted sum: each slot contributes its net_minutes if assigned
        weighted_terms = []
        for i, var in enumerate(slot_vars):
            weighted_terms.append(var * slot_net_minutes[i])
        
        model.Add(sum(weighted_terms) <= monthly_cap_minutes)
        constraints_added += 1
    
    print(f"[C19] APGD-D10 Monthly Hour Cap (HARD)")
    print(f"     APGD-D10 employees: {len(apgd_employees)}")
    print(f"     Standard cap: 224-246h (28-31 days)")
    print(f"     Foreign CPL/SGT cap: 244-268h (28-31 days)")
    print(f"     ✓ Added {constraints_added} monthly hour cap constraints\n")
