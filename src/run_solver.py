import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))  # repo root on sys.path

import json, argparse, pathlib, hashlib, copy, numpy as np
from datetime import datetime
from collections import defaultdict
from context.engine.data_loader import load_input
from context.engine.solver_engine import solve
from context.engine.time_utils import split_shift_hours, calculate_mom_compliant_hours
from src.ratio_cache import RatioCache
from src.solver import solve_problem

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
            
            # Calculate MOM-compliant hour breakdown (scheme-aware)
            hours_dict = calculate_mom_compliant_hours(
                start_dt=start_dt,
                end_dt=end_dt,
                employee_id=emp_id,
                assignment_date_obj=date_obj,
                all_assignments=assignments,
                employee_scheme=emp_scheme  # Pass scheme for Scheme P calculations
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

    # Check if auto-optimization is requested in requirements block
    auto_optimize_ratio = False
    requirement_config = None
    first_req = None
    first_demand = None
    
    demand_items = input_data.get('demandItems', [])
    if demand_items:
        first_demand = demand_items[0]
        requirements = first_demand.get('requirements', [])
        if requirements:
            first_req = requirements[0]
            # Check if auto-optimization config exists in requirement
            if 'autoOptimizeStrictRatio' in first_req:
                auto_optimize_ratio = first_req.get('autoOptimizeStrictRatio', False)
                requirement_config = first_req
    
    # Only proceed with caching/optimization if autoOptimizeStrictRatio exists in requirements
    if auto_optimize_ratio and requirement_config is not None:
        # Initialize ratio cache
        ratio_cache = RatioCache()
        
        pattern = first_req.get('workPattern', [])
        
        # Try to get cached ratio first (91% time savings!)
        cached_ratio = ratio_cache.get_cached_ratio(pattern, first_demand)
        
        if cached_ratio is not None:
            # Use cached ratio - skip auto-optimization!
            print(f"\n{'='*70}")
            print("USING CACHED OPTIMAL RATIO (91% TIME SAVINGS!)")
            print(f"{'='*70}\n")
            
            # Set ratio in solverConfig for the solver to use
            solver_config = ctx.get('solverConfig', {})
            solver_config['strictAdherenceRatio'] = cached_ratio
            ctx['solverConfig'] = solver_config
            
            auto_optimize_ratio = False  # Skip optimization loop
    
    if auto_optimize_ratio:
        print(f"\n{'='*70}")
        print("AUTO-OPTIMIZING STRICT ADHERENCE RATIO")
        print(f"{'='*70}\n")
        
        # Get optimization range from requirement config
        # DEFAULTS optimized for production (3-4 ratios instead of 11)
        min_ratio = requirement_config.get('minStrictRatio', 0.6)   # Default: 60%
        max_ratio = requirement_config.get('maxStrictRatio', 0.8)   # Default: 80%
        ratio_step = requirement_config.get('strictRatioStep', 0.1) # Default: 10% steps
        
        # Generate test ratios
        test_ratios = [round(r, 2) for r in np.arange(min_ratio, max_ratio + ratio_step/2, ratio_step)]
        
        print(f"Testing {len(test_ratios)} ratios from {min_ratio*100:.0f}% to {max_ratio*100:.0f}% "
              f"(step: {ratio_step*100:.0f}%)")
        print(f"Ratios to test: {[f'{r*100:.0f}%' for r in test_ratios]}")
        print(f"Expected time: ~{len(test_ratios)} × {args.time_limit}s = {len(test_ratios) * args.time_limit / 60:.1f} min max")
        
        best_ratio = None
        best_employees_used = float('inf')
        best_result = None
        optimal_solutions = []  # Store all OPTIMAL solutions for comparison
        
        for ratio in test_ratios:
            print(f"\n>>> Testing ratio {ratio:.0%} (strict) / {(1-ratio):.0%} (flexible)")
            print("-" * 70)
            
            # Reload input for each test to get fresh context
            test_ctx = load_input(str(infile_path))
            test_ctx["timeLimit"] = args.time_limit
            
            # Set the ratio to test
            test_solver_config = test_ctx.get('solverConfig', {})
            test_solver_config['strictAdherenceRatio'] = ratio
            test_ctx['solverConfig'] = test_solver_config
            
            # Solve with this ratio
            try:
                status, solver_result, assignments, violations = solve(test_ctx)
                
                # Count unique employees used
                employees_used = len(set(a.get('employeeId') for a in assignments))
                assigned_slots = len(assignments)
                total_slots = len(test_ctx.get('slots', []))
                
                print(f"  Result: {solver_result.get('status')} | Assigned: {assigned_slots}/{total_slots} | Employees: {employees_used}")
                
                # If OPTIMAL, track it
                if solver_result.get('status') == 'OPTIMAL':
                    optimal_solutions.append({
                        'ratio': ratio,
                        'employees_used': employees_used,
                        'status': status,
                        'solver_result': solver_result,
                        'assignments': assignments,
                        'violations': violations
                    })
                    print(f"  ✓ OPTIMAL with {employees_used} employees")
                    
                    if employees_used < best_employees_used:
                        best_employees_used = employees_used
                        best_ratio = ratio
                        best_result = (status, solver_result, assignments, violations)
            
            except Exception as e:
                print(f"  ✗ ERROR: {e}")
                continue
        
        # Select the best solution
        if optimal_solutions:
            print(f"\n{'='*70}")
            print("OPTIMIZATION RESULTS:")
            print(f"{'='*70}")
            print(f"\nFound {len(optimal_solutions)} OPTIMAL solution(s):\n")
            for sol in optimal_solutions:
                marker = " ← SELECTED" if sol['ratio'] == best_ratio else ""
                print(f"  Ratio {sol['ratio']:.0%}: {sol['employees_used']} employees{marker}")
            
            print(f"\n✓ Selected ratio: {best_ratio:.0%} strict / {(1-best_ratio):.0%} flexible")
            print(f"  Minimizes employees: {best_employees_used}")
            print(f"{'='*70}\n")
            
            # Use the best result
            status, solver_result, assignments, violations = best_result
            
            # Update the context to reflect the chosen ratio
            ctx['solverConfig']['strictAdherenceRatio'] = best_ratio
            solver_result['selectedStrictRatio'] = best_ratio
            solver_result['testedRatios'] = [s['ratio'] for s in optimal_solutions]
            solver_result['allOptimalSolutions'] = [{
                'ratio': s['ratio'],
                'employeesUsed': s['employees_used']
            } for s in optimal_solutions]
            
            # Cache the optimal ratio for future runs (91% time savings!)
            if first_req and first_demand:
                pattern = first_req.get('workPattern', [])
                
                metadata = {
                    'testedRatios': len(optimal_solutions),
                    'timeLimit': ctx.get('timeLimit'),
                    'solverVersion': '0.95',
                    'requirementId': first_req.get('requirementId', 'unknown')
                }
                
                ratio_cache.save_ratio(
                    pattern=pattern,
                    demand_config=first_demand,
                    optimal_ratio=best_ratio,
                    employees_used=best_employees_used,
                    metadata=metadata
                )
        else:
            print(f"\n{'='*70}")
            print("WARNING: No OPTIMAL solution found in any tested ratio!")
            print("Falling back to default ratio (0.6)")
            print(f"{'='*70}\n")
            
            # Fall back to solving with default ratio
            status, solver_result, assignments, violations = solve(ctx)
    else:
        # No ratio optimization - use unified solver
        print(f"[CLI] Using unified solver (no ratio optimization)")
        result = solve_problem(input_data, log_prefix="[CLI]")
        
        # Extract components from unified solver result for compatibility
        # with build_output_schema (which expects old format)
        status = result.get('status')
        
        # Add timestamps for output schema compatibility
        from datetime import datetime as dt
        now = dt.now().isoformat()
        
        solver_result = {
            'status': status,
            'scores': result.get('score', {}),
            'scoreBreakdown': result.get('scoreBreakdown', {}),
            'start_timestamp': now,
            'end_timestamp': now,
            'duration_seconds': result.get('durationSeconds', 0)
        }
        assignments = result.get('assignments', [])
        violations = result.get('violations', [])
        
        # Load ctx for build_output_schema (it needs employee info)
        ctx = load_input(input_data)
        ctx["timeLimit"] = args.time_limit

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
