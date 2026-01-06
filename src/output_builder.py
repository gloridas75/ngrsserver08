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


def build_employee_roster(input_data, ctx, assignments, off_day_assignments=None):
    """
    Build a comprehensive employee roster showing daily status for ALL employees.
    
    Args:
        input_data: Original input JSON
        ctx: Context dict with employees and patterns
        assignments: Work assignments ONLY (D, N shifts)
        off_day_assignments: Optional list of OFF day records (shiftCode='O', status='OFF_DAY')
    
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
    
    # Merge work assignments and OFF days for complete roster view
    # But remember: only work assignments go in output's assignments array
    all_assignments_for_roster = assignments.copy()
    if off_day_assignments:
        all_assignments_for_roster.extend(off_day_assignments)
    
    # Get date range from assignments (filter out None values explicitly)
    date_values = set(a.get('date') for a in all_assignments_for_roster if a.get('date') is not None)
    dates = sorted(date_values)
    if not dates:
        return []
    
    from datetime import date as date_cls, datetime
    # Handle both ISO date strings and datetime strings
    def parse_date_string(date_str):
        if 'T' in date_str:
            return datetime.fromisoformat(date_str).date()
        return date_cls.fromisoformat(date_str)
    
    start_date = parse_date_string(dates[0])
    end_date = parse_date_string(dates[-1])
    
    # Build assignment lookup: emp_id -> date -> assignment
    assignment_by_emp_date = defaultdict(dict)
    for assignment in all_assignments_for_roster:
        emp_id = assignment.get('employeeId')
        assign_date = assignment.get('date')
        if emp_id and assign_date:
            assignment_by_emp_date[emp_id][assign_date] = assignment
    
    # Get base rotation pattern from first demand (assuming single pattern for now)
    base_pattern = None
    pattern_start_date = None
    coverage_days = None
    demands = input_data.get('demandItems', [])
    if demands and len(demands) > 0:
        reqs = demands[0].get('requirements', [])
        if reqs and len(reqs) > 0:
            base_pattern = reqs[0].get('workPattern', [])
            coverage_days = reqs[0].get('coverageDays', None)
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
                # NOTE: We pass employee_offset=0 because emp_pattern is already rotated
                # calculate_pattern_day returns the index into the pattern
                pattern_day = calculate_pattern_day(
                    assignment_date=current_date,
                    pattern_start_date=pattern_start_date_obj,
                    employee_offset=0,  # Pattern is already rotated by emp_offset
                    pattern_length=len(base_pattern),
                    coverage_days=coverage_days
                )
            
            # Check if employee has assignment on this date
            assignment = assignment_by_emp_date.get(emp_id, {}).get(date_str)
            
            # PRIORITY 1: Check pattern first to determine if this is an OFF day
            # This ensures OFF days are marked correctly even if solver assigned work due to flexibility
            expected_shift_from_pattern = None
            if emp_pattern and pattern_day is not None:
                expected_shift_from_pattern = emp_pattern[pattern_day]
            
            if expected_shift_from_pattern == 'O' and not (assignment and assignment.get('shiftCode') in ['D', 'N']):
                # Pattern says OFF day and no actual work assignment - mark as OFF_DAY
                # Use OFF_DAY assignment data if it exists, otherwise create minimal entry
                if assignment and assignment.get('status') == 'OFF_DAY':
                    daily_status.append({
                        "date": date_str,
                        "status": "OFF_DAY",
                        "shiftCode": "O",
                        "patternDay": assignment.get('patternDay', pattern_day),
                        "assignmentId": assignment.get('assignmentId'),
                        "startDateTime": assignment.get('startDateTime'),
                        "endDateTime": assignment.get('endDateTime')
                    })
                else:
                    # Pattern says OFF but no OFF assignment generated - create default entry
                    daily_status.append({
                        "date": date_str,
                        "status": "OFF_DAY",
                        "shiftCode": "O",
                        "patternDay": pattern_day,
                        "reason": "Scheduled off-day per work pattern"
                    })
            elif assignment and assignment.get('shiftCode') in ['D', 'N']:
                # Employee has actual work assignment (D or N shift)
                daily_status.append({
                    "date": date_str,
                    "status": "ASSIGNED",
                    "shiftCode": assignment.get('shiftCode'),
                    "patternDay": pattern_day,
                    "assignmentId": assignment.get('assignmentId'),
                    "startDateTime": assignment.get('startDateTime'),
                    "endDateTime": assignment.get('endDateTime')
                })
            elif assignment and assignment.get('status') == 'OFF_DAY':
                # Has OFF_DAY assignment (backup case if pattern check didn't catch it)
                daily_status.append({
                    "date": date_str,
                    "status": "OFF_DAY",
                    "shiftCode": "O",
                    "patternDay": assignment.get('patternDay', pattern_day),
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
                elif emp_pattern and pattern_day is not None:
                    # Pattern says work (D or N) but not assigned
                    daily_status.append({
                        "date": date_str,
                        "status": "UNASSIGNED",
                        "shiftCode": None,
                        "expectedShift": expected_shift_from_pattern,
                        "reason": f"Pattern indicates {expected_shift_from_pattern} shift but not assigned"
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
        
        # Calculate hour totals from actual assignments
        total_normal_hours = 0.0
        total_ot_hours = 0.0
        total_hours = 0.0
        
        for date_str, assignment in assignment_by_emp_date.get(emp_id, {}).items():
            if assignment.get('status') == 'ASSIGNED':
                hours = assignment.get('hours', {})
                total_normal_hours += hours.get('normal', 0.0)
                total_ot_hours += hours.get('ot', 0.0)
                total_hours += hours.get('paid', 0.0)
        
        roster.append({
            "employeeId": emp_id,
            "rankId": emp.get('rankId'),  # FIX: Include employee rank
            "productTypeId": emp.get('productTypeId'),  # FIX: Include product type
            "ouId": emp.get('ouId'),  # FIX: Include OU
            "scheme": emp.get('scheme'),  # FIX: Include scheme
            "rotationOffset": emp_offset,
            "workPattern": emp_pattern,
            "totalDays": len(daily_status),
            "workDays": total_assignments,  # FIX: Add workDays (same as assignedDays)
            "offDays": total_off_days,
            "normalHours": round(total_normal_hours, 1),  # FIX: Add hour totals
            "otHours": round(total_ot_hours, 1),
            "totalHours": round(total_hours, 1),
            "assignedDays": total_assignments,
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
    
    # Count employees used (exclude None for UNASSIGNED slots)
    employee_counts = Counter(a['employeeId'] for a in assignments if a.get('employeeId') is not None)
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


def insert_off_day_assignments(assignments, input_data, ctx):
    """
    Insert explicit OFF day assignments for employees based on their work patterns.
    
    For demandBased rosters, employees have rotation patterns (e.g., DDNNOO).
    This function adds assignment records with shiftCode="O" for days when
    employees are on their scheduled rest days.
    
    Args:
        assignments: List of actual shift assignments (D, N shifts)
        input_data: Original input JSON
        ctx: Context dict with employees and their patterns
    
    Returns:
        Expanded assignments list including both work shifts and OFF days
    """
    from datetime import datetime, timedelta
    import uuid
    
    # Get date range from existing assignments (filter out None values explicitly)
    date_values = set(a.get('date') for a in assignments if a.get('date') is not None)
    dates = sorted(date_values)
    if not dates:
        return assignments
    
    start_date_str = dates[0]
    end_date_str = dates[-1]
    start_date = datetime.fromisoformat(start_date_str.split('T')[0]).date()
    end_date = datetime.fromisoformat(end_date_str.split('T')[0]).date()
    
    # Build lookup: emp_id -> date -> assignment
    assignments_by_emp_date = defaultdict(dict)
    for assignment in assignments:
        emp_id = assignment.get('employeeId')
        assign_date = assignment.get('date')
        if emp_id and assign_date:
            assignments_by_emp_date[emp_id][assign_date] = assignment
    
    # Get employees with work patterns
    employees = ctx.get('employees', [])
    optimized_offsets = ctx.get('optimized_offsets', {})
    
    # Get base rotation pattern and start date from first requirement
    base_pattern = None
    pattern_start_date = None
    coverage_days = None
    demands = input_data.get('demandItems', [])
    if demands and len(demands) > 0:
        reqs = demands[0].get('requirements', [])
        if reqs and len(reqs) > 0:
            base_pattern = reqs[0].get('workPattern', [])
            coverage_days = reqs[0].get('coverageDays', None)
        pattern_start_date = demands[0].get('shiftStartDate')
    
    if not base_pattern or not pattern_start_date:
        # No pattern info - can't insert OFF days
        return assignments
    
    pattern_start_date_obj = datetime.fromisoformat(pattern_start_date).date()
    pattern_length = len(base_pattern)
    
    # Generate OFF day assignments for each employee
    off_day_assignments = []
    
    for emp in employees:
        emp_id = emp.get('employeeId')
        emp_offset = optimized_offsets.get(emp_id, emp.get('rotationOffset', 0))
        
        # Generate OFF days for ALL employees (even if they have no work assignments)
        # This ensures pattern-based OFF days are always shown in employeeRoster
        
        # Calculate employee's rotated pattern
        from context.engine.solver_engine import calculate_employee_work_pattern
        emp_pattern = calculate_employee_work_pattern(base_pattern, emp_offset)
        
        # Iterate through date range and add OFF days
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.isoformat()
            
            # Skip if employee already has assignment on this date
            if date_str in assignments_by_emp_date[emp_id]:
                current_date += timedelta(days=1)
                continue
            
            # Calculate what shift code employee should have based on pattern
            from context.engine.solver_engine import calculate_pattern_day
            # NOTE: We pass employee_offset=0 because emp_pattern is already rotated
            pattern_day = calculate_pattern_day(
                assignment_date=current_date,
                pattern_start_date=pattern_start_date_obj,
                employee_offset=0,  # Pattern is already rotated by emp_offset
                pattern_length=pattern_length,
                coverage_days=coverage_days
            )
            
            expected_shift = emp_pattern[pattern_day]
            
            # Only add OFF day assignment if pattern says "O"
            if expected_shift == 'O':
                # Get demand/requirement info from one of employee's actual assignments (if any)
                emp_assignments_dict = assignments_by_emp_date.get(emp_id, {})
                sample_assignment = next(iter(emp_assignments_dict.values()), None) if emp_assignments_dict else None
                
                # Determine shift times for OFF day
                if sample_assignment:
                    # Determine typical shift times for this employee
                    # Use the employee's most common shift time pattern
                    emp_assignments = list(assignments_by_emp_date[emp_id].values())
                    
                    # Find most common shift type (D or N) for this employee
                    shift_types = [a.get('shiftCode') for a in emp_assignments if a.get('shiftCode') in ['D', 'N']]
                    if shift_types:
                        from collections import Counter
                        most_common_shift = Counter(shift_types).most_common(1)[0][0]
                        
                        # Get a sample assignment of that shift type
                        sample_shift = next((a for a in emp_assignments if a.get('shiftCode') == most_common_shift), None)
                        if sample_shift:
                            # Extract time portion from sample shift
                            sample_start = sample_shift.get('startDateTime', f"{date_str}T00:00:00")
                            sample_end = sample_shift.get('endDateTime', f"{date_str}T00:00:00")
                            
                            # Use the same time pattern but for the OFF day date
                            start_time = sample_start[11:] if len(sample_start) > 10 else "00:00:00"
                            end_time = sample_end[11:] if len(sample_end) > 10 else "00:00:00"
                            
                            # For OFF days, use the day's date + typical shift start time
                            off_start = f"{date_str}T{start_time}"
                            # Handle next-day end times (e.g., night shifts)
                            if end_time < start_time:  # Cross-midnight shift
                                next_date = (current_date + timedelta(days=1)).isoformat()
                                off_end = f"{next_date}T{end_time}"
                            else:
                                off_end = f"{date_str}T{end_time}"
                        else:
                            off_start = f"{date_str}T08:00:00"
                            off_end = f"{date_str}T20:00:00"
                    else:
                        # Default to day shift times if no pattern found
                        off_start = f"{date_str}T08:00:00"
                        off_end = f"{date_str}T20:00:00"
                else:
                    # Employee has no assignments - use default times and demand info
                    off_start = f"{date_str}T08:00:00"
                    off_end = f"{date_str}T20:00:00"
                
                # Create OFF_DAY assignment (with sample assignment data if available)
                off_assignment = {
                    "assignmentId": f"OFF-{emp_id}-{date_str}-{uuid.uuid4().hex[:6]}",
                    "demandId": sample_assignment.get('demandId', 'N/A') if sample_assignment else 'N/A',
                    "requirementId": sample_assignment.get('requirementId', 'N/A') if sample_assignment else 'N/A',
                    "slotId": f"OFF-{emp_id}-{date_str}",
                    "employeeId": emp_id,
                    "date": date_str,
                    "startDateTime": off_start,
                    "endDateTime": off_end,
                    "shiftCode": "O",
                    "patternDay": pattern_day,
                    "newRotationOffset": emp_offset,
                    "status": "OFF_DAY",
                    "hours": {
                        "gross": 0,
                        "lunch": 0,
                        "normal": 0,
                        "ot": 0,
                        "restDayPay": 0,
                        "paid": 0
                    }
                }
                off_day_assignments.append(off_assignment)
            
            current_date += timedelta(days=1)
    
    # Merge and sort by date, then employee (handle None values safely)
    all_assignments = assignments + off_day_assignments
    all_assignments_sorted = sorted(
        all_assignments,
        key=lambda a: (a.get('date') or '', a.get('employeeId') or '')
    )
    
    return all_assignments_sorted


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
    
    # ========== HANDLE OFF DAY ASSIGNMENTS (for demandBased rosters) ==========
    # Generate OFF day records but keep them separate from assignments array
    # OFF days should ONLY appear in employeeRoster.dailyStatus, NOT in assignments
    rostering_basis = input_data.get('demandItems', [{}])[0].get('rosteringBasis', 'demandBased')
    
    # Store OFF day assignments separately for employeeRoster only (not in assignments array)
    off_day_assignments_for_roster = []
    if rostering_basis == 'demandBased':
        all_with_off = insert_off_day_assignments(assignments, input_data, ctx)
        # Separate actual work assignments from OFF days
        off_day_assignments_for_roster = [a for a in all_with_off if a.get('status') == 'OFF_DAY']
        # Keep only work assignments in main assignments array
        assignments = [a for a in all_with_off if a.get('status') != 'OFF_DAY']
    
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
            # Check for OFF days (no work, no time calculation needed)
            if assignment.get('status') == 'OFF' or assignment.get('shiftCode') == 'O':
                # OFF day - keep zero hours as-is
                if 'hours' not in assignment:
                    assignment['hours'] = {
                        'gross': 0.0, 'lunch': 0.0, 'normal': 0.0, 
                        'ot': 0.0, 'restDayPay': 0.0, 'paid': 0.0
                    }
                annotated_assignments.append(assignment)
                continue
            
            start_dt = datetime.fromisoformat(assignment.get('startDateTime'))
            end_dt = datetime.fromisoformat(assignment.get('endDateTime'))
            emp_id = assignment.get('employeeId')
            assignment_date = assignment.get('date')
            
            # Get date object for MOM calculations
            date_obj = datetime.fromisoformat(assignment_date).date()
            
            # Check if assignment already has hours (template-based roster)
            # Skip recalculation if hours already exist with valid normal hours
            if 'hours' in assignment and isinstance(assignment['hours'], dict) and assignment['hours'].get('normal') is not None:
                # Use pre-calculated hours from template roster
                hours_dict = assignment['hours']
            else:
                # Calculate hours using MOM compliance logic
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
                    # For Scheme P, need to pass pattern work days count
                    pattern_work_days = None
                    if emp_scheme == 'P':
                        # Get employee's work pattern and count work days
                        emp_pattern = employee.get('workPattern', [])
                        if emp_pattern:
                            # Count non-'O' days in pattern
                            pattern_work_days = len([d for d in emp_pattern if d != 'O'])
                    
                    hours_dict = calculate_mom_compliant_hours(
                        start_dt=start_dt,
                        end_dt=end_dt,
                        employee_id=emp_id,
                        assignment_date_obj=date_obj,
                        all_assignments=assignments,
                        employee_scheme=emp_scheme,
                        pattern_work_days=pattern_work_days
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
    # Pass OFF day assignments separately - they appear in employeeRoster but NOT in assignments array
    employee_roster = build_employee_roster(input_data, ctx, annotated_assignments, off_day_assignments_for_roster)
    
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
                # For Scheme P, need to pass pattern work days count
                pattern_work_days = None
                if emp_scheme == 'P':
                    # Get employee's work pattern and count work days
                    emp_pattern = employee.get('workPattern', [])
                    if emp_pattern:
                        # Count non-'O' days in pattern
                        pattern_work_days = len([d for d in emp_pattern if d != 'O'])
                
                hours_dict = calculate_mom_compliant_hours(
                    start_dt=start_dt,
                    end_dt=end_dt,
                    employee_id=emp_id,
                    assignment_date_obj=date_obj,
                    all_assignments=all_assignments_for_context,
                    employee_scheme=emp_scheme,
                    pattern_work_days=pattern_work_days
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
    
    # Merge locked + new assignments (sort by date, handling None values safely)
    all_assignments = annotated_locked + annotated_new
    all_assignments_sorted = sorted(all_assignments, key=lambda a: a.get('date') or '')
    
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
