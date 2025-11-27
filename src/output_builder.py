"""
Shared output builder used by both CLI and API.

Refactored from run_solver.py to ensure CLI and API produce identical output.
"""

import json
import hashlib
from datetime import datetime
from collections import defaultdict
from context.engine.time_utils import split_shift_hours


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
    
    for assignment in assignments:
        try:
            start_dt = datetime.fromisoformat(assignment.get('startDateTime'))
            end_dt = datetime.fromisoformat(assignment.get('endDateTime'))
            
            # Calculate hour breakdown
            hours_dict = split_shift_hours(start_dt, end_dt)
            
            # Add hour breakdown to assignment
            assignment['hours'] = {
                'gross': hours_dict['gross'],
                'lunch': hours_dict['lunch'],
                'normal': hours_dict['normal'],
                'ot': hours_dict['ot'],
                'paid': hours_dict['paid']
            }
            
            # Accumulate totals per employee
            emp_id = assignment.get('employeeId')
            assignment_date = assignment.get('date')
            
            # Week calculation: ISO week (Mon-Sun)
            try:
                date_obj = datetime.fromisoformat(assignment_date).date()
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
    output = {
        "schemaVersion": "0.43",
        "planningReference": ctx.get("planningReference", "UNKNOWN"),
        "solverRun": {
            "runId": "SRN-local-0.4",
            "solverVersion": "optfold-py-0.4.2",
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
        "unmetDemand": [],
        "meta": {
            "inputHash": input_hash,
            "generatedAt": datetime.now().isoformat(),
            "employeeHours": employee_hours_summary
        }
    }
    
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
    
    for assignment in new_assignments:
        try:
            start_dt = datetime.fromisoformat(assignment.get('startDateTime'))
            end_dt = datetime.fromisoformat(assignment.get('endDateTime'))
            
            # Calculate hour breakdown
            hours_dict = split_shift_hours(start_dt, end_dt)
            
            # Add audit trail
            audit_info = {
                "solverRunId": run_id,
                "source": "incremental",
                "timestamp": current_timestamp,
                "inputHash": input_hash,
                "previousJobId": None
            }
            
            # Add hour breakdown + audit to assignment
            enriched_assignment = {
                **assignment,
                'hours': {
                    'gross': hours_dict['gross'],
                    'lunch': hours_dict['lunch'],
                    'normal': hours_dict['normal'],
                    'ot': hours_dict['ot'],
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
        "schemaVersion": "0.80",
        "planningReference": input_data.get("planningReference", "UNKNOWN"),
        "solverRun": {
            "runId": run_id,
            "solverVersion": "optSolve-py-1.0.0",
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
            "solvableSlots": len(incremental_ctx.get('solvableSlots', [])),
            "unassignedSlots": len([a for a in annotated_new if a.get('status') == 'UNASSIGNED'])
        },
        "meta": {
            "inputHash": input_hash,
            "generatedAt": current_timestamp,
            "employeeHours": employee_hours_summary
        }
    }
    
    return output
