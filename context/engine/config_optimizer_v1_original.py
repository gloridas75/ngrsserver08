#!/usr/bin/env python3
"""Configuration Optimizer - Find optimal work patterns and employee counts.

This module optimizes roster configuration by finding the best:
1. Work patterns for each requirement
2. Minimum employee count needed
3. Rotation offsets for employees
"""

from datetime import datetime
from typing import List, Dict, Tuple, Optional
from itertools import product
from .coverage_simulator import (
    simulate_coverage,
    calculate_min_employees,
    verify_pattern_feasibility,
    generate_staggered_offsets,
    evaluate_coverage_quality
)


def generate_pattern_candidates(
    shift_types: List[str],
    cycle_length: int = 6,
    min_work_days: int = 3,
    max_work_days: int = 5
) -> List[List[str]]:
    """
    Generate candidate work patterns based on allowed shift types.
    
    If shiftTypes = ["D"] -> Only D patterns
    If shiftTypes = ["N"] -> Only N patterns  
    If shiftTypes = ["D", "N"] -> D patterns, N patterns, AND mixed D+N patterns
    
    Args:
        shift_types: Available shift types (e.g., ['D'], ['N'], or ['D', 'N'])
        cycle_length: Length of rotation cycle
        min_work_days: Minimum work days in cycle
        max_work_days: Maximum work days in cycle
    
    Returns:
        List of candidate patterns
    """
    candidates = []
    
    # Single shift type patterns - always generate for each shift type provided
    for shift in shift_types:
        for work_days in range(min_work_days, max_work_days + 1):
            off_days = cycle_length - work_days
            
            # Consecutive work days pattern
            pattern = [shift] * work_days + ['O'] * off_days
            candidates.append(pattern)
            
            # Distributed pattern (if possible)
            if work_days >= 2 and off_days >= 2:
                # Split work days: first half, off, second half, off
                first_half = work_days // 2
                second_half = work_days - first_half
                first_off = off_days // 2
                second_off = off_days - first_off
                
                pattern = [shift] * first_half + ['O'] * first_off + [shift] * second_half + ['O'] * second_off
                if len(pattern) == cycle_length:
                    candidates.append(pattern)
    
    # Mixed shift patterns - ONLY if multiple shift types are provided
    # This means requirement explicitly wants mixed D+N patterns
    if len(shift_types) >= 2:
        for work_days in range(min_work_days, max_work_days + 1):
            off_days = cycle_length - work_days
            
            # Various D+N mix combinations
            for split in range(1, work_days):
                # Pattern: D's then N's
                pattern = [shift_types[0]] * split + [shift_types[1]] * (work_days - split) + ['O'] * off_days
                if len(pattern) == cycle_length:
                    candidates.append(pattern)
                
                # Pattern: N's then D's (reverse)
                pattern = [shift_types[1]] * split + [shift_types[0]] * (work_days - split) + ['O'] * off_days
                if len(pattern) == cycle_length:
                    candidates.append(pattern)
            
            # Alternating D/N patterns for longer work stretches
            if work_days >= 4:
                pattern = []
                for i in range(work_days):
                    pattern.append(shift_types[i % 2])
                pattern.extend(['O'] * off_days)
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


def optimize_requirement_config(
    requirement: Dict,
    constraints: Dict,
    days_in_horizon: int,
    anchor_date: datetime,
    shift_definitions: Optional[Dict[str, Dict]] = None,
    top_n: int = 5
) -> List[Dict]:
    """
    Find top N optimal configurations for a single requirement.
    
    Args:
        requirement: Requirement specification
        constraints: Constraint parameters
        days_in_horizon: Planning horizon length
        anchor_date: Coverage anchor date
        shift_definitions: Optional dict mapping shift codes to definitions
                          e.g., {"D": {"grossHours": 12.0, "lunchBreak": 1.0}}
        top_n: Number of top patterns to return (default: 5)
    
    Returns:
        List of top N configurations sorted by score (best first)
    """
    shift_types = requirement['shiftTypes']
    headcount_per_shift = requirement['headcountPerShift']

    # Generate candidate patterns
    candidates = generate_pattern_candidates(
        shift_types=shift_types,
        cycle_length=6,  # Standard 6-day cycle
        min_work_days=3,
        max_work_days=5
    )

    print(f"  Generated {len(candidates)} candidate patterns for {requirement['id']}")

    # Evaluate each candidate
    all_configs = []
    
    max_weekly_hours = constraints.get('maxWeeklyNormalHours', 44)

    for pattern in candidates:
        # Check feasibility
        is_feasible, issues = verify_pattern_feasibility(pattern, constraints)
        if not is_feasible:
            continue

        # For mixed patterns, calculate min employees for each shift type
        min_employees_total = 0
        shift_employee_counts = {}
        for shift in shift_types:
            # Count how many days this shift appears in the pattern
            shift_days = sum(1 for d in pattern if d == shift)
            if shift_days == 0:
                continue
            headcount = headcount_per_shift.get(shift, 0)
            
            # Get shift-specific hours
            if shift_definitions and shift in shift_definitions:
                shift_def = shift_definitions[shift]
                gross_hours = shift_def.get('grossHours', 12.0)
                lunch_break = shift_def.get('lunchBreak', 1.0)
                shift_hours = gross_hours - lunch_break
            else:
                shift_hours = 11.0  # Default: 12 gross - 1 lunch
            
            min_employees = calculate_min_employees(
                pattern,
                headcount,
                days_in_horizon,
                max_weekly_hours,
                shift_hours
            )
            shift_employee_counts[shift] = min_employees
            min_employees_total += min_employees

        # Optimize for large employee counts (100+)
        if min_employees_total > 100:
            offsets = [i % len(pattern) for i in range(min_employees_total)]
        else:
            offsets = generate_staggered_offsets(min_employees_total, len(pattern))

        # Simulate coverage for mixed patterns
        coverage = simulate_coverage(
            pattern,
            min_employees_total,
            offsets,
            headcount_per_shift,
            days_in_horizon,
            anchor_date
        )

        # Evaluate quality
        quality = evaluate_coverage_quality(
            coverage['coverageMap'],
            headcount_per_shift
        )

        # Score: prioritize fewer employees + high coverage + balance
        coverage_penalty = (100 - coverage['coverageRate']) * 100
        employee_penalty = min_employees_total * 10
        balance_penalty = quality['variance']

        score = coverage_penalty + employee_penalty + balance_penalty

        all_configs.append({
            'pattern': pattern,
            'employeeCount': min_employees_total,
            'shiftEmployeeCounts': shift_employee_counts,
            'offsets': offsets,
            'coverage': coverage,
            'quality': quality,
            'score': round(score, 2)
        })

    # Sort by score (best first) and return top N
    all_configs.sort(key=lambda x: x['score'])
    top_configs = all_configs[:top_n]

    return top_configs


def optimize_all_requirements(
    requirements: List[Dict],
    constraints: Dict,
    planning_horizon: Dict,
    shift_definitions: Optional[Dict[str, Dict]] = None
) -> Dict:
    """
    Optimize configuration for all requirements.
    
    Args:
        requirements: List of requirement specifications
        constraints: Constraint parameters
        planning_horizon: Planning horizon with start/end dates
        shift_definitions: Optional dict mapping shift codes to definitions
                          e.g., {"D": {"grossHours": 12.0, "lunchBreak": 1.0}}
    
    Returns:
        Optimal configuration for all requirements
    """
    start_date = datetime.fromisoformat(planning_horizon['startDate'])
    end_date = datetime.fromisoformat(planning_horizon['endDate'])
    days_in_horizon = (end_date - start_date).days + 1
    
    print(f"\n{'='*80}")
    print(f"OPTIMIZING CONFIGURATION FOR {len(requirements)} REQUIREMENTS")
    print(f"{'='*80}\n")
    print(f"Planning horizon: {start_date.date()} to {end_date.date()} ({days_in_horizon} days)\n")
    
    optimized_configs = {}
    total_employees_best = 0
    
    for req in requirements:
        print(f"Optimizing: {req['id']} ({req['name']})")
        headcount_summary = ', '.join([f"{shift}: {count}" for shift, count in req['headcountPerShift'].items()])
        print(f"  Shift types: {req['shiftTypes']}, Headcount: {headcount_summary}")
        
        top_configs = optimize_requirement_config(
            req,
            constraints,
            days_in_horizon,
            start_date,
            shift_definitions=shift_definitions,
            top_n=5  # Get top 5 patterns
        )
        
        if top_configs:
            optimized_configs[req['id']] = top_configs
            best_config = top_configs[0]  # Best is first
            total_employees_best += best_config['employeeCount']
            
            print(f"  ✓ Found {len(top_configs)} feasible patterns")
            print(f"  ✓ Best pattern: {best_config['pattern']}")
            print(f"  ✓ Employees needed: {best_config['employeeCount']}")
            print(f"  ✓ Coverage rate: {best_config['coverage']['coverageRate']:.1f}%")
            print(f"  ✓ Balance score: {best_config['quality']['balanceScore']:.1f}")
            
            # Show alternatives if available
            if len(top_configs) > 1:
                print(f"  ℹ️  Alternative patterns available: {len(top_configs) - 1}")
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
    
    return {
        'requirements': optimized_configs,
        'summary': {
            'totalRequirements': len(requirements),
            'totalEmployees': total_employees_best,
            'planningHorizon': {
                'startDate': start_date.isoformat(),
                'endDate': end_date.isoformat(),
                'days': days_in_horizon
            }
        }
    }


def format_output_config(optimized_result: Dict, requirements: List[Dict]) -> Dict:
    """
    Format optimized result for output JSON with top 5 patterns per requirement.
    
    Args:
        optimized_result: Result from optimize_all_requirements
        requirements: Original requirement specifications
    
    Returns:
        Formatted configuration with top 5 alternatives per requirement
    """
    req_map = {req['id']: req for req in requirements}
    
    formatted = {
        'schemaVersion': '0.8',
        'configType': 'optimizedRosterConfiguration',
        'generatedAt': datetime.now().isoformat(),
        'summary': optimized_result['summary'],
        'recommendations': []
    }
    
    for req_id, config_list in optimized_result['requirements'].items():
        req = req_map.get(req_id, {})
        
        # Each requirement now has a list of top configs
        for rank, config in enumerate(config_list, 1):
            # Limit offsets display for large teams
            display_offsets = config['offsets'][:10] if config['employeeCount'] <= 100 else []
            
            recommendation = {
                'requirementId': req_id,
                'requirementName': req.get('name', ''),
                'productType': req.get('productType', ''),
                'rank': req.get('rank', ''),
                'scheme': req.get('scheme', ''),
                'alternativeRank': rank,  # 1 = best, 2 = second best, etc.
                'configuration': {
                    'workPattern': config['pattern'],
                    'employeesRequired': config['employeeCount'],
                    'employeesRequiredPerShift': config.get('shiftEmployeeCounts', {}),
                    'rotationOffsets': display_offsets,
                    'cycleLength': len(config['pattern']),
                    'score': config['score']
                },
                'coverage': {
                    'expectedCoverageRate': round(config['coverage']['coverageRate'], 2),
                    'daysFullyCovered': config['coverage']['daysFullyCovered'],
                    'daysUndercovered': config['coverage']['daysUndercovered'],
                    'averageAvailable': config['coverage']['averageAvailable'],
                    'requiredPerShift': config['coverage'].get('requiredPerShift', {}),
                    'requiredPerDay': config['coverage'].get('requiredPerDay', {})
                },
                'quality': {
                    'balanceScore': config['quality']['balanceScore'],
                    'variance': config['quality']['variance'],
                    'totalExcessCoverage': config['quality']['totalExcessCoverage']
                },
                'notes': _generate_notes(config, req, rank)
            }
            
            formatted['recommendations'].append(recommendation)
    
    return formatted


def _generate_notes(config: Dict, requirement: Dict, rank: int = 1) -> List[str]:
    """Generate helpful notes about the configuration."""
    notes = []
    
    # Add rank indicator
    if rank == 1:
        notes.append("⭐ RECOMMENDED: Best overall score")
    elif rank <= 3:
        notes.append(f"Alternative #{rank}: {_rank_description(rank)}")
    else:
        notes.append(f"Alternative #{rank}")
    
    pattern = config['pattern']
    work_days = sum(1 for d in pattern if d != 'O')
    off_days = len(pattern) - work_days
    
    notes.append(f"Pattern has {work_days} work days and {off_days} off days per {len(pattern)}-day cycle")
    
    # Team size notes
    if config['employeeCount'] > 100:
        notes.append(f"⚠ Large team ({config['employeeCount']} employees) - optimized for performance")
    elif config['employeeCount'] > 50:
        notes.append(f"Large team ({config['employeeCount']} employees) - consider splitting requirement")
    elif config['employeeCount'] <= 10:
        notes.append(f"✓ Small team ({config['employeeCount']} employees) - easy to manage")
    
    if config['coverage']['coverageRate'] == 100:
        notes.append("✓ Achieves 100% coverage with this configuration")
    elif config['coverage']['coverageRate'] >= 95:
        notes.append(f"Achieves {config['coverage']['coverageRate']:.1f}% coverage (near-optimal)")
    else:
        notes.append(f"Warning: Only {config['coverage']['coverageRate']:.1f}% coverage - may need more employees")
    
    if config['quality']['variance'] < 1.0:
        notes.append("✓ Excellent workload balance across employees")
    elif config['quality']['variance'] < 2.0:
        notes.append("Good workload balance")
    
    return notes


def _rank_description(rank: int) -> str:
    """Get description for alternative rank."""
    descriptions = {
        2: "Second best option",
        3: "Third best option",
        4: "Fourth option",
        5: "Fifth option"
    }
    return descriptions.get(rank, f"Alternative option")
    
    offsets = config['offsets']
    if len(set(offsets)) == len(offsets):
        notes.append("✓ All employees have unique rotation offsets for maximum diversity")
    
    return notes
