"""C6: Part-time employee weekly hour limits (HARD constraint).

Enforce that part-time employees (Scheme P) do not exceed their weekly NORMAL hour limits.
Scheme P limit: Max 34.98 NORMAL hours per week (MOM Employment Act).

IMPORTANT: This constraint applies ONLY to normal hours, not total hours.
- Hours beyond 34.98h/week are considered OVERTIME
- Employee can work 6-7 days/week if they have OT hours
- Monthly OT cap (72h) is enforced separately by C17

Example: 8h shift (9h gross - 1h lunch)
- Week 1: 4 days × 8h = 32h normal ✅
- Week 2: 6 days × 8h = 32h normal + 16h OT ✅ (within 72h/month)
- Pattern DDDODDD (6 work days) is FEASIBLE
"""
from collections import defaultdict
from datetime import datetime
from context.engine.time_utils import normalize_scheme


def add_constraints(model, ctx):
    """
    Enforce weekly NORMAL hour limits for Scheme P (part-time) employees (HARD).
    
    Strategy: 
    1. Identify Scheme P employees
    2. For each week, sum NORMAL hours (not total hours)
    3. Enforce: normal_hours_per_week <= 34.98h
    
    Note: Normal hours are calculated per MOM rules:
    - For shifts ≤8h gross: All hours are normal
    - For shifts >8h gross: First 8h net are normal, rest is OT
    - Overtime hours are NOT counted against this limit
    
    Args:
        model: CP-SAT model
        ctx: Context dict with 'slots', 'employees', 'x'
    """
    
    slots = ctx.get('slots', [])
    employees = ctx.get('employees', [])
    x = ctx.get('x', {})
    
    if not slots or not x or not employees:
        print(f"[C6] Warning: Slots, employees, or decision variables not available")
        return
    
    # Identify Scheme P (part-time) employees
    # Use normalize_scheme() to handle both 'P' and 'Scheme P' formats
    scheme_p_employees = []
    for emp in employees:
        emp_id = emp.get('employeeId')
        scheme_raw = emp.get('scheme', '')
        scheme_normalized = normalize_scheme(scheme_raw)
        if scheme_normalized == 'P':
            scheme_p_employees.append(emp_id)
    
    if not scheme_p_employees:
        print(f"[C6] Part-Time Employee Weekly Normal Hour Limits Constraint (HARD)")
        print(f"     No Scheme P employees found\n")
        return
    
    # Group slots by (emp_id, week_key)
    emp_week_slots = defaultdict(list)  # (emp_id, week_key) -> [slots]
    
    for slot in slots:
        slot_date = slot.date
        iso_year, iso_week, _ = slot_date.isocalendar()
        week_key = f"{iso_year}-W{iso_week:02d}"
        
        for emp_id in scheme_p_employees:
            if (slot.slot_id, emp_id) in x:
                emp_week_slots[(emp_id, week_key)].append(slot)
    
    # Add constraints for each Scheme P employee per week
    constraints_added = 0
    max_normal_hours_per_week = 34.98  # Scheme P weekly normal hour cap
    
    for (emp_id, week_key), week_slots in emp_week_slots.items():
        # Calculate NET hours for this week (gross - lunch)
        # For Scheme P: Net hours up to 34.98h are normal, rest are OT
        # This allows 6-day patterns: 6 days × 8h net = 48h → 34.98h normal + 13.02h OT
        net_hour_terms = []
        
        from context.engine.time_utils import lunch_hours
        
        for slot in week_slots:
            if (slot.slot_id, emp_id) in x:
                var = x[(slot.slot_id, emp_id)]
                gross_hours = (slot.end - slot.start).total_seconds() / 3600.0
                lunch = lunch_hours(gross_hours)
                net_hours = gross_hours - lunch  # Actual working hours
                
                if net_hours > 0:
                    # For CP-SAT, scale hours to integer tenths (×10)
                    # 8.0h → 80, 8.745h → 87 (rounded)
                    int_hours = int(round(net_hours * 10))
                    net_hour_terms.append(var * int_hours)
        
        if not net_hour_terms:
            continue
        
        total_net_hours_var = sum(net_hour_terms)
        
        # CONSTRAINT: Net hours per week <= 34.98h (normal hour cap)
        # Hours beyond 34.98h automatically become OT (calculated post-solve)
        # Scaled: <=349.8 → 350 (in tenths)
        max_hours_scaled = int(round(max_normal_hours_per_week * 10))  # 349.8 → 350
        model.Add(total_net_hours_var <= max_hours_scaled)
        
        constraints_added += 1
    
    print(f"[C6] Part-Time Employee Weekly Normal Hour Limits Constraint (HARD)")
    print(f"     Total employees: {len(employees)}")
    print(f"     Scheme P (part-time) employees: {len(scheme_p_employees)}")
    print(f"     Max normal hours/week: {max_normal_hours_per_week}h")
    print(f"     Note: Employees can work >4 days/week if hours beyond 34.98h are OT")
    print(f"     ✓ Added {constraints_added} weekly normal hour limit constraints\n")
