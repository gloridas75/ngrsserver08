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
    # Remove runtime-added keys that aren't part of original input
    # This includes CP-SAT objects (IntVar), slots, and other solver internals
    clean_data = {k: v for k, v in input_data.items() 
                  if k not in ['slots', 'x', 'model', 'timeLimit', 'unassigned', 
                               'offset_vars', 'optimized_offsets', 'total_unassigned']}
    json_str = json.dumps(clean_data, sort_keys=True)
    return "sha256:" + hashlib.sha256(json_str.encode()).hexdigest()


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
