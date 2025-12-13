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
    
    # Identify Scheme P (part-time) employees and extract patterns
    # Use normalize_scheme() to handle both 'P' and 'Scheme P' formats
    scheme_p_employees = []
    emp_patterns = {}  # emp_id -> work_pattern list
    
    for emp in employees:
        emp_id = emp.get('employeeId')
        scheme_raw = emp.get('scheme', '')
        scheme_normalized = normalize_scheme(scheme_raw)
        pattern = emp.get('workPattern', [])
        
        if scheme_normalized == 'P':
            scheme_p_employees.append(emp_id)
            emp_patterns[emp_id] = pattern
    
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
    
    # Helper to count work days in pattern
    def count_work_days(pattern):
        """Count D days in pattern (excluding O and U)"""
        if not pattern:
            return 0
        return sum(1 for day in pattern if day == 'D')
    
    for (emp_id, week_key), week_slots in emp_week_slots.items():
        # Calculate NORMAL hours for this week (not NET hours!)
        # For Scheme P, per-shift normal hours are pattern-dependent
        # Example: 6-day pattern → 4.996h normal/shift
        # Weekly: 6 × 4.996h = 29.976h normal (fits under 29.98h cap)
        # Remaining hours are OT: 6 × (7h - 4.996h) = 12.024h OT
        
        normal_hour_terms = []
        pattern = emp_patterns.get(emp_id, [])
        
        from context.engine.time_utils import lunch_hours
        from context.constraints.C2_mom_weekly_hours import calculate_pattern_aware_hours
        
        for slot in week_slots:
            if (slot.slot_id, emp_id) not in x:
                continue
            
            var = x[(slot.slot_id, emp_id)]
            gross_hours = (slot.end - slot.start).total_seconds() / 3600.0
            lunch = lunch_hours(gross_hours)
            
            # Calculate NORMAL hours using Scheme P pattern-aware logic
            # This is the KEY difference from old C6 (which capped NET hours)
            pattern_day = slot.patternDay if hasattr(slot, 'patternDay') else None
            normal_hours, _ = calculate_pattern_aware_hours(
                pattern, pattern_day, gross_hours, lunch, 'P'
            )
            
            if normal_hours > 0:
                # Scale to integer tenths for CP-SAT
                int_hours = int(round(normal_hours * 10))
                normal_hour_terms.append(var * int_hours)
        
        if not normal_hour_terms:
            continue
        
        # PATTERN-AWARE WEEKLY NORMAL CAP (Scheme P)
        # ≤4 work days: 34.98h/week normal cap
        # 5+ work days: 29.98h/week normal cap
        work_days_count = count_work_days(pattern)
        
        if work_days_count <= 4:
            max_normal_hours_per_week = 34.98
        else:  # 5, 6, or 7 days
            max_normal_hours_per_week = 29.98
        
        total_normal_hours_var = sum(normal_hour_terms)
        
        # CONSTRAINT: NORMAL hours per week <= weekly cap (pattern-dependent)
        # Allows working 6 days: 6 × 4.996h = 29.976h normal (fits!)
        # Remaining hours are OT: 6 × 2.004h = 12.024h OT/week
        max_hours_scaled = int(round(max_normal_hours_per_week * 10))
        model.Add(total_normal_hours_var <= max_hours_scaled)
        
        constraints_added += 1
    
    print(f"[C6] Part-Time Employee Weekly Normal Hour Limits Constraint (HARD)")
    print(f"     Total employees: {len(employees)}")
    print(f"     Scheme P (part-time) employees: {len(scheme_p_employees)}")
    print(f"     Weekly caps: 34.98h (≤4 days) or 29.98h (5+ days)")
    print(f"     Note: Caps NORMAL hours (not NET) - hours beyond cap become OT")
    print(f"     ✓ Added {constraints_added} weekly normal hour limit constraints\n")
