"""
Shared output builder used by both CLI and API.

Refactored from run_solver.py to ensure CLI and API produce identical output.
"""

import json
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict
from context.engine.time_utils import (
    split_shift_hours, 
    calculate_mom_compliant_hours,
    calculate_apgd_d10_hours,
    is_apgd_d10_employee
)


def build_employee_roster(input_data, ctx, assignments):
    """
    Build a comprehensive employee roster showing daily status for ALL employees.
    
    Returns list with:
    - employeeRoster: List of all employees with their daily schedules
    - Each employee has: employeeId, offset, workPattern, dailyStatus[]
    - dailyStatus shows: date, status (ASSIGNED/OFF_DAY/UNASSIGNED/NOT_USED), shiftCode, assignmentId
    
    This allows consumers to clearly distinguish between:
    - ASSIGNED: Employee has an assignment on this date
    - OFF_DAY: Employee's pattern has 'O' for this date (legitimate rest day)
    - UNASSIGNED: Employee's pattern says work (D/N) but no assignment given
    - NOT_USED: Employee has no pattern/assignments (completely unused)
    """
    employees = ctx.get('employees', [])
    optimized_offsets = ctx.get('optimized_offsets', {})
    
    # Get date range from assignments (or input data)
    if not assignments:
        return []
    
    # Get date range from assignments
    dates = sorted(set(a.get('date') for a in assignments if a.get('date')))
    if not dates:
        return []
    
    from datetime import date as date_cls
    start_date = date_cls.fromisoformat(dates[0])
    end_date = date_cls.fromisoformat(dates[-1])
    
    # Build assignment lookup: emp_id -> date -> assignment
    assignment_by_emp_date = defaultdict(dict)
    for assignment in assignments:
        emp_id = assignment.get('employeeId')
        assign_date = assignment.get('date')
        if emp_id and assign_date:
            assignment_by_emp_date[emp_id][assign_date] = assignment
    
    # Get base rotation pattern from first demand (assuming single pattern for now)
    base_pattern = None
    pattern_start_date = None
    demands = input_data.get('demandItems', [])
    if demands and len(demands) > 0:
        reqs = demands[0].get('requirements', [])
        if reqs and len(reqs) > 0:
            base_pattern = reqs[0].get('workPattern', [])
        # Get pattern start date from shiftStartDate
        pattern_start_date = demands[0].get('shiftStartDate')
    
    # Convert pattern_start_date to date object if it exists
    pattern_start_date_obj = None
    if pattern_start_date:
        from datetime import date as date_cls
        pattern_start_date_obj = date_cls.fromisoformat(pattern_start_date)
    
    roster = []
    
    for emp in employees:
        emp_id = emp.get('employeeId')
        emp_offset = optimized_offsets.get(emp_id, emp.get('rotationOffset', 0))
        
        # Get employee's work pattern (rotated by their offset)
        emp_pattern = None
        if base_pattern:
            from context.engine.solver_engine import calculate_employee_work_pattern
            emp_pattern = calculate_employee_work_pattern(base_pattern, emp_offset)
        
        # Check if employee has any assignments
        has_assignments = emp_id in assignment_by_emp_date
        
        # Build daily status for each date
        daily_status = []
        current_date = start_date
        day_index = 0
        
        while current_date <= end_date:
            date_str = current_date.isoformat()
            
            # Calculate patternDay if we have pattern info
            pattern_day = None
            if base_pattern and pattern_start_date_obj:
                from context.engine.solver_engine import calculate_pattern_day
                pattern_day = calculate_pattern_day(
                    assignment_date=current_date,
                    pattern_start_date=pattern_start_date_obj,
                    employee_offset=emp_offset,
                    pattern_length=len(base_pattern)
                )
            
            # Check if employee has assignment on this date
            assignment = assignment_by_emp_date.get(emp_id, {}).get(date_str)
            
            if assignment:
                # Employee is ASSIGNED
                daily_status.append({
                    "date": date_str,
                    "status": "ASSIGNED",
                    "shiftCode": assignment.get('shiftCode'),
                    "patternDay": pattern_day,
                    "assignmentId": assignment.get('assignmentId'),
                    "startDateTime": assignment.get('startDateTime'),
                    "endDateTime": assignment.get('endDateTime')
                })
            else:
                # No assignment - determine why
                if not has_assignments:
                    # Employee has NO assignments at all (completely unused)
                    daily_status.append({
                        "date": date_str,
                        "status": "NOT_USED",
                        "shiftCode": None,
                        "reason": "Employee not used in this roster"
                    })
                elif emp_pattern:
                    # Check what employee's pattern says for this date
                    pattern_length = len(emp_pattern)
                    cycle_position = day_index % pattern_length
                    expected_shift = emp_pattern[cycle_position]
                    
                    if expected_shift == 'O':
                        # Pattern says off-day (legitimate rest)
                        daily_status.append({
                            "date": date_str,
                            "status": "OFF_DAY",
                            "shiftCode": "O",
                            "patternDay": pattern_day,
                            "reason": "Scheduled off-day per work pattern"
                        })
                    else:
                        # Pattern says work (D or N) but not assigned
                        daily_status.append({
                            "date": date_str,
                            "status": "UNASSIGNED",
                            "shiftCode": None,
                            "expectedShift": expected_shift,
                            "reason": f"Pattern indicates {expected_shift} shift but not assigned"
                        })
                else:
                    # Has some assignments but no pattern (edge case)
                    daily_status.append({
                        "date": date_str,
                        "status": "UNASSIGNED",
                        "shiftCode": None,
                        "reason": "No work pattern defined"
                    })
            
            current_date += timedelta(days=1)
            day_index += 1
        
        # Calculate totals for this employee
        total_assignments = len([d for d in daily_status if d['status'] == 'ASSIGNED'])
        total_off_days = len([d for d in daily_status if d['status'] == 'OFF_DAY'])
        total_unassigned = len([d for d in daily_status if d['status'] == 'UNASSIGNED'])
        
        roster.append({
            "employeeId": emp_id,
            "rotationOffset": emp_offset,
            "workPattern": emp_pattern,
            "totalDays": len(daily_status),
            "assignedDays": total_assignments,
            "offDays": total_off_days,
            "unassignedDays": total_unassigned,
            "dailyStatus": daily_status
        })
    
    return roster


def compute_input_hash(input_data):
    """Compute SHA256 hash of input JSON (excluding non-serializable runtime data)."""
    # Create a clean copy with only JSON-serializable data
    # Exclude keys that contain solver-internal objects
    exclude_keys = {
        'slots', 'x', 'model', 'timeLimit', 'unassigned', 
        'offset_vars', 'optimized_offsets', 'total_unassigned',
        'solver', 'cp_model', 'variables'
    }
    
    def clean_dict(obj):
        """Recursively clean dict to remove non-serializable objects."""
        if isinstance(obj, dict):
            return {k: clean_dict(v) for k, v in obj.items() if k not in exclude_keys}
        elif isinstance(obj, (list, tuple)):
            return [clean_dict(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            # Skip non-serializable objects (IntVar, Slot, etc.)
            return None
    
    try:
        clean_data = clean_dict(input_data)
        json_str = json.dumps(clean_data, sort_keys=True, default=str)
        return "sha256:" + hashlib.sha256(json_str.encode()).hexdigest()
    except Exception as e:
        # Fallback: use a simple hash of string representation
        return "sha256:" + hashlib.sha256(str(input_data).encode()).hexdigest()


def calculate_solution_quality(ctx, assignments, employee_roster, solver_status, input_data):
    """
    Calculate comprehensive solution quality metrics.
    
    Explains WHY the solution is FEASIBLE vs OPTIMAL and provides
    metrics for evaluating solution quality.
    
    Args:
        ctx: Context dict with slots, employees, constraints
        assignments: List of assignment dicts
        employee_roster: Employee roster with utilization data
        solver_status: Status from CP-SAT (OPTIMAL, FEASIBLE, INFEASIBLE)
        input_data: Original input JSON
    
    Returns:
        Dict with solution quality metrics and explanations
    """
    from collections import Counter
    
    slots = ctx.get('slots', [])
    employees = ctx.get('employees', [])
    
    # Count employees used
    employee_counts = Counter(a['employeeId'] for a in assignments)
    employees_used = len(employee_counts)
    employees_available = len(employees)
    
    # Calculate shift distribution
    if employee_counts:
        shifts_per_emp = list(employee_counts.values())
        min_shifts = min(shifts_per_emp)
        max_shifts = max(shifts_per_emp)
        avg_shifts = sum(shifts_per_emp) / len(shifts_per_emp)
        shift_variance = max_shifts - min_shifts
    else:
        min_shifts = max_shifts = avg_shifts = shift_variance = 0
    
    # Coverage rate
    total_slots = len(slots)
    assigned_slots = len(assignments)
    coverage_rate = (assigned_slots / total_slots * 100) if total_slots > 0 else 0
    
    # Employee utilization rate
    utilization_rate = (employees_used / employees_available * 100) if employees_available > 0 else 0
    
    # Workload balance quality (lower variance = better balance)
    if employees_used > 0:
        balance_quality = 100 - min(shift_variance / avg_shifts * 100 if avg_shifts > 0 else 100, 100)
    else:
        balance_quality = 0
    
    # Determine quality grade based on metrics
    if solver_status == "OPTIMAL":
        quality_grade = "OPTIMAL"
        quality_explanation = "CP-SAT solver proved this is the best possible solution within the constraint model."
    elif solver_status == "FEASIBLE":
        # Assess solution quality
        if coverage_rate == 100 and shift_variance <= 1 and utilization_rate <= 60:
            quality_grade = "EXCELLENT"
            quality_explanation = "Solution is FEASIBLE (not proven optimal by CP-SAT), but achieves 100% coverage with perfect workload balance (max 1 shift difference). This is effectively optimal for practical purposes."
        elif coverage_rate == 100 and shift_variance <= 2:
            quality_grade = "VERY_GOOD"
            quality_explanation = "Solution achieves 100% coverage with good workload balance. CP-SAT could not prove optimality within time limit, but solution quality is high."
        elif coverage_rate >= 95:
            quality_grade = "GOOD"
            quality_explanation = "Solution meets most demand with reasonable employee distribution. Time limit may have prevented finding a better solution."
        else:
            quality_grade = "ACCEPTABLE"
            quality_explanation = "Solution is feasible but may have room for improvement. Consider increasing solver time limit."
    elif solver_status == "INFEASIBLE":
        quality_grade = "INFEASIBLE"
        quality_explanation = "No valid solution exists that satisfies all hard constraints. Review constraints, employee availability, or demand requirements."
    else:
        quality_grade = "UNKNOWN"
        quality_explanation = f"Solver status: {solver_status}"
    
    # Optimization mode context
    opt_mode = input_data.get('solverConfig', {}).get('optimizationMode', 'balanceWorkload')
    fixed_offset = input_data.get('fixedRotationOffset', True)
    
    # Build quality metrics
    quality_metrics = {
        "qualityGrade": quality_grade,
        "solverStatus": solver_status,
        "solverStatusExplanation": get_solver_status_explanation(solver_status),
        "qualityExplanation": quality_explanation,
        
        "coverageMetrics": {
            "totalSlots": total_slots,
            "assignedSlots": assigned_slots,
            "unassignedSlots": total_slots - assigned_slots,
            "coverageRate": round(coverage_rate, 1),
            "coverageQuality": "COMPLETE" if coverage_rate == 100 else "PARTIAL"
        },
        
        "employeeUtilization": {
            "totalEmployeesAvailable": employees_available,
            "employeesUsed": employees_used,
            "employeesUnused": employees_available - employees_used,
            "utilizationRate": round(utilization_rate, 1),
            "underUtilizationIssues": check_under_utilization(employee_counts)
        },
        
        "workloadBalance": {
            "minShiftsPerEmployee": min_shifts,
            "maxShiftsPerEmployee": max_shifts,
            "avgShiftsPerEmployee": round(avg_shifts, 1),
            "shiftVariance": shift_variance,
            "balanceQuality": round(balance_quality, 1),
            "balanceGrade": get_balance_grade(shift_variance, avg_shifts)
        },
        
        "optimizationContext": {
            "optimizationMode": opt_mode,
            "fixedRotationOffset": fixed_offset,
            "patternBased": check_if_pattern_based(input_data),
            "continuousAdherence": check_continuous_adherence(employee_counts, avg_shifts)
        }
    }
    
    return quality_metrics


def get_solver_status_explanation(status):
    """Explain what each solver status means."""
    explanations = {
        "OPTIMAL": "CP-SAT proved this is the best possible solution. The solver exhaustively searched the solution space and mathematically verified no better solution exists.",
        "FEASIBLE": "CP-SAT found a valid solution but could not prove it's the absolute best within the time limit. The solution satisfies all hard constraints, and further solving might find marginal improvements.",
        "INFEASIBLE": "No solution exists that satisfies all hard constraints. This means the problem is over-constrained (too many restrictions) or under-resourced (not enough employees/capacity).",
        "MODEL_INVALID": "The constraint model has logical errors or conflicts. Check constraint definitions and input data validity.",
        "UNKNOWN": "Solver status could not be determined. This is unexpected and may indicate a solver error."
    }
    return explanations.get(status, f"Unknown status: {status}")


def check_under_utilization(employee_counts):
    """Check if any employees are significantly under-utilized."""
    if not employee_counts:
        return []
    
    counts = list(employee_counts.values())
    avg = sum(counts) / len(counts)
    issues = []
    
    # Check for employees with very few shifts
    low_shift_employees = [emp_id for emp_id, count in employee_counts.items() if count < avg * 0.5 and count < 10]
    if low_shift_employees:
        issues.append({
            "issue": "LOW_UTILIZATION",
            "description": f"{len(low_shift_employees)} employees have significantly fewer shifts than average",
            "affectedEmployees": low_shift_employees[:5],  # Show first 5
            "recommendation": "Consider using 'balanceWorkload' optimization mode or review employee constraints"
        })
    
    return issues


def get_balance_grade(variance, avg):
    """Grade workload balance quality."""
    if avg == 0:
        return "N/A"
    
    relative_variance = variance / avg if avg > 0 else 0
    
    if variance == 0:
        return "PERFECT"
    elif variance == 1:
        return "EXCELLENT"
    elif variance <= 2:
        return "VERY_GOOD"
    elif relative_variance < 0.15:
        return "GOOD"
    elif relative_variance < 0.25:
        return "ACCEPTABLE"
    else:
        return "POOR"


def check_if_pattern_based(input_data):
    """Check if the problem uses work patterns (rotation-based scheduling)."""
    demands = input_data.get('demandItems', [])
    for demand in demands:
        for req in demand.get('requirements', []):
            if req.get('workPattern'):
                return True
        for shift in demand.get('shifts', []):
            if shift.get('rotationSequence'):
                return True
    return False


def check_continuous_adherence(employee_counts, avg_shifts):
    """
    Check if continuous adherence is being followed.
    
    Continuous adherence means: IF an employee is selected, THEN they work
    all days in their pattern cycle (typically 20-21 shifts/month for 6-day patterns).
    
    Returns True if employees are working full patterns (~20+ shifts).
    """
    if not employee_counts or avg_shifts == 0:
        return False
    
    # For a 6-day pattern (D-D-N-N-O-O) over 30 days, expect ~20 shifts
    # If avg is around 20, continuous adherence is likely being followed
    return avg_shifts >= 18  # Allow some tolerance


def build_output(input_data, ctx, status, solver_result, assignments, violations):
    """
    Build output in expected schema format (v0.43+).
    
    This function is shared between CLI (run_solver.py) and API (api_server.py)
    to ensure identical output format and behavior.
    
    Args:
        input_data: Original input JSON (dict)
        ctx: Context dict with planning data (including slots, constraints, etc.)
        status: String status from solver (OPTIMAL, FEASIBLE, INFEASIBLE, etc.)
        solver_result: Dict with solver metadata (start_timestamp, end_timestamp, duration_seconds, status)
        assignments: List of assignment dicts from solver
        violations: List of violation dicts from scoring
    
    Returns:
        Dict in output schema format with all fields populated
    """
    
    # Compute input hash for reproducibility tracking (use input_data, not ctx which has IntVars)
    input_hash = compute_input_hash(input_data)
    
    # Extract scores from solver_result
    scores = solver_result.get('scores', {'hard': 0, 'soft': 0, 'overall': 0})
    score_breakdown = solver_result.get('scoreBreakdown', {
        'hard': {'violations': []},
        'soft': {}
    })
    
    # ========== ANNOTATE ASSIGNMENTS WITH HOUR BREAKDOWN ==========
    annotated_assignments = []
    employee_weekly_normal = defaultdict(float)  # emp_id:week -> hours
    employee_monthly_ot = defaultdict(float)     # emp_id:month -> hours
    
    # Build employee lookup dictionary for scheme information
    employee_dict = {emp['employeeId']: emp for emp in ctx.get('employees', [])}
    
    for assignment in assignments:
        try:
            start_dt = datetime.fromisoformat(assignment.get('startDateTime'))
            end_dt = datetime.fromisoformat(assignment.get('endDateTime'))
            emp_id = assignment.get('employeeId')
            assignment_date = assignment.get('date')
            
            # Get date object for MOM calculations
            date_obj = datetime.fromisoformat(assignment_date).date()
            
            # Get employee scheme for scheme-aware hour calculations
            employee = employee_dict.get(emp_id, {})
            emp_scheme_raw = employee.get('scheme', 'A')  # Default to Scheme A if not found
            # Normalize scheme to handle both 'P' and 'Scheme P' formats
            from context.engine.time_utils import normalize_scheme
            emp_scheme = normalize_scheme(emp_scheme_raw)
            
            # Check if employee is APGD-D10 (requires matching requirement)
            is_apgd = False
            product = employee.get('productTypeId', '')
            for demand in input_data.get('demandItems', []):
                for req in demand.get('requirements', []):
                    if req.get('productTypeId', '') == product:
                        if is_apgd_d10_employee(employee, req):
                            is_apgd = True
                            break
                if is_apgd:
                    break
            
            # Calculate hour breakdown (APGD-D10 or standard)
            if is_apgd:
                hours_dict = calculate_apgd_d10_hours(
                    start_dt=start_dt,
                    end_dt=end_dt,
                    employee_id=emp_id,
                    assignment_date_obj=date_obj,
                    all_assignments=assignments,
                    employee_dict=employee
                )
            else:
                hours_dict = calculate_mom_compliant_hours(
                    start_dt=start_dt,
                    end_dt=end_dt,
                    employee_id=emp_id,
                    assignment_date_obj=date_obj,
                    all_assignments=assignments,
                    employee_scheme=emp_scheme
                )
            
            # Add hour breakdown to assignment (including restDayPay)
            assignment['hours'] = {
                'gross': hours_dict['gross'],
                'lunch': hours_dict['lunch'],
                'normal': hours_dict['normal'],
                'ot': hours_dict['ot'],
                'restDayPay': hours_dict['restDayPay'],
                'paid': hours_dict['paid']
            }
            
            # Week calculation: ISO week (Mon-Sun)
            try:
                iso_year, iso_week, _ = date_obj.isocalendar()
                week_key = f"{iso_year}-W{iso_week:02d}"
                month_key = f"{iso_year}-{date_obj.month:02d}"
                
                # Accumulate normal hours for week
                employee_weekly_normal[f"{emp_id}:{week_key}"] += hours_dict['normal']
                
                # Accumulate OT hours for month
                employee_monthly_ot[f"{emp_id}:{month_key}"] += hours_dict['ot']
            except Exception:
                pass  # Skip if date parsing fails
            
        except Exception as e:
            # If hour calculation fails, annotate with error but continue
            assignment['hours'] = {
                'gross': 0, 'lunch': 0, 'normal': 0, 'ot': 0, 'paid': 0,
                'error': str(e)
            }
        
        annotated_assignments.append(assignment)
    
    # ========== BUILD EMPLOYEE HOURS SUMMARY ==========
    employee_hours_summary = {}
    
    for key, total in employee_weekly_normal.items():
        emp_id, week_key = key.split(':')
        if emp_id not in employee_hours_summary:
            employee_hours_summary[emp_id] = {
                'weekly_normal': {},
                'monthly_ot': {}
            }
        employee_hours_summary[emp_id]['weekly_normal'][week_key] = round(total, 2)
    
    for key, total in employee_monthly_ot.items():
        emp_id, month_key = key.split(':')
        if emp_id not in employee_hours_summary:
            employee_hours_summary[emp_id] = {
                'weekly_normal': {},
                'monthly_ot': {}
            }
        employee_hours_summary[emp_id]['monthly_ot'][month_key] = round(total, 2)
    
    # ========== BUILD OUTPUT ==========
    # Build employee roster with daily status for ALL employees
    employee_roster = build_employee_roster(input_data, ctx, annotated_assignments)
    
    # ========== CALCULATE ROSTER SUMMARY ==========
    roster_summary = {
        "totalDailyStatuses": 0,
        "byStatus": {
            "ASSIGNED": 0,
            "OFF_DAY": 0,
            "UNASSIGNED": 0,
            "NOT_USED": 0
        }
    }
    
    for emp_roster in employee_roster:
        for day in emp_roster.get('dailyStatus', []):
            roster_summary["totalDailyStatuses"] += 1
            status_type = day.get('status', 'UNKNOWN')
            if status_type in roster_summary["byStatus"]:
                roster_summary["byStatus"][status_type] += 1
    
    # ========== CALCULATE SOLUTION QUALITY METRICS ==========
    solution_quality = calculate_solution_quality(
        ctx, 
        annotated_assignments, 
        employee_roster, 
        solver_result.get("status", status),
        input_data
    )
    
    # Extract ICPMP preprocessing metadata if available
    icpmp_preprocessing = ctx.get('icpmp_preprocessing', None)
    publicHolidays = input_data.get('publicHolidays', [])
    
    output = {
        "schemaVersion": "0.95",
        "planningReference": ctx.get("planningReference", "UNKNOWN"),
        "publicHolidays": publicHolidays,
        "solverRun": {
            "runId": "SRN-local-0.4",
            "solverVersion": "optSolve-py-0.95.0",
            "startedAt": solver_result.get("start_timestamp", ""),
            "ended": solver_result.get("end_timestamp", ""),
            "durationSeconds": solver_result.get("duration_seconds", 0),
            "status": solver_result.get("status", status)
        },
        "score": {
            "overall": scores.get('overall', 0),
            "hard": scores.get('hard', 0),
            "soft": scores.get('soft', 0)
        },
        "scoreBreakdown": score_breakdown,
        "assignments": annotated_assignments,
        "employeeRoster": employee_roster,  # NEW: Complete employee roster with daily status
        "rosterSummary": roster_summary,  # NEW: Summary of roster statuses
        "solutionQuality": solution_quality,  # NEW: Solution quality metrics and explanations
        "unmetDemand": [],
        "meta": {
            "inputHash": input_hash,
            "generatedAt": datetime.now().isoformat(),
            "employeeHours": employee_hours_summary
        }
    }
    
    # Add ICPMP preprocessing data if available (for transparency and debugging)
    if icpmp_preprocessing:
        output["icpmpPreprocessing"] = icpmp_preprocessing
    
    return output


def build_incremental_output(
    input_data,
    ctx,
    status,
    solver_result,
    new_assignments,
    violations,
    locked_assignments,
    incremental_ctx
):
    """
    Build output for incremental solve (v0.80).
    
    Merges locked assignments (from previous solve) with new assignments (from this solve).
    Adds audit trail to each assignment.
    
    Args:
        input_data: Original incremental request data
        ctx: Context dict
        status: Solver status
        solver_result: Solver metadata
        new_assignments: List of newly assigned slots
        violations: Violations list
        locked_assignments: List of locked assignments from previous output
        incremental_ctx: Incremental context with temporal window, employee changes
    
    Returns:
        Dict in output schema format with incremental metadata
    """
    
    # Generate run ID
    run_id = f"incr-{int(datetime.now().timestamp())}"
    current_timestamp = datetime.now().isoformat()
    
    # Compute input hash
    input_hash = compute_input_hash(input_data)
    
    # Annotate locked assignments with audit trail
    annotated_locked = []
    for assignment in locked_assignments:
        audit_info = {
            "solverRunId": assignment.get('solverRun', {}).get('runId', 'unknown'),
            "source": "locked",
            "timestamp": assignment.get('lockedAt', current_timestamp),
            "inputHash": assignment.get('inputHash', ''),
            "previousJobId": None  # Can be enhanced to track job IDs
        }
        annotated_locked.append({
            **assignment,
            "auditInfo": audit_info
        })
    
    # Annotate new assignments with hour breakdown and audit trail
    annotated_new = []
    employee_weekly_normal = defaultdict(float)
    employee_monthly_ot = defaultdict(float)
    
    # Build employee lookup dictionary for scheme information
    employee_dict = {emp['employeeId']: emp for emp in ctx.get('employees', [])}
    
    # Combine locked and new for MOM context analysis
    all_assignments_for_context = locked_assignments + new_assignments
    
    for assignment in new_assignments:
        try:
            start_dt = datetime.fromisoformat(assignment.get('startDateTime'))
            end_dt = datetime.fromisoformat(assignment.get('endDateTime'))
            emp_id = assignment.get('employeeId')
            assignment_date = assignment.get('date')
            
            # Get date object for MOM calculations
            date_obj = datetime.fromisoformat(assignment_date).date()
            
            # Get employee scheme for scheme-aware hour calculations
            employee = employee_dict.get(emp_id, {})
            emp_scheme_raw = employee.get('scheme', 'A')  # Default to Scheme A if not found
            # Normalize scheme to handle both 'P' and 'Scheme P' formats
            from context.engine.time_utils import normalize_scheme
            emp_scheme = normalize_scheme(emp_scheme_raw)
            
            # Check if employee is APGD-D10 (requires matching requirement)
            is_apgd = False
            product = employee.get('productTypeId', '')
            for demand in input_data.get('demandItems', []):
                for req in demand.get('requirements', []):
                    if req.get('productTypeId', '') == product:
                        if is_apgd_d10_employee(employee, req):
                            is_apgd = True
                            break
                if is_apgd:
                    break
            
            # Calculate hour breakdown (APGD-D10 or standard)
            if is_apgd:
                hours_dict = calculate_apgd_d10_hours(
                    start_dt=start_dt,
                    end_dt=end_dt,
                    employee_id=emp_id,
                    assignment_date_obj=date_obj,
                    all_assignments=all_assignments_for_context,
                    employee_dict=employee
                )
            else:
                hours_dict = calculate_mom_compliant_hours(
                    start_dt=start_dt,
                    end_dt=end_dt,
                    employee_id=emp_id,
                    assignment_date_obj=date_obj,
                    all_assignments=all_assignments_for_context,
                    employee_scheme=emp_scheme
                )
            
            # Add audit trail
            audit_info = {
                "solverRunId": run_id,
                "source": "incremental",
                "timestamp": current_timestamp,
                "inputHash": input_hash,
                "previousJobId": None
            }
            
            # Add hour breakdown + audit to assignment (including restDayPay)
            enriched_assignment = {
                **assignment,
                'hours': {
                    'gross': hours_dict['gross'],
                    'lunch': hours_dict['lunch'],
                    'normal': hours_dict['normal'],
                    'ot': hours_dict['ot'],
                    'restDayPay': hours_dict['restDayPay'],
                    'paid': hours_dict['paid']
                },
                "auditInfo": audit_info
            }
            
            annotated_new.append(enriched_assignment)
            
            # Accumulate hours
            emp_id = assignment.get('employeeId')
            assignment_date = assignment.get('date')
            
            if emp_id and assignment_date:
                dt_obj = datetime.fromisoformat(assignment_date)
                iso_year, iso_week, _ = dt_obj.isocalendar()
                week_key = f"{iso_year}-W{iso_week:02d}"
                month_key = f"{dt_obj.year}-{dt_obj.month:02d}"
                
                employee_weekly_normal[(emp_id, week_key)] += hours_dict['normal']
                employee_monthly_ot[(emp_id, month_key)] += hours_dict['ot']
        
        except Exception as e:
            # If hour calc fails, include assignment without hours
            annotated_new.append(assignment)
    
    # Merge locked + new assignments (sort by date)
    all_assignments = annotated_locked + annotated_new
    all_assignments_sorted = sorted(all_assignments, key=lambda a: a.get('date', ''))
    
    # Build employee hours summary
    employee_hours_summary = {}
    for (emp_id, week_key), hours in employee_weekly_normal.items():
        if emp_id not in employee_hours_summary:
            employee_hours_summary[emp_id] = {'weekly_normal': {}, 'monthly_ot': {}}
        employee_hours_summary[emp_id]['weekly_normal'][week_key] = round(hours, 2)
    
    for (emp_id, month_key), hours in employee_monthly_ot.items():
        if emp_id not in employee_hours_summary:
            employee_hours_summary[emp_id] = {'weekly_normal': {}, 'monthly_ot': {}}
        employee_hours_summary[emp_id]['monthly_ot'][month_key] = round(hours, 2)
    
    # Extract scores
    scores = solver_result.get('scores', {'hard': 0, 'soft': 0, 'overall': 0})
    score_breakdown = solver_result.get('scoreBreakdown', {'hard': {'violations': []}, 'soft': {}})
    
    # Build output
    output = {
        "schemaVersion": "0.95",
        "planningReference": input_data.get("planningReference", "UNKNOWN"),
        "solverRun": {
            "runId": run_id,
            "solverVersion": "optSolve-py-0.95.0",
            "startedAt": solver_result.get("start_timestamp", current_timestamp),
            "ended": solver_result.get("end_timestamp", current_timestamp),
            "durationSeconds": solver_result.get("duration_seconds", 0),
            "status": solver_result.get("status", status)
        },
        "score": {
            "overall": scores.get('overall', 0),
            "hard": scores.get('hard', 0),
            "soft": scores.get('soft', 0)
        },
        "scoreBreakdown": score_breakdown,
        "assignments": all_assignments_sorted,
        "unmetDemand": [],
        "incrementalSolve": {
            "cutoffDate": incremental_ctx['temporalWindow']['cutoffDate'],
            "solveFromDate": incremental_ctx['temporalWindow']['solveFromDate'],
            "solveToDate": incremental_ctx['temporalWindow']['solveToDate'],
            "lockedAssignmentsCount": len(annotated_locked),
            "newAssignmentsCount": len(annotated_new),
            "solvableSlots": len(annotated_new),  # Total slots in solve window (not just freed slots)
            "unassignedSlots": len([a for a in annotated_new if a.get('status') == 'UNASSIGNED'])
        },
        "meta": {
            "inputHash": input_hash,
            "generatedAt": current_timestamp,
            "employeeHours": employee_hours_summary
        }
    }
    
    return output
