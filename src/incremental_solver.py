"""
Incremental Solver Module (v0.80)

Handles mid-month incremental solving scenarios:
- New employees joining mid-month
- Employee departures/resignations
- Long leave periods
- Re-assigning unassigned or freed slots without disturbing locked assignments
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Set, Tuple, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class IncrementalSolverError(Exception):
    """Custom exception for incremental solver errors."""
    pass


def parse_date(date_str: str) -> date:
    """Parse YYYY-MM-DD string to date object."""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def _validate_incremental_request(request_data: Dict[str, Any]) -> None:
    """
    Validate incremental solve request structure.
    
    Raises:
        IncrementalSolverError: If validation fails
    """
    required = ["temporalWindow", "previousOutput", "employeeChanges", 
                "demandItems", "planningHorizon", "planningReference"]
    
    missing = [f for f in required if f not in request_data]
    if missing:
        raise IncrementalSolverError(f"Missing required fields: {', '.join(missing)}")
    
    # Validate previousOutput has assignments
    if "assignments" not in request_data["previousOutput"]:
        raise IncrementalSolverError("previousOutput must contain 'assignments' array")
    
    logger.info("✓ Incremental request structure validated")


def _detect_rostering_basis(demand_items: List[Dict[str, Any]]) -> str:
    """
    Detect rostering basis from demand items.
    
    Priority:
    1. demandItems[0].rosteringBasis
    2. Default: 'demandBased'
    
    Returns:
        str: 'demandBased' or 'outcomeBased'
    """
    if demand_items and len(demand_items) > 0:
        rostering_basis = demand_items[0].get('rosteringBasis')
        if rostering_basis:
            return rostering_basis
    
    return 'demandBased'


def validate_temporal_window(temporal_window: Dict[str, str]) -> None:
    """
    Validate temporal window constraints.
    
    Raises:
        IncrementalSolverError: If validation fails
    """
    cutoff = parse_date(temporal_window["cutoffDate"])
    solve_from = parse_date(temporal_window["solveFromDate"])
    solve_to = parse_date(temporal_window["solveToDate"])
    
    if cutoff >= solve_from:
        raise IncrementalSolverError(
            f"cutoffDate ({cutoff}) must be < solveFromDate ({solve_from})"
        )
    
    if solve_from > solve_to:
        raise IncrementalSolverError(
            f"solveFromDate ({solve_from}) must be <= solveToDate ({solve_to})"
        )
    
    logger.info(f"✓ Temporal window validated: lock before {cutoff}, solve {solve_from} to {solve_to}")


def classify_slots(
    previous_assignments: List[Dict[str, Any]],
    temporal_window: Dict[str, str],
    not_available_employees: List[Dict[str, str]],
    long_leave_employees: List[Dict[str, str]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Set[str]]:
    """
    Classify slots into LOCKED (immutable) and SOLVABLE (can be reassigned).
    
    Args:
        previous_assignments: All assignments from previous output
        temporal_window: Cutoff, solve from/to dates
        not_available_employees: Employees who departed
        long_leave_employees: Employees on long leave
        
    Returns:
        Tuple of:
        - locked_assignments: Assignments before cutoffDate or assigned to available employees
        - solvable_slots: Slots that can be reassigned (unassigned, freed from departed, or in leave window)
        - departed_employee_ids: Set of employee IDs who are no longer available
    """
    cutoff_date = parse_date(temporal_window["cutoffDate"])
    solve_from_date = parse_date(temporal_window["solveFromDate"])
    
    # Build lookup maps
    not_available_map = {
        emp["employeeId"]: parse_date(emp["notAvailableFrom"])
        for emp in not_available_employees
    }
    
    long_leave_map = defaultdict(list)
    for leave in long_leave_employees:
        emp_id = leave["employeeId"]
        leave_from = parse_date(leave["leaveFrom"])
        leave_to = parse_date(leave["leaveTo"])
        long_leave_map[emp_id].append((leave_from, leave_to))
    
    locked_assignments = []
    solvable_slots = []
    departed_employee_ids = set(not_available_map.keys())
    
    for assignment in previous_assignments:
        assignment_date = parse_date(assignment["date"])
        employee_id = assignment.get("employeeId")
        status = assignment.get("status", "ASSIGNED")
        
        # Slot is before cutoff → LOCKED
        if assignment_date < cutoff_date:
            locked_assignments.append({
                **assignment,
                "source": "locked",
                "lockedReason": "before_cutoff"
            })
            continue
        
        # Slot is before solveFromDate → LOCKED (in between cutoff and solveFrom)
        if assignment_date < solve_from_date:
            locked_assignments.append({
                **assignment,
                "source": "locked",
                "lockedReason": "before_solve_window"
            })
            continue
        
        # From here: assignment_date >= solve_from_date (in solvable window)
        
        # Already unassigned → SOLVABLE
        if status == "UNASSIGNED":
            solvable_slots.append({
                **assignment,
                "originalStatus": "UNASSIGNED"
            })
            continue
        
        # Assigned to departed employee → SOLVABLE (free the slot)
        if employee_id in not_available_map:
            not_avail_date = not_available_map[employee_id]
            if assignment_date >= not_avail_date:
                solvable_slots.append({
                    **assignment,
                    "employeeId": None,  # Free the slot
                    "status": "UNASSIGNED",
                    "originalStatus": "FREED_DEPARTED",
                    "freedFrom": employee_id
                })
                continue
        
        # Assigned to employee on long leave during this period → SOLVABLE
        if employee_id in long_leave_map:
            on_leave = False
            for leave_from, leave_to in long_leave_map[employee_id]:
                if leave_from <= assignment_date <= leave_to:
                    on_leave = True
                    break
            
            if on_leave:
                solvable_slots.append({
                    **assignment,
                    "employeeId": None,  # Free the slot
                    "status": "UNASSIGNED",
                    "originalStatus": "FREED_LEAVE",
                    "freedFrom": employee_id
                })
                continue
        
        # Otherwise, assigned to available employee → LOCKED
        locked_assignments.append({
            **assignment,
            "source": "locked",
            "lockedReason": "assigned_available_employee"
        })
    
    logger.info(f"Slot classification complete:")
    logger.info(f"  Locked assignments: {len(locked_assignments)}")
    logger.info(f"  Solvable slots: {len(solvable_slots)}")
    logger.info(f"  Departed employees: {len(departed_employee_ids)}")
    
    return locked_assignments, solvable_slots, departed_employee_ids


def build_employee_pool(
    previous_output: Dict[str, Any],
    new_joiners: List[Dict[str, Any]],
    departed_employee_ids: Set[str],
    temporal_window: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Build employee pool for incremental solve.
    
    Combines:
    - Previous employees (excluding departed)
    - New joiners
    
    Args:
        previous_output: Previous solver output
        new_joiners: List of new employee data with availableFrom dates
        departed_employee_ids: Set of departed employee IDs to exclude
        temporal_window: Temporal window config
        
    Returns:
        List of employee objects for solving
    """
    # Extract employees from previous output's input (if embedded)
    # Or reconstruct from assignments
    previous_employees = []
    
    # Try to get from previousOutput.meta or derive from assignments
    if "meta" in previous_output and "inputData" in previous_output["meta"]:
        previous_employees = previous_output["meta"]["inputData"].get("employees", [])
    else:
        # Derive unique employee IDs from assignments
        unique_emp_ids = set()
        for assignment in previous_output.get("assignments", []):
            emp_id = assignment.get("employeeId")
            if emp_id:
                unique_emp_ids.add(emp_id)
        
        # We need full employee objects, so this is a limitation
        # Best practice: previous output should include input data
        logger.warning(
            f"Previous output doesn't contain employee data. "
            f"Found {len(unique_emp_ids)} unique employee IDs in assignments. "
            f"Cannot reconstruct full employee objects without original input."
        )
        # For now, just track IDs
        previous_employees = [{"employeeId": emp_id} for emp_id in unique_emp_ids]
    
    # Filter out departed employees
    available_previous_employees = [
        emp for emp in previous_employees
        if emp.get("employeeId") not in departed_employee_ids
    ]
    
    # Add new joiners
    new_employee_objects = [joiner["employee"] for joiner in new_joiners]
    
    all_employees = available_previous_employees + new_employee_objects
    
    logger.info(f"Employee pool built:")
    logger.info(f"  Previous employees (available): {len(available_previous_employees)}")
    logger.info(f"  New joiners: {len(new_employee_objects)}")
    logger.info(f"  Total employees: {len(all_employees)}")
    
    return all_employees


def calculate_locked_weekly_hours(
    locked_assignments: List[Dict[str, Any]],
    temporal_window: Dict[str, str]
) -> Dict[str, Dict[int, float]]:
    """
    Calculate hours already worked by each employee in weeks that span the cutoff.
    
    Returns:
        Dict[employee_id, Dict[iso_week_number, hours_worked]]
    """
    solve_from_date = parse_date(temporal_window["solveFromDate"])
    
    weekly_hours = defaultdict(lambda: defaultdict(float))
    
    for assignment in locked_assignments:
        emp_id = assignment.get("employeeId")
        if not emp_id:
            continue
        
        assignment_date = parse_date(assignment["date"])
        
        # Get ISO week number
        iso_year, iso_week, _ = assignment_date.isocalendar()
        week_key = (iso_year, iso_week)
        
        # Only track if this week overlaps with solve window
        # (i.e., the week contains dates >= solve_from_date)
        week_start = assignment_date - timedelta(days=assignment_date.weekday())
        week_end = week_start + timedelta(days=6)
        
        if week_end >= solve_from_date:
            # Get hours worked
            hours = 0.0
            if "hours" in assignment and isinstance(assignment["hours"], dict):
                hours = assignment["hours"].get("normal", 0.0)
            
            weekly_hours[emp_id][week_key] += hours
    
    logger.info(f"Calculated locked weekly hours for {len(weekly_hours)} employees")
    
    return dict(weekly_hours)


def calculate_locked_consecutive_days(
    locked_assignments: List[Dict[str, Any]],
    temporal_window: Dict[str, str]
) -> Dict[str, int]:
    """
    Calculate consecutive working days before solve window for each employee.
    
    Returns:
        Dict[employee_id, consecutive_days_count]
    """
    solve_from_date = parse_date(temporal_window["solveFromDate"])
    cutoff_date = parse_date(temporal_window["cutoffDate"])
    
    # Group by employee
    employee_dates = defaultdict(set)
    for assignment in locked_assignments:
        emp_id = assignment.get("employeeId")
        if not emp_id:
            continue
        assignment_date = parse_date(assignment["date"])
        employee_dates[emp_id].add(assignment_date)
    
    # Calculate consecutive days leading up to solve_from_date
    consecutive_days = {}
    
    for emp_id, dates in employee_dates.items():
        sorted_dates = sorted(dates)
        
        # Count backwards from (solve_from_date - 1)
        count = 0
        check_date = solve_from_date - timedelta(days=1)
        
        while check_date in sorted_dates and check_date >= cutoff_date:
            count += 1
            check_date -= timedelta(days=1)
        
        consecutive_days[emp_id] = count
    
    logger.info(f"Calculated consecutive days for {len(consecutive_days)} employees")
    
    return consecutive_days


def solve_incremental(
    request_data: Dict[str, Any],
    solver_engine: Any,
    run_id: str
) -> Dict[str, Any]:
    """
    Main orchestrator for incremental solving.
    
    Args:
        request_data: IncrementalSolveRequest data
        solver_engine: Solver engine instance
        run_id: Unique run ID
        
    Returns:
        Solution with locked + new assignments
    """
    logger.info("=" * 80)
    logger.info("[INCREMENTAL SOLVER STARTING]")
    logger.info("=" * 80)
    
    # Validate incremental request structure
    _validate_incremental_request(request_data)
    
    # Extract components
    temporal_window = request_data["temporalWindow"]
    previous_output = request_data["previousOutput"]
    employee_changes = request_data["employeeChanges"]
    demand_items = request_data["demandItems"]
    planning_horizon = request_data["planningHorizon"]
    
    # Detect rostering basis (demandBased vs outcomeBased)
    rostering_basis = _detect_rostering_basis(demand_items)
    logger.info(f"Detected rostering basis: {rostering_basis}")
    
    # Step 1: Validate temporal window
    validate_temporal_window(temporal_window)
    
    # Step 1.5: Validate demand items structure (catches headcount=0 errors, etc.)
    from src.input_validator import validate_input
    
    test_input = {
        "schemaVersion": request_data.get("schemaVersion", "0.95"),
        "demandItems": demand_items,
        "employees": [],  # Minimal for validation
        "planningHorizon": planning_horizon
    }
    
    validation_result = validate_input(test_input)
    if not validation_result.is_valid:
        error_msgs = [f"{e.field}: {e.message}" for e in validation_result.errors]
        raise IncrementalSolverError(f"Input validation failed: {'; '.join(error_msgs)}")
    
    logger.info(f"✓ Incremental input validated (rosteringBasis={rostering_basis})")
    
    # Step 2: Classify slots
    locked_assignments, solvable_slots, departed_employee_ids = classify_slots(
        previous_assignments=previous_output.get("assignments", []),
        temporal_window=temporal_window,
        not_available_employees=employee_changes.get("notAvailableFrom", []),
        long_leave_employees=employee_changes.get("longLeave", [])
    )
    
    # Early exit if no slots to solve
    if not solvable_slots:
        logger.info("✓ No solvable slots found. Returning previous output with locked assignments.")
        return {
            **previous_output,
            "assignments": locked_assignments,
            "incrementalSolve": {
                "status": "no_slots_to_solve",
                "message": "All slots are locked. No incremental solving required."
            }
        }
    
    # Step 3: Build employee pool
    all_employees = build_employee_pool(
        previous_output=previous_output,
        new_joiners=employee_changes.get("newJoiners", []),
        departed_employee_ids=departed_employee_ids,
        temporal_window=temporal_window
    )
    
    # Step 4: Calculate locked context for constraints (MODE-DEPENDENT)
    if rostering_basis == 'demandBased':
        # Pattern-based: Calculate locked hours/days for constraint continuity
        locked_weekly_hours = calculate_locked_weekly_hours(locked_assignments, temporal_window)
        locked_consecutive_days = calculate_locked_consecutive_days(locked_assignments, temporal_window)
        logger.info(f"✓ Calculated locked context for demandBased mode")
        logger.info(f"   - Locked weekly hours tracked for {len(locked_weekly_hours)} employees")
        logger.info(f"   - Locked consecutive days tracked for {len(locked_consecutive_days)} employees")
    else:
        # outcomeBased: Template-based rostering, no pattern continuity needed
        locked_weekly_hours = {}
        locked_consecutive_days = {}
        logger.info(f"✓ Skipped pattern continuity for outcomeBased mode (template-based)")
        logger.info(f"   Note: outcomeBased uses template validation without rotation patterns")
    
    # Step 5: Build modified input for solver
    # Only solve for solvable slots
    incremental_input = {
        "schemaVersion": request_data.get("schemaVersion", "0.95"),
        "planningReference": request_data["planningReference"],
        "planningHorizon": planning_horizon,
        "demandItems": demand_items,
        "employees": all_employees,
        "solverConfig": request_data.get("solverConfig", {}),
        
        # Pass incremental context
        "_incremental": {
            "mode": "incremental",
            "lockedAssignments": locked_assignments,
            "solvableSlots": solvable_slots,
            "lockedWeeklyHours": locked_weekly_hours,
            "lockedConsecutiveDays": locked_consecutive_days,
            "temporalWindow": temporal_window,
            "employeeChanges": employee_changes
        }
    }
    
    # Step 6: Invoke solver
    logger.info(f"Invoking solver for {len(solvable_slots)} solvable slots with {len(all_employees)} employees...")
    
    try:
        # Call the actual solver with incremental context
        logger.info("🔧 [DEBUG] Calling solver_engine()...")
        status, solver_result, new_assignments, violations = solver_engine(incremental_input)
        logger.info(f"🔧 [DEBUG] Solver returned: status={status}, new_assignments={len(new_assignments)}")
        
        # Step 7: Build combined output with audit trail
        logger.info("🔧 [DEBUG] Importing build_incremental_output()...")
        from src.output_builder import build_incremental_output
        
        logger.info(f"🔧 [DEBUG] Calling build_incremental_output() with:")
        logger.info(f"   - locked_assignments: {len(locked_assignments)}")
        logger.info(f"   - new_assignments: {len(new_assignments)}")
        logger.info(f"   - status: {solver_result.get('status', 'UNKNOWN')}")
        
        output = build_incremental_output(
            input_data=request_data,
            ctx=incremental_input,
            status=solver_result.get('status', 'UNKNOWN'),
            solver_result=solver_result,
            new_assignments=new_assignments,
            violations=violations,
            locked_assignments=locked_assignments,
            incremental_ctx=incremental_input['_incremental']
        )
        
        logger.info(f"🔧 [DEBUG] build_incremental_output() returned, checking output...")
        logger.info(f"   - schemaVersion: {output.get('schemaVersion')}")
        logger.info(f"   - has incrementalSolve: {'incrementalSolve' in output}")
        logger.info(f"   - total assignments: {len(output.get('assignments', []))}")
        
        logger.info(f"✓ Incremental solve completed")
        logger.info(f"  Status: {solver_result.get('status')}")
        logger.info(f"  Locked assignments: {len(locked_assignments)}")
        logger.info(f"  New assignments: {len(new_assignments)}")
        logger.info(f"  Total assignments: {len(output.get('assignments', []))}")
        
        logger.info("=" * 80)
        logger.info("[INCREMENTAL SOLVER COMPLETE]")
        logger.info("=" * 80)
        
        return output
        
    except Exception as e:
        logger.error(f"Error during incremental solve: {str(e)}", exc_info=True)
        raise IncrementalSolverError(f"Solver execution failed: {str(e)}")
