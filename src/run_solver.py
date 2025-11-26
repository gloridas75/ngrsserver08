import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))  # repo root on sys.path

import json, argparse, pathlib, hashlib
from datetime import datetime
from collections import defaultdict
from context.engine.data_loader import load_input
from context.engine.solver_engine import solve
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
    
    for assignment in assignments:
        # Parse start and end datetimes
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
            
            # Week calculation: assume ISO week (Mon-Sun)
            try:
                date_obj = datetime.fromisoformat(assignment_date).date()
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
                'gross': 0, 'lunch': 0, 'normal': 0, 'ot': 0, 'paid': 0,
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
    
    # Build output structure
    output = {
        "schemaVersion": "0.4",
        "planningReference": ctx.get("planningReference", "UNKNOWN"),
        "publicHolidays": ctx.get("publicHolidays", []),
        "solverRun": {
            "runId": "SRN-local-0.4",
            "solverVersion": "optfold-py-0.4.2",
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

    # Load input
    ctx = load_input(str(infile_path))
    ctx["timeLimit"] = args.time_limit

    # TODO: optionally validate against context/schemas/input.schema.json

    # Solve - now returns (status, solver_result, assignments, violations)
    status, solver_result, assignments, violations = solve(ctx)

    # Build output in expected schema format
    output = build_output_schema(str(infile_path), ctx, status, solver_result, assignments, violations)

    # Write output
    outfile_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"✓ Solve status: {solver_result['status']} → wrote {outfile_path}")
    print(f"  Assignments: {len(assignments)}")
    print(f"  Hard score: {output['score']['hard']}")
    print(f"  Soft score: {output['score']['soft']}")
    print(f"  Overall score: {output['score']['overall']}")

if __name__ == "__main__":
    main()
