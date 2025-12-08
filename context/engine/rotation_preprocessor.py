"""
Rotation Offset Pre-Processor for NGRS Solver

This module implements intelligent rotation offset assignment BEFORE CP-SAT solving.
Based on greedy sequential filling algorithm (user's Excel method) with research-backed
optimizations for cyclic scheduling with headcount constraints.

Key Features:
1. Detects all-zero rotation offset scenario (synchronized rest days)
2. Consolidates identical work patterns across multiple demands
3. Greedy calendar simulation: fills employees until headcount cap
4. Flexible gap-filling: tries all offsets before marking as truly flexible
5. Pattern affinity tracking: helps CP-SAT group assignments efficiently

Author: GitHub Copilot + User Algorithm Design
Date: 2025-12-06
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Set
import logging

logger = logging.getLogger(__name__)


def preprocess_rotation_offsets(input_data: dict) -> dict:
    """
    Main entry point: Pre-process rotation offsets before CP-SAT solving.
    
    Detects synchronized rest days (all offset=0) and applies intelligent
    offset distribution based on work pattern requirements.
    
    Args:
        input_data: Full input JSON dictionary
        
    Returns:
        Modified input_data with corrected rotationOffset values and metadata
    """
    
    # Skip if fixedRotationOffset is false (solver will optimize)
    if not input_data.get('fixedRotationOffset', True):
        logger.info("fixedRotationOffset=false, skipping pre-processing")
        return input_data
    
    # Check if all employees have offset=0 (synchronized rest days)
    employees = input_data.get('employees', [])
    if not employees:
        logger.warning("No employees found in input")
        return input_data
    
    offset_counts = {}
    for emp in employees:
        offset = emp.get('rotationOffset', 0)
        offset_counts[offset] = offset_counts.get(offset, 0) + 1
    
    # Only proceed if all employees have same offset (typically 0)
    if len(offset_counts) > 1:
        logger.info(f"Employees already have varied offsets: {offset_counts}")
        return input_data
    
    single_offset = list(offset_counts.keys())[0]
    logger.info(f"⚠️  All {len(employees)} employees have rotationOffset={single_offset}")
    logger.info("Starting rotation offset pre-processing...")
    
    # Extract and consolidate work patterns
    pattern_groups = extract_consolidated_patterns(input_data)
    
    if not pattern_groups:
        logger.warning("No work patterns found in demands")
        return input_data
    
    logger.info(f"Identified {len(pattern_groups)} unique work pattern(s)")
    
    # Process each pattern group
    pattern_results = []
    for pattern_info in pattern_groups:
        result = simulate_pattern_filling(
            work_pattern=pattern_info['workPattern'],
            combined_headcount=pattern_info['combined_headcount'],
            coverage_days=pattern_info['coverage_days'],
            start_date=input_data['planningHorizon']['startDate'],
            end_date=input_data['planningHorizon']['endDate'],
            available_employees=len(employees),
            pattern_info=pattern_info
        )
        pattern_results.append(result)
    
    # Assign offsets to actual employees
    input_data = assign_offsets_to_employees(input_data, pattern_results)
    
    # Log summary
    log_preprocessing_summary(pattern_results)
    
    return input_data


def extract_consolidated_patterns(input_data: dict) -> List[dict]:
    """
    Extract unique work patterns and consolidate identical patterns.
    Combines headcounts when same pattern appears in multiple demands.
    
    Validates that workPattern length matches coverage requirements.
    
    Returns:
        List of consolidated pattern dictionaries with combined headcounts
    """
    
    pattern_map = {}
    demand_items = input_data.get('demandItems', [])
    
    for demand in demand_items:
        demand_id = demand.get('demandId')
        shifts = demand.get('shifts', [])
        
        if not shifts:
            continue
        
        # Get coverage days from first shift (assuming uniform per demand)
        coverage_days = set(shifts[0].get('coverageDays', []))
        
        for req in demand.get('requirements', []):
            work_pattern = req.get('workPattern')
            
            if not work_pattern:
                continue
            
            # VALIDATION: Check pattern length vs coverage days
            pattern_length = len(work_pattern)
            coverage_length = len(coverage_days)
            req_id = req.get('requirementId', 'unknown')
            
            if pattern_length != coverage_length:
                logger.warning(
                    f"\n{'='*80}\n"
                    f"⚠️  PATTERN/COVERAGE MISMATCH DETECTED\n"
                    f"{'='*80}\n"
                    f"Requirement ID: {req_id}\n"
                    f"Demand ID: {demand_id}\n"
                    f"Pattern Length: {pattern_length} days {work_pattern}\n"
                    f"Coverage Days: {coverage_length} days {sorted(coverage_days)}\n"
                    f"\n"
                    f"Issue: Pattern has {pattern_length - coverage_length} extra day(s) that will never be used.\n"
                    f"This can cause suboptimal offset distribution.\n"
                    f"\n"
                    f"Action: Auto-truncating pattern to match coverage length.\n"
                    f"Original Pattern: {work_pattern}\n"
                    f"Truncated Pattern: {work_pattern[:coverage_length]}\n"
                    f"{'='*80}\n"
                )
                # Auto-truncate to match coverage
                work_pattern = work_pattern[:coverage_length]
            
            pattern_key = tuple(work_pattern)
            
            if pattern_key not in pattern_map:
                pattern_map[pattern_key] = {
                    'pattern_key': pattern_key,
                    'workPattern': work_pattern,
                    'combined_headcount': 0,
                    'coverage_days': coverage_days.copy(),
                    'demand_ids': [],
                    'requirements': []
                }
            
            # Combine headcounts
            pattern_map[pattern_key]['combined_headcount'] += req.get('headcount', 0)
            pattern_map[pattern_key]['demand_ids'].append(demand_id)
            pattern_map[pattern_key]['requirements'].append({
                'demandId': demand_id,
                'requirementId': req.get('requirementId'),
                'headcount': req.get('headcount', 0),
                'productTypeId': req.get('productTypeId'),
                'rankId': req.get('rankId')
            })
            
            # Intersect coverage days (most restrictive wins)
            pattern_map[pattern_key]['coverage_days'].intersection_update(coverage_days)
    
    return list(pattern_map.values())


def simulate_pattern_filling(
    work_pattern: List[str],
    combined_headcount: int,
    coverage_days: Set[str],
    start_date: str,
    end_date: str,
    available_employees: int,
    pattern_info: dict
) -> dict:
    """
    Greedy sequential filling simulation (user's Excel method).
    
    Algorithm:
    1. Generate calendar of work days (only coverageDays)
    2. Add employee 0 (offset=0), simulate contribution
    3. Add employee 1 (offset=1), simulate contribution
    4. Continue until adding next employee causes ANY day > headcount
    5. STOP = strict employees discovered
    6. Continue with flexible gap-filling for remaining employees
    
    Returns:
        Dictionary with strict/flexible employee assignments and metadata
    """
    
    logger.info(f"\n{'='*80}")
    logger.info(f"Pattern: {work_pattern}")
    logger.info(f"Headcount Required: {combined_headcount}")
    logger.info(f"Coverage Days: {sorted(coverage_days)}")
    
    # Generate coverage calendar
    calendar = generate_coverage_calendar(start_date, end_date, coverage_days)
    logger.info(f"Calendar Days: {len(calendar)} days")
    
    daily_coverage = {day: 0 for day in calendar}
    pattern_length = len(work_pattern)
    
    strict_employees = []
    current_offset = 0
    employee_index = 0
    
    # PHASE 1: STRICT FILLING (Greedy until overfill)
    logger.info("\n--- PHASE 1: STRICT PATTERN ADHERENCE ---")
    
    while employee_index < available_employees:
        temp_coverage = daily_coverage.copy()
        
        # Simulate this employee's contribution
        for day_index, calendar_day in enumerate(calendar):
            pattern_position = (day_index + current_offset) % pattern_length
            
            if work_pattern[pattern_position] != 'O':  # Working day
                temp_coverage[calendar_day] += 1
        
        # Check: Would this cause any day to exceed headcount?
        max_coverage = max(temp_coverage.values())
        
        if max_coverage <= combined_headcount:
            # ACCEPT: This employee fits within strict adherence
            daily_coverage = temp_coverage
            strict_employees.append({
                'index': employee_index,
                'rotationOffset': current_offset
            })
            employee_index += 1
            current_offset = (current_offset + 1) % pattern_length
        else:
            # STOP: Strict phase complete
            logger.info(f"Strict phase stopped at employee {employee_index}")
            logger.info(f"Adding next employee would cause max_coverage={max_coverage} > headcount={combined_headcount}")
            break
    
    min_coverage_strict = min(daily_coverage.values()) if daily_coverage else 0
    max_coverage_strict = max(daily_coverage.values()) if daily_coverage else 0
    
    logger.info(f"Strict Employees: {len(strict_employees)}")
    logger.info(f"Coverage Range: {min_coverage_strict} - {max_coverage_strict} (target: {combined_headcount})")
    
    # PHASE 2: FLEXIBLE GAP-FILLING
    logger.info("\n--- PHASE 2: FLEXIBLE GAP FILLING ---")
    
    flexible_candidates = []
    coverage_complete = (min_coverage_strict >= combined_headcount)
    
    if not coverage_complete and employee_index < available_employees:
        flexible_candidates = fill_coverage_gaps(
            work_pattern=work_pattern,
            combined_headcount=combined_headcount,
            daily_coverage=daily_coverage,
            calendar=calendar,
            remaining_employees=available_employees - employee_index,
            start_offset=current_offset,
            strict_count=len(strict_employees)
        )
        employee_index += len(flexible_candidates)
    
    min_coverage_final = min(daily_coverage.values()) if daily_coverage else 0
    max_coverage_final = max(daily_coverage.values()) if daily_coverage else 0
    coverage_complete = (min_coverage_final >= combined_headcount)
    
    # PHASE 3: TRULY FLEXIBLE (Can't follow pattern)
    truly_flexible_count = available_employees - employee_index
    
    logger.info(f"\nFlexible Candidates: {len(flexible_candidates)}")
    logger.info(f"Coverage After Flexible: {min_coverage_final} - {max_coverage_final}")
    logger.info(f"Truly Flexible (offset=-1): {truly_flexible_count}")
    logger.info(f"Coverage Complete: {coverage_complete}")
    
    # Calculate ratios
    total_assigned = len(strict_employees) + len(flexible_candidates)
    strict_ratio = len(strict_employees) / total_assigned if total_assigned > 0 else 0
    
    return {
        'pattern_info': pattern_info,
        'workPattern': work_pattern,
        'combined_headcount': combined_headcount,
        'strict_employees': strict_employees,
        'strict_count': len(strict_employees),
        'flexible_candidates': flexible_candidates,
        'flexible_count': len(flexible_candidates),
        'truly_flexible_count': truly_flexible_count,
        'coverage_complete': coverage_complete,
        'daily_coverage': daily_coverage,
        'min_coverage': min_coverage_final,
        'max_coverage': max_coverage_final,
        'strict_ratio': strict_ratio,
        'pattern_key': pattern_info['pattern_key']
    }


def fill_coverage_gaps(
    work_pattern: List[str],
    combined_headcount: int,
    daily_coverage: dict,
    calendar: list,
    remaining_employees: int,
    start_offset: int,
    strict_count: int
) -> List[dict]:
    """
    Flexible gap-filling phase: Try all possible offsets before giving up.
    
    User's insight: "try out to fill other employees with different rotation 
    offsets, finally when you can't assign accord to work pattern, 
    consider the remaining as floating offset"
    
    Returns:
        List of flexible employee assignments with best-fit offsets
    """
    
    pattern_length = len(work_pattern)
    flexible_candidates = []
    
    for emp_index in range(remaining_employees):
        # Try all possible offsets for this employee
        best_offset = None
        best_contribution = 0
        best_temp_coverage = None
        
        for trial_offset in range(pattern_length):
            contribution = 0
            violates = False
            
            temp_coverage = daily_coverage.copy()
            
            for day_index, calendar_day in enumerate(calendar):
                pattern_position = (day_index + trial_offset) % pattern_length
                
                if work_pattern[pattern_position] != 'O':
                    temp_coverage[calendar_day] += 1
                    
                    # Check if this helps fill gap without overfilling
                    if temp_coverage[calendar_day] > combined_headcount:
                        violates = True
                        break
                    
                    # Count contribution to underfilled days
                    if daily_coverage[calendar_day] < combined_headcount:
                        contribution += 1
            
            if not violates and contribution > best_contribution:
                best_offset = trial_offset
                best_contribution = contribution
                best_temp_coverage = temp_coverage
        
        if best_offset is not None and best_contribution > 0:
            # Accept this employee with best_offset
            daily_coverage.update(best_temp_coverage)
            
            flexible_candidates.append({
                'index': strict_count + len(flexible_candidates),
                'rotationOffset': best_offset,
                'contribution': best_contribution
            })
        else:
            # Cannot assign with any offset following pattern
            # Remaining will be truly flexible (offset=-1)
            logger.info(f"No valid offset found for employee {strict_count + len(flexible_candidates)}, stopping flexible phase")
            break
    
    return flexible_candidates


def generate_coverage_calendar(
    start_date: str,
    end_date: str,
    coverage_days: Set[str]
) -> List[str]:
    """
    Generate list of calendar dates that match coverage days.
    Only includes days specified in coverageDays (Mon-Fri vs 7-day).
    
    Returns:
        List of date strings in YYYY-MM-DD format
    """
    
    day_mapping = {
        'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3,
        'Fri': 4, 'Sat': 5, 'Sun': 6
    }
    
    allowed_weekdays = {day_mapping[day] for day in coverage_days if day in day_mapping}
    
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    calendar = []
    current = start
    
    while current <= end:
        if current.weekday() in allowed_weekdays:
            calendar.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)
    
    return calendar


def assign_offsets_to_employees(input_data: dict, pattern_results: List[dict]) -> dict:
    """
    Assign calculated rotation offsets to actual employees.
    
    Strategy: Round-robin assignment across pattern groups.
    Marks employees with metadata for CP-SAT optimization:
    - _pattern_group: Which work pattern this employee is assigned to
    - _strict_adherence: Whether this employee has strict pattern adherence
    
    Args:
        input_data: Full input JSON
        pattern_results: Results from simulate_pattern_filling for each pattern
        
    Returns:
        Modified input_data with updated employee rotationOffset values
    """
    
    employees = input_data['employees']
    employee_index = 0
    
    metadata = {
        'preprocessing_applied': True,
        'pattern_analysis': []
    }
    
    for result in pattern_results:
        pattern_key = str(result['pattern_key'])
        
        # Store metadata for reporting
        metadata['pattern_analysis'].append({
            'workPattern': result['workPattern'],
            'combined_headcount': result['combined_headcount'],
            'strict_employees_needed': result['strict_count'],
            'flexible_employees_needed': result['flexible_count'],
            'truly_flexible_needed': result['truly_flexible_count'],
            'strict_ratio': f"{result['strict_ratio']*100:.1f}%",
            'coverage_complete': result['coverage_complete'],
            'min_coverage': result['min_coverage'],
            'max_coverage': result['max_coverage']
        })
        
        # Assign strict employees
        for strict_emp in result['strict_employees']:
            if employee_index < len(employees):
                employees[employee_index]['rotationOffset'] = strict_emp['rotationOffset']
                employees[employee_index]['_pattern_group'] = pattern_key
                employees[employee_index]['_strict_adherence'] = True
                employee_index += 1
        
        # Assign flexible candidates
        for flex_emp in result['flexible_candidates']:
            if employee_index < len(employees):
                employees[employee_index]['rotationOffset'] = flex_emp['rotationOffset']
                employees[employee_index]['_pattern_group'] = pattern_key
                employees[employee_index]['_strict_adherence'] = False
                employees[employee_index]['_contribution_score'] = flex_emp.get('contribution', 0)
                employee_index += 1
        
        # Assign truly flexible (offset=-1 for floating assignment)
        for i in range(result['truly_flexible_count']):
            if employee_index < len(employees):
                employees[employee_index]['rotationOffset'] = -1  # Floating
                employees[employee_index]['_pattern_group'] = pattern_key
                employees[employee_index]['_strict_adherence'] = False
                employees[employee_index]['_truly_flexible'] = True
                employee_index += 1
    
    input_data['_preprocessing_metadata'] = metadata
    
    logger.info(f"\n✅ Assigned rotation offsets to {employee_index} employees")
    
    return input_data


def log_preprocessing_summary(pattern_results: List[dict]) -> None:
    """
    Log comprehensive summary of preprocessing results.
    """
    
    logger.info(f"\n{'='*80}")
    logger.info("PREPROCESSING SUMMARY")
    logger.info(f"{'='*80}")
    
    for idx, result in enumerate(pattern_results, 1):
        logger.info(f"\nPattern {idx}: {result['workPattern']}")
        logger.info(f"  Combined Headcount: {result['combined_headcount']}")
        logger.info(f"  Strict Employees: {result['strict_count']}")
        logger.info(f"  Flexible Employees: {result['flexible_count']}")
        logger.info(f"  Truly Flexible: {result['truly_flexible_count']}")
        logger.info(f"  Strict Ratio: {result['strict_ratio']*100:.1f}%")
        logger.info(f"  Coverage: {result['min_coverage']} - {result['max_coverage']}")
        logger.info(f"  Coverage Complete: {result['coverage_complete']}")
    
    logger.info(f"\n{'='*80}\n")
