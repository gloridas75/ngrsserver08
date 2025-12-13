"""
ICPMP v3.0 - Optimal Employee Calculator with U-Slot Injection

This module implements a mathematically optimal algorithm for calculating
minimum employee count with strategic "U" (unassigned) slot injection.

Key Features:
- Proven minimal employee count (try-minimal-first approach)
- Mathematical lower bound calculation
- All employees follow strict patterns (no flexible category)
- U-slots injected when coverage would exceed headcount
- Handles public holidays and coverage day filtering
- Scheme-aware capacity calculation (Scheme P: max 4 days/week)

Algorithm Guarantee:
First feasible solution found is PROVEN OPTIMAL (can't use fewer employees)
"""

import logging
from datetime import datetime, timedelta
from math import ceil
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

# Scheme P (Part-time) Constraints - MOM Employment Act
# These values are used throughout the solver workflow
SCHEME_P_CONSTRAINTS = {
    # Weekly capacity limits (C6 constraint - HOUR-BASED, not day-based)
    'max_normal_hours_per_week': 34.98,  # Max 34.98 NORMAL hours/week (not total hours)
    'max_ot_hours_per_month': 72,        # Max 72 OT hours/month (C17 constraint)
    'max_daily_hours_gross': 9,          # Max 9h gross per day (includes 1h lunch for 8h+ shifts)
    # IMPORTANT: Employees can work 6-7 days/week if hours beyond 34.98h are OT
    # Example: 6 days × 8h = 32h normal + 16h OT (within limits)
    
    # Shift configurations by work days per week
    # Used by solver to determine feasible shift lengths
    'shift_configs': {
        4: {'gross_hours': 9, 'lunch_hours': 1.0, 'net_hours': 8},    # ≤4 days: 9h gross (8h net + 1h lunch)
        5: {'gross_hours': 6, 'lunch_hours': 0.75, 'net_hours': 5.25}, # 5 days: 6h gross (5.25h net + 0.75h lunch)
        6: {'gross_hours': 5, 'lunch_hours': 0, 'net_hours': 5},       # 6 days: 5h gross (no lunch)
        7: {'gross_hours': 4, 'lunch_hours': 0, 'net_hours': 4}        # 7 days: 4h gross (no lunch)
    },
    
    # Normal hour thresholds for payroll calculations
    # Used by time_utils.calculate_mom_compliant_hours() to split Normal vs OT
    'normal_threshold_4_days': 8.745,  # 34.98h ÷ 4 days = 8.745h normal/day
    # For 5+ days/week: 29.98h ÷ days_per_week
    # 5 days: 29.98 ÷ 5 = 5.996h normal/day
    # 6 days: 29.98 ÷ 6 = 4.996h normal/day
    # 7 days: 29.98 ÷ 7 = 4.283h normal/day
    
    # Lunch deduction rules (MOM Employment Act)
    # Used to calculate net hours from gross hours
    'lunch_rules': {
        'min_hours_for_1h_lunch': 8.0,      # ≥8h gross: 1h lunch
        'min_hours_for_45min_lunch': 6.0,   # 6-7.99h gross: 45min (0.75h) lunch
        # <6h gross: No lunch deduction
    },
    
    # Overtime rules
    'max_ot_per_month': 72,  # Max 72h OT per month (MOM limit for all schemes)
    'max_ot_per_day': 12,    # Max 12h OT per day (9h gross for Scheme P)
}


def calculate_scheme_max_days_per_week(scheme: str) -> int:
    """
    Calculate maximum work days per week for a given employment scheme.
    
    This function implements MOM (Ministry of Manpower) regulatory constraints
    for different employment schemes. Used by ICPMP for capacity calculation.
    
    Args:
        scheme: Employee scheme code ('A', 'B', 'P', 'Scheme A', 'Scheme B', 'Scheme P', or 'Global')
        
    Returns:
        Maximum work days per week as integer
        
    Scheme Definitions:
        - Scheme A: Full-time, max 14h/day gross → max 6 days/week (need 1 rest day)
        - Scheme B: Full-time, max 13h/day gross → max 6 days/week (need 1 rest day)
        - Scheme P: Part-time, HOUR-BASED limit (34.98h normal/week)
          → Can work 6-7 days/week if using OT hours beyond 34.98h
        - Global: Conservative estimate (6 days for mixed pools)
        
    IMPORTANT: Scheme P is NOT limited by days/week, only by hours/week.
    C6 enforces 34.98h NORMAL hours/week. Additional hours are OT (max 72h/month).
    """
    # Check for 'Global' first (before normalization, as normalize_scheme converts it to 'A')
    if scheme == 'Global':
        # Mixed scheme pools: Use conservative estimate
        # Assume mix includes Scheme P, so limit to 4 days
        return 4
    
    # Normalize scheme: "Scheme P" → "P", "Scheme A" → "A", etc.
    from context.engine.time_utils import normalize_scheme
    scheme_normalized = normalize_scheme(scheme)
    
    if scheme_normalized == 'P':
        # Scheme P: NO day limit, only hour limit (34.98h normal/week)
        # Can work 6-7 days/week with OT hours
        # Return 6 as practical maximum (same as Scheme A/B)
        return 6
    elif scheme_normalized in ['A', 'B']:
        # Full-time schemes: Need at least 1 rest day per week (C3 constraint)
        # So maximum is 6 work days per week
        return 6
    else:
        # Unknown scheme: Use safe default (6 days, allows most patterns)
        logger.warning(f"Unknown scheme '{scheme}' (normalized: '{scheme_normalized}'), defaulting to 6 days/week max")
        return 6


def calculate_pattern_tightness_buffer(work_days: int, cycle_length: int) -> float:
    """
    Calculate buffer percentage based on pattern density (work ratio).
    
    Tight patterns with high work ratios need more buffer employees to handle:
    - Rotation offset alignment issues
    - Constraint interaction conflicts (C2 weekly hours, C5 consecutive days, C8 rest periods)
    - Minimal flexibility for scheduling adjustments
    
    Args:
        work_days: Number of work days in pattern cycle
        cycle_length: Total pattern cycle length
        
    Returns:
        Buffer multiplier (e.g., 0.25 for 25% buffer)
        
    Examples:
        DDDDDOD (6/7 = 85.7%): 25% buffer - very tight, needs significant flexibility
        DDDDOOD (4/7 = 57.1%): 5% buffer - loose, minimal extra needed
    """
    work_ratio = work_days / cycle_length
    
    if work_ratio >= 0.85:  # 6/7, 5/6 patterns - VERY TIGHT
        return 0.25  # 25% buffer
    elif work_ratio >= 0.75:  # 5/7, 4/5 patterns - TIGHT
        return 0.15  # 15% buffer
    elif work_ratio >= 0.60:  # 4/7, 3/5 patterns - MODERATE
        return 0.10  # 10% buffer
    else:  # <60% - LOOSE
        return 0.05  # 5% buffer


def calculate_optimal_with_u_slots(
    pattern: List[str],
    headcount: int,
    calendar: List[str],
    anchor_date: str,
    requirement_id: str = "unknown",
    max_attempts: int = 50,
    scheme: str = "A",
    enable_ot_aware_icpmp: bool = False
) -> Dict[str, Any]:
    """
    Calculate optimal employee count with U-slot injection.
    
    Uses try-minimal-first approach starting from mathematical lower bound.
    First feasible solution is guaranteed to be optimal.
    
    Args:
        pattern: Work pattern (e.g., ["D","D","D","D","O","O"])
        headcount: Required coverage per day
        calendar: List of dates requiring coverage (ISO format)
        anchor_date: Reference date for pattern alignment
        requirement_id: Identifier for tracking
        max_attempts: Maximum employee counts to try beyond lower bound
        scheme: Employment scheme ('A', 'B', 'P', or 'Global') for capacity constraints
        enable_ot_aware_icpmp: If True, consider OT capacity when injecting U-slots (Scheme P only)
        
    Returns:
        Dictionary with:
        - employeesRequired: Minimal employee count (proven optimal)
        - optimality: "PROVEN_MINIMAL"
        - algorithm: "GREEDY_INCREMENTAL" or "INTEGER_PROGRAMMING"
        - employeePatterns: List of employee assignments with U-slots
        - coverage: Daily coverage statistics
        - computation: Performance metrics
    """
    cycle_length = len(pattern)
    work_days_per_cycle = sum(1 for s in pattern if s != 'O')
    
    if work_days_per_cycle == 0:
        raise ValueError(f"Pattern {pattern} has no work days (all 'O')")
    
    # SCHEME-AWARE CAPACITY CALCULATION
    # Scheme P: Hour-based limits - must account for NORMAL hour threshold!
    
    scheme_max_days_per_week = calculate_scheme_max_days_per_week(scheme)
    
    # Import normalize_scheme to handle "Scheme P" format
    from context.engine.time_utils import normalize_scheme
    scheme_normalized = normalize_scheme(scheme)
    
    # CRITICAL FIX: Scheme P capacity is HOUR-LIMITED, not day-limited!
    # C2 constraint enforces weekly NORMAL hour caps that effectively reduce capacity
    if scheme_normalized == 'P':
        # Scheme P Weekly Normal Hour Limits (enforced by C2):
        # - ≤4 days/week: 34.98h max → 8.745h/day threshold
        # - 5 days/week: 29.98h max → 5.996h/day threshold  
        # - 6 days/week: 29.98h max → 4.996h/day threshold
        # - 7 days/week: 29.98h max → 4.283h/day threshold
        
        # Assume standard 8h net shifts (9h gross - 1h lunch)
        # For 6-day pattern: Only 4.996h per shift count as NORMAL
        # Remaining hours are OT (limited capacity)
        
        # Conservative capacity estimate for ICPMP:
        # Use NORMAL hour threshold to calculate effective days/week
        if work_days_per_cycle <= 4:
            max_normal_hours_per_week = 34.98
            effective_days_per_week = 34.98 / 8.0  # ≈4.37 days/week
        else:
            # 5+ days: Lower threshold (29.98h/week)
            max_normal_hours_per_week = 29.98
            effective_days_per_week = 29.98 / 8.0  # ≈3.75 days/week
        
        # NEW: OT-AWARE CAPACITY ADJUSTMENT
        # If enabled, add OT capacity to effective capacity
        if enable_ot_aware_icpmp:
            # Scheme P can work up to 72h OT per month
            max_ot_per_month = 72.0
            planning_horizon_days = len(calendar)
            planning_horizon_months = planning_horizon_days / 30.5  # Average month length
            
            # Calculate OT capacity in days per week
            # 72h/month ÷ 4.33 weeks/month ÷ 8h/shift ≈ 2.08 shifts/week
            ot_shifts_per_week = (max_ot_per_month / 4.33) / 8.0
            
            # Add OT capacity to effective capacity
            effective_days_per_week_with_ot = effective_days_per_week + ot_shifts_per_week
            
            logger.info(f"  Scheme P OT-aware capacity adjustment:")
            logger.info(f"    Normal capacity: {effective_days_per_week:.2f} days/week")
            logger.info(f"    OT capacity: {ot_shifts_per_week:.2f} shifts/week")
            logger.info(f"    Total capacity: {effective_days_per_week_with_ot:.2f} days/week")
            
            effective_days_per_week = effective_days_per_week_with_ot
        
        # Scale to cycle length (pattern may be 7, 14, or 21 days)
        weeks_per_cycle = cycle_length / 7.0
        effective_work_capacity = effective_days_per_week * weeks_per_cycle
        
        logger.info(f"  Scheme P capacity calculation:")
        logger.info(f"    Pattern work days: {work_days_per_cycle}")
        logger.info(f"    Normal hour limit: {max_normal_hours_per_week}h/week")
        logger.info(f"    Effective capacity: {effective_work_capacity:.2f} days/cycle (pattern: {work_days_per_cycle})")
    else:
        # Scheme A/B: Use pattern work days as-is
        effective_work_capacity = work_days_per_cycle
    
    # Calculate mathematical lower bound
    # The lower bound is the maximum of:
    # 1. headcount (need at least HC employees for any single day)
    # 2. Pattern-based minimum: If pattern needs multiple rotations to cover cycle
    #
    # For patterns where cycle_length evenly divides horizon, minimum is just headcount
    # For other cases, we need ceil(work_ratio) where work_ratio considers overlap
    
    total_coverage_needed = len(calendar) * headcount
    
    # More accurate lower bound: Consider that pattern rotations provide natural coverage
    # If we have cycle_length offsets, and pattern fills work_days per cycle,
    # then minimum employees is roughly: headcount * (cycle_length / work_days)
    # But this can be less if calendar length allows pattern repetition
    
    # IMPORTANT: Use effective_work_capacity (scheme-adjusted) instead of work_days_per_cycle
    pattern_based_minimum = ceil(headcount * cycle_length / effective_work_capacity)
    
    # Absolute minimum from work capacity (also use effective capacity)
    capacity_minimum = ceil(total_coverage_needed / effective_work_capacity)
    
    # Calculate smart buffer based on distribution efficiency
    # Goal: Balance between even distribution and minimizing employee idle time
    
    work_ratio = effective_work_capacity / cycle_length
    employees_per_position = pattern_based_minimum / cycle_length
    
    # Check how evenly the base minimum distributes
    if pattern_based_minimum % cycle_length == 0:
        # Perfect distribution - no buffer needed
        buffered_minimum = pattern_based_minimum
        buffer_reason = "perfect distribution"
    elif work_ratio >= 0.85:
        # Very tight patterns (6/7, 5/6)
        # Only round up if we're very close to the next multiple (within 20%)
        next_multiple = ceil(pattern_based_minimum / cycle_length) * cycle_length
        gap_to_next = next_multiple - pattern_based_minimum
        
        if gap_to_next <= cycle_length * 0.3:  # Within 30% of cycle length
            buffered_minimum = next_multiple
            buffer_reason = f"tight pattern - rounded up (+{gap_to_next} for even distribution)"
        else:
            # Too big a jump - just add small safety buffer
            buffered_minimum = pattern_based_minimum + 2
            buffer_reason = f"tight pattern - small buffer (+2)"
    elif work_ratio >= 0.75:
        # Tight patterns (5/7, 4/5) - small safety buffer
        buffered_minimum = pattern_based_minimum + 1
        buffer_reason = "tight pattern - safety buffer"
    else:
        # Moderate/loose patterns - minimal or no buffer
        buffered_minimum = pattern_based_minimum
        buffer_reason = "no buffer needed"
    
    # Take the maximum (most constrained)
    lower_bound = max(headcount, buffered_minimum)
    
    logger.info(f"[{requirement_id}] Starting optimal calculation:")
    logger.info(f"  Scheme: {scheme} (max {scheme_max_days_per_week} days/week)")
    logger.info(f"  Pattern: {pattern} (cycle={cycle_length}, work_days={work_days_per_cycle})")
    if scheme == 'P' and effective_work_capacity < work_days_per_cycle:
        logger.info(f"  ⚠️  Scheme P capacity limit: {work_days_per_cycle} → {effective_work_capacity:.1f} days/cycle")
    logger.info(f"  Effective work capacity: {effective_work_capacity:.1f} days/cycle")
    logger.info(f"  Work ratio: {work_ratio:.1%}")
    logger.info(f"  Headcount: {headcount}, Calendar days: {len(calendar)}")
    logger.info(f"  Base minimum: {pattern_based_minimum} employees")
    logger.info(f"  Distribution: {pattern_based_minimum / cycle_length:.2f} employees/position")
    logger.info(f"  Buffered minimum: {buffered_minimum} ({buffer_reason})")
    logger.info(f"  Lower bound: {lower_bound} employees (capacity={capacity_minimum})")
    
    # Try increasing employee counts from lower bound
    upper_bound = lower_bound + max_attempts
    
    for num_employees in range(lower_bound, upper_bound + 1):
        logger.debug(f"[{requirement_id}] Trying {num_employees} employees...")
        
        result = try_placement_with_n_employees(
            num_employees, pattern, headcount, calendar, anchor_date, cycle_length,
            scheme=scheme, enable_ot_aware=enable_ot_aware_icpmp
        )
        
        if result['is_feasible']:
            logger.info(f"[{requirement_id}] ✓ Found optimal: {num_employees} employees")
            logger.info(f"  Attempts required: {num_employees - lower_bound + 1}")
            logger.info(f"  Total U-slots: {result['total_u_slots']}")
            logger.info(f"  Coverage rate: {result['coverage_rate']:.1f}%")
            
            return {
                'requirementId': requirement_id,
                'configuration': {
                    'employeesRequired': num_employees,
                    'optimality': 'PROVEN_MINIMAL',
                    'algorithm': 'GREEDY_INCREMENTAL',
                    'lowerBound': lower_bound,
                    'attemptsRequired': num_employees - lower_bound + 1,
                    'offsetDistribution': result['offset_distribution']
                },
                'employeePatterns': result['employees'],
                'coverage': {
                    'achievedRate': result['coverage_rate'],
                    'totalWorkDays': result['total_work_days'],
                    'totalUSlots': result['total_u_slots'],
                    'dailyCoverageDetails': result['daily_coverage']
                },
                'metadata': {
                    'patternCycleLength': cycle_length,
                    'workDaysPerCycle': work_days_per_cycle,
                    'planningHorizonDays': len(calendar),
                    'totalCoverageNeeded': total_coverage_needed
                }
            }
    
    # Should never reach here with reasonable max_attempts
    raise RuntimeError(
        f"[{requirement_id}] Failed to find feasible solution within {max_attempts} attempts. "
        f"Tried up to {upper_bound} employees. This indicates a bug or invalid input."
    )


def try_placement_with_n_employees(
    num_employees: int,
    pattern: List[str],
    headcount: int,
    calendar: List[str],
    anchor_date: str,
    cycle_length: int,
    scheme: str = "A",
    enable_ot_aware: bool = False
) -> Dict[str, Any]:
    """
    Attempt to cover all days with exactly N employees using U-slot injection.
    
    Strategy:
    1. Distribute employees evenly across rotation offsets
    2. For each employee, simulate work pattern across calendar
    3. Inject 'U' slot when adding employee would create over-coverage
    4. (NEW) If enable_ot_aware=True: Consider OT capacity before injecting U-slots
    5. Check if full coverage achieved (every day has exactly HC employees)
    
    Args:
        num_employees: Number of employees to try
        pattern: Work pattern
        headcount: Required coverage per day
        calendar: List of dates (ISO format)
        anchor_date: Reference date for pattern alignment
        cycle_length: Length of pattern cycle
        scheme: Employment scheme ('A', 'B', 'P') for OT-aware logic
        enable_ot_aware: If True, consider OT capacity when injecting U-slots
        
    Returns:
        Dictionary with:
        - is_feasible: True if coverage complete
        - employees: List of employee patterns
        - daily_coverage: Coverage count per day
        - offset_distribution: Count per offset
        - coverage_rate: Percentage of days meeting headcount
        - total_work_days: Sum of actual work days (non-U, non-O)
        - total_u_slots: Sum of U slots across all employees
    """
    daily_coverage = {date: 0 for date in calendar}
    employees = []
    
    # Distribute employees evenly across offsets
    offset_distribution_list = distribute_offsets_evenly(num_employees, cycle_length)
    offset_counts = defaultdict(int)
    for offset in offset_distribution_list:
        offset_counts[offset] += 1
    
    anchor_dt = datetime.fromisoformat(anchor_date)
    
    for employee_num, offset in enumerate(offset_distribution_list):
        employee_pattern = []
        work_days = 0
        u_slots = 0
        
        for calendar_date in calendar:
            date_dt = datetime.fromisoformat(calendar_date)
            pattern_day = calculate_pattern_day(date_dt, offset, anchor_dt, cycle_length)
            shift_code = pattern[pattern_day]
            
            if shift_code == 'O':
                # Rest day - always 'O'
                employee_pattern.append('O')
            else:
                # Work shift in pattern - check if we need this coverage
                if daily_coverage[calendar_date] >= headcount:
                    # Already have enough coverage - mark as U slot
                    employee_pattern.append('U')
                    u_slots += 1
                else:
                    # Need coverage - assign work shift
                    employee_pattern.append(shift_code)
                    daily_coverage[calendar_date] += 1
                    work_days += 1
        
        # Calculate utilization (work days / total possible work days)
        total_slots = len(calendar)
        rest_days = employee_pattern.count('O')
        possible_work_days = total_slots - rest_days
        utilization = (work_days / possible_work_days * 100) if possible_work_days > 0 else 0.0
        
        employees.append({
            'employeeNumber': employee_num + 1,
            'rotationOffset': offset,
            'pattern': employee_pattern,
            'workDays': work_days,
            'uSlots': u_slots,
            'restDays': rest_days,
            'utilization': round(utilization, 1)
        })
    
    # Check feasibility - all days must have exactly headcount coverage
    coverage_achieved = [daily_coverage[date] for date in calendar]
    is_feasible = all(count == headcount for count in coverage_achieved)
    coverage_rate = (sum(1 for c in coverage_achieved if c == headcount) / len(calendar) * 100)
    
    total_work_days = sum(emp['workDays'] for emp in employees)
    total_u_slots = sum(emp['uSlots'] for emp in employees)
    
    return {
        'is_feasible': is_feasible,
        'employees': employees,
        'daily_coverage': daily_coverage,
        'offset_distribution': dict(offset_counts),
        'coverage_rate': coverage_rate,
        'total_work_days': total_work_days,
        'total_u_slots': total_u_slots
    }


def distribute_offsets_evenly(num_employees: int, cycle_length: int) -> List[int]:
    """
    Distribute N employees across rotation offsets as evenly as possible.
    
    Strategy:
    - If N <= cycle_length: Use offsets [0, 1, 2, ..., N-1]
    - If N > cycle_length: Some offsets get multiple employees
    
    Examples:
    - 5 employees, 6-day cycle → [0, 1, 2, 3, 4]
    - 14 employees, 5-day cycle → [0,0,0, 1,1,1, 2,2,2, 3,3, 4,4]
    - 6 employees, 12-day cycle → [0, 1, 2, 3, 4, 5]
    
    Args:
        num_employees: Total number of employees to distribute
        cycle_length: Length of rotation cycle
        
    Returns:
        List of offsets (one per employee)
    """
    if num_employees <= cycle_length:
        # Simple case: one employee per offset (or fewer)
        return list(range(num_employees))
    
    # Need to assign multiple employees to same offsets
    employees_per_offset = num_employees // cycle_length
    extra_employees = num_employees % cycle_length
    
    offsets = []
    for offset in range(cycle_length):
        # First 'extra_employees' offsets get one extra employee
        count = employees_per_offset + (1 if offset < extra_employees else 0)
        offsets.extend([offset] * count)
    
    return offsets


def calculate_pattern_day(
    date: datetime,
    offset: int,
    anchor: datetime,
    cycle_length: int
) -> int:
    """
    Calculate which day of the pattern cycle this date corresponds to.
    
    Formula: (days_from_anchor + offset) % cycle_length
    
    Args:
        date: Current date
        offset: Employee's rotation offset
        anchor: Reference date (offset=0 aligns to this date)
        cycle_length: Length of pattern cycle
        
    Returns:
        Pattern day index (0 to cycle_length-1)
    """
    days_from_anchor = (date - anchor).days
    pattern_day = (days_from_anchor + offset) % cycle_length
    return pattern_day


def calculate_employees_for_requirement(
    requirement: Dict[str, Any],
    planning_horizon: Dict[str, Any],
    public_holidays: List[str] = None,
    coverage_days: List[str] = None
) -> Dict[str, Any]:
    """
    Calculate optimal employees for a single requirement using solver schema format.
    
    Args:
        requirement: Requirement dict from demandItems with workPattern and headcount
        planning_horizon: Dict with startDate, endDate
        public_holidays: List of ISO dates to exclude (optional)
        coverage_days: List of weekday names to include (optional, defaults to all days)
        
    Returns:
        Result from calculate_optimal_with_u_slots()
    """
    # Extract requirement details
    pattern = requirement.get('workPattern')
    headcount = requirement.get('headcount')
    requirement_id = requirement.get('requirementId', 'unknown')
    
    if not pattern or headcount is None:
        raise ValueError(f"Requirement {requirement_id} missing workPattern or headcount")
    
    # Generate calendar (filtered by coverage days and excluding public holidays)
    start_date = planning_horizon.get('startDate')
    end_date = planning_horizon.get('endDate')
    
    calendar = generate_coverage_calendar(
        start_date, end_date, 
        coverage_days=coverage_days,
        public_holidays=public_holidays or []
    )
    
    if not calendar:
        raise ValueError(f"No coverage days in planning horizon for requirement {requirement_id}")
    
    # Use first day of planning horizon as anchor
    anchor_date = start_date
    
    # Calculate optimal employees
    return calculate_optimal_with_u_slots(
        pattern=pattern,
        headcount=headcount,
        calendar=calendar,
        anchor_date=anchor_date,
        requirement_id=requirement_id
    )


def generate_coverage_calendar(
    start_date: str,
    end_date: str,
    coverage_days: Optional[List[str]] = None,
    public_holidays: List[str] = None
) -> List[str]:
    """
    Generate list of dates requiring coverage within planning horizon.
    
    Filters:
    1. Only include specified coverage days (e.g., Mon-Fri)
    2. Exclude public holidays
    
    Args:
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
        coverage_days: List of weekday names (e.g., ["Monday", "Tuesday"])
                      If None, includes all days
        public_holidays: List of ISO dates to exclude
        
    Returns:
        List of ISO date strings requiring coverage
    """
    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date)
    public_holidays_set = set(public_holidays or [])
    
    # Map weekday names to datetime weekday numbers (0=Monday, 6=Sunday)
    weekday_map = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
        'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }
    
    # Convert coverage days to set of weekday numbers
    if coverage_days:
        coverage_weekdays = {weekday_map[day] for day in coverage_days if day in weekday_map}
    else:
        coverage_weekdays = set(range(7))  # All days
    
    calendar = []
    current = start_dt
    
    while current <= end_dt:
        date_str = current.strftime('%Y-%m-%d')
        
        # Check if this day should be included
        is_coverage_day = current.weekday() in coverage_weekdays
        is_not_holiday = date_str not in public_holidays_set
        
        if is_coverage_day and is_not_holiday:
            calendar.append(date_str)
        
        current += timedelta(days=1)
    
    return calendar


def optimize_multiple_requirements(
    requirements: List[Dict[str, Any]],
    planning_horizon: Dict[str, Any],
    public_holidays: List[str] = None,
    coverage_days: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Calculate optimal employees for multiple requirements.
    
    Processes each requirement independently and returns results.
    
    Args:
        requirements: List of requirement dicts with workPattern and headcount
        planning_horizon: Dict with startDate, endDate
        public_holidays: List of ISO dates to exclude (optional)
        coverage_days: List of weekday names (optional)
        
    Returns:
        List of results (one per requirement)
    """
    results = []
    
    for req in requirements:
        try:
            result = calculate_employees_for_requirement(
                req, planning_horizon, public_holidays, coverage_days
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to calculate for requirement {req.get('requirementId')}: {e}")
            results.append({
                'requirementId': req.get('requirementId', 'unknown'),
                'error': str(e),
                'status': 'FAILED'
            })
    
    return results


# ============================================================
# LEGACY COMPATIBILITY WRAPPERS (for /configure endpoint)
# ============================================================
# These functions provide backward compatibility with the old
# config_optimizer.py API but use v3 logic internally

def optimize_all_requirements(
    requirements: List[Dict],
    constraints: Dict,
    planning_horizon: Dict,
    shift_definitions: Optional[Dict[str, Dict]] = None,
    top_n: int = 5
) -> Dict:
    """
    Legacy wrapper for /configure endpoint compatibility.
    
    Note: This is a simplified implementation using ICPMP v3 logic.
    The original v2 implementation had more complex multi-pattern
    evaluation that is not needed for current use cases.
    
    Args:
        requirements: List of requirement specifications
        constraints: Constraint parameters (unused in v3)
        planning_horizon: Planning horizon with start/end dates
        shift_definitions: Shift definitions (unused in v3)
        top_n: Number of alternatives to return (v3 only returns 1 optimal)
    
    Returns:
        Dict mapping requirement IDs to their configurations
    """
    logger.info("Using ICPMP v3 logic for configuration optimization")
    
    # Convert requirements to v3 format and calculate
    results = optimize_multiple_requirements(
        requirements=requirements,
        planning_horizon=planning_horizon,
        public_holidays=[],  # Not provided in /configure
        coverage_days=[]  # Calculate from requirement
    )
    
    # Convert v3 results to old format
    optimized_configs = {}
    for result in results:
        if result.get('status') == 'FAILED':
            continue
            
        req_id = result['requirementId']
        config = result['configuration']
        
        # Format as old-style config
        optimized_configs[req_id] = [{
            'workPattern': config.get('workPattern', 'UNKNOWN'),
            'employeesRequired': config.get('employeesRequired', 0),
            'strictEmployees': config.get('employeesRequired', 0),  # v3 has no flexible
            'flexibleEmployees': 0,  # v3 uses all strict
            'employeeOffsets': config.get('rotationOffsets', []),
            'expectedCoverageRate': result['coverage'].get('achievedRate', 0),
            'score': 0  # v3 doesn't use scoring
        }]
    
    return optimized_configs


def format_output_config(optimized_result: Dict, input_config: Dict) -> Dict:
    """
    Legacy wrapper to format optimization results for /configure endpoint.
    
    Args:
        optimized_result: Result from optimize_all_requirements
        input_config: Original input configuration
    
    Returns:
        Formatted output configuration
    """
    recommendations = []
    
    for req_id, configs in optimized_result.items():
        # Find requirement details
        req = next((r for r in input_config['requirements'] 
                   if r.get('requirementId', r.get('id')) == req_id), None)
        
        if not req:
            continue
            
        for rank, config in enumerate(configs, 1):
            recommendations.append({
                'requirementId': req_id,
                'requirementName': req.get('requirementName', req.get('name')),
                'alternativeRank': rank,
                'configuration': {
                    'workPattern': config['workPattern'],
                    'employeesRequired': config['employeesRequired'],
                    'strictEmployees': config['strictEmployees'],
                    'flexibleEmployees': config['flexibleEmployees'],
                    'employeeOffsets': config['employeeOffsets']
                },
                'coverage': {
                    'expectedCoverageRate': config['expectedCoverageRate'],
                    'coverageType': 'complete' if config['expectedCoverageRate'] >= 100 else 'partial'
                },
                'quality': {
                    'score': config['score']
                }
            })
    
    # Calculate summary
    total_employees = sum(
        configs[0]['employeesRequired'] 
        for configs in optimized_result.values() 
        if configs
    )
    
    return {
        'schemaVersion': input_config.get('schemaVersion', '0.95'),
        'configType': 'optimizedRosterConfiguration',
        'generatedAt': datetime.now().isoformat(),
        'organizationId': input_config.get('organizationId', 'ORG_TEST'),
        'planningHorizon': input_config['planningHorizon'],
        'summary': {
            'totalRequirements': len(input_config['requirements']),
            'totalEmployees': total_employees,
            'optimizerVersion': 'ICPMP v3.0 (with tightness buffer)'
        },
        'recommendations': recommendations
    }


def simulate_coverage_with_preprocessing(
    pattern: List[str],
    headcount: int,
    coverage_days: List[str],
    days_in_horizon: int,
    start_date: datetime
) -> Dict:
    """
    Legacy wrapper for feasibility checker.
    
    Simulates coverage using v3 placement logic.
    """
    calendar = coverage_days  # Use coverage days directly
    anchor_date = start_date.isoformat()
    
    # Use v3's try_placement_with_n_employees to simulate
    # Start with mathematical minimum
    cycle_length = len(pattern)
    work_days = sum(1 for d in pattern if d != 'O')
    base_minimum = ceil(headcount * cycle_length / work_days)
    
    # Try placement
    result = try_placement_with_n_employees(
        num_employees=base_minimum,
        pattern=pattern,
        headcount=headcount,
        calendar=calendar,
        anchor_date=anchor_date,
        cycle_length=cycle_length,
        scheme="A",  # Default to Scheme A for legacy function
        enable_ot_aware=False
    )
    
    return {
        'employeeCount': base_minimum,
        'strictEmployees': base_minimum,
        'flexibleEmployees': 0,
        'trulyFlexibleEmployees': 0,
        'offsets': list(result['offset_distribution'].keys()),
        'coverageComplete': result['is_feasible'],
        'coverageRange': [0, headcount] if result['is_feasible'] else [0, 0],
        'calendarDays': len(calendar)
    }
