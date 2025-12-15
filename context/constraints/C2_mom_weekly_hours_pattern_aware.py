"""C2: Weekly <=44h (normal hours only) and Monthly OT <=72h - HARD constraints.

PATTERN-AWARE VERSION with MOM-compliant hour calculation:

Based on MOM Employment Act rules:
- 4 work days/week: 11.0h normal + rest OT per shift
- 5 work days/week: 8.8h normal + rest OT per shift  
- 6 work days/week: 
  - First 5 consecutive days: 8.8h normal + rest OT per shift
  - 6th consecutive day: 0h normal + rest day pay (8.0h) + rest OT per shift
  
Weekly cap: sum(normal_hours) <= 44h per employee per ISO week
Monthly cap: sum(ot_hours) <= 72h per employee per calendar month

All constraints added via model.Add() for hard enforcement.
"""
from datetime import datetime, timedelta
from context.engine.time_utils import split_shift_hours
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
    
    Based on official MOM table:
    - 4 days/week: 11.0h normal per shift
    - 5 days/week: 8.8h normal per shift
    - 6 days/week: 8.8h normal for first 5 consecutive days, 0h normal for 6th+ day
    
    Args:
        gross: Gross shift hours
        lunch: Lunch break hours
        work_pattern: Employee work pattern list
        pattern_day: Current day position in pattern (0-based)
        
    Returns:
        Normal hours for this shift (MOM compliant)
    """
    work_days_per_week = get_work_days_per_week(work_pattern)
    
    if work_days_per_week <= 4.5:
        # 4 working days per week: 11.0 normal hours per shift
        return min(11.0, gross - lunch)
        
    elif work_days_per_week <= 5.5:
        # 5 working days per week: 8.8 normal hours per shift
        return min(8.8, gross - lunch)
        
    else:
        # 6+ working days per week: Check consecutive position
        consecutive_position = get_consecutive_work_position(work_pattern, pattern_day)
        
        if consecutive_position >= 6:
            # 6th+ consecutive day: 0 normal hours (rest day pay applies)
            return 0.0
        else:
            # First 5 consecutive days: 8.8 normal hours
            return min(8.8, gross - lunch)


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
    
    # Build requirement → pattern mapping from demandItems
    # This is needed for v0.70 schema where ICPMP assigns patterns to requirements,
    # not directly to employees
    req_patterns = {}
    for demand in demand_items:
        for req in demand.get('requirements', []):
            req_id = req.get('requirementId')
            pattern = req.get('workPattern', [])
            if req_id and pattern:
                req_patterns[req_id] = pattern
    
    # Build employee → pattern mapping by checking which slots they can be assigned to
    # This works because slots have requirementId, and requirements have workPattern
    emp_patterns = {}
    for emp in employees:
        emp_id = emp.get('employeeId')
        pattern = emp.get('workPattern', [])  # Try direct first (v0.95+)
        
        if not pattern:
            # Find pattern from slots this employee can be assigned to
            # Check first slot with this employee in decision variables
            for slot in slots:
                if (slot.slot_id, emp_id) in x:
                    # This employee can be assigned to this slot
                    req_id = getattr(slot, 'requirementId', None)
                    if req_id and req_id in req_patterns:
                        pattern = req_patterns[req_id]
                        break  # Found pattern, stop searching
            
            if not pattern:
                # Fallback: assume 5-day pattern
                pattern = ['D', 'D', 'D', 'D', 'D', 'O', 'O']
        
        emp_patterns[emp_id] = pattern
    
    # Debug: Check pattern detection
    pattern_lengths = [len(p) for p in emp_patterns.values()]
    work_days_counts = [sum(1 for d in p if d != 'O') for p in emp_patterns.values()]
    print(f"[C2] DEBUG: Pattern lengths: min={min(pattern_lengths) if pattern_lengths else 0}, max={max(pattern_lengths) if pattern_lengths else 0}")
    print(f"[C2] DEBUG: Work days: min={min(work_days_counts) if work_days_counts else 0}, max={max(work_days_counts) if work_days_counts else 0}")
    print(f"[C2] DEBUG: Sample patterns: {list(emp_patterns.values())[:3]}")
    print(f"[C2] DEBUG: Requirement patterns available: {list(req_patterns.values())}")

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
                
                remaining_capacity = 44.0 - locked_hours
                remaining_capacity_int = int(round(remaining_capacity * 10))
                
                # Add constraint: sum(normal_hours) <= 44h
                constraint_expr = sum(var * hours for var, hours in weighted_assignments)
                model.Add(constraint_expr <= remaining_capacity_int)
                weekly_constraints += 1

    # ===== ADD CONSTRAINTS FOR MONTHLY OT HOURS <= 72H =====
    monthly_constraints = 0
    for emp_id, months in emp_month_slots.items():
        for month_key, month_slots in months.items():
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
                model.Add(constraint_expr <= 720)  # 72 hours = 720 tenths
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
    print(f"     4-day employees: {four_day_employees} (11.0h normal/shift)")
    print(f"     5-day employees: {five_day_employees} (8.8h normal/shift)")
    print(f"     6-day employees: {six_day_employees} (8.8h normal for first 5 days, 0h for 6th)")
    if apgd_skipped > 0:
        print(f"     APGD-D10: {apgd_skipped} employees EXEMPT from weekly 44h cap (use monthly caps)")
    print(f"     ✓ Added {weekly_constraints} weekly normal hours constraints (HARD)")
    print(f"     ✓ Added {monthly_constraints} monthly OT hours constraints (HARD)\n")