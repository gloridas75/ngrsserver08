"""C2: Weekly <=44h (normal hours only) and Monthly OT <=72h - HARD constraints.

Pattern-aware weekly/monthly hour caps with rest-day pay support.

Canonical model (MATCHES calculate_mom_compliant_hours in time_utils.py):
- 4 work days/week: normal = min(gross - lunch, 11.0), ot = max(0, gross - lunch - 11.0)
- 5 work days/week: normal = min(gross - lunch, 8.8), ot = max(0, gross - lunch - 8.8)
- 6+ work days/week:
  * Consecutive positions 1-5: normal = min(gross - lunch, 8.8), ot = max(0, gross - lunch - 8.8)
  * Consecutive position 6+: normal = 0.0, ot = max(0, gross - lunch - 8.0) [rest day pay = 8.0h]

This enforces:
1. Sum of normal_hours per employee per week <= 44h (HARD)
2. Sum of ot_hours per employee per month <= 72h (HARD)

Rest Day Pay (6th consecutive day):
- Pattern DDDDDOD: Days 1-5 = 8.8h normal each, Day 6 = 0h normal (8.0h rest day pay)
- Total weekly normal: 5 × 8.8h = 44h ✓
- 6th day paid via rest day pay (doesn't count toward 44h cap)

Input Schema (v0.70):
- employees: [{ employeeId, workPattern, rotationOffset, ... }]
- demandItems: [{ demandId, shifts: [{ shiftDetails }] }]
- slots: [{ slot_id, requirementId, date, shiftCode, ... }]
"""
from datetime import datetime, timedelta
from context.engine.time_utils import split_shift_hours, normalize_scheme
from context.engine.constraint_config import get_constraint_param
from collections import defaultdict


def analyze_pattern_consecutive_positions(pattern: list) -> dict:
    """Analyze work pattern to identify consecutive work day positions.
    
    Returns dict mapping pattern_index -> consecutive_position.
    
    Example:
        Pattern ['D','D','D','D','D','O','D']:
        {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 0, 6: 1}
        (Positions 0-4 are consecutive days 1-5, position 6 resets to 1 after 'O')
    
    Example with 6 consecutive:
        Pattern ['D','D','D','D','D','D','O']:
        {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 0}
        (Position 5 is 6th consecutive day)
    """
    position_map = {}
    consecutive_count = 0
    
    for idx, day in enumerate(pattern):
        if day != 'O':  # Work day
            consecutive_count += 1
            position_map[idx] = consecutive_count
        else:  # Off day
            position_map[idx] = 0  # Mark as off
            consecutive_count = 0  # Reset counter
    
    return position_map


def count_work_days_in_pattern(pattern: list) -> int:
    """Count total work days in pattern.
    
    Returns:
        Number of work days (non-'O' days)
    
    Examples:
        ['D','D','D','D','O','O','O'] → 4
        ['D','D','D','D','D','O','O'] → 5
        ['D','D','D','D','D','D','O'] → 6
    """
    return sum(1 for day in pattern if day != 'O')


def calculate_pattern_aware_hours(pattern: list, pattern_day: int, gross_hours: float, lunch_hours: float, employee_scheme: str = 'A') -> tuple:
    """Calculate normal and OT hours based on work pattern (MATCHES time_utils.py logic).
    
    Args:
        pattern: Employee work pattern
        pattern_day: Pattern day index (0-based)
        gross_hours: Gross shift hours
        lunch_hours: Lunch break hours
        employee_scheme: 'A', 'B', or 'P' (defaults to 'A')
    
    Returns:
        Tuple of (normal_hours, ot_hours)
    
    Examples (Scheme A/B):
        4-day pattern, 12h shift → (11.0, 0.0)
        5-day pattern, 12h shift → (8.8, 2.2)
        6-day pattern, position 3, 12h → (8.8, 2.2)
        6-day pattern, position 6, 12h → (0.0, 3.0) [rest day pay = 8.0h]
    
    Examples (Scheme P):
        4-day pattern, 8h net → (8.0, 0.0)  # 8h < 8.745h threshold
        6-day pattern, 8h net → (4.996, 3.004)  # 29.98h ÷ 6 = 4.996h/day threshold
    """
    if not pattern or pattern_day >= len(pattern):
        # Fallback: use 8.8h formula
        normal = min(8.8, gross_hours - lunch_hours)
        ot = max(0.0, gross_hours - lunch_hours - 8.8)
        return normal, ot
    
    work_days_count = count_work_days_in_pattern(pattern)
    consecutive_positions = analyze_pattern_consecutive_positions(pattern)
    consecutive_pos = consecutive_positions.get(pattern_day, 0)
    
    working_hours = gross_hours - lunch_hours  # Net working time
    
    # SCHEME P (PART-TIME) - Different thresholds than A/B
    if employee_scheme == 'P':
        if work_days_count <= 4:
            # ≤4 days/week: Max 34.98h/week → 8.745h/day threshold
            normal_threshold = 8.745
            normal = min(normal_threshold, working_hours)
            ot = max(0.0, working_hours - normal_threshold)
        elif work_days_count == 5:
            # 5 days/week: Max 29.98h/week → 5.996h/day threshold
            # 5th day: Entire shift is OT
            if consecutive_pos >= 5:
                normal = 0.0
                ot = working_hours
            else:
                normal_threshold = 5.996
                normal = min(normal_threshold, working_hours)
                ot = max(0.0, working_hours - normal_threshold)
        elif work_days_count == 6:
            # 6 days/week: Max 29.98h/week → 4.996h/day threshold
            normal_threshold = 4.996
            normal = min(normal_threshold, working_hours)
            ot = max(0.0, working_hours - normal_threshold)
        elif work_days_count >= 7:
            # 7 days/week: Max 29.98h/week → 4.283h/day threshold
            normal_threshold = 4.283
            normal = min(normal_threshold, working_hours)
            ot = max(0.0, working_hours - normal_threshold)
        else:
            # Fallback
            normal = min(8.745, working_hours)
            ot = max(0.0, working_hours - 8.745)
        
        return round(normal, 2), round(ot, 2)
    
    # SCHEME A/B (FULL-TIME) - Original logic
    if work_days_count == 4:
        # 4 days/week: 11.0h normal per shift
        normal = min(11.0, working_hours)
        ot = max(0.0, working_hours - 11.0)
    
    elif work_days_count == 5:
        # 5 days/week: 8.8h normal per shift
        normal = min(8.8, working_hours)
        ot = max(0.0, working_hours - 8.8)
    
    elif work_days_count >= 6:
        # 6+ days/week: Check if this is 6th+ consecutive day
        if consecutive_pos >= 6:
            # 6th+ consecutive day: 0h normal, rest day pay = 8.0h
            normal = 0.0
            # OT = working_hours - rest_day_pay
            ot = max(0.0, working_hours - 8.0)
        else:
            # Positions 1-5: 8.8h normal per shift
            normal = min(8.8, working_hours)
            ot = max(0.0, working_hours - 8.8)
    
    else:
        # Fallback for < 4 days
        normal = min(8.8, working_hours)
        ot = max(0.0, working_hours - 8.8)
    
    return round(normal, 2), round(ot, 2)


def add_constraints(model, ctx):
    """
    Enforce weekly normal-hours cap (44h) and monthly OT cap (72h) - HARD constraints.
    
    Uses pattern-aware calculation matching calculate_mom_compliant_hours() from time_utils.py.
    
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
    
    # Build employee work pattern, scheme, and product type maps
    emp_patterns = {}  # emp_id -> work_pattern list
    emp_schemes = {}   # emp_id -> scheme ('A', 'B', or 'P')
    emp_products = {}  # emp_id -> productTypeId
    
    for emp in employees:
        emp_id = emp.get('employeeId')
        pattern = emp.get('workPattern', [])
        scheme_raw = emp.get('scheme', 'A')
        scheme_normalized = normalize_scheme(scheme_raw)
        product_type = emp.get('productTypeId', '')
        
        emp_patterns[emp_id] = pattern
        emp_schemes[emp_id] = scheme_normalized
        emp_products[emp_id] = product_type
    
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
    
    # ===== ADD CONSTRAINTS FOR WEEKLY NORMAL HOURS <= 44H (PATTERN-AWARE) =====
    weekly_constraints = 0
    
    # Check for incremental mode locked hours
    incremental_ctx = ctx.get('_incremental')
    locked_weekly_hours = {}
    if incremental_ctx:
        locked_weekly_hours = incremental_ctx.get('lockedWeeklyHours', {})
        if locked_weekly_hours:
            print(f"[C2] INCREMENTAL MODE: Using locked weekly hours for {len(locked_weekly_hours)} employees")
    
    for emp_id, weeks in emp_week_slots.items():
        # Get employee's work pattern, scheme, and product type
        work_pattern = emp_patterns.get(emp_id, [])
        emp_scheme = emp_schemes.get(emp_id, 'A')
        emp_product = emp_products.get(emp_id, '')
        
        # Check if Scheme A + APO (eligible for 6th day in week rest pay)
        is_scheme_a_apo = (emp_scheme == 'A' and emp_product == 'APO')
        
        for week_key, week_slots in weeks.items():
            # Sort slots by date to determine work day sequence in week
            sorted_week_slots = sorted(week_slots, key=lambda s: s.date)
            
            # If Scheme A APO and 6+ work days in week, identify 6th day
            sixth_day_slot_id = None
            if is_scheme_a_apo and len(sorted_week_slots) >= 6:
                # Count work days (slots that would be assigned)
                work_day_count = 0
                for slot in sorted_week_slots:
                    if (slot.slot_id, emp_id) in x:
                        work_day_count += 1
                        if work_day_count == 6:
                            sixth_day_slot_id = slot.slot_id
                            break
            
            # For each slot in this week, calculate pattern-aware normal hours
            weighted_assignments = []
            for slot in sorted_week_slots:
                if (slot.slot_id, emp_id) not in x:
                    continue
                
                # Get shift hours
                slot_key = f"{slot.demandId}-{slot.shiftCode}"
                hours_data = shift_info.get(slot_key)
                
                if not hours_data:
                    try:
                        hours_data = split_shift_hours(slot.start, slot.end)
                    except Exception:
                        continue
                
                if hours_data:
                    gross = hours_data.get('gross', 0)
                    lunch = hours_data.get('lunch', 0)
                    pattern_day = getattr(slot, 'patternDay', 0)
                    
                    # SCHEME A APO: 6th day in week gets rest day pay (0h normal)
                    if is_scheme_a_apo and slot.slot_id == sixth_day_slot_id:
                        normal_hours = 0.0  # Rest day pay - doesn't count toward 44h
                    else:
                        # Use pattern-aware calculation with employee scheme
                        normal_hours, _ = calculate_pattern_aware_hours(
                            work_pattern, pattern_day, gross, lunch, emp_scheme
                        )
                    
                    var = x[(slot.slot_id, emp_id)]
                    
                    # Only include if there are actual normal hours
                    if normal_hours > 0:
                        # Scale to integer (multiply by 10 for tenths of hours)
                        int_hours = int(round(normal_hours * 10))
                        weighted_assignments.append((var, int_hours))
            
            if weighted_assignments:
                # Get locked hours for incremental mode
                locked_hours = 0.0
                if incremental_ctx and emp_id in locked_weekly_hours:
                    iso_year_str, week_str = week_key.split('-W')
                    iso_year = int(iso_year_str)
                    iso_week = int(week_str)
                    week_tuple = (iso_year, iso_week)
                    locked_hours = locked_weekly_hours[emp_id].get(week_tuple, 0.0)
                
                # SCHEME-AWARE WEEKLY NORMAL CAP (read from JSON with fallback)
                # Scheme A/B: 44h/week (default)
                # Scheme P: 34.98h (≤4 days) or 29.98h (5+ days)
                employee_dict = {'employeeId': emp_id, 'scheme': emp_scheme}
                
                if emp_scheme == 'P':
                    work_days_count = count_work_days_in_pattern(work_pattern)
                    if work_days_count <= 4:
                        weekly_normal_cap = get_constraint_param(
                            ctx, 'partTimerWeeklyHours', employee_dict, default=34.98
                        )
                    else:
                        weekly_normal_cap = get_constraint_param(
                            ctx, 'partTimerWeeklyHours', employee_dict, default=29.98
                        )
                else:
                    weekly_normal_cap = get_constraint_param(
                        ctx, 'momWeeklyHoursCap44h', employee_dict, default=44.0
                    )
                
                # Calculate remaining capacity
                remaining_capacity = weekly_normal_cap - locked_hours
                remaining_capacity_int = int(round(remaining_capacity * 10))
                
                # Create constraint: sum(var_i * normal_hours_i) <= remaining_capacity
                constraint_expr = sum(var * hours for var, hours in weighted_assignments)
                model.Add(constraint_expr <= remaining_capacity_int)
                weekly_constraints += 1
    
    # ===== ADD CONSTRAINTS FOR MONTHLY OT HOURS <= 72H =====
    monthly_constraints = 0
    for emp_id, months in emp_month_slots.items():
        work_pattern = emp_patterns.get(emp_id, [])
        emp_scheme = emp_schemes.get(emp_id, 'A')
        
        for month_key, month_slots in months.items():
            weighted_assignments = []
            for slot in month_slots:
                if (slot.slot_id, emp_id) not in x:
                    continue
                
                # Get shift hours
                slot_key = f"{slot.demandId}-{slot.shiftCode}"
                hours_data = shift_info.get(slot_key)
                
                if not hours_data:
                    try:
                        hours_data = split_shift_hours(slot.start, slot.end)
                    except Exception:
                        continue
                
                if hours_data:
                    gross = hours_data.get('gross', 0)
                    lunch = hours_data.get('lunch', 0)
                    pattern_day = getattr(slot, 'patternDay', 0)
                    
                    # Use pattern-aware calculation with employee scheme
                    _, ot_hours = calculate_pattern_aware_hours(
                        work_pattern, pattern_day, gross, lunch, emp_scheme
                    )
                    
                    var = x[(slot.slot_id, emp_id)]
                    
                    # Only include if there are actual OT hours
                    if ot_hours > 0:
                        # Scale to integer (multiply by 10 for tenths of hours)
                        int_hours = int(round(ot_hours * 10))
                        weighted_assignments.append((var, int_hours))
            
            if weighted_assignments:
                # Read monthly OT cap from JSON with fallback to 72h
                employee_dict = {'employeeId': emp_id, 'scheme': emp_schemes.get(emp_id, 'A')}
                monthly_ot_cap = get_constraint_param(
                    ctx, 'momMonthlyOTcap72h', employee_dict, default=72.0
                )
                monthly_ot_cap_int = int(round(monthly_ot_cap * 10))  # Convert to tenths
                
                # Create constraint: sum(var_i * ot_hours_i) <= monthly_ot_cap
                constraint_expr = sum(var * hours for var, hours in weighted_assignments)
                model.Add(constraint_expr <= monthly_ot_cap_int)
                monthly_constraints += 1
    
    # Count employees with 6-day patterns and Scheme P
    six_day_employees = sum(1 for emp_id in emp_patterns 
                           if emp_patterns[emp_id] and 
                           sum(1 for d in emp_patterns[emp_id] if d not in ['O', '0']) >= 6)
    scheme_p_count = sum(1 for scheme in emp_schemes.values() if scheme == 'P')
    
    print(f"[C2] Weekly & Monthly Hours Constraints (HARD) - PATTERN-AWARE")
    print(f"     Employees: {len(employees)} ({six_day_employees} with 6+ day patterns, {scheme_p_count} Scheme P)")
    print(f"     Slots: {len(slots)}")
    print(f"     Formula (Scheme A/B):")
    print(f"       • 4 days/week: 11.0h normal/shift → 4 × 11.0h = 44h/week")
    print(f"       • 5 days/week: 8.8h normal/shift → 5 × 8.8h = 44h/week")
    print(f"       • 6 days/week: 8.8h (pos 1-5) + 0h (pos 6+) → 5 × 8.8h = 44h/week")
    print(f"     Formula (Scheme P):")
    print(f"       • ≤4 days/week: 8.745h normal/shift → ≤34.98h/week")
    print(f"       • 6 days/week: 4.996h normal/shift → ≤29.98h/week (rest is OT)")
    print(f"     ✓ Added {weekly_constraints} weekly normal hours constraints (≤44h for A/B, ≤34.98h for P)")
    print(f"     ✓ Added {monthly_constraints} monthly OT hours constraints (≤72h)\n")

