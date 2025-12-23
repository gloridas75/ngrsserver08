"""
Slot-based Outcome Rostering Mode

When rosteringBasis = "outcomeBased" with headcount > available employees,
this module creates explicit slots (like demandBased) and fills them with
available employees using constraint-driven template validation.

Key differences from standard outcomeBased:
- Creates explicit slots based on headcount (not just employee count)
- Allows unassigned slots when employees < headcount
- Balances workload across available employees
- Uses pattern-based slot generation with rotation offsets
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


def should_use_slot_based_outcome(demand: Dict[str, Any], requirement: Dict[str, Any], 
                                   available_employees: int) -> bool:
    """
    Determine if slot-based outcome mode should be used.
    
    Conditions:
    1. rosteringBasis = "outcomeBased"
    2. minStaffThresholdPercentage = 100
    3. headcount > 0 (explicitly set)
    4. available_employees < headcount
    
    Args:
        demand: Demand item dictionary
        requirement: Requirement dictionary
        available_employees: Number of available employees
        
    Returns:
        True if slot-based mode should be used
    """
    headcount = requirement.get('headcount', 0)
    
    return (
        demand.get('rosteringBasis') == 'outcomeBased' and
        demand.get('minStaffThresholdPercentage') == 100 and
        headcount > 0 and
        available_employees < headcount
    )


def solve_outcome_based_with_slots(ctx: Dict[str, Any], demand: Dict[str, Any], 
                                   requirement: Dict[str, Any], eligible_employees: List[Dict[str, Any]],
                                   shift_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate slots based on headcount, then assign available employees with constraint validation.
    
    Args:
        ctx: Solver context with constraints, planning horizon, etc.
        demand: Demand item dictionary
        requirement: Requirement with headcount and work pattern
        eligible_employees: List of eligible employee dictionaries
        shift_config: Shift configuration with coverage days, times, etc.
        
    Returns:
        Dictionary with 'assignments' (assigned + unassigned slots) and metadata
    """
    headcount = requirement.get('headcount', 0)
    work_pattern = requirement.get('workPattern', [])
    
    # Coverage days - try multiple locations
    # 1. From requirement (daysOfWeek)
    # 2. From demand shifts (coverageDays)
    # 3. Default to all days
    coverage_days = requirement.get('daysOfWeek')
    if not coverage_days:
        shifts = demand.get('shifts', [])
        if shifts:
            coverage_days = shifts[0].get('coverageDays', ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'])
        else:
            coverage_days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
    
    logger.info(f"[SLOT-BASED OUTCOME] Starting slot-based outcome rostering")
    logger.info(f"  Headcount: {headcount}")
    logger.info(f"  Available Employees: {len(eligible_employees)}")
    logger.info(f"  Work Pattern: {work_pattern}")
    logger.info(f"  Coverage Days: {coverage_days}")
    
    # Step 1: Build slots based on headcount (pattern-based like demandBased)
    slots = _build_headcount_slots(
        ctx=ctx,
        demand=demand,
        requirement=requirement,
        headcount=headcount,
        work_pattern=work_pattern,
        coverage_days=coverage_days,
        shift_config=shift_config
    )
    
    logger.info(f"  Created {len(slots)} slots for {headcount} positions")
    
    # Step 2: Generate templates for each employee with constraint validation
    employee_templates = {}
    for employee in eligible_employees:
        template = _generate_employee_template_with_constraints(
            ctx=ctx,
            employee=employee,
            work_pattern=work_pattern,
            coverage_days=coverage_days,
            shift_config=shift_config,
            demand=demand,
            requirement=requirement
        )
        employee_templates[employee['employeeId']] = template
    
    # Step 3: Assign employees to slots with load balancing
    assignments = _assign_employees_to_slots_balanced(
        slots=slots,
        eligible_employees=eligible_employees,
        employee_templates=employee_templates,
        ctx=ctx
    )
    
    assigned_count = len([a for a in assignments if a['status'] == 'ASSIGNED'])
    unassigned_count = len([a for a in assignments if a['status'] == 'UNASSIGNED'])
    
    logger.info(f"  ✓ Assignments: {assigned_count} assigned, {unassigned_count} unassigned")
    
    return {
        'assignments': assignments,
        'metadata': {
            'mode': 'slot_based_outcome',
            'required_positions': headcount,
            'available_employees': len(eligible_employees),
            'total_slots': len(slots),
            'assigned_slots': assigned_count,
            'unassigned_slots': unassigned_count,
            'coverage_percentage': (assigned_count / len(slots) * 100) if slots else 0
        }
    }


def _build_headcount_slots(ctx: Dict[str, Any], demand: Dict[str, Any], requirement: Dict[str, Any],
                           headcount: int, work_pattern: List[str], coverage_days: List[str],
                           shift_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build slots using pattern-based rotation offsets (similar to demandBased).
    
    Each position gets a rotation offset and follows the work pattern.
    """
    from context.engine.slot_builder import build_slots
    from datetime import datetime
    
    slots = []
    planning_ref = ctx.get('planningReference', {})
    
    # Handle both dict and string planningReference
    if isinstance(planning_ref, str):
        # planningReference is sometimes stored as string, get from ctx directly
        planning_horizon = ctx.get('planningHorizon', {})
    else:
        planning_horizon = planning_ref.get('planningHorizon', {})
    
    start_date = datetime.strptime(planning_horizon['startDate'], '%Y-%m-%d').date()
    end_date = datetime.strptime(planning_horizon['endDate'], '%Y-%m-%d').date()
    
    pattern_length = len(work_pattern)
    demand_id = demand.get('demandId', 'UNKNOWN')
    req_id = requirement.get('requirementId', 'UNKNOWN')
    
    # Create slots for each position (rotation offset)
    for position in range(headcount):
        offset = position % pattern_length  # Pattern-based offset
        
        current_date = start_date
        pattern_index = offset
        
        while current_date <= end_date:
            day_name = current_date.strftime('%a')
            
            # Check if day is in coverage
            if day_name not in coverage_days:
                current_date += timedelta(days=1)
                pattern_index = (pattern_index + 1) % pattern_length
                continue
            
            # Check pattern - only create slot if it's a work day
            shift_code = work_pattern[pattern_index]
            
            if shift_code != 'O':  # Not an off day
                slot_id = f"{demand_id}-{req_id}-{shift_code}-P{position}-{current_date.strftime('%Y-%m-%d')}"
                
                # Get shift details
                shift_detail = _get_shift_detail(shift_config, shift_code)
                
                if shift_detail:
                    slot = {
                        'id': slot_id,
                        'demandId': demand_id,
                        'requirementId': req_id,
                        'date': current_date.strftime('%Y-%m-%d'),
                        'shiftCode': shift_code,
                        'position': position,
                        'rotationOffset': offset,
                        'patternDay': pattern_index,
                        'start': shift_detail['start'],
                        'end': shift_detail['end'],
                        'nextDay': shift_detail.get('nextDay', False),
                        'assigned': False,
                        'employeeId': None
                    }
                    slots.append(slot)
            
            current_date += timedelta(days=1)
            pattern_index = (pattern_index + 1) % pattern_length
    
    return slots


def _get_shift_detail(shift_config: Dict[str, Any], shift_code: str) -> Optional[Dict[str, Any]]:
    """Extract shift detail for given shift code."""
    shift_definitions = shift_config.get('shiftDefinitions', shift_config.get('shiftDetails', []))
    
    for detail in shift_definitions:
        if detail.get('shiftCode') == shift_code:
            return {
                'start': detail.get('startTime') or detail.get('start', '08:00:00'),
                'end': detail.get('endTime') or detail.get('end', '20:00:00'),
                'nextDay': detail.get('nextDay', False)
            }
    
    return None


def _generate_employee_template_with_constraints(ctx: Dict[str, Any], employee: Dict[str, Any],
                                                 work_pattern: List[str], coverage_days: List[str],
                                                 shift_config: Dict[str, Any], demand: Dict[str, Any],
                                                 requirement: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a constraint-validated work template for an employee.
    
    Uses the template roster validation logic to determine which days
    the employee CAN work while respecting all constraints.
    """
    from context.engine.template_roster import _generate_validated_template
    from datetime import datetime
    
    # Get planning horizon
    planning_ref = ctx.get('planningReference', {})
    
    # Handle both dict and string planningReference
    if isinstance(planning_ref, str):
        planning_horizon = ctx.get('planningHorizon', {})
    else:
        planning_horizon = planning_ref.get('planningHorizon', {})
    
    start_date = datetime.strptime(planning_horizon['startDate'], '%Y-%m-%d').date()
    end_date = datetime.strptime(planning_horizon['endDate'], '%Y-%m-%d').date()
    
    # Get shift details
    shift_definitions = shift_config.get('shiftDefinitions', [])
    shift_code = requirement.get('shiftCode', 'D')
    shift_details = next((s for s in shift_definitions if s.get('shiftCode') == shift_code), {})
    
    # Generate template with constraint validation
    template_result = _generate_validated_template(
        template_emp=employee,
        work_pattern=work_pattern,
        start_date=start_date,
        end_date=end_date,
        shift_details=shift_details,
        ctx=ctx,
        demand=demand,
        requirement=requirement,
        coverage_days=coverage_days
    )
    
    # Extract valid work days
    valid_work_days = set()
    for date_str, day_info in template_result.items():
        if day_info.get('assigned', False):
            valid_work_days.add(date_str)
    
    return {
        'valid_work_days': valid_work_days,
        'template_result': template_result
    }


def _assign_employees_to_slots_balanced(slots: List[Dict[str, Any]], 
                                       eligible_employees: List[Dict[str, Any]],
                                       employee_templates: Dict[str, Dict[str, Any]],
                                       ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Assign employees to slots with load balancing and constraint compliance.
    
    Strategy:
    1. Sort slots by date
    2. For each slot, find eligible employees who can work that day
    3. Pick employee with lowest current workload
    4. Respect constraints via template validation
    """
    assignments = []
    employee_workload = {emp['employeeId']: 0 for emp in eligible_employees}
    employee_assignments = {emp['employeeId']: [] for emp in eligible_employees}
    
    # Sort slots by date for chronological assignment
    sorted_slots = sorted(slots, key=lambda s: s['date'])
    
    for slot in sorted_slots:
        slot_date = slot['date']
        slot_shift_code = slot['shiftCode']
        
        # Find employees who can work this day (based on template validation)
        eligible_for_slot = []
        for emp in eligible_employees:
            emp_id = emp['employeeId']
            template = employee_templates.get(emp_id, {})
            valid_days = template.get('valid_work_days', set())
            
            # Check if employee can work this date
            if slot_date in valid_days:
                # Check unavailability
                unavailable_dates = [u.get('date') for u in emp.get('unavailability', [])]
                if slot_date not in unavailable_dates:
                    eligible_for_slot.append(emp)
        
        # Assign to employee with lowest workload
        if eligible_for_slot:
            # Sort by current workload (ascending)
            eligible_for_slot.sort(key=lambda e: employee_workload[e['employeeId']])
            selected_employee = eligible_for_slot[0]
            emp_id = selected_employee['employeeId']
            
            # Create assignment
            assignment = {
                'slotId': slot['id'],
                'demandId': slot['demandId'],
                'requirementId': slot['requirementId'],
                'employeeId': emp_id,
                'date': slot_date,
                'startDateTime': f"{slot_date}T{slot['start']}",
                'endDateTime': f"{slot_date}T{slot['end']}" if not slot['nextDay'] 
                              else f"{(datetime.strptime(slot_date, '%Y-%m-%d').date() + timedelta(days=1)).strftime('%Y-%m-%d')}T{slot['end']}",
                'shiftCode': slot_shift_code,
                'position': slot['position'],
                'rotationOffset': slot['rotationOffset'],
                'patternDay': slot['patternDay'],
                'status': 'ASSIGNED'
            }
            
            assignments.append(assignment)
            employee_workload[emp_id] += 1
            employee_assignments[emp_id].append(slot_date)
            slot['assigned'] = True
            slot['employeeId'] = emp_id
        else:
            # No eligible employee - mark as unassigned
            assignment = {
                'slotId': slot['id'],
                'demandId': slot['demandId'],
                'requirementId': slot['requirementId'],
                'employeeId': None,
                'date': slot_date,
                'shiftCode': slot_shift_code,
                'position': slot['position'],
                'rotationOffset': slot['rotationOffset'],
                'patternDay': slot['patternDay'],
                'status': 'UNASSIGNED',
                'reason': f"No eligible employees available (constraints or unavailability)"
            }
            assignments.append(assignment)
    
    # Log workload distribution
    logger.info(f"  Workload distribution:")
    for emp_id, count in employee_workload.items():
        logger.info(f"    {emp_id}: {count} days")
    
    return assignments
