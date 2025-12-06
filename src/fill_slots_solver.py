"""
Empty Slots Solver Module (v0.96)

Fills unassigned/empty slots with existing and new employees, with availability tracking.
Optimized for lightweight slot filling without requiring full previousOutput.
"""

import logging
import json
import hashlib
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Set, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class FillSlotsSolverError(Exception):
    """Custom exception for fill slots solver errors."""
    pass


def parse_date(date_str: str) -> date:
    """Parse YYYY-MM-DD string to date object."""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def parse_time(time_str: str) -> tuple:
    """Parse HH:MM:SS string to (hour, minute, second)."""
    parts = time_str.split(":")
    return (int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)


def calculate_length_days(temporal_window: Dict[str, Any]) -> int:
    """Calculate length in days from temporal window."""
    if temporal_window.get("lengthDays"):
        return temporal_window["lengthDays"]
    
    solve_from = parse_date(temporal_window["solveFromDate"])
    solve_to = parse_date(temporal_window["solveToDate"])
    return (solve_to - solve_from).days + 1


def validate_fill_slots_request(request_data: Dict[str, Any]) -> None:
    """
    Validate fill slots request structure.
    
    Raises:
        FillSlotsSolverError: If validation fails
    """
    # Check required fields
    required = ["schemaVersion", "mode", "planningReference", "temporalWindow", 
                "emptySlots", "existingEmployees"]
    
    missing = [f for f in required if f not in request_data]
    if missing:
        raise FillSlotsSolverError(f"Missing required fields: {', '.join(missing)}")
    
    # Validate temporal window
    tw = request_data["temporalWindow"]
    required_tw = ["cutoffDate", "solveFromDate", "solveToDate"]
    missing_tw = [f for f in required_tw if f not in tw]
    if missing_tw:
        raise FillSlotsSolverError(f"Missing temporal window fields: {', '.join(missing_tw)}")
    
    cutoff = parse_date(tw["cutoffDate"])
    solve_from = parse_date(tw["solveFromDate"])
    solve_to = parse_date(tw["solveToDate"])
    
    if cutoff >= solve_from:
        raise FillSlotsSolverError(
            f"cutoffDate ({cutoff}) must be < solveFromDate ({solve_from})"
        )
    
    if solve_from > solve_to:
        raise FillSlotsSolverError(
            f"solveFromDate ({solve_from}) must be <= solveToDate ({solve_to})"
        )
    
    # Check empty slots
    if not request_data["emptySlots"]:
        raise FillSlotsSolverError("emptySlots cannot be empty")
    
    # Check existing employees
    if not request_data["existingEmployees"] and not request_data.get("newJoiners"):
        raise FillSlotsSolverError("Must have at least one existing employee or new joiner")
    
    logger.info(f"✓ Fill slots request validated: {len(request_data['emptySlots'])} slots, "
                f"{len(request_data['existingEmployees'])} existing employees, "
                f"{len(request_data.get('newJoiners', []))} new joiners")


def build_employee_pool(
    existing_employees: List[Dict[str, Any]],
    new_joiners: List[Dict[str, Any]],
    temporal_window: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """
    Build unified employee pool with availability tracking.
    
    Returns:
        Dict mapping employeeId to employee info with availability
    """
    solve_from = parse_date(temporal_window["solveFromDate"])
    employee_pool = {}
    
    # Add existing employees
    for emp in existing_employees:
        emp_id = emp["employeeId"]
        
        # Build availability lookup
        availability_map = {}
        if emp.get("availability"):
            availability_map = {
                parse_date(avail["date"]): avail["available"]
                for avail in emp["availability"]
            }
        
        employee_pool[emp_id] = {
            "employeeId": emp_id,
            "type": "existing",
            "availableHours": emp.get("availableHours", {"weekly": 44.0, "monthly": 176.0}),
            "availableDays": emp.get("availableDays", {"consecutive": 12, "total": 31}),
            "currentState": emp.get("currentState", {
                "consecutiveDaysWorked": 0,
                "lastWorkDate": None,
                "rotationOffset": 0,
                "patternDay": 0
            }),
            "availabilityMap": availability_map,
            "assignedSlots": []  # Track assignments
        }
    
    # Add new joiners
    for joiner in new_joiners:
        emp_id = joiner["employeeId"]
        available_from = parse_date(joiner.get("availableFrom", temporal_window["solveFromDate"]))
        
        # Calculate contracted hours (default 176 monthly)
        contracted_hours = joiner.get("contractedHours", 176.0)
        
        employee_pool[emp_id] = {
            "employeeId": emp_id,
            "type": "new_joiner",
            "firstName": joiner.get("firstName"),
            "lastName": joiner.get("lastName"),
            "rankId": joiner.get("rankId"),
            "productTypes": joiner.get("productTypes", []),
            "workPattern": joiner.get("workPattern"),
            "availableFrom": available_from,
            "contractedHours": contracted_hours,
            "availableHours": {"weekly": 44.0, "monthly": contracted_hours},
            "availableDays": {"consecutive": 12, "total": 31},
            "currentState": {
                "consecutiveDaysWorked": 0,
                "lastWorkDate": None,
                "rotationOffset": joiner.get("rotationOffset", 0),
                "patternDay": 0
            },
            "availabilityMap": {},  # New joiners available for all dates >= availableFrom
            "assignedSlots": []
        }
    
    logger.info(f"✓ Employee pool built: {len(employee_pool)} total employees")
    return employee_pool


def can_assign_employee_to_slot(
    employee: Dict[str, Any],
    slot: Dict[str, Any],
    slot_date: date
) -> Tuple[bool, Optional[str]]:
    """
    Check if employee can be assigned to slot.
    
    Returns:
        Tuple of (can_assign: bool, reason: Optional[str])
    """
    emp_id = employee["employeeId"]
    
    # Check if new joiner is available from this date
    if employee["type"] == "new_joiner":
        if slot_date < employee["availableFrom"]:
            return False, f"New joiner not available until {employee['availableFrom']}"
    
    # Check date-specific availability (existing employees)
    if slot_date in employee["availabilityMap"]:
        if not employee["availabilityMap"][slot_date]:
            return False, f"Employee marked unavailable on {slot_date}"
    
    # Check available hours
    slot_hours = slot["hours"].get("normal", 8.0)
    if employee["availableHours"]["monthly"] < slot_hours:
        return False, f"Insufficient monthly hours ({employee['availableHours']['monthly']}h remaining)"
    
    # Check consecutive days limit
    current_state = employee["currentState"]
    consecutive_worked = current_state.get("consecutiveDaysWorked", 0)
    last_work_date = current_state.get("lastWorkDate")
    
    if last_work_date:
        last_date = parse_date(last_work_date) if isinstance(last_work_date, str) else last_work_date
        days_gap = (slot_date - last_date).days
        
        # If continuous (next day), check consecutive limit
        if days_gap == 1:
            if consecutive_worked >= 12:
                return False, f"Would exceed 12 consecutive days limit"
    
    return True, None


def assign_slot_to_employee(
    employee: Dict[str, Any],
    slot: Dict[str, Any],
    slot_date: date
) -> Dict[str, Any]:
    """
    Assign slot to employee and update their state.
    
    Returns:
        Assignment dict
    """
    # Create assignment
    assignment = {
        "employeeId": employee["employeeId"],
        "date": slot["date"],
        "demandId": slot.get("demandId"),
        "shiftCode": slot["shiftCode"],
        "patternDay": employee["currentState"].get("patternDay", 0),
        "startDateTime": f"{slot['date']}T{slot['startTime']}",
        "endDateTime": slot["date"] if slot["shiftCode"] != "N" else str(slot_date + timedelta(days=1)) + f"T{slot['endTime']}",
        "hours": slot["hours"],
        "slotId": slot.get("slotId"),
        "source": "fill_slots",
        "employeeType": employee["type"]
    }
    
    # Update employee state
    slot_hours = slot["hours"].get("normal", 8.0)
    employee["availableHours"]["monthly"] -= slot_hours
    employee["assignedSlots"].append(assignment)
    
    # Update consecutive days
    last_work_date = employee["currentState"].get("lastWorkDate")
    if last_work_date:
        last_date = parse_date(last_work_date) if isinstance(last_work_date, str) else last_work_date
        days_gap = (slot_date - last_date).days
        
        if days_gap == 1:
            # Continuous work
            employee["currentState"]["consecutiveDaysWorked"] += 1
        else:
            # Gap, reset streak
            employee["currentState"]["consecutiveDaysWorked"] = 1
    else:
        # First assignment
        employee["currentState"]["consecutiveDaysWorked"] = 1
    
    employee["currentState"]["lastWorkDate"] = slot["date"]
    
    return assignment


def simple_greedy_assignment(
    empty_slots: List[Dict[str, Any]],
    employee_pool: Dict[str, Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Simple greedy algorithm to assign slots to employees.
    
    Returns:
        Tuple of (assignments, unmet_slots)
    """
    assignments = []
    unmet_slots = []
    
    # Sort slots by date
    sorted_slots = sorted(empty_slots, key=lambda s: s["date"])
    
    for slot in sorted_slots:
        slot_date = parse_date(slot["date"])
        assigned = False
        
        # Try to assign to first available employee
        for emp_id, employee in employee_pool.items():
            can_assign, reason = can_assign_employee_to_slot(employee, slot, slot_date)
            
            if can_assign:
                assignment = assign_slot_to_employee(employee, slot, slot_date)
                assignments.append(assignment)
                assigned = True
                logger.debug(f"✓ Assigned slot {slot.get('slotId')} on {slot['date']} to {emp_id}")
                break
        
        if not assigned:
            unmet_slots.append(slot)
            logger.warning(f"✗ Could not assign slot {slot.get('slotId')} on {slot['date']}")
    
    logger.info(f"✓ Assignments complete: {len(assignments)} assigned, {len(unmet_slots)} unmet")
    return assignments, unmet_slots


def solve_fill_slots(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for fill slots solving.
    
    Args:
        request_data: Validated request payload
        
    Returns:
        Solver response in standard format
    """
    start_time = datetime.now()
    run_id = str(uuid.uuid4())[:8]
    
    logger.info(f"=== Fill Slots Solver v0.96 - Run {run_id} ===")
    
    # Validate request
    validate_fill_slots_request(request_data)
    
    # Extract data
    temporal_window = request_data["temporalWindow"]
    empty_slots = request_data["emptySlots"]
    existing_employees = request_data["existingEmployees"]
    new_joiners = request_data.get("newJoiners", [])
    
    # Build employee pool
    employee_pool = build_employee_pool(existing_employees, new_joiners, temporal_window)
    
    # Run greedy assignment
    assignments, unmet_slots = simple_greedy_assignment(empty_slots, employee_pool)
    
    # Calculate end time
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Build response
    response = {
        "schemaVersion": "0.96",
        "planningReference": request_data["planningReference"],
        "solverRun": {
            "runId": f"FILL-{run_id}",
            "solverVersion": "fillSlots-py-0.96.0",
            "startedAt": start_time.isoformat(),
            "ended": end_time.isoformat(),
            "durationSeconds": duration,
            "status": "OPTIMAL" if len(unmet_slots) == 0 else "FEASIBLE",
            "numSlots": len(empty_slots),
            "numAssignments": len(assignments),
            "numUnmetSlots": len(unmet_slots)
        },
        "score": {
            "hard": len(unmet_slots),
            "soft": 0,
            "overall": len(unmet_slots)
        },
        "assignments": assignments,
        "unmetDemand": [
            {
                "slotId": slot.get("slotId"),
                "date": slot["date"],
                "shiftCode": slot["shiftCode"],
                "reason": slot.get("reason", "UNASSIGNED"),
                "requirementId": slot.get("requirementId")
            }
            for slot in unmet_slots
        ],
        "meta": {
            "requestId": f"fill-{run_id}",
            "generatedAt": datetime.now().isoformat(),
            "inputHash": hashlib.sha256(
                json.dumps(request_data, sort_keys=True).encode()
            ).hexdigest()[:16],
            "warnings": []
        }
    }
    
    # Add warnings if any unmet slots
    if unmet_slots:
        response["meta"]["warnings"].append(
            f"{len(unmet_slots)} slots could not be assigned due to availability/capacity constraints"
        )
    
    logger.info(f"✓ Fill slots solver complete: {len(assignments)} assignments, {len(unmet_slots)} unmet")
    return response
