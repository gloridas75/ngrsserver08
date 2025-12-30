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
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


# ============================================================================
# QUALIFICATION/LICENSE VALIDATION (C7 Logic)
# ============================================================================

def _has_valid_qualification(emp_licenses: Dict[str, str], qual_code: Any, 
                            slot_date: date) -> bool:
    """Check if employee has a valid (non-expired) qualification.
    
    Args:
        emp_licenses: Dict mapping qual codes to expiry dates
        qual_code: Qualification code to check (int or str)
        slot_date: Date of the shift
        
    Returns:
        bool: True if employee has the qualification and it's not expired
    """
    # Convert qual_code to string for consistent comparison
    qual_key = str(qual_code)
    
    if qual_key not in emp_licenses:
        return False
    
    expiry_date_str = emp_licenses[qual_key]
    if not expiry_date_str:
        # No expiry date means qualification never expires
        return True
        
    try:
        expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
        # Qualification is valid if shift date is on or before expiry date
        return slot_date <= expiry_date
    except (ValueError, AttributeError):
        # Failed to parse expiry date - treat as invalid
        return False


def _evaluate_qualification_groups(emp_licenses: Dict[str, str], 
                                   qual_groups: List[Dict[str, Any]], 
                                   slot_date: date) -> bool:
    """Check if employee meets all qualification group requirements.
    
    Args:
        emp_licenses: Dict mapping qual codes to expiry dates for employee
        qual_groups: List of qualification groups (normalized format)
        slot_date: Date of the shift
        
    Returns:
        bool: True if employee satisfies all groups
    """
    if not qual_groups:
        return True  # No requirements
    
    for group in qual_groups:
        match_type = group.get('matchType', 'ALL')
        required_quals = group.get('qualifications', [])
        
        if not required_quals:
            continue  # Empty group, skip
        
        if match_type == 'ALL':
            # Employee must have ALL qualifications in this group
            for qual in required_quals:
                if not _has_valid_qualification(emp_licenses, qual, slot_date):
                    return False  # Missing or expired qualification
        
        elif match_type == 'ANY':
            # Employee must have AT LEAST ONE qualification in this group
            has_any = False
            for qual in required_quals:
                if _has_valid_qualification(emp_licenses, qual, slot_date):
                    has_any = True
                    break
            
            if not has_any:
                return False  # No valid qualification from this group
        
        else:
            # Unknown match type - treat as ALL for safety
            for qual in required_quals:
                if not _has_valid_qualification(emp_licenses, qual, slot_date):
                    return False
    
    return True  # All groups satisfied


def _build_employee_licenses_map(employees: List[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    """Build employee license map: emp_id -> {license_code -> expiry_date}.
    
    Args:
        employees: List of employee dictionaries
        
    Returns:
        Dict mapping employee IDs to their qualification/license maps
    """
    employee_licenses = {}
    
    for emp in employees:
        emp_id = emp.get('employeeId')
        licenses = {}
        
        # Check 'licenses' field (old schema)
        for lic in emp.get('licenses', []):
            if isinstance(lic, dict):
                code = lic.get('code')
                expiry = lic.get('expiryDate')
                if code:
                    # Convert to string for consistent comparison
                    licenses[str(code)] = expiry
        
        # Also check 'qualifications' field (v0.70+ schema)
        for qual in emp.get('qualifications', []):
            if isinstance(qual, dict):
                code = qual.get('code')
                expiry = qual.get('expiryDate')
                if code:
                    # Convert to string for consistent comparison
                    licenses[str(code)] = expiry
            elif isinstance(qual, (str, int)):
                # Simple format: just a code without expiry
                licenses[str(qual)] = None
        
        employee_licenses[emp_id] = licenses
    
    return employee_licenses


def _check_employee_qualifications(employee: Dict[str, Any], 
                                   requirement: Dict[str, Any],
                                   slot_date: date,
                                   employee_licenses_map: Dict[str, Dict[str, str]]) -> bool:
    """Check if employee meets qualification requirements for a slot.
    
    Args:
        employee: Employee dictionary
        requirement: Requirement dictionary with requiredQualifications
        slot_date: Date of the shift
        employee_licenses_map: Pre-built license map for all employees
        
    Returns:
        bool: True if employee meets all qualification requirements
    """
    emp_id = employee.get('employeeId')
    emp_licenses = employee_licenses_map.get(emp_id, {})
    
    # Get required qualifications from requirement
    required_quals = requirement.get('requiredQualifications', [])
    
    if not required_quals:
        return True  # No qualification requirements
    
    # Normalize to group format if needed
    if required_quals and isinstance(required_quals[0], dict) and 'qualifications' in required_quals[0]:
        # Already in group format
        qual_groups = required_quals
    elif required_quals and isinstance(required_quals[0], (str, int)):
        # Old format - convert to group with ALL logic
        qual_groups = [{
            'groupId': 'default',
            'matchType': 'ALL',
            'qualifications': required_quals
        }]
    else:
        # Empty or invalid
        return True
    
    # Evaluate qualification groups
    return _evaluate_qualification_groups(emp_licenses, qual_groups, slot_date)


# ============================================================================
# RANK/PRODUCT TYPE VALIDATION (C11 Logic)
# ============================================================================

def _check_rank_product_match(employee: Dict[str, Any], 
                              requirement: Dict[str, Any]) -> bool:
    """Check if employee's rank and product type match requirement.
    
    Args:
        employee: Employee dictionary with rankId and productTypeId
        requirement: Requirement dictionary with rankIds and productTypeId
        
    Returns:
        bool: True if employee matches rank and product requirements
    """
    emp_rank = employee.get('rankId')
    emp_product = employee.get('productTypeId')
    
    # Check product type match
    req_product = requirement.get('productTypeId')
    if req_product and emp_product != req_product:
        return False
    
    # Check rank match (OR logic - employee must match ANY of the required ranks)
    req_ranks = requirement.get('rankIds', [])
    if not req_ranks:
        # Also check singular rankId for backward compatibility
        req_ranks = [requirement.get('rankId')] if requirement.get('rankId') else []
    
    if req_ranks and emp_rank not in req_ranks:
        return False
    
    return True


def should_use_slot_based_outcome(demand: Dict[str, Any], requirement: Dict[str, Any], 
                                   available_employees: int) -> bool:
    """
    Determine if slot-based outcome mode should be used.
    
    UPDATED LOGIC: Always use slot-based mode for outcomeBased rostering.
    This ensures empty slots are created even when insufficient employees are available.
    
    Conditions:
    1. rosteringBasis = "outcomeBased"
    2. minStaffThresholdPercentage = 100 (optional check)
    3. headcount > 0 (explicitly set)
    
    OLD CONDITION (REMOVED): available_employees < headcount
    REASON: Template-based rostering fails when insufficient employees.
            Slot-based always creates slots and leaves them unassigned when needed.
    
    Args:
        demand: Demand item dictionary
        requirement: Requirement dictionary
        available_employees: Number of available employees (not used in decision)
        
    Returns:
        True if slot-based mode should be used
    """
    headcount = requirement.get('headcount', 0)
    
    # Check rosteringBasis - can be at demand or requirement level
    rostering_basis = requirement.get('rosteringBasis') or demand.get('rosteringBasis')
    min_threshold = requirement.get('minStaffThresholdPercentage') or demand.get('minStaffThresholdPercentage', 0)
    
    # ALWAYS use slot-based mode when outcomeBased (creates empty slots when needed)
    return (
        rostering_basis == 'outcomeBased' and
        min_threshold == 100 and
        headcount > 0
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
    
    # Step 0: Build employee licenses map for qualification checking
    all_employees = ctx.get('employees', [])
    employee_licenses_map = _build_employee_licenses_map(all_employees)
    
    # Check if any employees have required qualifications
    required_quals = requirement.get('requiredQualifications', [])
    if required_quals:
        qualified_count = sum(
            1 for emp in eligible_employees 
            if _check_rank_product_match(emp, requirement) and 
               _check_employee_qualifications(emp, requirement, 
                                             datetime.now().date(), 
                                             employee_licenses_map)
        )
        logger.info(f"  Qualification requirements: {required_quals}")
        logger.info(f"  Employees with valid qualifications: {qualified_count}/{len(eligible_employees)}")
        
        if qualified_count == 0:
            logger.warning(f"  ⚠️  NO EMPLOYEES have required qualifications! All slots will be unassigned.")
    
    # Step 1: Build slots based on headcount (pattern-based like demandBased)
    slot_result = _build_headcount_slots(
        ctx=ctx,
        demand=demand,
        requirement=requirement,
        headcount=headcount,
        work_pattern=work_pattern,
        coverage_days=coverage_days,
        shift_config=shift_config
    )
    
    slots = slot_result['slots']
    positions_created = slot_result['positions_created']
    
    logger.info(f"  Created {len(slots)} slots for {positions_created} positions (headcount={headcount})")
    
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
        requirement=requirement,
        employee_licenses_map=employee_licenses_map,
        ctx=ctx
    )
    
    assigned_count = len([a for a in assignments if a['status'] == 'ASSIGNED'])
    unassigned_count = len([a for a in assignments if a['status'] == 'UNASSIGNED'])
    
    logger.info(f"  ✓ Assignments: {assigned_count} assigned, {unassigned_count} unassigned")
    
    return {
        'assignments': assignments,
        'metadata': {
            'mode': 'slot_based_outcome',
            'headcount': headcount,  # Number of positions specified in input
            'positions_created': positions_created,  # Same as headcount (for backward compatibility)
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
    Build slots for headcount positions on EVERY coverage day (like demandBased).
    
    CRITICAL: headcount = number of positions needed per day.
    workPattern is for EMPLOYEE ASSIGNMENT, not slot creation.
    
    Like demandBased slot_builder.py, we create:
    - headcount positions (e.g., 5 positions)
    - For EACH position, create slots for EVERY day in coverage
    - Result: headcount slots per day (e.g., 5 positions × every day = 5 slots/day)
    
    Example: headcount=5, coverageDays=all 7 days
      - Creates 5 positions (0,1,2,3,4)
      - Each position gets slots for ALL days (Mon-Sun)
      - Result: 5 slots per day, every day
      - workPattern [D,D,D,D,O,O] is used by employees for their rotation
    """
    from context.engine.slot_builder import build_slots
    from datetime import datetime
    import math
    
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
    
    # HEADCOUNT = NUMBER OF POSITIONS NEEDED PER DAY
    positions_needed = headcount
    
    logger.info(f"[SLOT-BASED] Creating {positions_needed} positions (headcount={headcount})")
    logger.info(f"[SLOT-BASED] Each position gets slots for EVERY day in coverage")
    logger.info(f"[SLOT-BASED] Expected: {headcount} slots per day")
    logger.info(f"[SLOT-BASED] Work pattern {work_pattern} is for employee assignment only")
    
    demand_id = demand.get('demandId', 'UNKNOWN')
    req_id = requirement.get('requirementId', 'UNKNOWN')
    
    # Get shift code from pattern (first non-O code)
    shift_code = next((code for code in work_pattern if code != 'O'), 'D')
    
    # Create slots for each position on EVERY coverage day
    for position in range(positions_needed):
        current_date = start_date
        
        while current_date <= end_date:
            day_name = current_date.strftime('%a')
            
            # Check if day is in coverage
            if day_name not in coverage_days:
                current_date += timedelta(days=1)
                continue
            
            # Create slot for this position on this day
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
                    'rotationOffset': position % pattern_length,  # For metadata
                    'patternDay': None,  # Not used in slot creation
                    'start': shift_detail['start'],
                    'end': shift_detail['end'],
                    'nextDay': shift_detail.get('nextDay', False),
                    'assigned': False,
                    'employeeId': None
                }
                slots.append(slot)
            
            current_date += timedelta(days=1)
    
    return {
        'slots': slots,
        'positions_created': positions_needed
    }


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
    
    # Extract valid work days (exclude off days AND unavailable dates)
    valid_work_days = set()
    
    # Get employee unavailability (handle both formats)
    unavailability = employee.get('unavailability', [])
    unavailable_dates_set = set()
    for u in unavailability:
        if isinstance(u, dict):
            # Format: [{"date": "2026-01-05", ...}]
            date_val = u.get('date') or u.get('startDate')
            if date_val:
                unavailable_dates_set.add(date_val)
        elif isinstance(u, str):
            # Format: ["2026-01-05", "2026-01-26"]
            unavailable_dates_set.add(u)
    
    for date_str, day_info in template_result.items():
        # Only include days where:
        # 1. assigned == True (passed validation)
        # 2. is_work_day == True (not an off day)
        # 3. OR has an actual assignment dict
        # 4. NOT in unavailable dates
        if (day_info.get('assigned', False) and (
            day_info.get('is_work_day', False) or day_info.get('assignment') is not None
        ) and date_str not in unavailable_dates_set):
            valid_work_days.add(date_str)
    
    return {
        'valid_work_days': valid_work_days,
        'template_result': template_result
    }


def _assign_employees_to_slots_balanced(slots: List[Dict[str, Any]], 
                                       eligible_employees: List[Dict[str, Any]],
                                       employee_templates: Dict[str, Dict[str, Any]],
                                       requirement: Dict[str, Any],
                                       employee_licenses_map: Dict[str, Dict[str, str]],
                                       ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Assign employees to slots with load balancing and constraint compliance.
    
    Strategy:
    1. Sort slots by date
    2. For each slot, find eligible employees who can work that day
    3. Check qualifications, rank, and product type match (C7 + C11)
    4. Exclude employees already assigned on that date (one position per day)
    5. Pick employee with lowest current workload
    6. Respect constraints via template validation
    """
    assignments = []
    employee_workload = {emp['employeeId']: 0 for emp in eligible_employees}
    employee_assignments = {emp['employeeId']: [] for emp in eligible_employees}
    
    # Track which employees are assigned on each date (prevent double-booking)
    employees_assigned_by_date = defaultdict(set)
    
    # Track filtering statistics
    filtered_by_qualification = 0
    filtered_by_rank_product = 0
    
    # Sort slots by date for chronological assignment
    sorted_slots = sorted(slots, key=lambda s: s['date'])
    
    for slot in sorted_slots:
        slot_date = slot['date']
        slot_date_obj = datetime.strptime(slot_date, '%Y-%m-%d').date()
        slot_shift_code = slot['shiftCode']
        
        # Find employees who can work this day (based on template validation)
        eligible_for_slot = []
        for emp in eligible_employees:
            emp_id = emp['employeeId']
            
            # CRITICAL: Check if employee is already assigned on this date
            if emp_id in employees_assigned_by_date[slot_date]:
                continue  # Skip - already assigned to another position today
            
            # CHECK 1: Rank and Product Type Match (C11)
            if not _check_rank_product_match(emp, requirement):
                filtered_by_rank_product += 1
                continue
            
            # CHECK 2: Qualifications/Licenses (C7)
            if not _check_employee_qualifications(emp, requirement, slot_date_obj, employee_licenses_map):
                filtered_by_qualification += 1
                continue
            
            template = employee_templates.get(emp_id, {})
            valid_days = template.get('valid_work_days', set())
            
            # Check if employee can work this date
            if slot_date in valid_days:
                # Check unavailability (handle both formats: array of strings or array of dicts)
                unavailability = emp.get('unavailability', [])
                unavailable_dates = []
                for u in unavailability:
                    if isinstance(u, dict):
                        # Format: [{"date": "2026-01-05", ...}]
                        date_val = u.get('date') or u.get('startDate')
                        if date_val:
                            unavailable_dates.append(date_val)
                    elif isinstance(u, str):
                        # Format: ["2026-01-05", "2026-01-26"]
                        unavailable_dates.append(u)
                
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
            
            # Track that this employee is now assigned on this date
            employees_assigned_by_date[slot_date].add(emp_id)
            
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
    
    # Log constraint filtering statistics
    logger.info(f"  Constraint filtering statistics:")
    logger.info(f"    Filtered by qualifications (C7): {filtered_by_qualification} slot-employee pairs")
    logger.info(f"    Filtered by rank/product (C11): {filtered_by_rank_product} slot-employee pairs")
    
    # Log workload distribution
    logger.info(f"  Workload distribution:")
    for emp_id, count in employee_workload.items():
        logger.info(f"    {emp_id}: {count} days")
    
    return assignments
