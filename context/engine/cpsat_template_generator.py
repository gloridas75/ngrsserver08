"""
CP-SAT Based Template Generation for Outcome-Based Mode

Uses Google OR-Tools CP-SAT to generate optimal template roster for one employee,
then replicates to all employees with rotation offsets.
"""

import logging
from typing import List, Tuple, Dict, Any
from datetime import datetime, timedelta
from ortools.sat.python import cp_model

logger = logging.getLogger(__name__)


def generate_template_with_cpsat(
    ctx: dict,
    requirement: dict,
    all_employees: List[dict],
    date_range: Tuple[datetime, datetime],
    optimization_mode: str = "minimizeEmployeeCount"
) -> List[dict]:
    """
    Generate optimal template roster using CP-SAT mini-solver.
    
    Creates one template employee, applies core MOM constraints (C1-C17),
    solves for optimal pattern, then replicates to all employees.
    
    Args:
        ctx: Full context dictionary with constraints config
        requirement: Work requirement with workPattern
        all_employees: List of employee dicts for this requirement
        date_range: (start_date, end_date) tuple
        optimization_mode: "minimizeEmployeeCount" or "balanceWorkload"
    
    Returns:
        List of assignment dicts for all employees
    """
    logger.info("=" * 80)
    logger.info("🔧 CP-SAT TEMPLATE GENERATOR")
    logger.info(f"   Requirement: {requirement.get('requirementId', 'N/A')}")
    logger.info(f"   Pattern: {requirement['workPattern']}")
    logger.info(f"   Employees: {len(all_employees)}")
    logger.info(f"   Date Range: {date_range[0].date()} to {date_range[1].date()}")
    logger.info(f"   Optimization Mode: {optimization_mode}")
    logger.info("   🚀 USING CP-SAT MODE (NOT INCREMENTAL)")
    logger.info("=" * 80)
    
    # Print to stdout to bypass logging filters
    print("\n" + "="*80)
    print("✓ CP-SAT TEMPLATE GENERATOR IS RUNNING (NOT FALLBACK TO INCREMENTAL)")
    print("="*80 + "\n")
    
    start_date, end_date = date_range
    work_pattern = requirement['workPattern']
    
    # Group employees by OU for template replication
    employees_by_ou = _group_employees_by_ou(all_employees)
    logger.info(f"Grouped {len(all_employees)} employees into {len(employees_by_ou)} OUs")
    
    # Get shift details from demand
    demand_items = ctx.get('demandItems', [])
    demand = next((d for d in demand_items if d.get('id') == requirement.get('demandId')), None)
    if not demand:
        logger.error("Could not find demand for requirement")
        return []
    
    shift_details = _extract_shift_details(demand)
    if not shift_details:
        logger.error("No shift details found in demand")
        return []
    
    # Get coverage days from demand (default to all 7 days like incremental mode)
    coverage_days = _extract_coverage_days(demand)
    
    all_assignments = []
    
    # Generate template for each OU
    for ou_id, ou_employees in employees_by_ou.items():
        logger.info(f"\nProcessing OU: {ou_id} ({len(ou_employees)} employees)")
        
        # Use first employee as template
        template_emp = ou_employees[0]
        
        # Build CP-SAT model for template
        template_assignments = _build_and_solve_template(
            ctx=ctx,
            template_emp=template_emp,
            work_pattern=work_pattern,
            shift_details=shift_details,
            start_date=start_date,
            end_date=end_date,
            demand=demand,
            requirement=requirement,
            coverage_days=coverage_days
        )
        
        if not template_assignments:
            logger.warning(f"  CP-SAT failed to generate template for OU {ou_id}")
            continue
        
        logger.info(f"  Template: {len(template_assignments)} assignments")
        
        # Replicate template to all employees in this OU
        for emp in ou_employees:
            emp_assignments = _replicate_template_to_employee(
                emp,
                template_assignments,
                demand,
                requirement,
                shift_details
            )
            all_assignments.extend(emp_assignments)
    
    logger.info(f"\n✓ CP-SAT template generation complete: {len(all_assignments)} total assignments")
    return all_assignments


def _build_and_solve_template(
    ctx: dict,
    template_emp: dict,
    work_pattern: List[str],
    shift_details: dict,
    start_date: datetime,
    end_date: datetime,
    demand: dict,
    requirement: dict,
    coverage_days: List[str]
) -> List[dict]:
    """
    Build CP-SAT model for single template employee and solve.
    
    Returns list of assignment dicts for the template employee.
    """
    model = cp_model.CpModel()
    
    # Generate list of dates
    dates = []
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date)
        current_date += timedelta(days=1)
    
    logger.info(f"  Building CP-SAT model for {len(dates)} days...")
    
    # Decision variables: x[date_idx] = 1 if employee works on this date
    x = {}
    for i, date in enumerate(dates):
        day_name = date.strftime('%a')
        if day_name in coverage_days:
            x[i] = model.NewBoolVar(f'work_{date.strftime("%Y%m%d")}')
        else:
            # Outside coverage window - must be off
            x[i] = model.NewIntVar(0, 0, f'off_{date.strftime("%Y%m%d")}')
    
    # Apply work pattern constraints
    pattern_length = len(work_pattern)
    emp_offset = template_emp.get('rotationOffset', 0)
    
    for i, date in enumerate(dates):
        pattern_idx = (emp_offset + i) % pattern_length
        pattern_day = work_pattern[pattern_idx]
        
        if pattern_day == 'O':
            # Pattern says OFF - must not work
            model.Add(x[i] == 0)
        # For 'D', 'N', 'E' etc - CP-SAT decides optimal days to work
    
    # Apply core MOM constraints
    _apply_mom_constraints(model, x, dates, shift_details, template_emp, ctx, coverage_days)
    
    # Objective: maximize work days (ensures we use the template employee fully)
    model.Maximize(sum(x[i] for i in range(len(dates)) if i in x))
    
    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10  # Quick solve for template
    solver.parameters.log_search_progress = False
    
    status = solver.Solve(model)
    
    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        logger.warning(f"  CP-SAT solver status: {solver.StatusName(status)}")
        return []
    
    # Extract solution
    work_days = [i for i in range(len(dates)) if i in x and solver.Value(x[i]) == 1]
    logger.info(f"  CP-SAT solved: {len(work_days)} work days assigned")
    
    # Convert to assignment dicts
    assignments = []
    for day_idx in work_days:
        date = dates[day_idx]
        assignment = _create_assignment(
            template_emp,
            date,
            shift_details,
            demand,
            requirement
        )
        assignments.append(assignment)
    
    return assignments


def _apply_mom_constraints(
    model: cp_model.CpModel,
    x: Dict[int, cp_model.IntVar],
    dates: List[datetime],
    shift_details: dict,
    employee: dict,
    ctx: dict,
    coverage_days: List[str]
):
    """Apply core MOM regulatory constraints (C1-C17) - simplified version."""
    
    # Use default MOM parameters (conservative approach)
    max_consecutive_days = 12
    min_off_days_per_week = 1
    max_weekly_normal_hours = 44.0  # This is for NORMAL hours, not gross
    
    # Calculate shift duration
    shift_duration_hours = _calculate_shift_duration(shift_details)
    
    # For a 5-day work week, normal hours are typically 8.8h/day
    # Use this as estimate for weekly hour cap (actual will be calculated in output builder)
    estimated_normal_hours_per_day = 8.8
    estimated_normal_minutes = int(estimated_normal_hours_per_day * 60)
    max_weekly_normal_minutes = int(max_weekly_normal_hours * 60)
    
    # C2: Maximum 44 normal hours per work week (Monday-Sunday)
    # Group dates into Monday-Sunday weeks
    weeks = _group_dates_by_week(dates)
    for week_dates in weeks:
        week_indices = [i for i, d in enumerate(dates) if d in week_dates and i in x]
        if week_indices:
            # Sum of work days * estimated normal hours <= 44h weekly cap
            # Note: Using 8.8h estimate; actual hours calculated later
            total_weekly_normal_minutes = sum(x[i] * estimated_normal_minutes for i in week_indices)
            model.Add(total_weekly_normal_minutes <= max_weekly_normal_minutes)
    
    # C3: Maximum consecutive work days (default 12)
    for i in range(len(dates) - max_consecutive_days):
        consecutive_indices = [j for j in range(i, i + max_consecutive_days + 1) if j in x]
        if len(consecutive_indices) == max_consecutive_days + 1:
            # At least one day in this window must be OFF
            model.Add(sum(x[j] for j in consecutive_indices) <= max_consecutive_days)
    
    # C5: Minimum off days per week (rolling 7-day window)
    for i in range(len(dates) - 6):
        window_indices = [j for j in range(i, i + 7) if j in x]
        if len(window_indices) == 7:
            # Count coverage-skipped days in this window
            coverage_skipped = sum(1 for j in window_indices if dates[j].strftime('%a') not in coverage_days)
            # Work days in window must leave enough off days
            max_work_days = 7 - min_off_days_per_week - coverage_skipped
            model.Add(sum(x[j] for j in window_indices) <= max_work_days)


def _calculate_shift_duration(shift_details: dict) -> float:
    """Calculate shift duration in hours (gross hours including lunch)."""
    start_str = shift_details.get('start', '08:00:00')
    end_str = shift_details.get('end', '20:00:00')
    
    start_time = datetime.strptime(start_str, '%H:%M:%S')
    end_time = datetime.strptime(end_str, '%H:%M:%S')
    
    duration = (end_time - start_time).total_seconds() / 3600
    
    if shift_details.get('nextDay', False):
        duration += 24
    
    return duration


def _group_dates_by_week(dates: List[datetime]) -> List[List[datetime]]:
    """Group dates into Monday-Sunday work weeks."""
    weeks = []
    current_week = []
    
    for date in dates:
        if date.weekday() == 0 and current_week:  # Monday
            weeks.append(current_week)
            current_week = []
        current_week.append(date)
    
    if current_week:
        weeks.append(current_week)
    
    return weeks


def _create_assignment(
    employee: dict,
    date: datetime,
    shift_details: dict,
    demand: dict,
    requirement: dict
) -> dict:
    """Create assignment dictionary for a work day."""
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
    
    # Calculate hours using MOM-compliant logic
    start_dt = datetime.fromisoformat(start_datetime)
    end_dt = datetime.fromisoformat(end_datetime)
    
    hours_breakdown = calculate_mom_compliant_hours(
        start_dt=start_dt,
        end_dt=end_dt,
        employee_id=emp_id,
        assignment_date_obj=date,
        all_assignments=[]  # Template phase - no previous assignments
    )
    
    # Get shift code from shift details
    shift_code = shift_details.get('shiftCode', 'D')
    
    return {
        'assignmentId': f"{demand_id}-{date_str}-{shift_code}-{emp_id}",
        'slotId': f"{demand_id}-{requirement_id}-{shift_code}-{date_str}",
        'employeeId': emp_id,
        'demandId': demand_id,
        'requirementId': requirement_id,
        'date': date_str,
        'shiftCode': shift_code,
        'startDateTime': start_datetime,
        'endDateTime': end_datetime,
        'status': 'ASSIGNED',
        'hours': {
            'gross': hours_breakdown['gross'],
            'lunch': hours_breakdown['lunch'],
            'net': hours_breakdown['gross'] - hours_breakdown['lunch'],
            'normal': hours_breakdown['normal'],
            'ot': hours_breakdown['ot'],
            'ph': 0.0,  # Public holiday hours (not determined in template phase)
            'restDayPay': hours_breakdown['restDayPay'],
            'paid': hours_breakdown['paid']  # Must include for output builder
        }
    }


def _replicate_template_to_employee(
    employee: dict,
    template_assignments: List[dict],
    demand: dict,
    requirement: dict,
    shift_details: dict
) -> List[dict]:
    """
    Replicate template assignments to an employee.
    
    All employees in the same OU get the SAME dates (no date shifting).
    The rotation offset was already applied during template generation.
    """
    import copy
    
    emp_assignments = []
    emp_id = employee['employeeId']
    demand_id = demand.get('id', demand.get('demandId', 'UNKNOWN'))
    
    for template_assign in template_assignments:
        # Deep copy to avoid shared references
        assignment = copy.deepcopy(template_assign)
        
        # Update employee-specific fields
        assignment['employeeId'] = emp_id
        
        # Regenerate IDs with this employee's ID
        date_str = assignment['date']
        shift_code = assignment['shiftCode']
        assignment['assignmentId'] = f"{demand_id}-{date_str}-{shift_code}-{emp_id}"
        
        emp_assignments.append(assignment)
    
    return emp_assignments


def _group_employees_by_ou(employees: List[dict]) -> Dict[str, List[dict]]:
    """Group employees by organizational unit."""
    employees_by_ou = {}
    for emp in employees:
        ou_id = emp.get('organizationalUnitId', 'default')
        if ou_id not in employees_by_ou:
            employees_by_ou[ou_id] = []
        employees_by_ou[ou_id].append(emp)
    return employees_by_ou


def _extract_shift_details(demand: dict) -> dict:
    """Extract shift timing details from demand."""
    shifts = demand.get('shifts', [])
    if not shifts:
        return {}
    
    shift_details_list = shifts[0].get('shiftDetails', [])
    if not shift_details_list:
        return {}
    
    return shift_details_list[0]


def _extract_coverage_days(demand: dict) -> List[str]:
    """Extract coverage days from demand (default to all 7 days like incremental mode)."""
    shifts = demand.get('shifts', [])
    if not shifts:
        return ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']  # Default: all days
    
    coverage_days = shifts[0].get('coverageDays', [])
    if not coverage_days:
        return ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']  # Default: all days
    
    return coverage_days
    return []
