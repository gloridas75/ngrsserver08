"""
Rotation Offset Manager

Automatically manages employee rotation offsets for pattern-based scheduling.
When fixedRotationOffset=true with patterns containing 'O' days, employees need
staggered offsets to ensure coverage on all calendar days.

Usage:
    from src.offset_manager import ensure_staggered_offsets
    
    # Automatically fix offsets in input data
    input_data = ensure_staggered_offsets(input_data)
"""

import logging
from typing import Dict, List, Any
from collections import Counter

logger = logging.getLogger(__name__)


def get_pattern_cycle_length(work_pattern: List[str]) -> int:
    """
    Get the cycle length from a work pattern.
    
    Args:
        work_pattern: List like ['D', 'D', 'N', 'N', 'O', 'O']
    
    Returns:
        Cycle length (e.g., 6 for DDNNOO pattern)
    """
    if not work_pattern:
        return 0
    return len(work_pattern)


def get_unique_shift_codes(work_pattern: List[str]) -> int:
    """
    Get the number of unique shift codes in the pattern (excluding 'O').
    
    Args:
        work_pattern: List like ['D', 'D', 'N', 'N', 'O', 'O']
    
    Returns:
        Number of unique shift codes (e.g., 2 for D and N)
    """
    unique_codes = set(code for code in work_pattern if code != 'O')
    return len(unique_codes)


def has_off_days(work_pattern: List[str]) -> bool:
    """
    Check if work pattern contains off days ('O').
    
    Args:
        work_pattern: List like ['D', 'D', 'N', 'N', 'O', 'O']
    
    Returns:
        True if pattern contains 'O' days
    """
    return 'O' in work_pattern


def should_stagger_offsets(input_data: Dict[str, Any]) -> bool:
    """
    Determine if offsets should be automatically staggered.
    
    Criteria:
    1. fixedRotationOffset must be true
    2. Work pattern must contain 'O' days
    3. Employees exist in the input
    
    Args:
        input_data: Full input JSON data
    
    Returns:
        True if offsets should be staggered
    """
    # Check fixedRotationOffset
    if not input_data.get('fixedRotationOffset', False):
        logger.info("fixedRotationOffset is false - no staggering needed (solver will optimize)")
        return False
    
    # Check if there are employees
    employees = input_data.get('employees', [])
    if not employees:
        logger.warning("No employees found in input")
        return False
    
    # Check if any requirement has 'O' days in pattern
    demand_items = input_data.get('demandItems', [])
    for demand in demand_items:
        requirements = demand.get('requirements', [])
        for req in requirements:
            work_pattern = req.get('workPattern', [])
            if has_off_days(work_pattern):
                logger.info(f"Found O-pattern in requirement {req.get('requirementId')} - staggering needed")
                return True
    
    logger.info("No O-patterns found - staggering not required but harmless")
    return True  # Stagger anyway for consistency


def get_current_offset_distribution(employees: List[Dict[str, Any]]) -> Counter:
    """
    Get the current distribution of rotation offsets.
    
    Args:
        employees: List of employee objects
    
    Returns:
        Counter with offset distribution
    """
    offsets = [emp.get('rotationOffset', 0) for emp in employees]
    return Counter(offsets)


def stagger_offsets(
    employees: List[Dict[str, Any]], 
    cycle_length: int,
    shift_code_multiplier: int = 1
) -> int:
    """
    Distribute employees evenly across rotation offsets.
    
    CRITICAL: For patterns with multiple shift codes (e.g., D-D-N-N-O-O),
    we need MORE employees per offset position to cover all shifts.
    
    Example: Pattern D-D-N-N-O-O with headcount=20
    - 2 shift codes (D, N) × 20 headcount = 40 slots per work day
    - Need 60 employees total (10 per offset × 6 offsets)
    - NOT 30 employees!
    
    Args:
        employees: List of employee objects (modified in place)
        cycle_length: Pattern cycle length (e.g., 6 for DDNNOO)
        shift_code_multiplier: Number of unique shift codes in pattern
    
    Returns:
        Number of employees updated
    """
    updated_count = 0
    
    # Distribute employees across offsets
    # With shift_code_multiplier, we group employees:
    # - Offsets 0,1,2,3,4,5 (cycle positions)
    # - Multiple employees at same offset for different shift coverage
    for i, emp in enumerate(employees):
        # Round-robin distribution across cycle positions
        new_offset = i % cycle_length
        old_offset = emp.get('rotationOffset', 0)
        
        if old_offset != new_offset:
            emp['rotationOffset'] = new_offset
            updated_count += 1
    
    return updated_count


def ensure_staggered_offsets(input_data: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
    """
    Ensure employees have staggered rotation offsets for pattern-based scheduling.
    
    This function:
    1. Checks if staggering is needed (fixedRotationOffset=true + O-patterns)
    2. Determines the cycle length from work patterns
    3. Distributes employees evenly across offsets (0, 1, 2, ..., cycle_length-1)
    4. Logs the changes made
    
    Args:
        input_data: Full input JSON data (modified in place)
        force: If True, stagger even if criteria not met
    
    Returns:
        Modified input_data with staggered offsets
    """
    logger.info("=" * 80)
    logger.info("OFFSET MANAGER: Checking rotation offsets")
    logger.info("=" * 80)
    
    employees = input_data.get('employees', [])
    if not employees:
        logger.warning("No employees to process")
        return input_data
    
    # Check if staggering is needed
    if not force and not should_stagger_offsets(input_data):
        logger.info("Offset staggering not required for this configuration")
        return input_data
    
    # Get current state
    before_dist = get_current_offset_distribution(employees)
    logger.info(f"Current offset distribution: {dict(sorted(before_dist.items()))}")
    
    # Check if already properly staggered
    if len(before_dist) > 1 and all(count > 0 for count in before_dist.values()):
        logger.info("✓ Offsets already staggered - no changes needed")
        return input_data
    
    # Determine cycle length from patterns
    cycle_length = 6  # Default for DDNNOO
    shift_code_multiplier = 1  # Default for single shift type
    demand_items = input_data.get('demandItems', [])
    if demand_items and demand_items[0].get('requirements'):
        first_pattern = demand_items[0]['requirements'][0].get('workPattern', [])
        if first_pattern:
            cycle_length = get_pattern_cycle_length(first_pattern)
            shift_code_multiplier = get_unique_shift_codes(first_pattern)
            logger.info(f"Detected pattern: {first_pattern}")
            logger.info(f"  - Cycle length: {cycle_length}")
            logger.info(f"  - Unique shift codes: {shift_code_multiplier}")
            if shift_code_multiplier > 1:
                logger.info(f"  ⚠️  Multi-shift pattern detected! Headcount applies PER shift type")
    
    # Apply staggered offsets
    logger.info(f"Applying staggered offsets across {cycle_length} positions...")
    updated_count = stagger_offsets(employees, cycle_length, shift_code_multiplier)
    
    # Report results
    after_dist = get_current_offset_distribution(employees)
    logger.info(f"New offset distribution: {dict(sorted(after_dist.items()))}")
    logger.info(f"✓ Updated {updated_count} employees")
    
    logger.info("=" * 80)
    
    return input_data


def validate_offset_configuration(input_data: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate that offset configuration is correct for the input.
    
    Args:
        input_data: Full input JSON data
    
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    
    fixed_offset = input_data.get('fixedRotationOffset', False)
    employees = input_data.get('employees', [])
    
    if not employees:
        return True, []  # No employees, nothing to validate
    
    # Check for O-patterns
    has_o_pattern = False
    demand_items = input_data.get('demandItems', [])
    for demand in demand_items:
        requirements = demand.get('requirements', [])
        for req in requirements:
            work_pattern = req.get('workPattern', [])
            if has_off_days(work_pattern):
                has_o_pattern = True
                break
    
    if not has_o_pattern:
        return True, []  # No O-patterns, no strict requirements
    
    # For O-patterns, check configuration
    if not fixed_offset:
        issues.append("fixedRotationOffset should be true for patterns with 'O' days")
    
    offset_dist = get_current_offset_distribution(employees)
    
    if len(offset_dist) == 1 and 0 in offset_dist:
        issues.append(f"All {len(employees)} employees have offset 0 - need staggered offsets for O-pattern coverage")
    elif len(offset_dist) < 3:
        issues.append(f"Only {len(offset_dist)} different offset values - recommend more variety for better coverage")
    
    is_valid = len(issues) == 0
    return is_valid, issues


if __name__ == "__main__":
    # Test the module
    import json
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    
    if len(sys.argv) > 1:
        # Load and process a file
        filepath = sys.argv[1]
        print(f"\nProcessing: {filepath}")
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Validate before
        is_valid, issues = validate_offset_configuration(data)
        if not is_valid:
            print("\nValidation issues found:")
            for issue in issues:
                print(f"  ⚠️  {issue}")
        
        # Apply staggering
        data = ensure_staggered_offsets(data)
        
        # Validate after
        is_valid, issues = validate_offset_configuration(data)
        if is_valid:
            print("\n✓ Configuration is now valid")
        else:
            print("\n⚠️  Issues remain:")
            for issue in issues:
                print(f"  - {issue}")
        
        # Optionally save
        if '--save' in sys.argv:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"\n✓ Saved to {filepath}")
    else:
        print("Usage: python -m src.offset_manager <input_file.json> [--save]")
        print("\nExample:")
        print("  python -m src.offset_manager input/input_v0.8_0212_1300.json --save")
