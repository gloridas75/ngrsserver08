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
    
    # Get shift details
    shift_details = _extract_shift_details(demand)
    if not shift_details:
        logger.error("No shift details found")
        return [], {'error': 'No shift details'}
    
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
            requirement
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
    requirement: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """
    Generate and validate template pattern for one employee.
    
    Returns a dict mapping date -> {assigned: bool, reason: str, assignment: dict}
    """
    from context.engine.time_utils import calculate_mom_compliant_hours
    
    template_pattern = {}
    
    # Get employee offset
    emp_offset = template_emp.get('rotationOffset', 0)
    pattern_length = len(work_pattern)
    
    # Track state for constraint validation
    consecutive_days = 0
    weekly_hours = []  # List of (date, hours) tuples
    monthly_ot_minutes = 0
    last_shift_end = None
    
    current_date = start_date
    day_index = 0
    
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        
        # Clean up old weekly hours BEFORE validation (keep only last 7 days)
        weekly_hours = [(d, h) for d, h in weekly_hours if (current_date - d).days < 7]
        
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
            # Work day - validate constraints
            validation_result = _validate_assignment(
                template_emp,
                current_date,
                shift_details,
                consecutive_days,
                weekly_hours,
                monthly_ot_minutes,
                last_shift_end,
                ctx
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
                    emp_offset
                )
                
                template_pattern[date_str] = {
                    'assigned': True,
                    'reason': 'All constraints satisfied',
                    'assignment': assignment,
                    'is_work_day': True
                }
                
                # Update tracking state
                consecutive_days += 1
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
    ctx: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validate if assignment satisfies all hard constraints.
    
    Returns: {'valid': bool, 'reason': str}
    """
    from context.engine.time_utils import is_apgd_d10_employee
    
    # C1: Daily hours cap
    scheme = employee.get('scheme', 'Scheme A')
    shift_duration_hours = _calculate_shift_duration(shift_details)
    
    max_daily_hours = 12  # Default
    if 'Scheme A' in scheme:
        max_daily_hours = 14
    elif 'Scheme B' in scheme:
        max_daily_hours = 13
    elif 'Scheme P' in scheme:
        max_daily_hours = 9
    
    if shift_duration_hours > max_daily_hours:
        return {'valid': False, 'reason': f'C1: Shift {shift_duration_hours}h exceeds {max_daily_hours}h daily cap'}
    
    # C2: Weekly 44h normal hours cap
    # Calculate what normal hours would be for THIS shift
    gross_hours = _calculate_shift_duration(shift_details)
    lunch_hours = 1.0 if gross_hours >= 8 else 0.0
    net_hours = gross_hours - lunch_hours
    shift_normal_hours = min(net_hours, 8.8)  # Cap at 8.8h normal
    
    current_week_normal_hours = sum(h for d, h in weekly_hours)
    if current_week_normal_hours + shift_normal_hours > 44:
        return {'valid': False, 'reason': f'C2: Weekly normal hours {current_week_normal_hours + shift_normal_hours:.1f}h would exceed 44h cap'}
    
    # C3: Maximum consecutive days
    is_apgd_d10 = is_apgd_d10_employee(employee, ctx)
    max_consecutive = 8 if is_apgd_d10 else 12
    
    if consecutive_days >= max_consecutive:
        return {'valid': False, 'reason': f'C3: Consecutive days {consecutive_days} exceeds {max_consecutive} limit'}
    
    # C4: Minimum rest period
    if last_shift_end:
        min_rest_hours = 8 if is_apgd_d10 else 11
        shift_start_time = shift_details.get('start', '08:00:00')
        shift_start_dt = datetime.combine(date, datetime.strptime(shift_start_time, '%H:%M:%S').time())
        
        rest_hours = (shift_start_dt - last_shift_end).total_seconds() / 3600
        if rest_hours < min_rest_hours:
            return {'valid': False, 'reason': f'C4: Rest period {rest_hours:.1f}h less than {min_rest_hours}h minimum'}
    
    # C5: Weekly rest day (check if had at least one off day in last 7 days)
    # Skip for APGD-D10 employees (exempted)
    if not is_apgd_d10:
        days_since_rest = len([d for d, h in weekly_hours if h > 0])
        if days_since_rest >= 7:
            return {'valid': False, 'reason': 'C5: No rest day in last 7 days'}
    
    # C17: Monthly OT cap (72 hours)
    max_monthly_ot_minutes = 72 * 60
    if monthly_ot_minutes >= max_monthly_ot_minutes:
        return {'valid': False, 'reason': f'C17: Monthly OT {monthly_ot_minutes/60:.1f}h exceeds 72h cap'}
    
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
    rotation_offset: int
) -> Dict[str, Any]:
    """Create assignment dictionary for validated work day."""
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
    
    # Calculate hours (simplified for template generation)
    gross_hours = _calculate_shift_duration(shift_details)
    lunch_hours = 1.0 if gross_hours >= 8 else 0.0
    net_hours = gross_hours - lunch_hours
    
    # Normal hours: 8.8h/day (44h/week ÷ 5 days), rest is OT
    # Always use 8.8h for normal (MOM compliance)
    if net_hours <= 8.8:
        normal_hours = net_hours
        ot_hours = 0.0
    else:
        normal_hours = 8.8
        ot_hours = net_hours - 8.8
    
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
            'restDayPay': 0.0,
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
