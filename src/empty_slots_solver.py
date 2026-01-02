"""
Empty Slots Solver

Optimized solving mode that accepts only empty slots + locked employee context.
Bypasses slot classification and directly builds solvable slots from input.

Key Benefits:
- 97% smaller payloads: Send only 50 empty slots vs 1,550 full assignments
- Faster processing: No classification needed, direct to solving
- Clearer intent: Explicit about what needs to be filled
- All constraints: Full C1-C17 and S1-S16 support

Usage:
    from src.empty_slots_solver import solve_empty_slots
    
    result = solve_empty_slots(
        request_data=empty_slots_request,
        solver_engine=solver_engine,
        run_id="empty-12345"
    )
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
from collections import defaultdict, Counter
import logging

logger = logging.getLogger(__name__)


class EmptySlotsSolverError(Exception):
    """Errors during empty slots solving."""
    pass


def validate_empty_slots_request(request_data: Dict[str, Any]) -> None:
    """
    Validate empty slots request structure.
    
    Args:
        request_data: EmptySlotsRequest data
        
    Raises:
        EmptySlotsSolverError: If validation fails
    """
    # Check required fields
    required = ["emptySlots", "lockedContext", "employees", "planningHorizon"]
    for field in required:
        if field not in request_data:
            raise EmptySlotsSolverError(f"Missing required field: {field}")
    
    # Validate empty slots
    empty_slots = request_data["emptySlots"]
    if not isinstance(empty_slots, list):
        raise EmptySlotsSolverError("emptySlots must be a list")
    
    if len(empty_slots) == 0:
        raise EmptySlotsSolverError("emptySlots cannot be empty - must have at least 1 slot to fill")
    
    # Validate each slot has required fields
    required_slot_fields = ["slotId", "date", "shiftCode", "requirementId", "demandId", 
                            "locationId", "productTypeId", "rankId", "startTime", "endTime", "reason"]
    for idx, slot in enumerate(empty_slots):
        for field in required_slot_fields:
            if field not in slot:
                raise EmptySlotsSolverError(
                    f"Empty slot at index {idx} missing required field: {field}"
                )
    
    # Validate locked context
    locked_context = request_data["lockedContext"]
    if "cutoffDate" not in locked_context:
        raise EmptySlotsSolverError("lockedContext missing cutoffDate")
    
    if "employeeAssignments" not in locked_context:
        raise EmptySlotsSolverError("lockedContext missing employeeAssignments")
    
    # Validate planning horizon
    horizon = request_data["planningHorizon"]
    if "startDate" not in horizon or "endDate" not in horizon:
        raise EmptySlotsSolverError("planningHorizon missing startDate or endDate")
    
    # Validate employees
    employees = request_data["employees"]
    if not isinstance(employees, list) or len(employees) == 0:
        raise EmptySlotsSolverError("employees must be a non-empty list")
    
    logger.info(f"✓ Empty slots request validated")
    logger.info(f"  Empty slots: {len(empty_slots)}")
    logger.info(f"  Employees: {len(employees)}")
    logger.info(f"  Locked context employees: {len(locked_context.get('employeeAssignments', []))}")


def build_demand_items_from_empty_slots(
    empty_slots: List[Dict[str, Any]],
    planning_horizon: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Build demandItems structure from empty slots.
    
    Groups empty slots by requirementId and builds demand structure
    that the solver engine expects.
    
    Args:
        empty_slots: List of empty slot dicts
        planning_horizon: Planning period with startDate and endDate
        
    Returns:
        List of demand items with demand patterns
    """
    start_date = datetime.fromisoformat(planning_horizon["startDate"]).date()
    end_date = datetime.fromisoformat(planning_horizon["endDate"]).date()
    
    # Group slots by requirementId
    slots_by_requirement = defaultdict(list)
    for slot in empty_slots:
        req_id = slot["requirementId"]
        slots_by_requirement[req_id].append(slot)
    
    # Build demand items
    demand_items = []
    for req_id, slots in slots_by_requirement.items():
        # Use first slot as template
        template = slots[0]
        
        # Count slots per date
        slots_per_date = defaultdict(int)
        for slot in slots:
            slot_date = datetime.fromisoformat(slot["date"]).date()
            slots_per_date[slot_date] += 1
        
        # Build demand item
        demand_item = {
            "requirementId": req_id,
            "demandId": template.get("demandId", req_id),
            "locationId": template["locationId"],
            "productTypeId": template["productTypeId"],
            "rankId": template["rankId"],
            "shiftStartDate": start_date.isoformat(),  # Required by slot_builder
            "shifts": [
                {
                    "shiftCode": template["shiftCode"],
                    "startTime": template["startTime"],
                    "endTime": template["endTime"]
                }
            ],
            "demandPattern": []
        }
        
        # Build demand pattern for date range
        current_date = start_date
        while current_date <= end_date:
            count = slots_per_date.get(current_date, 0)
            demand_item["demandPattern"].append({
                "date": current_date.isoformat(),
                "count": count
            })
            current_date += timedelta(days=1)
        
        demand_items.append(demand_item)
    
    logger.info(f"Built {len(demand_items)} demand items from {len(empty_slots)} empty slots")
    return demand_items


def parse_locked_weekly_hours(locked_context: Dict[str, Any]) -> Dict[str, Dict[Tuple[int, int], float]]:
    """
    Parse locked weekly hours from employee context.
    
    Converts week string keys (e.g., "2026-W01") to tuple keys (2026, 1).
    
    Args:
        locked_context: LockedContext dict
        
    Returns:
        Dict[employee_id, Dict[week_tuple, hours]]
    """
    locked_weekly_hours = {}
    
    for emp_ctx in locked_context.get("employeeAssignments", []):
        emp_id = emp_ctx["employeeId"]
        
        # Convert week keys from "YYYY-WNN" to (year, week_num)
        weekly_hours_dict = {}
        for week_key, hours in emp_ctx.get("weeklyHours", {}).items():
            try:
                # Parse "2026-W01" -> (2026, 1)
                if "W" in week_key:
                    parts = week_key.split("-W")
                    year = int(parts[0])
                    week_num = int(parts[1])
                else:
                    # Fallback: try direct split
                    parts = week_key.split("-")
                    year = int(parts[0])
                    week_num = int(parts[1])
                weekly_hours_dict[(year, week_num)] = hours
            except (ValueError, IndexError) as e:
                logger.warning(f"Could not parse week key '{week_key}' for employee {emp_id}: {e}")
                continue
        
        locked_weekly_hours[emp_id] = weekly_hours_dict
    
    logger.info(f"Parsed locked weekly hours for {len(locked_weekly_hours)} employees")
    return locked_weekly_hours


def parse_locked_consecutive_days(locked_context: Dict[str, Any]) -> Dict[str, int]:
    """
    Parse locked consecutive working days from employee context.
    
    Args:
        locked_context: LockedContext dict
        
    Returns:
        Dict[employee_id, consecutive_days]
    """
    locked_consecutive_days = {}
    
    for emp_ctx in locked_context.get("employeeAssignments", []):
        emp_id = emp_ctx["employeeId"]
        consecutive = emp_ctx.get("consecutiveWorkingDays", 0)
        locked_consecutive_days[emp_id] = consecutive
    
    logger.info(f"Parsed locked consecutive days for {len(locked_consecutive_days)} employees")
    return locked_consecutive_days


def build_employee_context_map(locked_context: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Build employee context lookup map.
    
    Args:
        locked_context: LockedContext dict
        
    Returns:
        Dict[employee_id, employee_context]
    """
    employee_context_map = {}
    
    for emp_ctx in locked_context.get("employeeAssignments", []):
        emp_id = emp_ctx["employeeId"]
        employee_context_map[emp_id] = emp_ctx
    
    return employee_context_map


def solve_empty_slots(
    request_data: Dict[str, Any],
    solver_engine: Any,
    run_id: str
) -> Dict[str, Any]:
    """
    Solve empty slots without full roster history.
    
    This is the main entry point for empty slots solving mode.
    
    Process:
    1. Validate request
    2. Extract empty slots and locked context
    3. Parse locked weekly hours, consecutive days, employee context
    4. Build demand items (or use provided)
    5. Construct solver input with _emptySlots context
    6. Invoke solver engine with all constraints
    7. Build output with empty slots metadata
    
    Args:
        request_data: EmptySlotsRequest data
        solver_engine: Solver engine function (context.engine.solver_engine.solver_engine)
        run_id: Unique run identifier
        
    Returns:
        Solution dict with:
        - assignments: List of new assignments
        - solverRun: Solver metadata
        - emptySlotsMetadata: Empty slots-specific stats
        - All standard output fields
        
    Raises:
        EmptySlotsSolverError: If validation or solving fails
    """
    logger.info("=" * 80)
    logger.info("[EMPTY SLOTS SOLVER STARTING]")
    logger.info("=" * 80)
    
    # Step 1: Validate request
    try:
        validate_empty_slots_request(request_data)
    except EmptySlotsSolverError as e:
        logger.error(f"✗ Validation failed: {e}")
        raise
    
    # Step 2: Extract components
    empty_slots = request_data["emptySlots"]
    locked_context = request_data["lockedContext"]
    employees = request_data["employees"]
    planning_horizon = request_data["planningHorizon"]
    
    logger.info(f"Empty slots to fill: {len(empty_slots)}")
    logger.info(f"Available employees: {len(employees)}")
    logger.info(f"Locked context cutoff: {locked_context.get('cutoffDate')}")
    
    # Count reasons
    reason_counts = Counter(slot.get("reason", "UNKNOWN") for slot in empty_slots)
    logger.info(f"Empty slot reasons: {dict(reason_counts)}")
    
    # Step 3: Build demand items from empty slots (or use provided)
    demand_items = request_data.get("demandItems")
    if not demand_items:
        logger.info("No demandItems provided - auto-generating from empty slots")
        demand_items = build_demand_items_from_empty_slots(empty_slots, planning_horizon)
    else:
        logger.info(f"Using provided demandItems: {len(demand_items)}")
    
    # Step 4: Parse locked context
    locked_weekly_hours = parse_locked_weekly_hours(locked_context)
    locked_consecutive_days = parse_locked_consecutive_days(locked_context)
    employee_context_map = build_employee_context_map(locked_context)
    
    logger.info(f"Locked weekly hours for {len(locked_weekly_hours)} employees")
    logger.info(f"Locked consecutive days for {len(locked_consecutive_days)} employees")
    
    # Step 5: Build solver input with _emptySlots context
    solver_input = {
        "schemaVersion": request_data.get("schemaVersion", "0.96"),
        "planningReference": request_data["planningReference"],
        "planningHorizon": planning_horizon,
        "employees": employees,
        "demandItems": demand_items,
        "constraintList": request_data.get("constraintList", []),
        "solverScoreConfig": request_data.get("solverScoreConfig", {}),
        "solverConfig": request_data.get("solverConfig", {}),
        
        # Empty slots context (used by constraints)
        "_emptySlots": {
            "mode": "emptySlots",
            "emptySlots": empty_slots,
            "lockedWeeklyHours": locked_weekly_hours,
            "lockedConsecutiveDays": locked_consecutive_days,
            "lockedContext": locked_context,
            "employeeContextMap": employee_context_map
        }
    }
    
    # Step 6: Invoke solver engine
    logger.info("=" * 80)
    logger.info("INVOKING SOLVER ENGINE")
    logger.info("=" * 80)
    logger.info(f"Empty slots to solve: {len(empty_slots)}")
    logger.info(f"Employees available: {len(employees)}")
    logger.info(f"Constraints enabled: {len(solver_input['constraintList'])}")
    
    try:
        status, solver_result, assignments, violations = solver_engine(solver_input)
        
        logger.info("=" * 80)
        logger.info(f"✓ Solver completed: {status}")
        logger.info("=" * 80)
        logger.info(f"  Assignments generated: {len(assignments)}")
        logger.info(f"  Violations detected: {len(violations)}")
        
    except Exception as e:
        logger.error(f"✗ Solver execution failed: {e}", exc_info=True)
        raise EmptySlotsSolverError(f"Solver execution failed: {e}")
    
    # Step 7: Build output
    logger.info("Building output...")
    from src.output_builder import build_output
    
    output = build_output(
        input_data=request_data,
        ctx=solver_input,
        status=solver_result.get("status", "UNKNOWN"),
        solver_result=solver_result,
        assignments=assignments,
        violations=violations
    )
    
    # Step 8: Add empty slots metadata
    filled_count = len([a for a in assignments if a.get("employeeId")])
    unassigned_count = len([a for a in assignments if a.get("status") == "UNASSIGNED"])
    
    output["emptySlotsMetadata"] = {
        "mode": "emptySlots",
        "emptySlotCount": len(empty_slots),
        "filledSlotCount": filled_count,
        "unassignedSlotCount": unassigned_count,
        "coveragePercent": round((filled_count / len(empty_slots)) * 100, 1) if empty_slots else 0,
        "cutoffDate": locked_context["cutoffDate"],
        "reasonBreakdown": dict(reason_counts),
        "lockedEmployeeCount": len(locked_context.get("employeeAssignments", [])),
        "availableEmployeeCount": len(employees)
    }
    
    logger.info("=" * 80)
    logger.info("[EMPTY SLOTS SOLVER COMPLETED]")
    logger.info("=" * 80)
    logger.info(f"Results:")
    logger.info(f"  Filled: {filled_count}/{len(empty_slots)} ({output['emptySlotsMetadata']['coveragePercent']}%)")
    logger.info(f"  Unassigned: {unassigned_count}")
    logger.info(f"  Status: {status}")
    logger.info("=" * 80)
    
    return output
