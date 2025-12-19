import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))  # repo root on sys.path

import json, argparse, pathlib, hashlib, copy, numpy as np
from datetime import datetime
from collections import defaultdict
from context.engine.data_loader import load_input
from context.engine.solver_engine import solve
from context.engine.time_utils import (
    split_shift_hours, 
    calculate_mom_compliant_hours,
    calculate_apgd_d10_hours,
    is_apgd_d10_employee
)

from src.solver import solve_problem
from src.resource_limiter import apply_solver_resource_limits

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

def build_output_schema(input_path, ctx, status, solver_result, assignments, violations):
    """
    Build output in the expected schema format (v0.4).
    
    Also annotates each assignment with hour breakdown and computes per-employee totals.
    
    Expected output structure:
    {
      "schemaVersion": "0.4",
      "planningReference": (from input),
      "solverRun": { runId, solverVersion, startedAt, ended, durationSeconds, status },
      "score": { overall, hard, soft },
      "scoreBreakdown": { hard: {violations}, soft: {constraint_scores} },
      "assignments": [],  # Now includes hour breakdowns
      "unmetDemand": [],
      "meta": { 
        "inputHash", 
        "generatedAt",
        "employeeHours": { per-employee weekly normal and monthly OT totals }
      }
    }
    """
    
    # Compute input hash
    input_hash = compute_input_hash(ctx)
    
    # Extract scores from solver_result
    scores = solver_result.get('scores', {'hard': 0, 'soft': 0, 'overall': 0})
    score_breakdown = solver_result.get('scoreBreakdown', {
        'hard': {'violations': []},
        'soft': {}
    })
    
    # ========== ANNOTATE ASSIGNMENTS WITH HOUR BREAKDOWN ==========
    annotated_assignments = []
    employee_weekly_normal = defaultdict(float)  # emp_id -> total normal hours for week
    employee_monthly_ot = defaultdict(float)     # emp_id -> total OT hours for month
    
    # Build employee lookup dictionary for scheme information
    employee_dict = {emp['employeeId']: emp for emp in ctx.get('employees', [])}
    
    for assignment in assignments:
        # Parse start and end datetimes
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
            for demand in ctx.get('demandItems', []):
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
            
            # Week calculation: assume ISO week (Mon-Sun)
            try:
                iso_year, iso_week, _ = date_obj.isocalendar()
                week_key = f"{iso_year}-W{iso_week:02d}"
                
                # Accumulate normal hours for week
                employee_weekly_normal[f"{emp_id}:{week_key}"] += hours_dict['normal']
                
                # Accumulate OT hours for month
                month_key = f"{iso_year}-{date_obj.month:02d}"
                employee_monthly_ot[f"{emp_id}:{month_key}"] += hours_dict['ot']
            except:
                pass  # If date parsing fails, skip accumulation
            
        except Exception as e:
            # If hour calculation fails, just skip the annotation
            assignment['hours'] = {
                'gross': 0, 'lunch': 0, 'normal': 0, 'ot': 0, 'restDayPay': 0, 'paid': 0,
                'error': str(e)
            }
        
        annotated_assignments.append(assignment)
    
    # ========== BUILD META WITH EMPLOYEE TOTALS ==========
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
    
    # ========== BUILD EMPLOYEE ROSTER ==========
    from src.output_builder import build_employee_roster
    
    # Load input data for employee roster
    with open(input_path, 'r', encoding='utf-8') as f:
        input_data = json.load(f)
    
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
    
    # Build output structure
    output = {
        "schemaVersion": "0.43",
        "planningReference": ctx.get("planningReference", "UNKNOWN"),
        "publicHolidays": ctx.get("publicHolidays", []),
        "solverRun": {
            "runId": "SRN-local-0.4",
            "solverVersion": "optSolve-py-0.9.0",
            "startedAt": solver_result["start_timestamp"],
            "ended": solver_result["end_timestamp"],
            "durationSeconds": solver_result["duration_seconds"],
            "status": solver_result["status"]
        },
        "score": {
            "overall": scores.get('overall', 0),
            "hard": scores.get('hard', 0),
            "soft": scores.get('soft', 0)
        },
        "scoreBreakdown": score_breakdown,
        "assignments": annotated_assignments,  # Now includes hour breakdowns
        "employeeRoster": employee_roster,  # NEW: comprehensive daily status for ALL employees
        "rosterSummary": roster_summary,  # NEW: Summary of roster statuses
        "unmetDemand": [],
        "meta": {
            "inputHash": input_hash,
            "generatedAt": datetime.now().isoformat(),
            "employeeHours": employee_hours_summary  # NEW: transparency on hour totals
        }
    }
    
    # Add optimized rotation offsets if available
    if 'optimizedRotationOffsets' in solver_result:
        output['solverRun']['optimizedRotationOffsets'] = solver_result['optimizedRotationOffsets']
    
    return output

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--out", dest="outfile", required=False, default=None)
    ap.add_argument("--time", dest="time_limit", type=int, default=15)
    args = ap.parse_args()

    # Resolve input file path (support both direct and input/ folder)
    infile_path = pathlib.Path(args.infile)
    if not infile_path.exists():
        infile_path = pathlib.Path("input") / args.infile
    
    # Generate or resolve output file path
    if args.outfile is None:
        # Auto-generate timestamp-based filename: output_DDMM_HHmm.json
        now = datetime.now()
        timestamp = now.strftime("%d%m_%H%M")
        outfile_name = f"output_{timestamp}.json"
        outfile_path = pathlib.Path("output") / outfile_name
    else:
        # Resolve output file path (support both direct and output/ folder)
        outfile_path = pathlib.Path(args.outfile)
        if str(outfile_path.parent) == ".":
            outfile_path = pathlib.Path("output") / args.outfile
    
    # Ensure output directory exists
    outfile_path.parent.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # UNIFIED SOLVER - ALL LOGIC IN src/solver.py
    # ============================================================
    # Load the raw input JSON
    with open(infile_path, 'r', encoding='utf-8') as f:
        input_data = json.load(f)

    # Use unified solver (same path as async API)
    print(f"[CLI] Using unified solver")
    result = solve_problem(input_data, log_prefix="[CLI]")
    
    # Result from solve_problem() is ALREADY the complete output with:
    # - Full hour breakdowns (normal, OT, RDP, public holiday hours)
    # - Employee roster with daily status
    # - Proper MOM-compliant calculations
    # Just write it directly - no need to rebuild!
    output = result
    
    # For backwards compatibility with code that expects these variables
    status = result.get('status')
    assignments = result.get('assignments', [])
    solver_run = result.get('solverRun', {})

    # Build output in expected schema format
    # (output already contains everything, no need to rebuild)

    # Write output
    outfile_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    
    # Display summary
    score = output.get('score', {})
    solver_status = output.get('solverRun', {}).get('status', 'UNKNOWN')
    print(f"✓ Solve status: {solver_status} → wrote {outfile_path}")
    print(f"  Assignments: {len(output.get('assignments', []))}")
    print(f"  Hard score: {score.get('hard', 0)}")
    print(f"  Soft score: {score.get('soft', 0)}")
    print(f"  Overall score: {score.get('overall', 0)}")

if __name__ == "__main__":
    # Apply resource limits before starting solver (prevent system crashes)
    # Default: Use 75% of system RAM, leaving 25% for OS and other processes
    import os
    memory_limit_pct = int(os.getenv('SOLVER_MEMORY_LIMIT_PCT', '75'))
    print(f"[CLI] Applying resource limits ({memory_limit_pct}% system RAM)...")
    apply_solver_resource_limits(memory_percentage=memory_limit_pct)
    
    main()
