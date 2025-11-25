#!/usr/bin/env python3
"""Coverage Simulator - Simulate roster coverage for given configuration.

This module provides functions to simulate whether a given configuration
(pattern, employee count, offsets) will achieve desired coverage.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from math import ceil


def simulate_coverage(
    pattern: List[str],
    employee_count: int,
    offsets: List[int],
    headcount_per_shift: Dict[str, int],
    days_in_horizon: int,
    anchor_date: datetime
) -> Dict:
    """
    Simulate coverage for a requirement with given configuration.
    
    Args:
        pattern: Work pattern like ["D","D","D","D","O","O"]
        employee_count: Number of employees assigned
        offsets: Rotation offsets for each employee
        headcount_per_shift: Required headcount per shift type (e.g., {"D": 4, "N": 2})
        days_in_horizon: Planning horizon length
        anchor_date: Coverage anchor date
    
    Returns:
        Dict with coverage statistics
    """
    cycle_length = len(pattern)
    coverage_map = {}  # date -> available employees
    shift_coverage_map = {}  # date -> {shift: count}
    
    # Simulate each day
    for day_offset in range(days_in_horizon):
        current_date = anchor_date + timedelta(days=day_offset)
        available_employees = []
        shift_counts = {}
        
        # Check each employee
        for emp_idx in range(employee_count):
            if emp_idx < len(offsets):
                rotation_offset = offsets[emp_idx]
            else:
                rotation_offset = emp_idx % cycle_length
            
            # Calculate cycle day for this employee
            emp_cycle_day = (day_offset - rotation_offset) % cycle_length
            expected_shift = pattern[emp_cycle_day]
            
            # If not 'O' (off), employee is available
            if expected_shift != 'O':
                available_employees.append(emp_idx)
                shift_counts[expected_shift] = shift_counts.get(expected_shift, 0) + 1
        
        coverage_map[day_offset] = len(available_employees)
        shift_coverage_map[day_offset] = shift_counts
    
    # Calculate statistics
    total_days = len(coverage_map)
    
    # For mixed patterns, check if ANY shift requirement is met
    # For single-shift patterns, check the specific shift
    days_fully_covered = 0
    days_undercovered = 0
    
    # Calculate total required per day (sum of all shift requirements)
    total_required_per_day = sum(headcount_per_shift.values())
    
    for day_offset, shift_counts in shift_coverage_map.items():
        day_covered = True
        for shift, required in headcount_per_shift.items():
            if shift_counts.get(shift, 0) < required:
                day_covered = False
                break
        if day_covered:
            days_fully_covered += 1
        else:
            days_undercovered += 1
    
    avg_coverage = sum(coverage_map.values()) / total_days if total_days > 0 else 0
    
    return {
        'totalDays': total_days,
        'requiredPerShift': headcount_per_shift,
        'requiredPerDay': total_required_per_day,
        'daysFullyCovered': days_fully_covered,
        'daysUndercovered': days_undercovered,
        'coverageRate': (days_fully_covered / total_days * 100) if total_days > 0 else 0,
        'averageAvailable': round(avg_coverage, 2),
        'coverageMap': coverage_map,
        'shiftCoverageMap': shift_coverage_map
    }


def calculate_min_employees(
    pattern: List[str],
    headcount_per_day: int,
    days_in_horizon: int,
    max_weekly_hours: float,
    shift_normal_hours: float
) -> int:
    """
    Calculate minimum employees needed to cover requirement.
    
    Args:
        pattern: Work pattern like ["D","D","D","D","O","O"]
        headcount_per_day: Required headcount per day
        days_in_horizon: Planning horizon length
        max_weekly_hours: Maximum weekly normal hours (e.g., 44)
        shift_normal_hours: Normal hours per shift (gross - lunch)
    
    Returns:
        Minimum employee count
    """
    cycle_length = len(pattern)
    work_days_in_cycle = sum(1 for d in pattern if d != 'O')
    
    # Basic coverage calculation
    # Each employee covers work_days_in_cycle out of cycle_length days
    coverage_per_employee = work_days_in_cycle / cycle_length
    
    # Theoretical minimum (ignoring hour constraints)
    theoretical_min = ceil(headcount_per_day / coverage_per_employee)
    
    # Adjust for weekly hour constraint
    # How many times does cycle repeat in a week?
    cycles_per_week = 7.0 / cycle_length
    work_days_per_week = work_days_in_cycle * cycles_per_week
    weekly_hours = work_days_per_week * shift_normal_hours
    
    if weekly_hours > max_weekly_hours:
        # Need more employees due to hour cap
        adjustment = weekly_hours / max_weekly_hours
        adjusted_min = ceil(theoretical_min * adjustment)
    else:
        adjusted_min = theoretical_min
    
    return max(theoretical_min, adjusted_min)


def verify_pattern_feasibility(
    pattern: List[str],
    constraints: Dict
) -> Tuple[bool, List[str]]:
    """
    Verify if a work pattern is feasible under constraints.
    
    Args:
        pattern: Work pattern to verify
        constraints: Dictionary of constraint values
    
    Returns:
        Tuple of (is_feasible, list_of_issues)
    """
    issues = []
    cycle_length = len(pattern)
    work_days = sum(1 for d in pattern if d != 'O')
    
    # Check max consecutive work days
    max_consecutive = 0
    current_consecutive = 0
    for shift in pattern:
        if shift != 'O':
            current_consecutive += 1
            max_consecutive = max(max_consecutive, current_consecutive)
        else:
            current_consecutive = 0
    
    if max_consecutive > constraints.get('maxConsecutiveWorkDays', 12):
        issues.append(f"Pattern has {max_consecutive} consecutive work days (max: {constraints.get('maxConsecutiveWorkDays', 12)})")
    
    # Check minimum off days per week
    min_off_days = constraints.get('minOffDaysPerWeek', 1)
    off_days_in_cycle = cycle_length - work_days
    cycles_per_week = 7.0 / cycle_length
    off_days_per_week = off_days_in_cycle * cycles_per_week
    
    if off_days_per_week < min_off_days:
        issues.append(f"Pattern provides only {off_days_per_week:.1f} off days per week (min: {min_off_days})")
    
    return (len(issues) == 0, issues)


def generate_staggered_offsets(employee_count: int, cycle_length: int) -> List[int]:
    """
    Generate staggered offsets for maximum coverage diversity.
    
    Args:
        employee_count: Number of employees
        cycle_length: Length of rotation cycle
    
    Returns:
        List of recommended offsets
    """
    # Evenly distribute offsets across cycle
    offsets = []
    for i in range(employee_count):
        offset = i % cycle_length
        offsets.append(offset)
    
    return offsets


def evaluate_coverage_quality(coverage_map: Dict[int, int], headcount_per_shift: Dict[str, int]) -> Dict:
    """
    Evaluate quality of coverage distribution.
    
    Args:
        coverage_map: Map of day_offset -> available_employee_count
        headcount_per_shift: Required headcount per shift type
    
    Returns:
        Quality metrics
    """
    values = list(coverage_map.values())
    required = sum(headcount_per_shift.values())
    
    # Calculate variance
    mean = sum(values) / len(values) if values else 0
    variance = sum((x - mean) ** 2 for x in values) / len(values) if values else 0
    
    # Count days at exact requirement
    exact_match = sum(1 for v in values if v == required)
    
    # Calculate waste (overcoverage)
    total_excess = sum(max(0, v - required) for v in values)
    
    return {
        'mean': round(mean, 2),
        'variance': round(variance, 2),
        'exactMatchDays': exact_match,
        'totalExcessCoverage': total_excess,
        'balanceScore': round(100 - variance, 2)  # Lower variance = better balance
    }
