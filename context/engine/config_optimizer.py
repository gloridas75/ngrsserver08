#!/usr/bin/env python3
"""
Enhanced Configuration Optimizer (ICPMP v2.0)

Key Improvements:
1. Coverage-aware pattern generation (5-day for Mon-Fri, 7-day for full week)
2. Integration with rotation_preprocessor for intelligent offset distribution
3. Pattern length validation against coverage days
4. Support for flexible employees (offset=-1)
5. Calendar-aware employee count calculation
"""

from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from itertools import product
from math import ceil
import logging

logger = logging.getLogger(__name__)


def generate_coverage_aware_patterns(
    shift_types: List[str],
    coverage_days: List[str],
    min_work_days: int = 3,
    max_work_days: int = 5
) -> List[List[str]]:
    """
    Generate work patterns that match coverage requirements.
    
    **KEY IMPROVEMENT**: Cycle length matches coverage days!
    - Mon-Fri (5 days) → 5-day patterns
    - 7 days → 7-day patterns
    - 6 days → 6-day patterns
    
    Args:
        shift_types: Available shift types (e.g., ['D'], ['N'], or ['D', 'N'])
        coverage_days: Days needing coverage (e.g., ['Mon','Tue','Wed','Thu','Fri'])
        min_work_days: Minimum work days in cycle
        max_work_days: Maximum work days in cycle
    
    Returns:
        List of candidate patterns matching coverage length
    """
    # Cycle length = number of coverage days
    cycle_length = len(coverage_days)
    
    # Adjust work day limits to cycle length
    max_work_days = min(max_work_days, cycle_length - 1)  # At least 1 rest day
    min_work_days = min(min_work_days, max_work_days)
    
    candidates = []
    
    # Single shift type patterns
    for shift in shift_types:
        for work_days in range(min_work_days, max_work_days + 1):
            off_days = cycle_length - work_days
            
            if off_days < 1:
                continue  # Must have at least 1 rest day
            
            # Consecutive work days pattern
            pattern = [shift] * work_days + ['O'] * off_days
            candidates.append(pattern)
            
            # Distributed pattern (if possible)
            if work_days >= 2 and off_days >= 2:
                first_half = work_days // 2
                second_half = work_days - first_half
                first_off = off_days // 2
                second_off = off_days - first_off
                
                pattern = [shift] * first_half + ['O'] * first_off + [shift] * second_half + ['O'] * second_off
                if len(pattern) == cycle_length:
                    candidates.append(pattern)
    
    # Mixed shift patterns (if multiple shift types requested)
    if len(shift_types) >= 2:
        for work_days in range(min_work_days, max_work_days + 1):
            off_days = cycle_length - work_days
            
            if off_days < 1:
                continue
            
            for split in range(1, work_days):
                # D's then N's
                pattern = [shift_types[0]] * split + [shift_types[1]] * (work_days - split) + ['O'] * off_days
                if len(pattern) == cycle_length:
                    candidates.append(pattern)
    
    # Remove duplicates
    unique_patterns = []
    seen = set()
    for pattern in candidates:
        pattern_tuple = tuple(pattern)
        if pattern_tuple not in seen:
            seen.add(pattern_tuple)
            unique_patterns.append(pattern)
    
    return unique_patterns


def simulate_coverage_with_preprocessing(
    pattern: List[str],
    headcount: int,
    coverage_days: List[str],
    days_in_horizon: int,
    start_date: datetime,
    available_employees: int = 200
) -> Dict:
    """
    Simulate coverage using rotation preprocessing logic.
    
    **KEY IMPROVEMENT**: Uses actual calendar simulation with coverage day filtering
    
    **CRITICAL**: For patterns with multiple shift codes (e.g., D-D-N-N-O-O),
    headcount applies PER SHIFT TYPE, not per day total.
    - Pattern ["D","D","N","N","O","O"] with headcount=20 means:
      20 D slots + 20 N slots = 40 slots per work day
    
    Returns:
        Dict with coverage stats including strict/flexible employee distribution
    """
    from .rotation_preprocessor import (
        generate_coverage_calendar,
        simulate_pattern_filling
    )
    
    # Generate calendar filtered by coverage days
    calendar_dates = []
    for day_offset in range(days_in_horizon):
        current_date = start_date + timedelta(days=day_offset)
        weekday = current_date.strftime('%a')
        if weekday in coverage_days:
            calendar_dates.append(current_date.strftime('%Y-%m-%d'))
    
    # CRITICAL FIX: Calculate actual slots per day based on unique shift codes
    # If pattern has multiple shift types (D, N), headcount applies to EACH shift type
    unique_shift_codes = set(code for code in pattern if code != 'O')
    slots_per_work_day = len(unique_shift_codes) * headcount
    
    # Simulate pattern filling
    pattern_info = {
        'pattern_key': tuple(pattern),
        'workPattern': pattern,
        'combined_headcount': slots_per_work_day,  # Use total slots, not just headcount
        'coverage_days': set(coverage_days)
    }
    
    try:
        result = simulate_pattern_filling(
            work_pattern=pattern,
            combined_headcount=slots_per_work_day,  # Use total slots per day
            coverage_days=set(coverage_days),
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=(start_date + timedelta(days=days_in_horizon-1)).strftime('%Y-%m-%d'),
            available_employees=200,  # Generous pool for simulation
            pattern_info=pattern_info
        )
        
        # Extract employee counts from simulation result
        strict_count = result.get('strict_count', 0)
        flexible_count = result.get('flexible_count', 0)
        truly_flexible_count = result.get('truly_flexible_count', 0)
        
        # Extract offsets from strict + flexible employees
        all_offsets = []
        for emp in result.get('strict_employees', []):
            all_offsets.append(emp['rotationOffset'])
        for emp in result.get('flexible_candidates', []):
            all_offsets.append(emp['rotationOffset'])
        
        return {
            'employeeCount': strict_count + flexible_count + truly_flexible_count,
            'strictEmployees': strict_count,
            'flexibleEmployees': flexible_count,
            'trulyFlexibleEmployees': truly_flexible_count,
            'offsets': all_offsets,
            'coverageComplete': result.get('coverage_complete', False),
            'coverageRange': (result.get('min_coverage', 0), result.get('max_coverage', 0)),
            'calendarDays': len(calendar_dates),
            'uniqueShiftCodes': len(unique_shift_codes),
            'slotsPerWorkDay': slots_per_work_day
        }
    except Exception as e:
        logger.warning(f"Preprocessing simulation failed: {e}, falling back to basic calculation")
        # Fallback to simple calculation with multi-shift support
        unique_shift_codes = set(code for code in pattern if code != 'O')
        slots_per_work_day = len(unique_shift_codes) * headcount
        
        cycle_length = len(pattern)
        work_days_in_cycle = sum(1 for d in pattern if d != 'O')
        coverage_per_employee = work_days_in_cycle / cycle_length
        min_employees = ceil(slots_per_work_day / coverage_per_employee)
        
        # Calculate expected coverage: employees * work_days_per_cycle / cycle_length
        # This gives average daily coverage
        expected_daily_coverage = min_employees * coverage_per_employee
        
        return {
            'employeeCount': min_employees,
            'strictEmployees': min_employees,
            'flexibleEmployees': 0,
            'trulyFlexibleEmployees': 0,
            'offsets': [i % cycle_length for i in range(min_employees)],
            'uniqueShiftCodes': len(unique_shift_codes),
            'slotsPerWorkDay': slots_per_work_day,
            'coverageComplete': expected_daily_coverage >= slots_per_work_day,
            'coverageRange': (int(expected_daily_coverage), int(expected_daily_coverage)),
            'calendarDays': len(calendar_dates)
        }


def optimize_requirement_config_v2(
    requirement: Dict,
    constraints: Dict,
    days_in_horizon: int,
    start_date: datetime,
    shift_definitions: Optional[Dict[str, Dict]] = None,
    top_n: int = 5
) -> List[Dict]:
    """
    Enhanced configuration optimizer with coverage-aware pattern generation.
    
    **KEY IMPROVEMENTS**:
    - Generates patterns matching coverage day length
    - Uses rotation preprocessing for accurate employee counts
    - Validates pattern length vs coverage
    - Supports flexible employees
    """
    shift_types = requirement['shiftTypes']
    headcount_per_shift = requirement['headcountPerShift']
    coverage_days = requirement.get('coverageDays', ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'])
    
    # Generate coverage-aware patterns
    candidates = generate_coverage_aware_patterns(
        shift_types=shift_types,
        coverage_days=coverage_days,
        min_work_days=3,
        max_work_days=min(5, len(coverage_days) - 1)
    )
    
    logger.info(f"  Generated {len(candidates)} coverage-aware patterns for {requirement['id']}")
    logger.info(f"  Coverage: {', '.join(coverage_days)} ({len(coverage_days)} days)")
    
    all_configs = []
    
    for pattern in candidates:
        # VALIDATION: Pattern length must match coverage length
        if len(pattern) != len(coverage_days):
            logger.warning(f"  ⚠️ Skipping pattern {pattern}: length {len(pattern)} != coverage days {len(coverage_days)}")
            continue
        
        # Get headcount (for single shift, it's the only key)
        total_headcount = sum(headcount_per_shift.values())
        
        # Simulate coverage with preprocessing
        sim_result = simulate_coverage_with_preprocessing(
            pattern=pattern,
            headcount=total_headcount,
            coverage_days=coverage_days,
            days_in_horizon=days_in_horizon,
            start_date=start_date
        )
        
        # Calculate score
        employee_penalty = sim_result['employeeCount'] * 10
        coverage_penalty = 0 if sim_result['coverageComplete'] else 1000
        flexible_bonus = -sim_result['flexibleEmployees'] * 5  # Reward flexibility
        
        score = employee_penalty + coverage_penalty + flexible_bonus
        
        all_configs.append({
            'pattern': pattern,
            'employeeCount': sim_result['employeeCount'],
            'strictEmployees': sim_result['strictEmployees'],
            'flexibleEmployees': sim_result['flexibleEmployees'],
            'trulyFlexibleEmployees': sim_result['trulyFlexibleEmployees'],
            'offsets': sim_result['offsets'],
            'coverageComplete': sim_result['coverageComplete'],
            'coverageRange': sim_result['coverageRange'],
            'calendarDays': sim_result['calendarDays'],
            'score': round(score, 2)
        })
    
    # Sort and return top N
    all_configs.sort(key=lambda x: x['score'])
    return all_configs[:top_n]


def optimize_all_requirements(
    requirements: List[Dict],
    constraints: Dict,
    planning_horizon: Dict,
    shift_definitions: Optional[Dict[str, Dict]] = None,
    top_n: int = 5
) -> Dict:
    """
    Optimize configuration for all requirements using ICPMP v2.
    
    Args:
        requirements: List of requirement specifications
        constraints: Constraint parameters
        planning_horizon: Planning horizon with start/end dates
        top_n: Number of top patterns to return per requirement
    
    Returns:
        Dict mapping requirement IDs to their top configurations
    """
    start_date = datetime.fromisoformat(planning_horizon['startDate'])
    end_date = datetime.fromisoformat(planning_horizon['endDate'])
    days_in_horizon = (end_date - start_date).days + 1
    
    print(f"\n{'='*80}")
    print(f"OPTIMIZING CONFIGURATION - ICPMP v2 (Enhanced)")
    print(f"{'='*80}\n")
    print(f"Planning horizon: {start_date.date()} to {end_date.date()} ({days_in_horizon} days)\n")
    
    optimized_configs = {}
    total_employees_best = 0
    
    for req in requirements:
        req_id = req.get('requirementId', req.get('id'))
        req_name = req.get('requirementName', req.get('name'))
        
        print(f"Optimizing: {req_id} ({req_name})")
        
        # Build requirement dict in expected format
        requirement = {
            'id': req_id,
            'name': req_name,
            'coverageDays': req['coverageDays'],
            'shiftTypes': req['shiftTypes'],
            'headcountPerShift': req.get('headcountByShift', req.get('headcountPerShift', {}))
        }
        
        top_configs = optimize_requirement_config_v2(
            requirement=requirement,
            constraints=constraints,
            days_in_horizon=days_in_horizon,
            start_date=start_date,
            top_n=top_n
        )
        
        if top_configs:
            # Convert to output format
            formatted_configs = []
            for config in top_configs:
                # Calculate expected coverage rate
                if config['coverageComplete']:
                    expected_coverage = 100.0
                else:
                    # Calculate based on coverage range vs required headcount
                    required_headcount = list(requirement['headcountPerShift'].values())[0]
                    max_coverage = config['coverageRange'][1] if config['coverageRange'] else 0
                    expected_coverage = round((max_coverage / required_headcount * 100) if required_headcount > 0 else 0.0, 2)
                
                formatted_configs.append({
                    'workPattern': config['pattern'],
                    'employeesRequired': config['employeeCount'],
                    'strictEmployees': config['strictEmployees'],
                    'flexibleEmployees': config['flexibleEmployees'],
                    'employeeOffsets': config['offsets'],
                    'expectedCoverageRate': expected_coverage,
                    'score': config['score']
                })
            
            optimized_configs[req_id] = formatted_configs
            best_config = top_configs[0]
            total_employees_best += best_config['employeeCount']
            
            print(f"  ✓ Found {len(top_configs)} coverage-aware patterns")
            print(f"  ✓ Best pattern: {best_config['pattern']} ({len(best_config['pattern'])}-day cycle)")
            print(f"  ✓ Employees needed: {best_config['employeeCount']}")
            print(f"  ✓ Coverage: {'Complete' if best_config['coverageComplete'] else 'Partial'}")
            print()
        else:
            print(f"  ✗ No feasible configuration found!")
            print()
    
    print(f"{'='*80}")
    print(f"OPTIMIZATION COMPLETE")
    print(f"{'='*80}")
    print(f"Total requirements: {len(requirements)}")
    print(f"Total employees needed (using best patterns): {total_employees_best}")
    print(f"{'='*80}\n")
    
    return optimized_configs


def format_output_config(optimized_result: Dict, input_config: Dict) -> Dict:
    """
    Format optimized result for JSON output.
    
    Args:
        optimized_result: Result from optimize_all_requirements_v2
        input_config: Original input configuration
    
    Returns:
        Formatted output configuration
    """
    recommendations = []
    
    for req_id, configs in optimized_result.items():
        # Find requirement details
        req = next(r for r in input_config['requirements'] 
                  if r.get('requirementId', r.get('id')) == req_id)
        
        for rank, config in enumerate(configs, 1):
            recommendations.append({
                'requirementId': req_id,
                'requirementName': req.get('requirementName', req.get('name')),
                'alternativeRank': rank,
                'configuration': {
                    'workPattern': config['workPattern'],
                    'employeesRequired': config['employeesRequired'],
                    'strictEmployees': config['strictEmployees'],
                    'flexibleEmployees': config['flexibleEmployees'],
                    'employeeOffsets': config['employeeOffsets']
                },
                'coverage': {
                    'expectedCoverageRate': config['expectedCoverageRate'],
                    'coverageType': 'complete' if config['expectedCoverageRate'] >= 100 else 'partial'
                },
                'quality': {
                    'score': config['score']
                }
            })
    
    # Calculate summary
    total_employees = sum(
        configs[0]['employeesRequired'] 
        for configs in optimized_result.values() 
        if configs
    )
    
    return {
        'schemaVersion': input_config.get('schemaVersion', '0.8'),
        'configType': 'optimizedRosterConfiguration',
        'generatedAt': datetime.now().isoformat(),
        'organizationId': input_config.get('organizationId', 'ORG_TEST'),
        'planningHorizon': input_config['planningHorizon'],
        'summary': {
            'totalRequirements': len(input_config['requirements']),
            'totalEmployees': total_employees,
            'optimizerVersion': 'ICPMP v2.0 (Enhanced)'
        },
        'recommendations': recommendations
    }


# Export functions
__all__ = [
    'generate_coverage_aware_patterns',
    'simulate_coverage_with_preprocessing',
    'optimize_requirement_config_v2',
    'optimize_all_requirements',
    'format_output_config'
]
