"""C2: Weekly <=44h (normal hours only) and Monthly OT <=72h - HARD constraints.

PATTERN-AWARE VERSION with MOM-compliant hour calculation:

UPDATED (28 Jan 2026): Normal hours are proportional to work days per week.
The 44h weekly cap is distributed evenly across all work days:
- 4 days/week: 44/4 = 11.0h normal per shift
- 5 days/week: 44/5 = 8.8h normal per shift
- 6 days/week: 44/6 = 7.33h normal per shift (ALL 6 days get normal hours)
- 7 days/week: 44/7 = 6.29h normal per shift
  
Weekly cap: sum(normal_hours) <= 44h per employee per ISO week
Monthly cap: sum(ot_hours) <= 72h per employee per calendar month

All constraints added via model.Add() for hard enforcement.
"""
from datetime import datetime, timedelta
from context.engine.time_utils import split_shift_hours, normalize_scheme
from context.engine.constraint_config import get_constraint_param
from collections import defaultdict


def get_work_days_per_week(pattern):
    """Calculate work days per 7-day week from pattern."""
    if not pattern:
        return 5  # Default 5-day
    work_days = sum(1 for day in pattern if day not in ['O', '0'])
    pattern_length = len(pattern) 
    return (work_days / pattern_length) * 7.0


def get_consecutive_work_position(pattern, pattern_day):
    """
    Get position in consecutive work sequence for given pattern day.
    
    Args:
        pattern: Work pattern list (e.g., ['D','D','D','D','D','D','O'])
        pattern_day: Current position in pattern (0-based)
    
    Returns:
        Position in consecutive work sequence (1-based). 
        Returns 1 for first work day or after off day.
    
    Examples:
        Pattern: ['D','D','D','D','D','D','O']
        pattern_day=0 → position=1 (1st consecutive)
        pattern_day=2 → position=3 (3rd consecutive)  
        pattern_day=5 → position=6 (6th consecutive)
        
        Pattern: ['D','D','O','D','D','D','O']
        pattern_day=0 → position=1 (1st consecutive)
        pattern_day=1 → position=2 (2nd consecutive)
        pattern_day=3 → position=1 (1st after off day)
        pattern_day=4 → position=2 (2nd consecutive)
        pattern_day=5 → position=3 (3rd consecutive)
    """
    if not pattern or pattern_day < 0 or pattern_day >= len(pattern):
        return 1
    
    # Count backwards from current position to find consecutive work days
    position = 1
    
    # Look backwards from pattern_day-1 to count consecutive work days  
    for i in range(pattern_day - 1, -1, -1):
        if pattern[i] not in ['O', '0']:
            position += 1
        else:
            # Hit an off day, stop counting
            break
    
    return position


def calculate_pattern_aware_normal_hours(gross, lunch, work_pattern, pattern_day):
    """
    Calculate normal hours using MOM-compliant pattern-aware rules.
    
    UPDATED (28 Jan 2026): Normal hours are proportional to work days per week.
    The 44h weekly cap is distributed evenly across all work days.
    
    Normal hours threshold per day:
    - 4 days/week: 44/4 = 11.0h normal per shift
    - 5 days/week: 44/5 = 8.8h normal per shift
    - 6 days/week: 44/6 = 7.33h normal per shift (ALL 6 days get normal hours)
    - 7 days/week: 44/7 = 6.29h normal per shift
    
    Args:
        gross: Gross shift hours
        lunch: Lunch break hours
        work_pattern: Employee work pattern list
        pattern_day: Current day position in pattern (0-based)
        
    Returns:
        Normal hours for this shift (MOM compliant)
    """
    work_days_per_week = get_work_days_per_week(work_pattern)
    
    # Protect against edge cases
    if work_days_per_week <= 0:
        work_days_per_week = 5  # Default to 5-day week
    
    # Calculate normal hours threshold: 44h weekly cap / work days in week
    # This evenly distributes the 44h cap across all work days
    normal_threshold = 44.0 / work_days_per_week
    
    # Apply threshold: normal = min(threshold, net hours)
    return min(normal_threshold, gross - lunch)


def add_constraints(model, ctx):
    """
    Enforce weekly normal-hours cap (44h) and monthly OT cap (72h) - HARD constraints.
    
    Uses PATTERN-AWARE normal hours calculation to correctly handle 6-day patterns.
    APGD-D10 EXEMPTION: APGD-D10 employees exempt from weekly 44h cap (use monthly caps instead).
    
    Args:
        model: CP-SAT model
        ctx: Context dict with 'employees', 'demandItems', 'slots', 'x'
    """
    from context.engine.time_utils import is_apgd_d10_employee
    
    employees = ctx.get('employees', [])
    demand_items = ctx.get('demandItems', [])
    slots = ctx.get('slots', [])
    x = ctx.get('x', {})
    
    if not slots or not x:
        print(f"[C2] Warning: Slots or decision variables not available")
        return
    
    # Build requirement map for APGD-D10 detection
    req_map = {}
    for demand in demand_items:
        for req in demand.get('requirements', []):
            req_map[req['requirementId']] = req
    
    # Identify APGD-D10 employees (exempt from weekly 44h cap)
    apgd_employees = set()
    for emp in employees:
        emp_id = emp.get('employeeId')
        product = emp.get('productTypeId', '')
        for req_id, req in req_map.items():
            if req.get('productTypeId', '') == product:
                if is_apgd_d10_employee(emp, req):
                    apgd_employees.add(emp_id)
                    break
    
    if apgd_employees:
        print(f"[C2] APGD-D10 detected: {len(apgd_employees)} employees EXEMPT from weekly 44h cap")
    
    # Build requirement → pattern and scheme mapping from demandItems
    # This is needed for v0.70 schema where ICPMP assigns patterns to requirements,
    # not directly to employees
    req_patterns = {}  # requirementId -> work_pattern list
    req_schemes = {}   # requirementId -> scheme
    for demand in demand_items:
        for req in demand.get('requirements', []):
            req_id = req.get('requirementId')
            pattern = req.get('workPattern', [])
            schemes = req.get('schemes', [])
            # Get first scheme or default to 'A'
            scheme_str = schemes[0] if schemes else 'A'
            scheme_normalized = normalize_scheme(scheme_str)
            
            if req_id and pattern:
                req_patterns[req_id] = pattern
                req_schemes[req_id] = scheme_normalized
    
    # Build employee → pattern and scheme mapping by checking which slots they can be assigned to
    # For demandBased: ICPMP assigns patterns to requirements, NOT employees
    # For outcomeBased: patterns may be in requirements OR employees
    # Strategy: Always look up from slots → requirements (works for both modes)
    emp_patterns = {}  # emp_id -> work_pattern list
    emp_schemes = {}   # emp_id -> scheme ('A', 'B', or 'P')
    for emp in employees:
        emp_id = emp.get('employeeId')
        pattern = []
        scheme = None
        
        # Find pattern and scheme from slots this employee can be assigned to
        # This works for both demandBased (ICPMP) and outcomeBased modes
        for slot in slots:
            if (slot.slot_id, emp_id) in x:
                # This employee can be assigned to this slot
                req_id = getattr(slot, 'requirementId', None)
                if req_id and req_id in req_patterns:
                    pattern = req_patterns[req_id]
                    # Also get scheme from requirement (for Scheme P detection)
                    if req_id in req_schemes:
                        scheme = req_schemes[req_id]
                    break  # Found pattern, stop searching
        
        # Fallback 1: Try direct employee.workPattern and scheme (for outcomeBased with explicit patterns)
        if not pattern:
            pattern = emp.get('workPattern', [])
        if not scheme:
            scheme_raw = emp.get('scheme', 'A')
            scheme = normalize_scheme(scheme_raw)
        
        # Fallback 2: Assume standard 5-day pattern
        if not pattern:
            pattern = ['D', 'D', 'D', 'D', 'D', 'O', 'O']
        if not scheme:
            scheme = 'A'
        
        emp_patterns[emp_id] = pattern
        emp_schemes[emp_id] = scheme
    
    # Debug: Check pattern and scheme detection
    pattern_lengths = [len(p) for p in emp_patterns.values()]
    work_days_counts = [sum(1 for d in p if d != 'O') for p in emp_patterns.values()]
    print(f"[C2] DEBUG: Pattern lengths: min={min(pattern_lengths) if pattern_lengths else 0}, max={max(pattern_lengths) if pattern_lengths else 0}")
    print(f"[C2] DEBUG: Work days: min={min(work_days_counts) if work_days_counts else 0}, max={max(work_days_counts) if work_days_counts else 0}")
    print(f"[C2] DEBUG: Sample patterns: {list(emp_patterns.values())[:3]}")
    print(f"[C2] DEBUG: Sample schemes: {list(emp_schemes.values())[:3]}")
    print(f"[C2] DEBUG: Requirement patterns available: {list(req_patterns.values())}")
    print(f"[C2] DEBUG: Requirement schemes available: {list(req_schemes.values())}")

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
    emp_week_slots = defaultdict(lambda: defaultdict(list))  
    emp_month_slots = defaultdict(lambda: defaultdict(list))  
    
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
    apgd_skipped = 0
    
    # Check for incremental mode locked hours
    incremental_ctx = ctx.get('_incremental')
    locked_weekly_hours = {}
    if incremental_ctx:
        locked_weekly_hours = incremental_ctx.get('lockedWeeklyHours', {})
        if locked_weekly_hours:
            print(f"[C2] INCREMENTAL MODE: Using locked weekly hours for {len(locked_weekly_hours)} employees")
    
    for emp_id, weeks in emp_week_slots.items():
        # Skip APGD-D10 employees (they use monthly caps, not weekly caps)
        if emp_id in apgd_employees:
            apgd_skipped += 1
            continue
        
        work_pattern = emp_patterns.get(emp_id, [])
        
        for week_key, week_slots in weeks.items():
            weighted_assignments = []
            
            for slot in week_slots:
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
                    
                    # PATTERN-AWARE NORMAL HOURS (MOM compliant)
                    normal_hours = calculate_pattern_aware_normal_hours(
                        gross, lunch, work_pattern, pattern_day
                    )
                    
                    var = x[(slot.slot_id, emp_id)]
                    
                    if normal_hours > 0:
                        int_hours = int(round(normal_hours * 10))
                        weighted_assignments.append((var, int_hours))
            
            if weighted_assignments:
                # Handle incremental mode locked hours
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
                employee_dict = {'employeeId': emp_id, 'scheme': emp_schemes.get(emp_id, 'A')}
                emp_scheme = emp_schemes.get(emp_id, 'A')
                
                if emp_scheme == 'P':
                    # Part-timer: Different caps based on work days per week
                    work_days_count = sum(1 for d in work_pattern if d != 'O')
                    if work_days_count <= 4:
                        weekly_normal_cap = get_constraint_param(
                            ctx, 'partTimerWeeklyHours', employee_dict, param_name='maxHours4Days', default=34.98
                        )
                    else:  # 5, 6, or 7 days
                        weekly_normal_cap = get_constraint_param(
                            ctx, 'partTimerWeeklyHours', employee_dict, param_name='maxHoursMoreDays', default=29.98
                        )
                else:
                    # Full-timer: 44h/week
                    weekly_normal_cap = get_constraint_param(
                        ctx, 'momWeeklyHoursCap44h', employee_dict, default=44.0
                    )
                
                remaining_capacity = weekly_normal_cap - locked_hours
                remaining_capacity_int = int(round(remaining_capacity * 10))
                
                # Add constraint: sum(normal_hours) <= weekly_normal_cap
                constraint_expr = sum(var * hours for var, hours in weighted_assignments)
                model.Add(constraint_expr <= remaining_capacity_int)
                weekly_constraints += 1

    # ===== ADD CONSTRAINTS FOR MONTHLY OT HOURS =====
    # APGD-D10 employees have month-dependent OT caps from monthlyHourLimits:
    # - 28 days: 112h OT
    # - 29 days: 116h OT
    # - 30 days: 120h OT
    # - 31 days: 124h OT
    # - Standard employees: 72h OT (all months)
    monthly_constraints = 0
    
    # Extract APGD max OT hours from monthlyHourLimits
    apgd_ot_by_days = {}
    monthly_hour_limits = ctx.get('monthlyHourLimits', [])
    for limit_config in monthly_hour_limits:
        if limit_config.get('id') == 'apgdMaximumOvertimeHours':
            values_by_length = limit_config.get('valuesByMonthLength', {})
            for days_str, values in values_by_length.items():
                apgd_ot_by_days[int(days_str)] = values.get('maxOvertimeHours', 72)
            break
    
    # Track applied caps for debug output
    applied_ot_caps = {}  # emp_id -> (is_apgd, month_length, cap_hours)
    
    for emp_id, months in emp_month_slots.items():
        # Get employee data to check APGD-D10 status
        employee_dict = next((e for e in employees if e.get('employeeId') == emp_id), None)
        if not employee_dict:
            continue
        
        # Determine if this is APGD-D10 employee
        is_apgd = is_apgd_d10_employee(employee_dict)
        
        for month_key, month_slots in months.items():
            # Determine month length (number of days in this month)
            if month_slots:
                # Get first and last date of the month from slots
                month_dates = set(slot.date for slot in month_slots)
                month_length = len(month_dates)
                
                # Get appropriate OT cap based on employee type and month length
                if is_apgd:
                    # APGD-D10: Use month-dependent cap (112-124h)
                    monthly_ot_cap_hours = apgd_ot_by_days.get(month_length, 72.0)
                else:
                    # Standard employee: 72h for all months
                    monthly_ot_cap_hours = 72.0
                
                monthly_ot_cap_int = int(round(monthly_ot_cap_hours * 10))  # Convert to tenths
                
                # Track for debug output
                if emp_id not in applied_ot_caps:
                    applied_ot_caps[emp_id] = (is_apgd, month_length, monthly_ot_cap_hours)
            else:
                continue
            
            weighted_assignments = []
            
            for slot in month_slots:
                if (slot.slot_id, emp_id) not in x:
                    continue
                
                slot_key = f"{slot.demandId}-{slot.shiftCode}"
                hours_data = shift_info.get(slot_key)
                
                if not hours_data:
                    try:
                        hours_data = split_shift_hours(slot.start, slot.end)
                    except Exception:
                        continue
                
                if hours_data:
                    ot_hours = hours_data.get('ot', 0)
                    var = x[(slot.slot_id, emp_id)]
                    
                    if ot_hours > 0:
                        int_hours = int(round(ot_hours * 10))
                        weighted_assignments.append((var, int_hours))
            
            if weighted_assignments:
                constraint_expr = sum(var * hours for var, hours in weighted_assignments)
                model.Add(constraint_expr <= monthly_ot_cap_int)
                monthly_constraints += 1

    # Summary
    four_day_employees = sum(1 for emp_id, pattern in emp_patterns.items() 
                            if get_work_days_per_week(pattern) <= 4.5)
    five_day_employees = sum(1 for emp_id, pattern in emp_patterns.items() 
                            if 4.5 < get_work_days_per_week(pattern) <= 5.5)
    six_day_employees = sum(1 for emp_id, pattern in emp_patterns.items() 
                           if get_work_days_per_week(pattern) > 5.5)
    
    print(f"[C2] Pattern-Aware Weekly & Monthly Hours Constraints (HARD)")
    print(f"     Employees: {len(employees)}, Slots: {len(slots)}")
    print(f"     4-day employees: {four_day_employees} (44h/4 = 11.0h normal/shift)")
    print(f"     5-day employees: {five_day_employees} (44h/5 = 8.8h normal/shift)")
    print(f"     6-day employees: {six_day_employees} (44h/6 = 7.33h normal/shift)")
    if apgd_skipped > 0:
        print(f"     APGD-D10: {apgd_skipped} employees EXEMPT from weekly 44h cap (use monthly caps)")
    
    # Show applied monthly OT caps
    if applied_ot_caps:
        apgd_caps = [(emp_id, month_len, cap) for emp_id, (is_apgd, month_len, cap) in applied_ot_caps.items() if is_apgd]
        std_caps = [(emp_id, month_len, cap) for emp_id, (is_apgd, month_len, cap) in applied_ot_caps.items() if not is_apgd]
        
        if apgd_caps:
            print(f"     Monthly OT caps (APGD-D10):")
            for emp_id, month_len, cap in apgd_caps:
                print(f"       {emp_id}: {cap:.0f}h ({month_len}-day month)")
        if std_caps:
            print(f"     Monthly OT caps (Standard):")
            for emp_id, month_len, cap in std_caps:
                print(f"       {emp_id}: {cap:.0f}h")
    
    print(f"     ✓ Added {weekly_constraints} weekly normal hours constraints (HARD)")
    print(f"     ✓ Added {monthly_constraints} monthly OT hours constraints (HARD)\n")