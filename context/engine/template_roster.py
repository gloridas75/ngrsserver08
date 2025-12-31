"""
Template-Based Validation Roster Generator

This module implements a hybrid approach between pattern-based and CP-SAT:
- Validates ALL hard constraints (like CP-SAT)
- Fast execution (like pattern-based)
- Graceful failure handling (unassigned slots when constraints violated)

Strategy:
1. For each OU, select one "template employee"
2. Generate full month roster following workPattern
3. Validate EVERY assignment against ALL constraints
4. Store validated pattern (assigned/unassigned per day)
5. Replicate pattern to all employees in same OU
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any
import logging

try:
    from context.engine.constraint_config import get_constraint_param
    _has_constraint_config = True
except ImportError:
    _has_constraint_config = False

logger = logging.getLogger(__name__)


def generate_template_validated_roster(
    ctx: Dict[str, Any],
    selected_employees: List[Dict[str, Any]],
    requirement: Dict[str, Any],
    demand: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Generate roster using template-based validation.
    
    Phase 1: Generate template pattern per OU (validate all constraints)
    Phase 2: Replicate validated pattern to all employees in OU
    
    Args:
        ctx: Context dictionary with planning data
        selected_employees: List of employees to roster
        requirement: Requirement configuration
        demand: Demand item configuration
    
    Returns:
        Tuple of (assignments list, statistics dict)
    """
    logger.info("=" * 80)
    logger.info("TEMPLATE-BASED VALIDATION ROSTER")
    logger.info("=" * 80)
    
    work_pattern = requirement.get('workPattern', [])
    if not work_pattern:
        logger.error("No work pattern defined in requirement")
        return [], {'error': 'No work pattern'}
    
    # Extract planning horizon
    planning_horizon = ctx.get('planningHorizon', {})
    start_date_str = planning_horizon.get('startDate')
    end_date_str = planning_horizon.get('endDate')
    
    if not start_date_str or not end_date_str:
        logger.error("Planning horizon not defined")
        return [], {'error': 'No planning horizon'}
    
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    # Get shift details and coverage days
    shift_details = _extract_shift_details(demand)
    if not shift_details:
        logger.error("No shift details found")
        return [], {'error': 'No shift details'}
    
    # Extract coverage days (e.g., ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'])
    coverage_days = _extract_coverage_days(demand)
    logger.info(f"Coverage days: {coverage_days}")
    
    # Group employees by OU
    employees_by_ou = _group_employees_by_ou(selected_employees)
    logger.info(f"Grouped employees into {len(employees_by_ou)} OUs")
    
    # Phase 1: Generate and validate template per OU
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 1: Template Generation & Validation")
    logger.info("=" * 80)
    
    ou_templates = {}
    for ou_id, ou_employees in employees_by_ou.items():
        logger.info(f"\nProcessing OU: {ou_id} ({len(ou_employees)} employees)")
        
        # Select template employee (first one in list)
        template_emp = ou_employees[0]
        logger.info(f"  Template: {template_emp['employeeId']}")
        
        # Generate and validate template pattern
        template_pattern = _generate_validated_template(
            template_emp,
            work_pattern,
            start_date,
            end_date,
            shift_details,
            ctx,
            demand,
            requirement,
            coverage_days
        )
        
        ou_templates[ou_id] = template_pattern
        
        assigned_days = sum(1 for day_status in template_pattern.values() if day_status['assigned'])
        unassigned_days = len(template_pattern) - assigned_days
        logger.info(f"  Template validated: {assigned_days} assigned, {unassigned_days} unassigned")
    
    # Phase 2: Replicate template to all employees
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 2: Template Replication")
    logger.info("=" * 80)
    
    all_assignments = []
    for ou_id, ou_employees in employees_by_ou.items():
        template_pattern = ou_templates[ou_id]
        logger.info(f"\nReplicating OU {ou_id} template to {len(ou_employees)} employees")
        
        for emp in ou_employees:
            emp_assignments = _replicate_template_to_employee(
                emp,
                template_pattern,
                demand,
                requirement
            )
            all_assignments.extend(emp_assignments)
    
    # Generate statistics
    stats = _generate_statistics(all_assignments, selected_employees)
    
    logger.info("\n" + "=" * 80)
    logger.info("TEMPLATE ROSTER COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total Assignments: {len(all_assignments)}")
    logger.info(f"  - Assigned: {stats['assigned_count']}")
    logger.info(f"  - Unassigned: {stats['unassigned_count']}")
    logger.info(f"Employees Used: {stats['employees_used']}")
    logger.info(f"Generation Time: {stats['generation_time']:.3f}s")
    logger.info("=" * 80)
    
    return all_assignments, stats


def _extract_shift_details(demand: Dict[str, Any]) -> Dict[str, Any]:
    """Extract shift timing details from demand."""
    shifts = demand.get('shifts', [])
    if not shifts:
        return {}
    
    shift_details_list = shifts[0].get('shiftDetails', [])
    if not shift_details_list:
        return {}
    
    # Find 'D' shift (day shift)
    for shift_detail in shift_details_list:
        if shift_detail.get('shiftCode') == 'D':
            return shift_detail
    
    return shift_details_list[0] if shift_details_list else {}


def _extract_coverage_days(demand: Dict[str, Any]) -> List[str]:
    """Extract coverage days from demand (e.g., ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'])."""
    shifts = demand.get('shifts', [])
    if not shifts:
        return ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']  # Default: all days
    
    coverage_days = shifts[0].get('coverageDays', [])
    if not coverage_days:
        return ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']  # Default: all days
    
    return coverage_days


def _group_employees_by_ou(employees: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group employees by their OU."""
    ou_groups = {}
    for emp in employees:
        ou_id = emp.get('ouId', 'UNKNOWN')
        if ou_id not in ou_groups:
            ou_groups[ou_id] = []
        ou_groups[ou_id].append(emp)
    return ou_groups


def _generate_validated_template(
    template_emp: Dict[str, Any],
    work_pattern: List[str],
    start_date,
    end_date,
    shift_details: Dict[str, Any],
    ctx: Dict[str, Any],
    demand: Dict[str, Any],
    requirement: Dict[str, Any],
    coverage_days: List[str]
) -> Dict[str, Dict[str, Any]]:
    """
    Generate and validate template pattern for one employee.
    
    Args:
        coverage_days: List of day names when shifts should be assigned (e.g., ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'])
    
    Returns a dict mapping date -> {assigned: bool, reason: str, assignment: dict}
    """
    from context.engine.time_utils import calculate_mom_compliant_hours
    
    template_pattern = {}
    
    # Get employee offset
    emp_offset = template_emp.get('rotationOffset', 0)
    pattern_length = len(work_pattern)
    
    # Detect if this is Scheme A + APO (eligible for 6-day week with rest day pay)
    emp_scheme = template_emp.get('scheme', '')
    emp_product = template_emp.get('productTypeId', '')
    req_product = requirement.get('productTypeId', '')
    is_scheme_a_apo = (emp_scheme == 'Scheme A' and emp_product == 'APO' and req_product == 'APO')
    
    # Track state for constraint validation
    consecutive_days = 0
    weekly_hours = []  # List of (date, hours) tuples
    work_days_this_week = []  # Track work days in current Monday-Sunday week
    monthly_ot_minutes = 0
    last_shift_end = None
    
    current_date = start_date
    day_index = 0
    
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        day_name = current_date.strftime('%a')  # Mon, Tue, Wed, etc.
        
        # Check if this day is in coverage days
        if day_name not in coverage_days:
            # Outside coverage window - skip this day entirely
            template_pattern[date_str] = {
                'assigned': False,
                'reason': f'Outside coverage days (only {coverage_days})',
                'assignment': None,
                'is_work_day': False
            }
            current_date += timedelta(days=1)
            day_index += 1
            continue
        
        # Calculate Monday-Sunday work week for MOM compliance
        # MOM law defines work week as Monday-Sunday, NOT rolling 7-day window
        monday_of_week = current_date - timedelta(days=current_date.weekday())  # weekday() returns 0 for Monday
        sunday_of_week = monday_of_week + timedelta(days=6)
        
        # Clean up old weekly hours: keep only hours from current Monday-Sunday week
        weekly_hours = [(d, h) for d, h in weekly_hours if monday_of_week <= d < current_date]
        
        # Clean up work days tracking for current week
        work_days_this_week = [d for d in work_days_this_week if monday_of_week <= d < current_date]
        
        # Calculate pattern position with offset
        pattern_index = (emp_offset + day_index) % pattern_length
        pattern_day = work_pattern[pattern_index]
        
        if pattern_day == 'O':
            # Off day - always assigned (no work)
            template_pattern[date_str] = {
                'assigned': True,
                'reason': 'Off day',
                'assignment': None,
                'is_work_day': False
            }
            consecutive_days = 0  # Reset consecutive days
        else:
            # Work day - check if this would be 6th day in week for Scheme A APO
            work_day_position_in_week = len(work_days_this_week) + 1  # Current day would be Nth work day
            is_6th_day_apo = is_scheme_a_apo and work_day_position_in_week == 6
            
            # Validate constraints
            validation_result = _validate_assignment(
                template_emp,
                current_date,
                shift_details,
                consecutive_days,
                weekly_hours,
                monthly_ot_minutes,
                last_shift_end,
                ctx,
                coverage_days,
                requirement,
                demand,
                is_scheme_a_apo,
                work_day_position_in_week
            )
            
            if validation_result['valid']:
                # Create assignment
                assignment = _create_validated_assignment(
                    template_emp,
                    current_date,
                    shift_details,
                    demand,
                    requirement,
                    pattern_index,
                    emp_offset,
                    is_6th_day_apo
                )
                
                template_pattern[date_str] = {
                    'assigned': True,
                    'reason': 'All constraints satisfied',
                    'assignment': assignment,
                    'is_work_day': True
                }
                
                # Update tracking state
                consecutive_days += 1
                work_days_this_week.append(current_date)  # Track this work day
                
                # Track only normal hours for C2 weekly cap validation
                normal_hours = assignment['hours']['normal']
                weekly_hours.append((current_date, normal_hours))
                monthly_ot_minutes += assignment['hours']['ot'] * 60
                
                # Calculate last shift end time for rest period
                shift_end_time = shift_details.get('end', '20:00:00')
                shift_end_dt = datetime.combine(current_date, datetime.strptime(shift_end_time, '%H:%M:%S').time())
                if shift_details.get('nextDay', False):
                    shift_end_dt += timedelta(days=1)
                last_shift_end = shift_end_dt
            else:
                # Constraint violated - mark as unassigned
                template_pattern[date_str] = {
                    'assigned': False,
                    'reason': validation_result['reason'],
                    'assignment': None,
                    'is_work_day': True
                }
                consecutive_days = 0  # Reset if can't work
        
        current_date += timedelta(days=1)
        day_index += 1
    
    return template_pattern


def _validate_assignment(
    employee: Dict[str, Any],
    date,
    shift_details: Dict[str, Any],
    consecutive_days: int,
    weekly_hours: List[Tuple[Any, float]],
    monthly_ot_minutes: float,
    last_shift_end,
    ctx: Dict[str, Any],
    coverage_days: List[str],
    requirement: Dict[str, Any] = None,
    demand: Dict[str, Any] = None,
    is_scheme_a_apo: bool = False,
    work_day_position_in_week: int = 1
) -> Dict[str, Any]:
    """
    Validate if assignment satisfies all hard constraints.
    
    Args:
        coverage_days: List of day names when shifts can be assigned (e.g., ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'])
        requirement: Requirement dict with qualification and rank requirements (optional)
        is_scheme_a_apo: True if Scheme A + APO (eligible for 6-day week with rest day pay)
        work_day_position_in_week: Position of this work day in current Monday-Sunday week (1-6)
        demand: Demand dict (optional)
    
    Returns: {'valid': bool, 'reason': str}
    """
    from context.engine.time_utils import is_apgd_d10_employee
    
    # C7: Qualifications/Licenses (if requirement specified)
    if requirement:
        # Check rank/product type match (C11)
        emp_rank = employee.get('rankId')
        emp_product = employee.get('productTypeId')
        
        req_product = requirement.get('productTypeId')
        if req_product and emp_product != req_product:
            return {'valid': False, 'reason': f'C11: Product type {emp_product} does not match required {req_product}'}
        
        req_ranks = requirement.get('rankIds', [])
        if not req_ranks:
            req_ranks = [requirement.get('rankId')] if requirement.get('rankId') else []
        
        if req_ranks and emp_rank not in req_ranks:
            return {'valid': False, 'reason': f'C11: Rank {emp_rank} not in required ranks {req_ranks}'}
        
        # Check qualifications (C7)
        required_quals = requirement.get('requiredQualifications', [])
        if required_quals:
            # Build employee licenses map
            emp_licenses = {}
            for lic in employee.get('licenses', []):
                if isinstance(lic, dict):
                    code = lic.get('code')
                    expiry = lic.get('expiryDate')
                    if code:
                        emp_licenses[str(code)] = expiry
            
            for qual in employee.get('qualifications', []):
                if isinstance(qual, dict):
                    code = qual.get('code')
                    expiry = qual.get('expiryDate')
                    if code:
                        emp_licenses[str(code)] = expiry
                elif isinstance(qual, (str, int)):
                    # Simple format: just a code without expiry
                    emp_licenses[str(qual)] = None
            
            # Normalize to group format if needed
            if required_quals and isinstance(required_quals[0], dict) and 'qualifications' in required_quals[0]:
                qual_groups = required_quals
            elif required_quals and isinstance(required_quals[0], (str, int)):
                qual_groups = [{
                    'groupId': 'default',
                    'matchType': 'ALL',
                    'qualifications': required_quals
                }]
            else:
                qual_groups = []
            
            # Check each qualification group
            for group in qual_groups:
                match_type = group.get('matchType', 'ALL')
                group_quals = group.get('qualifications', [])
                
                if match_type == 'ALL':
                    for qual_code in group_quals:
                        qual_key = str(qual_code)
                        if qual_key not in emp_licenses:
                            return {'valid': False, 'reason': f'C7: Missing required qualification {qual_code}'}
                        
                        # Check expiry
                        expiry_str = emp_licenses[qual_key]
                        if expiry_str:
                            try:
                                expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
                                if date > expiry_date:
                                    return {'valid': False, 'reason': f'C7: Qualification {qual_code} expired on {expiry_str}'}
                            except:
                                pass
                
                elif match_type == 'ANY':
                    has_any = False
                    for qual_code in group_quals:
                        qual_key = str(qual_code)
                        if qual_key in emp_licenses:
                            expiry_str = emp_licenses[qual_key]
                            if not expiry_str:  # No expiry
                                has_any = True
                                break
                            try:
                                expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
                                if date <= expiry_date:
                                    has_any = True
                                    break
                            except:
                                pass
                    
                    if not has_any:
                        return {'valid': False, 'reason': f'C7: No valid qualification from group {group.get("groupId", "unknown")}'}
    
    # C1: Daily hours cap
    scheme = employee.get('scheme', 'Scheme A')
    shift_duration_hours = _calculate_shift_duration(shift_details)
    
    # Determine default based on scheme
    if 'Scheme A' in scheme:
        default_daily_cap = 14.0
    elif 'Scheme B' in scheme:
        default_daily_cap = 13.0
    elif 'Scheme P' in scheme:
        default_daily_cap = 9.0
    else:
        default_daily_cap = 12.0
    
    # Read from JSON config if available
    employee_dict = {'employeeId': employee.get('employeeId'), 'scheme': scheme}
    if _has_constraint_config:
        max_daily_hours = get_constraint_param(ctx, 'momDailyHoursCap', employee_dict, default=default_daily_cap)
    else:
        max_daily_hours = default_daily_cap
    
    if shift_duration_hours > max_daily_hours:
        return {'valid': False, 'reason': f'C1: Shift {shift_duration_hours}h exceeds {max_daily_hours}h daily cap'}
    
    # C2: Weekly 44h normal hours cap
    # SPECIAL CASE: Scheme A APO employees can work 6th day with rest day pay (0h normal)
    # Calculate what normal hours would be for THIS shift
    gross_hours = _calculate_shift_duration(shift_details)
    lunch_hours = 1.0 if gross_hours >= 8 else 0.0
    net_hours = gross_hours - lunch_hours
    
    # For Scheme A APO 6th work day in week: Use 0h normal (rest day pay applies)
    if is_scheme_a_apo and work_day_position_in_week == 6:
        shift_normal_hours = 0.0  # Rest day pay - doesn't count toward 44h cap
    else:
        shift_normal_hours = min(net_hours, 8.8)  # Standard: Cap at 8.8h normal
    
    # Read weekly cap from JSON config if available
    if _has_constraint_config:
        weekly_cap = get_constraint_param(ctx, 'momWeeklyHoursCap44h', employee_dict, default=44.0)
    else:
        weekly_cap = 44.0
    
    current_week_normal_hours = sum(h for d, h in weekly_hours)
    if current_week_normal_hours + shift_normal_hours > weekly_cap:
        return {'valid': False, 'reason': f'C2: Weekly normal hours {current_week_normal_hours + shift_normal_hours:.1f}h would exceed {weekly_cap}h cap'}
    
    # C3: Maximum consecutive days
    is_apgd_d10 = is_apgd_d10_employee(employee, ctx)
    default_consecutive = 8 if is_apgd_d10 else 12
    
    # Read from JSON config if available
    if _has_constraint_config:
        max_consecutive = get_constraint_param(ctx, 'maxConsecutiveWorkingDays', employee_dict, default=default_consecutive)
    else:
        max_consecutive = default_consecutive
    
    if consecutive_days >= max_consecutive:
        return {'valid': False, 'reason': f'C3: Consecutive days {consecutive_days} exceeds {max_consecutive} limit'}
    
    # C4: Minimum rest period
    if last_shift_end:
        default_rest = 8.0 if is_apgd_d10 else 11.0
        
        # Read from JSON config if available
        if _has_constraint_config:
            min_rest_hours = get_constraint_param(ctx, 'apgdMinRestBetweenShifts', employee_dict, default=default_rest)
        else:
            min_rest_hours = default_rest
        
        shift_start_time = shift_details.get('start', '08:00:00')
        shift_start_dt = datetime.combine(date, datetime.strptime(shift_start_time, '%H:%M:%S').time())
        
        rest_hours = (shift_start_dt - last_shift_end).total_seconds() / 3600
        if rest_hours < min_rest_hours:
            return {'valid': False, 'reason': f'C4: Rest period {rest_hours:.1f}h less than {min_rest_hours}h minimum'}
    
    # C5: Weekly rest day (check if had at least one off day in last 7 days)
    # Skip for APGD-D10 employees (exempted)
    if not is_apgd_d10:
        # Read from JSON config if available (minimum off days per week)
        if _has_constraint_config:
            min_off_days = get_constraint_param(ctx, 'minimumOffDaysPerWeek', employee_dict, default=1)
        else:
            min_off_days = 1
        
        # Count work days in rolling 7-day window
        work_days_in_window = len([d for d, h in weekly_hours if h > 0])
        
        # Count coverage-skipped days (e.g., weekends) in rolling 7-day window
        # These automatically count as off days
        coverage_skipped_count = 0
        for i in range(1, 8):  # Check previous 7 days
            check_date = date - timedelta(days=i)
            day_name = check_date.strftime('%a')
            if day_name not in coverage_days:
                coverage_skipped_count += 1
        
        # Calculate off days:
        # - Coverage-skipped days are always OFF (e.g., weekends when coverage is Mon-Fri)
        # - Remaining days in window = 7 - coverage_skipped_count
        # - Work days in remaining days = work_days_in_window
        # - Off days in remaining days = (7 - coverage_skipped_count) - work_days_in_window
        # - Total off days = coverage_skipped_count + off_days_in_remaining
        off_days_in_remaining = max(0, (7 - coverage_skipped_count) - work_days_in_window)
        total_off_days = coverage_skipped_count + off_days_in_remaining
        
        if total_off_days < min_off_days:
            return {'valid': False, 'reason': f'C5: Only {total_off_days} off day(s) in last 7 days (minimum {min_off_days} required)'}
    
    # C17: Monthly OT cap (72 hours)
    # Read from JSON config if available
    if _has_constraint_config:
        max_monthly_ot_hours = get_constraint_param(ctx, 'momMonthlyOTcap72h', employee_dict, default=72.0)
    else:
        max_monthly_ot_hours = 72.0
    
    max_monthly_ot_minutes = max_monthly_ot_hours * 60
    if monthly_ot_minutes >= max_monthly_ot_minutes:
        return {'valid': False, 'reason': f'C17: Monthly OT {monthly_ot_minutes/60:.1f}h exceeds {max_monthly_ot_hours}h cap'}
    
    return {'valid': True, 'reason': 'All constraints satisfied'}


def _calculate_shift_duration(shift_details: Dict[str, Any]) -> float:
    """Calculate shift duration in hours including lunch."""
    start_str = shift_details.get('start', '08:00:00')
    end_str = shift_details.get('end', '20:00:00')
    
    start_time = datetime.strptime(start_str, '%H:%M:%S')
    end_time = datetime.strptime(end_str, '%H:%M:%S')
    
    duration = (end_time - start_time).total_seconds() / 3600
    
    if shift_details.get('nextDay', False):
        duration += 24
    
    return duration


def _create_validated_assignment(
    employee: Dict[str, Any],
    date,
    shift_details: Dict[str, Any],
    demand: Dict[str, Any],
    requirement: Dict[str, Any],
    pattern_day: int,
    rotation_offset: int,
    is_6th_day_apo: bool = False
) -> Dict[str, Any]:
    """Create assignment dictionary for validated work day.
    
    Args:
        is_6th_day_apo: True if this is 6th work day in week for Scheme A APO (rest day pay applies)
    """
    from context.engine.time_utils import calculate_mom_compliant_hours
    
    emp_id = employee['employeeId']
    date_str = date.strftime('%Y-%m-%d')
    
    demand_id = demand.get('id', demand.get('demandId', 'UNKNOWN'))
    requirement_id = requirement.get('id', requirement.get('requirementId', 'unknown'))
    
    # Extract shift times
    shift_start = shift_details.get('start', '08:00:00')
    shift_end = shift_details.get('end', '20:00:00')
    next_day = shift_details.get('nextDay', False)
    
    # Create datetime strings
    start_datetime = f"{date_str}T{shift_start}"
    
    if next_day:
        end_date = date + timedelta(days=1)
        end_datetime = f"{end_date.strftime('%Y-%m-%d')}T{shift_end}"
    else:
        end_datetime = f"{date_str}T{shift_end}"
    
    # Calculate hours
    gross_hours = _calculate_shift_duration(shift_details)
    lunch_hours = 1.0 if gross_hours >= 8 else 0.0
    net_hours = gross_hours - lunch_hours
    
    # SCHEME A APO 6TH DAY: Apply rest day pay
    if is_6th_day_apo:
        normal_hours = 0.0
        rest_day_pay = 8.0
        ot_hours = max(0.0, net_hours - 8.0)  # OT is anything beyond 8h rest day pay
    else:
        # Standard pattern-aware calculation
        from context.constraints.C2_mom_weekly_hours import calculate_pattern_aware_hours
        work_pattern = employee.get('workPattern', [])
        emp_scheme = employee.get('scheme', 'A')
        normal_hours, ot_hours = calculate_pattern_aware_hours(
            work_pattern, pattern_day, gross_hours, lunch_hours, emp_scheme
        )
        rest_day_pay = 0.0
    
    assignment = {
        'assignmentId': f"{demand_id}-{date_str}-D-{emp_id}",
        'demandId': demand_id,
        'requirementId': requirement_id,
        'slotId': f"{demand_id}-{requirement_id}-D-P{pattern_day}-{date_str}",
        'employeeId': emp_id,
        'date': date_str,
        'startDateTime': start_datetime,
        'endDateTime': end_datetime,
        'shiftCode': 'D',
        'patternDay': pattern_day,
        'newRotationOffset': rotation_offset,
        'status': 'ASSIGNED',
        'hours': {
            'gross': round(gross_hours, 1),
            'lunch': round(lunch_hours, 1),
            'normal': round(normal_hours, 1),
            'ot': round(ot_hours, 1),
            'restDayPay': round(rest_day_pay, 1),
            'paid': round(gross_hours, 1)
        }
    }
    
    return assignment


def _replicate_template_to_employee(
    employee: Dict[str, Any],
    template_pattern: Dict[str, Dict[str, Any]],
    demand: Dict[str, Any],
    requirement: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Replicate validated template pattern to an employee."""
    import copy
    assignments = []
    
    for date_str, day_info in sorted(template_pattern.items()):
        if day_info['is_work_day'] and day_info['assigned']:
            # Deep copy template assignment to avoid shared references
            template_assignment = day_info['assignment']
            
            assignment = copy.deepcopy(template_assignment)
            # Update employee-specific fields
            assignment['assignmentId'] = template_assignment['assignmentId'].replace(
                template_assignment['employeeId'],
                employee['employeeId']
            )
            assignment['employeeId'] = employee['employeeId']
            
            assignments.append(assignment)
        elif day_info['is_work_day'] and not day_info['assigned']:
            # Create unassigned slot
            emp_id = employee['employeeId']
            demand_id = demand.get('id', demand.get('demandId', 'UNKNOWN'))
            requirement_id = requirement.get('id', requirement.get('requirementId', 'unknown'))
            
            assignment = {
                'assignmentId': f"{demand_id}-{date_str}-D-{emp_id}-UNASSIGNED",
                'demandId': demand_id,
                'requirementId': requirement_id,
                'slotId': f"{demand_id}-{requirement_id}-D-{date_str}",
                'employeeId': emp_id,
                'date': date_str,
                'shiftCode': 'D',
                'status': 'UNASSIGNED',
                'reason': day_info['reason']
            }
            
            assignments.append(assignment)
    
    return assignments


def _generate_statistics(assignments: List[Dict[str, Any]], employees: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate statistics about the roster."""
    import time
    
    assigned_count = sum(1 for a in assignments if a.get('status') == 'ASSIGNED')
    unassigned_count = sum(1 for a in assignments if a.get('status') == 'UNASSIGNED')
    
    unique_employees = set(a['employeeId'] for a in assignments if a.get('status') == 'ASSIGNED')
    
    return {
        'total_assignments': len(assignments),
        'assigned_count': assigned_count,
        'unassigned_count': unassigned_count,
        'employees_used': len(unique_employees),
        'total_available_employees': len(employees),
        'generation_time': 0.0,  # Will be set externally
        'method': 'template_validation'
    }
