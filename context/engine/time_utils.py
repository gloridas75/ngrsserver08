"""Working Hours Calculation Utilities.

Canonical working-hours model:
  - gross_hours: Total duration (start → end)
  - lunch_hours: 1.0 if gross > 6.0, else 0.0
  - normal_hours: min(gross, 9.0) - lunch (working hours cap per shift is 9h)
  - ot_hours: max(0, gross - 9.0) (everything beyond 9h is OT)

Usage:
  - Weekly 44h cap: Sum of normal_hours only (exclude lunch & OT)
  - Monthly 72h OT cap: Sum of ot_hours only
  - Daily cap (14h, 13h, 9h by scheme): Can use gross_hours

Examples:
  09:00-18:00 → gross=9,  lunch=1, normal=8,  ot=0  (9h shift = 8h normal + 1h lunch)
  09:00-20:00 → gross=11, lunch=1, normal=8,  ot=2  (11h shift = 8h normal + 1h lunch + 2h OT)
  22:00-06:00 → gross=8,  lunch=1, normal=7,  ot=0  (8h overnight = 7h normal + 1h lunch)
  10:00-14:00 → gross=4,  lunch=0, normal=4,  ot=0  (4h short shift, no lunch)
"""

from datetime import datetime, time
from typing import Optional, Dict, List, Tuple


def normalize_scheme(scheme_value: str) -> str:
    """
    Normalize scheme value to single letter code.
    Handles both short codes ('P', 'A', 'B') and full names ('Scheme P', 'Scheme A', 'Scheme B').
    
    Args:
        scheme_value: Either 'P' or 'Scheme P' format
    
    Returns:
        Single letter code: 'P', 'A', or 'B'
    """
    if not scheme_value:
        return 'A'  # Default to Scheme A
    
    scheme_str = str(scheme_value).strip()
    
    # If already a single letter, return it
    if len(scheme_str) == 1 and scheme_str.upper() in ('A', 'B', 'P'):
        return scheme_str.upper()
    
    # Extract letter from "Scheme X" format
    if scheme_str.startswith('Scheme '):
        letter = scheme_str.split()[-1].strip().upper()
        if letter in ('A', 'B', 'P'):
            return letter
    
    # Default fallback
    return 'A'


def span_hours(start_dt: datetime, end_dt: datetime) -> float:
    """Calculate gross hours between two datetimes.
    
    Handles overnight shifts correctly by considering the time span.
    
    Args:
        start_dt: Shift start time (datetime)
        end_dt: Shift end time (datetime)
    
    Returns:
        Gross hours as float (can be fractional)
    
    Examples:
        09:00-18:00 → 9.0 hours
        19:00-07:00 (next day) → 12.0 hours
        10:00-14:30 → 4.5 hours
    """
    delta = end_dt - start_dt
    total_seconds = delta.total_seconds()
    
    if total_seconds < 0:
        # Handle case where end is before start (overnight assumed, but should be handled by slot_builder)
        raise ValueError(f"End time {end_dt} is before start time {start_dt}")
    
    gross = total_seconds / 3600.0  # Convert seconds to hours
    return round(gross, 2)  # Round to 2 decimal places


def lunch_hours(gross: float) -> float:
    """Calculate lunch break duration.
    
    Industry standard: 1-hour meal break applies only if gross hours > 6.
    
    Args:
        gross: Gross hours worked
    
    Returns:
        Lunch hours: 1.0 if gross > 6.0, else 0.0
    
    Examples:
        gross=4.0  → 0.0 (no lunch on short shifts)
        gross=6.0  → 0.0 (exactly 6 hours, no lunch)
        gross=6.5  → 1.0 (more than 6, lunch applies)
        gross=9.0  → 1.0 (standard 9h shift with lunch)
        gross=11.0 → 1.0 (11h shift with lunch and OT)
    """
    return 1.0 if gross > 6.0 else 0.0


def split_normal_ot(gross: float) -> tuple:
    """Split working hours into normal and overtime.
    
    - Normal hours: capped at 9h per shift, minus lunch
    - OT hours: everything beyond 9h
    
    Args:
        gross: Gross hours worked
    
    Returns:
        Tuple of (normal_hours, ot_hours)
    
    Examples:
        gross=4.0  → (4.0, 0.0)     [4h normal, no OT, no lunch]
        gross=8.0  → (7.0, 0.0)     [8h gross = 7h normal + 1h lunch]
        gross=9.0  → (8.0, 0.0)     [9h gross = 8h normal + 1h lunch]
        gross=11.0 → (8.0, 2.0)     [11h gross = 8h normal + 1h lunch + 2h OT]
        gross=12.0 → (8.0, 3.0)     [12h gross = 8h normal + 1h lunch + 3h OT]
    """
    ln = lunch_hours(gross)
    
    # Normal hours = min(gross, 9.0) - lunch
    # This ensures normal never exceeds 8h when lunch applies, and never exceeds 9h when it doesn't
    normal = max(0.0, min(gross, 9.0) - ln)
    
    # OT hours = anything beyond 9h
    ot = max(0.0, gross - 9.0)
    
    return round(normal, 2), round(ot, 2)


def split_shift_hours(start_dt: datetime, end_dt: datetime) -> dict:
    """Complete breakdown of shift hours into all components.
    
    This is the primary function to use for any shift hour calculation.
    
    Args:
        start_dt: Shift start time (datetime)
        end_dt: Shift end time (datetime)
    
    Returns:
        Dictionary with keys:
        - 'gross': Total duration in hours
        - 'lunch': Meal break hours (0.0 or 1.0)
        - 'normal': Normal working hours (for 44h weekly cap)
        - 'ot': Overtime hours (for 72h monthly cap)
        - 'paid': Total paid hours (gross - lunch + any adjustments, typically = gross)
    
    Examples:
        09:00-18:00 →
        {
            'gross': 9.0,
            'lunch': 1.0,
            'normal': 8.0,
            'ot': 0.0,
            'paid': 9.0
        }
        
        09:00-20:00 →
        {
            'gross': 11.0,
            'lunch': 1.0,
            'normal': 8.0,
            'ot': 2.0,
            'paid': 11.0
        }
        
        19:00-23:30 →
        {
            'gross': 4.5,
            'lunch': 0.0,
            'normal': 4.5,
            'ot': 0.0,
            'paid': 4.5
        }
    """
    gross = span_hours(start_dt, end_dt)
    ln = lunch_hours(gross)
    normal, ot = split_normal_ot(gross)
    
    return {
        'gross': gross,
        'lunch': ln,
        'normal': normal,
        'ot': ot,
        'paid': gross  # In most systems, employee gets paid for full hours (including lunch time)
    }


def validate_shift_hours(start_dt: datetime, end_dt: datetime, max_gross_by_scheme: Optional[Dict] = None) -> dict:
    """Validate shift against scheme limits and return detailed breakdown.
    
    Args:
        start_dt: Shift start time
        end_dt: Shift end time
        max_gross_by_scheme: Optional dict mapping scheme -> max gross hours
                            Defaults to: {'A': 14, 'B': 13, 'P': 9}
    
    Returns:
        Dictionary with:
        - 'valid': True if shift is valid
        - 'hours': Complete hour breakdown (from split_shift_hours)
        - 'scheme_violations': List of scheme violations if any
    
    Examples:
        # Standard 8h shift for Scheme A
        result = validate_shift_hours(dt1, dt2, {'A': 14})
        # {'valid': True, 'hours': {...}, 'scheme_violations': []}
        
        # 15h shift exceeds Scheme A limit
        result = validate_shift_hours(dt1, dt2, {'A': 14})
        # {'valid': False, 'hours': {...}, 'scheme_violations': ['Scheme A max 14h']}
    """
    if max_gross_by_scheme is None:
        max_gross_by_scheme = {'A': 14, 'B': 13, 'P': 9}
    
    hours = split_shift_hours(start_dt, end_dt)
    violations = []
    
    # Check against each scheme's max gross hours
    for scheme, max_hours in max_gross_by_scheme.items():
        if hours['gross'] > max_hours:
            violations.append(f"Scheme {scheme}: gross hours {hours['gross']}h exceeds max {max_hours}h")
    
    return {
        'valid': len(violations) == 0,
        'hours': hours,
        'scheme_violations': violations
    }


# ============ SUMMARY HELPERS ============

def calculate_weekly_normal_hours(shifts: list) -> float:
    """Calculate total normal (working) hours for a week from list of shifts.
    
    Use this for 44h weekly cap checks.
    
    Args:
        shifts: List of (start_dt, end_dt) tuples
    
    Returns:
        Sum of normal_hours (excludes lunch and OT)
    """
    total = 0.0
    for start_dt, end_dt in shifts:
        hours_dict = split_shift_hours(start_dt, end_dt)
        total += hours_dict['normal']
    return round(total, 2)


def calculate_monthly_ot_hours(shifts: list) -> float:
    """Calculate total OT hours for a month from list of shifts.
    
    Use this for 72h monthly OT cap checks.
    
    Args:
        shifts: List of (start_dt, end_dt) tuples
    
    Returns:
        Sum of ot_hours only
    """
    total = 0.0
    for start_dt, end_dt in shifts:
        hours_dict = split_shift_hours(start_dt, end_dt)
        total += hours_dict['ot']
    return round(total, 2)


def calculate_daily_gross_hours(shifts_same_day: list) -> float:
    """Calculate total gross hours for a single day.
    
    Use this for daily cap checks (14h/13h/9h by scheme).
    
    Args:
        shifts_same_day: List of (start_dt, end_dt) tuples for same calendar day
    
    Returns:
        Sum of gross_hours for the day
    """
    total = 0.0
    for start_dt, end_dt in shifts_same_day:
        total += span_hours(start_dt, end_dt)
    return round(total, 2)


# ============ MOM COMPLIANCE HELPERS ============

def get_calendar_week_bounds(date_obj) -> tuple:
    """Get Monday and Sunday of the calendar week for a given date.
    
    Args:
        date_obj: date object
    
    Returns:
        Tuple of (monday_date, sunday_date)
    
    Examples:
        2026-01-07 (Wed) → (2026-01-05 Mon, 2026-01-11 Sun)
        2026-01-11 (Sun) → (2026-01-05 Mon, 2026-01-11 Sun)
    """
    from datetime import timedelta
    
    # Get weekday (0=Monday, 6=Sunday)
    weekday = date_obj.weekday()
    
    # Calculate Monday of this week
    monday = date_obj - timedelta(days=weekday)
    
    # Calculate Sunday of this week
    sunday = monday + timedelta(days=6)
    
    return (monday, sunday)


def count_work_days_in_calendar_week(
    employee_id: str,
    date_obj,
    all_assignments: list
) -> int:
    """Count work days for an employee in the calendar week (Mon-Sun) containing the given date.
    
    Args:
        employee_id: Employee ID
        date_obj: date object to determine which calendar week
        all_assignments: All assignments list (must have 'employeeId', 'date', 'shiftCode')
    
    Returns:
        Number of work days (D/N shifts, excluding O) in that calendar week
    
    Examples:
        Week with [D,D,O,D,D,D,O] → 5 work days
        Week with [D,D,D,D,O,O,O] → 4 work days
    """
    monday, sunday = get_calendar_week_bounds(date_obj)
    
    # Filter assignments for this employee in this week
    work_days = set()
    for assignment in all_assignments:
        if assignment.get('employeeId') != employee_id:
            continue
        
        assign_date_str = assignment.get('date')
        if not assign_date_str:
            continue
        
        try:
            from datetime import datetime as dt
            assign_date = dt.fromisoformat(assign_date_str).date()
            
            # Check if in this calendar week
            if monday <= assign_date <= sunday:
                shift_code = assignment.get('shiftCode', '')
                # Count D/N shifts only (work days), exclude O
                if shift_code and shift_code != 'O':
                    work_days.add(assign_date_str)
        except Exception:
            continue
    
    return len(work_days)


def find_consecutive_position(
    employee_id: str,
    current_date_obj,
    all_assignments: list
) -> int:
    """Find the position of current date in consecutive work days sequence.
    
    Looks backward from current date to find consecutive work days.
    
    Args:
        employee_id: Employee ID
        current_date_obj: Current date object
        all_assignments: All assignments list
    
    Returns:
        Position in consecutive sequence (1-based). Returns 1 if first work day or after gap.
    
    Examples:
        [O,O,D,D,D,D,O] current=index 5 → position 4 (4th consecutive day)
        [D,D,O,D,D,D,O] current=index 5 → position 3 (3rd consecutive after gap)
        [D,D,D,D,D,D,D] current=index 6 → position 7 (7th consecutive)
    """
    from datetime import timedelta
    
    # Build set of work dates for this employee
    work_dates = set()
    for assignment in all_assignments:
        if assignment.get('employeeId') != employee_id:
            continue
        
        assign_date_str = assignment.get('date')
        shift_code = assignment.get('shiftCode', '')
        
        if assign_date_str and shift_code and shift_code != 'O':
            try:
                from datetime import datetime as dt
                assign_date = dt.fromisoformat(assign_date_str).date()
                work_dates.add(assign_date)
            except Exception:
                continue
    
    # Count consecutive work days including current date
    position = 1
    check_date = current_date_obj - timedelta(days=1)
    
    # Look backward to count consecutive days
    while check_date in work_dates:
        position += 1
        check_date -= timedelta(days=1)
    
    return position


def calculate_mom_compliant_hours(
    start_dt: datetime,
    end_dt: datetime,
    employee_id: str,
    assignment_date_obj,
    all_assignments: list,
    employee_scheme: str = 'A'
) -> dict:
    """Calculate MOM-compliant work hours with scheme-aware normal/OT split.
    
    Rules for Scheme A/B (Full-time):
    - 4 work days/week: 11.0h normal + rest OT
    - 5 work days/week: 8.8h normal + rest OT
    - 6 work days/week, position 1-5: 8.8h normal + rest OT
    - 6 work days/week, position 6+: 0h normal, 8.0h rest day pay, rest OT
    - MOM minimum: 1 weekly off day (max 6 consecutive work days)
    
    Rules for Scheme P (Part-time):
    - ≤4 days/week: 34.98h max → 8.745h normal/day threshold, rest is OT
    - 5th day (after working 4 days): Entire shift is OT
    - 5 days/week: 29.98h max → 5.996h normal/day (typically 6h shifts with 0.75h lunch)
    - 6 days/week: 29.98h max → 4.996h normal/day (typically 5h shifts, no lunch)
    - 7 days/week: 29.98h max → 4.283h normal/day (typically 4h shifts, no lunch)
    - OT cap: 72h/month (same as Scheme A/B)
    
    Args:
        start_dt: Shift start datetime
        end_dt: Shift end datetime
        employee_id: Employee ID
        assignment_date_obj: Assignment date (date object)
        all_assignments: All assignments for context analysis
        employee_scheme: Employment scheme ('A', 'B', or 'P'). Defaults to 'A'.
    
    Returns:
        Dictionary with keys:
        - 'gross': Total duration
        - 'lunch': Meal break (0.0, 0.75, or 1.0)
        - 'normal': Normal hours (MOM compliant)
        - 'ot': Overtime hours
        - 'restDayPay': Rest day pay (8.0h for 6th+ consecutive day, else 0.0)
        - 'paid': Total paid hours
    
    Examples (Scheme A/B):
        4 days/week, 12h shift → {normal: 11.0, ot: 0.0, restDayPay: 0.0}
        5 days/week, 12h shift → {normal: 8.8, ot: 2.2, restDayPay: 0.0}
    
    Examples (Scheme P):
        4 days/week, 8h net → {normal: 8.0, ot: 0.0} (8h < 8.745h threshold)
        4 days/week, 10h net → {normal: 8.745, ot: 1.255} (exceeds threshold)
        5 days (5th day), 8h net → {normal: 0.0, ot: 8.0} (entire 5th day is OT)
    """
    # Calculate basic components
    gross = span_hours(start_dt, end_dt)
    ln = lunch_hours(gross)
    
    # Get work days in calendar week and consecutive position
    work_days_in_week = count_work_days_in_calendar_week(
        employee_id, assignment_date_obj, all_assignments
    )
    consecutive_position = find_consecutive_position(
        employee_id, assignment_date_obj, all_assignments
    )
    
    # Initialize rest day pay
    rest_day_pay = 0.0
    
    # Apply scheme-specific normal/OT calculation rules
    if employee_scheme == 'P':
        # SCHEME P (PART-TIME) - C6 constraint-aware calculations
        # Reference: config_optimizer_v3.SCHEME_P_CONSTRAINTS
        
        if work_days_in_week <= 4:
            # ≤4 days/week: Max 34.98h/week
            # Normal threshold: 34.98h ÷ 4 days = 8.745h/day
            # Example: 8h shift → all normal (8h < 8.745h), OT: 0h
            # Example: 10h shift → normal: 8.745h, OT: 1.255h
            normal_threshold = 8.745  # 34.98 / 4
            normal = min(normal_threshold, gross - ln)
            ot = max(0.0, gross - ln - normal_threshold)
        
        elif work_days_in_week == 5:
            # 5 days/week: Max 29.98h/week
            # Normal threshold: 29.98h ÷ 5 days = 5.996h/day
            # Typically: 6h gross shifts (5.25h net + 0.75h lunch)
            # 5th day (after 4 days): Entire shift is OT
            # NOTE: Solver should prevent 5-day patterns via C6 constraint,
            # but if it happens, treat 5th consecutive day as all OT
            if consecutive_position >= 5:
                # 5th+ consecutive day: Entire shift is OT
                normal = 0.0
                ot = gross - ln
            else:
                # Position 1-4: Apply normal threshold
                normal_threshold = 5.996  # 29.98 / 5
                normal = min(normal_threshold, gross - ln)
                ot = max(0.0, gross - ln - normal_threshold)
        
        elif work_days_in_week == 6:
            # 6 days/week: Max 29.98h/week
            # Normal threshold: 29.98h ÷ 6 days = 4.996h/day
            # Typically: 5h gross shifts (no lunch)
            normal_threshold = 4.996  # 29.98 / 6
            normal = min(normal_threshold, gross - ln)
            ot = max(0.0, gross - ln - normal_threshold)
        
        elif work_days_in_week >= 7:
            # 7 days/week: Max 29.98h/week
            # Normal threshold: 29.98h ÷ 7 days = 4.283h/day
            # Typically: 4h gross shifts (no lunch)
            normal_threshold = 4.283  # 29.98 / 7
            normal = min(normal_threshold, gross - ln)
            ot = max(0.0, gross - ln - normal_threshold)
        
        else:
            # Fallback for < 4 days (shouldn't happen, but handle gracefully)
            # Use ≤4 days threshold as conservative default
            normal_threshold = 8.745
            normal = min(normal_threshold, gross - ln)
            ot = max(0.0, gross - ln - normal_threshold)
    
    else:
        # SCHEME A/B (FULL-TIME) - Original logic
        
        if work_days_in_week == 4:
            # 4 days/week: 11.0h normal + rest OT
            normal = min(11.0, gross - ln)
            ot = max(0.0, gross - ln - 11.0)
        
        elif work_days_in_week == 5:
            # 5 days/week: 8.8h normal + rest OT
            normal = min(8.8, gross - ln)
            ot = max(0.0, gross - ln - 8.8)
        
        elif work_days_in_week >= 6:
            # 6+ days/week: Check if 6th consecutive day WITHIN SAME ISO WEEK
            # Rest-day pay only applies when all 6 consecutive days fall in same ISO week
            # This encourages solver to pack 6 work days within single week (reduces gaps)
            if consecutive_position >= 6:
                # 6th+ consecutive day within same ISO week: 0h normal, 8.0h rest day pay, rest OT
                normal = 0.0
                rest_day_pay = 8.0
                ot = max(0.0, gross - ln - rest_day_pay)
            else:
                # Position 1-5: 8.8h normal + rest OT
                normal = min(8.8, gross - ln)
                ot = max(0.0, gross - ln - 8.8)
        
        else:
            # Fallback for < 4 days (shouldn't happen with MOM compliance, but handle gracefully)
            # Use 8.8h formula as conservative default
            normal = min(8.8, gross - ln)
            ot = max(0.0, gross - ln - 8.8)
    
    return {
        'gross': round(gross, 2),
        'lunch': round(ln, 2),
        'normal': round(normal, 2),
        'ot': round(ot, 2),
        'restDayPay': round(rest_day_pay, 2),
        'paid': round(gross, 2)  # Paid hours = gross (includes everything)
    }
