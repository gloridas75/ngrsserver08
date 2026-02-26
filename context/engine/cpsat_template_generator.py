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
    
    # Extract public holiday settings
    public_holidays_list = ctx.get('publicHolidays', [])
    public_holidays = set()
    for ph in public_holidays_list:
        try:
            ph_date = datetime.fromisoformat(ph + "T00:00:00").date() if isinstance(ph, str) else ph
            public_holidays.add(ph_date)
        except Exception:
            pass
    
    include_public_holidays, include_eve_ph = _extract_public_holiday_settings(demand)
    logger.info(f"Public holidays: {public_holidays}, includePH: {include_public_holidays}, includeEvePH: {include_eve_ph}")
    
    all_assignments = []
    
    # Generate template for each OU
    for ou_id, ou_employees in employees_by_ou.items():
        logger.info(f"\nProcessing OU: {ou_id} ({len(ou_employees)} employees)")
        print(f"[DEBUG] Processing OU: {ou_id}, Employees: {len(ou_employees)}")
        
        # Use first employee as template
        template_emp = ou_employees[0]
        print(f"[DEBUG] Template employee: {template_emp.get('employeeId')}, Offset: {template_emp.get('rotationOffset')}")
        
        # Build CP-SAT model for template
        template_assignments = _build_and_solve_template(
            ctx=ctx,
            template_emp=template_emp,
            work_pattern=work_pattern,
            shift_details_map=shift_details,
            start_date=start_date,
            end_date=end_date,
            demand=demand,
            requirement=requirement,
            coverage_days=coverage_days,
            public_holidays=public_holidays,
            include_public_holidays=include_public_holidays,
            include_eve_ph=include_eve_ph
        )
        
        if not template_assignments:
            logger.warning(f"  CP-SAT failed to generate template for OU {ou_id}")
            continue
        
        logger.info(f"  Template: {len(template_assignments)} assignments")
        
        # Replicate template to employees
        # headcount = 0 means "roster all employees" (no limit)
        # headcount > 0 means "roster first N employees only"
        headcount = requirement.get('headcount', 0)
        if headcount > 0:
            employees_to_roster = ou_employees[:headcount]  # Limit to first N employees
            logger.info(f"  Headcount limit: Using {headcount}/{len(ou_employees)} employees")
            logger.info(f"  Selected employees: {[e.get('employeeId') for e in employees_to_roster]}")
        else:
            employees_to_roster = ou_employees  # Roster all employees in OU
            logger.info(f"  No headcount limit: Rostering all {len(ou_employees)} employees in OU")
        
        for emp in employees_to_roster:
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
    shift_details_map: dict,
    start_date: datetime,
    end_date: datetime,
    demand: dict,
    requirement: dict,
    coverage_days: List[str],
    public_holidays: set = None,
    include_public_holidays: bool = True,
    include_eve_ph: bool = True
) -> List[dict]:
    """
    Build CP-SAT model for single template employee and solve.
    
    Args:
        shift_details_map: Dict mapping shift codes to their timing details
        public_holidays: Set of public holiday dates
        include_public_holidays: If False, skip creating work slots on PH dates
        include_eve_ph: If False, skip creating work slots on eve of PH dates
    
    Returns list of assignment dicts for the template employee.
    """
    model = cp_model.CpModel()
    
    if public_holidays is None:
        public_holidays = set()
    
    # Generate list of dates
    dates = []
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date)
        current_date += timedelta(days=1)
    
    logger.info(f"  Building CP-SAT model for {len(dates)} days...")
    
    # Decision variables: x[date_idx] = 1 if employee works on this date
    x = {}
    pattern_violations = {}  # Track when pattern says work but constraints prevent it
    ph_work_days = {}  # Track PH dates where pattern would have been work (need PUBLIC_HOLIDAY status)
    ph_skipped = 0  # Track dates skipped due to public holidays
    eve_ph_skipped = 0  # Track dates skipped due to eve of public holidays
    pattern_length = len(work_pattern)
    emp_offset = template_emp.get('rotationOffset', 0)
    
    for i, date in enumerate(dates):
        day_name = date.strftime('%a')
        pattern_idx = (emp_offset + i) % pattern_length
        pattern_day = work_pattern[pattern_idx]
        date_as_date = date.date() if hasattr(date, 'date') else date
        
        # Check public holiday exclusion
        if date_as_date in public_holidays and not include_public_holidays:
            # Skip work on public holidays - treat as off day
            x[i] = model.NewIntVar(0, 0, f'ph_off_{date.strftime("%Y%m%d")}')
            ph_skipped += 1
            # Track if pattern would have been a work day - needs PUBLIC_HOLIDAY status
            if day_name in coverage_days and pattern_day != 'O':
                ph_work_days[i] = pattern_idx
            continue
        
        # Check eve of public holiday exclusion
        next_day = date_as_date + timedelta(days=1)
        if next_day in public_holidays and not include_eve_ph:
            # Skip work on eve of public holidays - treat as off day
            x[i] = model.NewIntVar(0, 0, f'eve_ph_off_{date.strftime("%Y%m%d")}')
            eve_ph_skipped += 1
            continue
        
        if day_name in coverage_days and pattern_day != 'O':
            # Pattern says work AND day is in coverage window
            # Create decision variable - let CP-SAT decide based on constraints
            x[i] = model.NewBoolVar(f'work_{date.strftime("%Y%m%d")}')
            # Track this as a day where pattern expects work
            pattern_violations[i] = True
        elif day_name in coverage_days and pattern_day == 'O':
            # Pattern says OFF but day is in coverage window - should not work
            x[i] = model.NewIntVar(0, 0, f'off_{date.strftime("%Y%m%d")}')
        else:
            # Outside coverage window - must be off
            x[i] = model.NewIntVar(0, 0, f'off_{date.strftime("%Y%m%d")}')
    
    if ph_skipped > 0:
        logger.info(f"  Skipped {ph_skipped} public holiday dates (includePH=False)")
    if eve_ph_skipped > 0:
        logger.info(f"  Skipped {eve_ph_skipped} eve of public holiday dates (includeEvePH=False)")
    
    # NOTE: We do NOT enforce pattern days as hard constraints
    # Instead, we let MOM constraints (C1-C17) determine feasibility
    # Days where pattern says work but constraints prevent it will become UNASSIGNED
    
    # For MOM constraints, use first shift details for duration calculation
    # (constraints care about shift duration, not specific shift type)
    first_shift_details = list(shift_details_map.values())[0] if shift_details_map else {}
    
    # Apply core MOM constraints (C2, C3, C5, C6, C7, C17)
    _apply_mom_constraints(
        model, x, dates, first_shift_details, template_emp, ctx, coverage_days,
        requirement=requirement,
        demand=demand
    )
    
    # Objective: maximize work days where pattern expects work
    # This prioritizes working on pattern days while respecting MOM constraints
    model.Maximize(sum(x[i] for i in pattern_violations.keys() if i in x))
    
    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10  # Quick solve for template
    solver.parameters.log_search_progress = False
    
    status = solver.Solve(model)
    
    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        logger.warning(f"  CP-SAT solver status: {solver.StatusName(status)}")
        return []
    
    # Extract solution and identify constraint violations
    work_days = [i for i in range(len(dates)) if i in x and solver.Value(x[i]) == 1]
    off_days = [i for i in range(len(dates)) if i in x and solver.Value(x[i]) == 0]
    
    # Identify UNASSIGNED days: pattern expected work but constraints prevented it
    unassigned_days = [i for i in pattern_violations.keys() if i in off_days]
    # Actual off days: off days that are NOT unassigned AND NOT PH work days
    actual_off_days = [i for i in off_days if i not in pattern_violations and i not in ph_work_days]
    
    logger.info(f"  CP-SAT solved: {len(work_days)} work days, {len(actual_off_days)} off days, {len(unassigned_days)} unassigned, {len(ph_work_days)} PH work days")
    
    # Convert to assignment dicts - include ASSIGNED, OFF_DAY, PUBLIC_HOLIDAY, and UNASSIGNED
    assignments = []
    
    # Create ASSIGNED work day assignments
    for day_idx in work_days:
        date = dates[day_idx]
        pattern_idx = (emp_offset + day_idx) % pattern_length
        assignment = _create_assignment(
            template_emp,
            date,
            shift_details_map,
            demand,
            requirement,
            work_pattern=work_pattern,
            pattern_idx=pattern_idx
        )
        assignments.append(assignment)
    
    # Create OFF_DAY assignments (pattern said off OR outside coverage - excludes PH work days)
    for day_idx in actual_off_days:
        date = dates[day_idx]
        off_assignment = _create_off_day_assignment(
            template_emp,
            date,
            demand,
            requirement,
            shift_details_map,
            public_holidays
        )
        assignments.append(off_assignment)
    
    # Create PUBLIC_HOLIDAY assignments (pattern said work but skipped due to PH exclusion)
    for day_idx, pattern_idx in ph_work_days.items():
        date = dates[day_idx]
        ph_assignment = _create_public_holiday_assignment(
            template_emp,
            date,
            demand,
            requirement,
            shift_details_map,
            work_pattern=work_pattern,
            pattern_idx=pattern_idx
        )
        assignments.append(ph_assignment)
    
    # Create UNASSIGNED assignments (pattern said work but constraints prevented)
    for day_idx in unassigned_days:
        date = dates[day_idx]
        pattern_idx = (emp_offset + day_idx) % pattern_length
        pattern_day = work_pattern[pattern_idx]
        
        unassigned_assignment = _create_unassigned_assignment(
            template_emp,
            date,
            demand,
            requirement,
            shift_details_map,
            work_pattern=work_pattern,
            pattern_idx=pattern_idx,
            reason=f"MOM constraint violation: pattern requires '{pattern_day}' shift but conflicts with weekly rest day requirement"
        )
        assignments.append(unassigned_assignment)
    
    # Sort by date for readability
    assignments.sort(key=lambda a: a['date'])
    
    return assignments


def _apply_mom_constraints(
    model: cp_model.CpModel,
    x: Dict[int, cp_model.IntVar],
    dates: List[datetime],
    shift_details: dict,
    employee: dict,
    ctx: dict,
    coverage_days: List[str],
    requirement: dict = None,
    demand: dict = None
):
    """Apply core MOM regulatory constraints (C2, C3, C5, C6, C7, C17)."""
    
    from context.engine.time_utils import normalize_scheme, is_apgd_d10_employee
    
    # Get work pattern info early (needed for both C2 and C5)
    work_pattern = requirement.get('workPattern', []) if requirement else []
    pattern_length = len(work_pattern)
    
    # Use default MOM parameters (conservative approach)
    min_off_days_per_week = 1
    max_weekly_normal_hours = 44.0  # For full-time (Scheme A/B)
    max_monthly_ot_hours = 72.0
    
    # Employee scheme and product type for special rules
    emp_scheme_raw = employee.get('scheme', 'A')
    emp_scheme = normalize_scheme(emp_scheme_raw)
    
    # Check if employee is APGD-D10 (Scheme A + APO)
    is_apgd = is_apgd_d10_employee(employee, requirement)
    
    # C3: Maximum consecutive work days
    # Standard: 12 days, APGD-D10 (APO): 8 days
    max_consecutive_days = 8 if is_apgd else 12
    
    if is_apgd:
        logger.info(f"  APGD-D10 detected (Scheme A + APO): Using 8-day consecutive limit and NO monthly OT cap")
    
    # Calculate shift duration
    shift_duration_hours = _calculate_shift_duration(shift_details)
    
    # For a 5-day work week, normal hours are typically 8.8h/day
    # Use this as estimate for weekly hour cap (actual will be calculated in output builder)
    estimated_normal_hours_per_day = 8.8
    estimated_normal_minutes = int(estimated_normal_hours_per_day * 60)
    
    # C2: Maximum 44 normal hours per work week (Monday-Sunday) - Full-time only (Scheme A/B)
    # Note: Scheme P (part-time) is EXEMPT from C2 - handled by C6 in post-solution validation
    # C6 enforces 34.98h or 29.98h weekly limits for part-timers based on actual shift hours
    
    max_weekly_normal_minutes = int(max_weekly_normal_hours * 60)
    
    # Group dates into Monday-Sunday weeks
    weeks = _group_dates_by_week(dates)
    
    # C2: Only apply to full-time employees (Scheme A/B)
    # Scheme P employees are exempt - C6 handles them with proper hour calculations
    if emp_scheme == 'P':
        print(f"[C2 DEBUG] Scheme P employee - SKIPPING C2 (handled by C6 post-solution)")
        logger.info(f"  C2: Skipping for Scheme P - C6 will enforce part-timer limits")
    else:
        # C2 with scheme-aware weekly cap logic for full-time:
        # Scheme A/B (full-time): Days 1-5 count as normal hours (8.8h), Days 6-7 get rest day pay (0h normal)
        print(f"[C2 DEBUG] Applying scheme-aware weekly hours constraint (pattern length = {pattern_length})")
        print(f"[C2 DEBUG] Scheme: {emp_scheme}, Weekly cap: {max_weekly_normal_hours}h")
        print(f"[C2 DEBUG] Scheme A/B: Only first 5 work days per week count toward {max_weekly_normal_hours}h cap")
        print(f"[C2 DEBUG] Days 6-7 in calendar week get rest day pay (0h normal)")
    
        for week_dates in weeks:
            week_indices = [i for i, d in enumerate(dates) if d in week_dates and i in x]
            if not week_indices:
                continue
        
            # Count how many work days we might have in this week
            num_potential_work_days = len(week_indices)
        
            # Scheme A/B: Only first 5 work days contribute to normal hours cap
            # Days 6+ get rest day pay (0h normal), so they don't count toward 44h
            days_that_count = min(5, num_potential_work_days)
        
            # Build constraint: sum of work days × 8.8h <= weekly cap
            normal_hour_terms = []
            for position in range(days_that_count):
                idx = week_indices[position]
                normal_hour_terms.append(x[idx] * estimated_normal_minutes)
        
            if normal_hour_terms:
                model.Add(sum(normal_hour_terms) <= max_weekly_normal_minutes)
            
                expected_max_normal = days_that_count * 8.8
                print(f"[C2 DEBUG] Week {week_dates[0].strftime('%Y-%m-%d')}: "
                      f"Up to {num_potential_work_days} work days, "
                      f"{days_that_count} count toward cap (max {expected_max_normal:.1f}h normal)")
    
    # C3: Maximum consecutive work days (12 for standard, 8 for APGD-D10/APO)
    for i in range(len(dates) - max_consecutive_days):
        consecutive_indices = [j for j in range(i, i + max_consecutive_days + 1) if j in x]
        if len(consecutive_indices) == max_consecutive_days + 1:
            # At least one day in this window must be OFF
            model.Add(sum(x[j] for j in consecutive_indices) <= max_consecutive_days)
    
    # C5: Minimum off days per week
    # Use different strategies based on pattern alignment with calendar weeks
    # (pattern_length already defined earlier)
    
    print(f"[C5 DEBUG] Pattern length: {pattern_length}, Pattern: {work_pattern}")
    print(f"[C5 DEBUG] Max consecutive days: {max_consecutive_days}, Is APGD-D10: {is_apgd}")
    
    if pattern_length == 7:
        # For APGD-D10 with 7-day patterns and 8-day consecutive approval:
        # Use 8-day windows (not 7) to allow 8 consecutive work days
        if is_apgd and max_consecutive_days >= 8 and all(d != 'O' for d in work_pattern):
            print(f"[C5 DEBUG] APGD-D10 with 7 consecutive work pattern and 8-day approval")
            print(f"[C5 DEBUG] Using 8-day windows to allow 8 consecutive days")
            logger.info(f"  C5: APGD-D10 special - using 8-day windows for 8 consecutive")
            
            # Use 8-day rolling windows: max 8 work days, min 1 OFF in any 9 days
            for i in range(len(dates) - 8):
                window_indices = [j for j in range(i, i + 9) if j in x]
                if len(window_indices) == 9:
                    # In any 9 consecutive days, allow up to 8 work days
                    model.Add(sum(x[j] for j in window_indices) <= 8)
        else:
            # Pattern aligns with calendar weeks - use rolling 7-day windows (stricter)
            print(f"[C5 DEBUG] Using rolling 7-day windows (standard pattern length = 7)")
            logger.info(f"  C5: Using rolling windows (pattern length = 7)")
            for i in range(len(dates) - 6):
                window_indices = [j for j in range(i, i + 7) if j in x]
                if len(window_indices) == 7:
                    # Count coverage-skipped days in this window
                    coverage_skipped = sum(1 for j in window_indices if dates[j].strftime('%a') not in coverage_days)
                    # Work days in window must leave enough off days
                    max_work_days = 7 - min_off_days_per_week - coverage_skipped
                    model.Add(sum(x[j] for j in window_indices) <= max_work_days)
    else:
        # Pattern doesn't align with calendar weeks - use calendar week boundaries
        # This avoids false violations from pattern drift across week boundaries
        print(f"[C5 DEBUG] Using calendar weeks (pattern length = {pattern_length} ≠ 7)")
        logger.info(f"  C5: Using calendar weeks (pattern length = {pattern_length} ≠ 7)")
        weeks = _group_dates_by_week(dates)
        print(f"[C5 DEBUG] Grouped {len(dates)} dates into {len(weeks)} calendar weeks")
        for week_dates in weeks:
            week_indices = [i for i, d in enumerate(dates) if d in week_dates and i in x]
            if week_indices:
                # Only enforce weekly rest for FULL 7-day weeks
                # Partial weeks at start/end don't need this constraint
                if len(week_dates) == 7:
                    # Count coverage-skipped days in this week
                    coverage_skipped = sum(1 for i in week_indices if dates[i].strftime('%a') not in coverage_days)
                    # Work days in week must leave enough off days
                    max_work_days = 7 - min_off_days_per_week - coverage_skipped
                    print(f"[C5 DEBUG] Full week {week_dates[0].strftime('%Y-%m-%d')} - {week_dates[-1].strftime('%Y-%m-%d')}: max_work_days={max_work_days}, coverage_skipped={coverage_skipped}")
                    model.Add(sum(x[i] for i in week_indices) <= max_work_days)
                else:
                    print(f"[C5 DEBUG] Partial week {week_dates[0].strftime('%Y-%m-%d')} - {week_dates[-1].strftime('%Y-%m-%d')}: Skipping constraint ({len(week_dates)} days < 7)")
    
    # C7: Qualification/license validity (only if requiredQualifications specified)
    required_quals_raw = requirement.get('requiredQualifications', []) if requirement else []
    
    # Normalize qualifications to handle both old (array of strings) and new (grouped) formats
    from context.engine.slot_builder import normalize_qualifications
    required_qual_groups = normalize_qualifications(required_quals_raw)
    
    if required_qual_groups:
        # Flatten all qualifications from all groups for checking
        required_quals = []
        for group in required_qual_groups:
            required_quals.extend(group.get('qualifications', []))
        
        logger.info(f"  Applying C7: Checking qualifications {required_quals}")
        emp_licenses = {}
        
        # Build license map for this employee
        for lic in employee.get('licenses', []):
            code = lic.get('code')
            expiry = lic.get('expiryDate')
            if code and expiry:
                emp_licenses[code] = expiry
        
        # Also check 'qualifications' field
        for qual in employee.get('qualifications', []):
            code = qual.get('code')
            expiry = qual.get('expiryDate')
            if code and expiry:
                emp_licenses[code] = expiry
        
        # Check if employee meets requirements
        has_required_quals = True
        for qual_code in required_quals:
            if qual_code not in emp_licenses:
                has_required_quals = False
                logger.warning(f"  ⚠️  Employee {employee.get('employeeId')} missing qualification: {qual_code}")
                break
            
            # Check expiry for each work date
            expiry_str = emp_licenses[qual_code]
            try:
                from datetime import datetime as dt
                expiry_date = dt.strptime(expiry_str, '%Y-%m-%d').date()
                
                # For all work dates, ensure license is valid
                for i, date in enumerate(dates):
                    if i in x:
                        if date.date() > expiry_date:
                            # License expired before this date - cannot work
                            model.Add(x[i] == 0)
                            logger.info(f"    Blocking date {date.date()} (license expires {expiry_date})")
            except (ValueError, AttributeError) as e:
                logger.warning(f"  ⚠️  Invalid expiry date for {qual_code}: {expiry_str}")
                has_required_quals = False
                break
        
        if not has_required_quals:
            # Employee doesn't meet qualifications - cannot work any day
            logger.warning(f"  ⚠️  Employee {employee.get('employeeId')} does not meet qualification requirements")
            for i in x:
                model.Add(x[i] == 0)
    
    # C17: Monthly overtime cap (using 44h/week threshold - consistent with output builder)
    # Read monthly OT cap from monthlyHourLimits (scheme/product-specific)
    # Standard: 72h/month, APGD-D10 (APO): 112-124h/month depending on month length
    from context.engine.constraint_config import get_monthly_hour_limits
    
    # Weekly normal hours threshold (MOM standard)
    WEEKLY_HOURS_THRESHOLD = 44.0
    SCALE = 100  # Scale factor for integer arithmetic (2 decimal precision)
    weekly_threshold_scaled = int(WEEKLY_HOURS_THRESHOLD * SCALE)
    
    # Group dates by (calendar month, ISO week) for weekly OT calculation
    # We need weekly OT = max(0, weekly_gross - 44h), then sum for monthly cap
    
    # First, group dates by ISO week
    week_groups = {}  # (iso_year, iso_week) -> [date_indices]
    for i, date in enumerate(dates):
        if i in x:
            iso_year, iso_week, _ = date.isocalendar()
            week_key = (iso_year, iso_week)
            if week_key not in week_groups:
                week_groups[week_key] = []
            week_groups[week_key].append(i)
    
    # Group dates by calendar month
    months = {}  # month_key -> (year, month, set of (iso_year, iso_week))
    for i, date in enumerate(dates):
        if i in x:
            month_key = f"{date.year}-{date.month:02d}"
            iso_year, iso_week, _ = date.isocalendar()
            if month_key not in months:
                months[month_key] = (date.year, date.month, set())
            months[month_key][2].add((iso_year, iso_week))
    
    # Gross hours per shift
    gross_hours = shift_duration_hours
    gross_scaled = int(round(gross_hours * SCALE))
    
    # Create weekly OT variables for each week
    weekly_ot_vars = {}  # (iso_year, iso_week) -> IntVar for weekly OT
    
    for week_key, week_indices in week_groups.items():
        iso_year, iso_week = week_key
        
        # Weekly gross = sum of (x[i] * gross_hours) for all days in week
        weekly_gross_terms = [x[i] * gross_scaled for i in week_indices]
        
        if weekly_gross_terms:
            max_weekly_gross = int(24 * 7 * SCALE)  # Max: 168h/week
            max_weekly_ot = max_weekly_gross - weekly_threshold_scaled
            
            # Create weekly gross variable
            weekly_gross_var = model.NewIntVar(0, max_weekly_gross, f"wg_{iso_year}_{iso_week}")
            model.Add(weekly_gross_var == sum(weekly_gross_terms))
            
            # Create weekly OT variable: max(0, weekly_gross - 44h)
            weekly_ot_var = model.NewIntVar(0, max_weekly_ot, f"wot_{iso_year}_{iso_week}")
            
            # weekly_ot = max(0, weekly_gross - 44h)
            diff_var = model.NewIntVar(-max_weekly_gross, max_weekly_gross, f"wd_{iso_year}_{iso_week}")
            model.Add(diff_var == weekly_gross_var - weekly_threshold_scaled)
            model.AddMaxEquality(weekly_ot_var, [diff_var, 0])
            
            weekly_ot_vars[week_key] = weekly_ot_var
    
    # Apply monthly OT cap for each month
    for month_key, (year, month, weeks_in_month) in months.items():
        # Collect weekly OT variables for this month
        monthly_ot_terms = []
        for week_key in weeks_in_month:
            if week_key in weekly_ot_vars:
                monthly_ot_terms.append(weekly_ot_vars[week_key])
        
        if monthly_ot_terms:
            # Get scheme/product-specific monthly OT cap
            monthly_limits = get_monthly_hour_limits(ctx, employee, year, month)
            monthly_ot_cap = monthly_limits.get('maxOvertimeHours', max_monthly_ot_hours)
            monthly_ot_cap_scaled = int(round(monthly_ot_cap * SCALE))
            
            # Sum of weekly OT for this month <= monthly cap
            model.Add(sum(monthly_ot_terms) <= monthly_ot_cap_scaled)
            if is_apgd:
                logger.info(f"  Applying C17 (APGD-D10): Monthly OT cap for {month_key} <= {monthly_ot_cap}h (44h/week threshold)")
            else:
                logger.info(f"  Applying C17: Monthly OT cap for {month_key} <= {monthly_ot_cap}h (44h/week threshold)")


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
    shift_details_map: dict,
    demand: dict,
    requirement: dict,
    work_pattern: List[str] = None,
    pattern_idx: int = None
) -> dict:
    """Create assignment dictionary for a work day.
    
    Args:
        employee: Employee dict
        date: Assignment date
        shift_details_map: Dict mapping shift codes to shift details
        demand: Demand dict
        requirement: Requirement dict
        work_pattern: List of shift codes (e.g., ['D', 'D', 'N', 'N', 'O', 'O'])
        pattern_idx: Index in work_pattern for this date
    """
    emp_id = employee['employeeId']
    date_str = date.strftime('%Y-%m-%d')
    
    demand_id = demand.get('id', demand.get('demandId', 'UNKNOWN'))
    requirement_id = requirement.get('id', requirement.get('requirementId', 'unknown'))
    
    # Determine shift code from work pattern
    if work_pattern and pattern_idx is not None:
        shift_code = work_pattern[pattern_idx]
    else:
        shift_code = 'D'  # Default
    
    # Get shift details for this shift code
    shift_details = shift_details_map.get(shift_code, {})
    if not shift_details:
        # Fallback: if shift code not in map, use first available shift
        shift_details = list(shift_details_map.values())[0] if shift_details_map else {}
    
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
    
    # Use the determined shift code
    shift_code = shift_details.get('shiftCode', shift_code)
    
    # NOTE: Hours NOT calculated here during template generation
    # Output builder will calculate hours properly with full assignment context
    # This ensures rest day pay logic can access all assignments in the week
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
        'status': 'ASSIGNED'
        # No 'hours' field - will be calculated by output builder
    }


def _create_off_day_assignment(
    employee: dict,
    date: datetime,
    demand: dict,
    requirement: dict,
    shift_details_map: dict,
    public_holidays: set = None
) -> dict:
    """Create assignment dictionary for an OFF day (non-work day).
    
    For public holidays, uses shiftCode='PH' and status='PUBLIC_HOLIDAY'.
    For regular off days, uses shiftCode='O' and status='OFF_DAY'.
    """
    
    emp_id = employee['employeeId']
    date_str = date.strftime('%Y-%m-%d')
    date_as_date = date.date() if hasattr(date, 'date') else date
    
    # Check if this is a public holiday
    is_public_holiday = False
    if public_holidays:
        is_public_holiday = date_as_date in public_holidays or date_str in public_holidays
    
    # Use appropriate shift code and status
    if is_public_holiday:
        shift_code = 'PH'
        status = 'PUBLIC_HOLIDAY'
    else:
        shift_code = 'O'
        status = 'OFF_DAY'
    
    demand_id = demand.get('id', demand.get('demandId', 'UNKNOWN'))
    requirement_id = requirement.get('id', requirement.get('requirementId', 'unknown'))
    
    # Use first shift details for display purposes (even though it's an OFF day)
    shift_details = list(shift_details_map.values())[0] if shift_details_map else {}
    shift_start = shift_details.get('start', '08:00:00')
    shift_end = shift_details.get('end', '20:00:00')
    next_day = shift_details.get('nextDay', False)
    
    # Create datetime strings
    start_datetime = f"{date_str}T{shift_start}"
    if next_day:
        from datetime import timedelta
        end_date = date + timedelta(days=1)
        end_datetime = f"{end_date.strftime('%Y-%m-%d')}T{shift_end}"
    else:
        end_datetime = f"{date_str}T{shift_end}"
    
    # OFF day assignment with zero hours
    return {
        'assignmentId': f"{demand_id}-{date_str}-{shift_code}-{emp_id}",
        'slotId': f"{demand_id}-{requirement_id}-{shift_code}-{date_str}",
        'employeeId': emp_id,
        'demandId': demand_id,
        'requirementId': requirement_id,
        'date': date_str,
        'shiftCode': shift_code,
        'startDateTime': start_datetime,  # Include shift time for UI display
        'endDateTime': end_datetime,
        'status': status,
        'hours': {
            'gross': 0.0,
            'lunch': 0.0,
            'net': 0.0,
            'normal': 0.0,
            'ot': 0.0,
            'ph': 0.0,
            'restDayPay': 0.0,
            'paid': 0.0
        }
    }


def _create_public_holiday_assignment(
    employee: dict,
    date: datetime,
    demand: dict,
    requirement: dict,
    shift_details_map: dict,
    work_pattern: List[str] = None,
    pattern_idx: int = None
) -> dict:
    """Create assignment dictionary for a PUBLIC_HOLIDAY day.
    
    This is for days where the employee's work pattern indicates a work day (D/N)
    but the date is a public holiday and includePublicHolidays=false.
    Uses shiftCode='PH' and status='PUBLIC_HOLIDAY'.
    Records the expected shift that would have been worked.
    """
    
    emp_id = employee['employeeId']
    date_str = date.strftime('%Y-%m-%d')
    
    demand_id = demand.get('id', demand.get('demandId', 'UNKNOWN'))
    requirement_id = requirement.get('id', requirement.get('requirementId', 'unknown'))
    
    # Determine what shift would have been worked from work pattern
    expected_shift = None
    if work_pattern and pattern_idx is not None:
        expected_shift = work_pattern[pattern_idx]
    
    # Get shift details for display purposes
    shift_details = {}
    if expected_shift and expected_shift in shift_details_map:
        shift_details = shift_details_map.get(expected_shift, {})
    if not shift_details:
        # Fallback: use first available shift
        shift_details = list(shift_details_map.values())[0] if shift_details_map else {}
    
    shift_start = shift_details.get('start', '08:00:00')
    shift_end = shift_details.get('end', '20:00:00')
    next_day = shift_details.get('nextDay', False)
    
    # Create datetime strings
    start_datetime = f"{date_str}T{shift_start}"
    if next_day:
        from datetime import timedelta
        end_date = date + timedelta(days=1)
        end_datetime = f"{end_date.strftime('%Y-%m-%d')}T{shift_end}"
    else:
        end_datetime = f"{date_str}T{shift_end}"
    
    # PUBLIC_HOLIDAY assignment with zero hours
    assignment = {
        'assignmentId': f"{demand_id}-{date_str}-PH-{emp_id}",
        'slotId': f"{demand_id}-{requirement_id}-PH-{date_str}",
        'employeeId': emp_id,
        'demandId': demand_id,
        'requirementId': requirement_id,
        'date': date_str,
        'shiftCode': 'PH',
        'startDateTime': start_datetime,
        'endDateTime': end_datetime,
        'status': 'PUBLIC_HOLIDAY',
        'hours': {
            'gross': 0.0,
            'lunch': 0.0,
            'net': 0.0,
            'normal': 0.0,
            'ot': 0.0,
            'ph': 0.0,
            'restDayPay': 0.0,
            'paid': 0.0
        }
    }
    
    # Include the expected shift that would have been worked
    if expected_shift:
        assignment['expectedShift'] = expected_shift
    
    return assignment


def _create_unassigned_assignment(
    employee: dict,
    date: datetime,
    demand: dict,
    requirement: dict,
    shift_details_map: dict,
    work_pattern: List[str] = None,
    pattern_idx: int = None,
    reason: str = "Constraint violation"
) -> dict:
    """Create assignment dictionary for an UNASSIGNED slot (constraint violation)."""
    
    emp_id = employee['employeeId']
    date_str = date.strftime('%Y-%m-%d')
    
    demand_id = demand.get('id', demand.get('demandId', 'UNKNOWN'))
    requirement_id = requirement.get('id', requirement.get('requirementId', 'unknown'))
    
    # Determine shift code from work pattern
    if work_pattern and pattern_idx is not None:
        shift_code = work_pattern[pattern_idx]
    else:
        shift_code = 'D'  # Default
    
    # Get shift details for this shift code
    shift_details = shift_details_map.get(shift_code, {})
    if not shift_details:
        # Fallback: use first available shift
        shift_details = list(shift_details_map.values())[0] if shift_details_map else {}
    
    # Extract shift times
    shift_start = shift_details.get('start', '08:00:00')
    shift_end = shift_details.get('end', '20:00:00')
    shift_code = shift_details.get('shiftCode', shift_code)  # Use actual shift code from details
    next_day = shift_details.get('nextDay', False)
    
    # Create datetime strings
    start_datetime = f"{date_str}T{shift_start}"
    if next_day:
        from datetime import timedelta
        end_date = date + timedelta(days=1)
        end_datetime = f"{end_date.strftime('%Y-%m-%d')}T{shift_end}"
    else:
        end_datetime = f"{date_str}T{shift_end}"
    
    # UNASSIGNED assignment with zero hours but includes reason
    return {
        'assignmentId': f"{demand_id}-{date_str}-UNASSIGNED-{emp_id}",
        'slotId': f"{demand_id}-{requirement_id}-{shift_code}-{date_str}",
        'employeeId': None,  # No employee assigned
        'demandId': demand_id,
        'requirementId': requirement_id,
        'date': date_str,
        'shiftCode': shift_code,
        'startDateTime': start_datetime,
        'endDateTime': end_datetime,
        'status': 'UNASSIGNED',
        'reason': reason,
        'hours': {
            'gross': 0.0,
            'lunch': 0.0,
            'net': 0.0,
            'normal': 0.0,
            'ot': 0.0,
            'ph': 0.0,
            'restDayPay': 0.0,
            'paid': 0.0
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
        
        # Update employee-specific fields ONLY for ASSIGNED/OFF_DAY/PUBLIC_HOLIDAY statuses
        # UNASSIGNED slots must keep employeeId=null
        status = assignment.get('status', 'ASSIGNED')
        if status in ['ASSIGNED', 'OFF_DAY', 'PUBLIC_HOLIDAY']:
            assignment['employeeId'] = emp_id
            # Regenerate IDs with this employee's ID
            date_str = assignment['date']
            shift_code = assignment['shiftCode']
            assignment['assignmentId'] = f"{demand_id}-{date_str}-{shift_code}-{emp_id}"
        else:
            # UNASSIGNED: keep employeeId=null, but update assignmentId for tracking
            date_str = assignment['date']
            shift_code = assignment['shiftCode']
            assignment['assignmentId'] = f"{demand_id}-{date_str}-UNASSIGNED-{date_str}"
        
        emp_assignments.append(assignment)
    
    return emp_assignments


def _group_employees_by_ou(employees: List[dict]) -> Dict[str, List[dict]]:
    """Group employees by organizational unit AND rotation offset.
    
    For staggered patterns (different employees have different offsets), 
    employees are grouped by BOTH ouId AND rotationOffset so each offset
    gets its own template.
    
    For non-staggered patterns (all same offset), employees are grouped
    by ouId only.
    """
    employees_by_ou = {}
    
    # Check if employees have OU IDs or just rotation offsets
    has_ou_ids = any(emp.get('ouId') or emp.get('organizationalUnitId') for emp in employees)
    
    # Check if employees have individual/staggered offsets
    offsets = [emp.get('rotationOffset', 0) for emp in employees]
    unique_offsets = set(offsets)
    has_staggered_offsets = len(unique_offsets) > 1
    
    for emp in employees:
        if has_ou_ids:
            # Get OU ID
            ou_id = emp.get('ouId') or emp.get('organizationalUnitId', 'default')
            
            if has_staggered_offsets:
                # Staggered mode: Group by BOTH OU and offset
                # This ensures each offset gets its own template
                rotation_offset = emp.get('rotationOffset', 0)
                group_key = f"{ou_id}|offset_{rotation_offset}"
            else:
                # Non-staggered: Group by OU only
                group_key = ou_id
        else:
            # No OU IDs: Group by rotation offset only
            rotation_offset = emp.get('rotationOffset', 0)
            group_key = f"offset_{rotation_offset}"
        
        if group_key not in employees_by_ou:
            employees_by_ou[group_key] = []
        employees_by_ou[group_key].append(emp)
    
    return employees_by_ou


def _extract_shift_details(demand: dict) -> dict:
    """Extract shift timing details from demand and create shift code mapping.
    
    Returns dict mapping shift codes to their details:
    {
        'D': {shiftCode: 'D', start: '08:00', end: '20:00', ...},
        'N': {shiftCode: 'N', start: '20:00', end: '08:00', nextDay: True, ...}
    }
    """
    shifts = demand.get('shifts', [])
    if not shifts:
        return {}
    
    shift_details_list = shifts[0].get('shiftDetails', [])
    if not shift_details_list:
        return {}
    
    # Create mapping of shift code → shift details
    shift_map = {}
    for shift_detail in shift_details_list:
        shift_code = shift_detail.get('shiftCode', 'D')
        shift_map[shift_code] = shift_detail
    
    return shift_map


def _extract_coverage_days(demand: dict) -> List[str]:
    """Extract coverage days from demand (default to all 7 days like incremental mode)."""
    shifts = demand.get('shifts', [])
    if not shifts:
        return ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']  # Default: all days
    
    coverage_days = shifts[0].get('coverageDays', [])
    if not coverage_days:
        return ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']  # Default: all days
    
    return coverage_days


def _extract_public_holiday_settings(demand: dict) -> Tuple[bool, bool]:
    """Extract public holiday settings from demand shifts.
    
    Returns:
        Tuple of (include_public_holidays, include_eve_of_public_holidays)
    """
    shifts = demand.get('shifts', [])
    if not shifts:
        return True, True  # Default: include PH days
    
    # Use first shift's settings
    include_ph = shifts[0].get('includePublicHolidays', True)
    include_eve_ph = shifts[0].get('includeEveOfPublicHolidays', True)
    
    return include_ph, include_eve_ph
