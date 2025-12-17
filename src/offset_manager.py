"""
Rotation Offset Manager

Automatically manages employee rotation offsets for pattern-based scheduling.
Supports multiple offset assignment modes:
- "auto": Sequential staggering (0, 1, 2, ...)
- "ouOffsets": OU-level offset assignment (each OU has its own rotation offset)
- "solverOptimized": Solver decides offsets

Usage:
    from src.offset_manager import ensure_staggered_offsets
    
    # Automatically fix offsets in input data
    input_data = ensure_staggered_offsets(input_data)
"""

import logging
from typing import Dict, List, Any, Union
from collections import Counter

logger = logging.getLogger(__name__)


def normalize_rostering_basis(value: Union[str, None]) -> str:
    """
    Normalize rosteringBasis value to string format.
    
    Args:
        value: String value or None
    
    Returns:
        Normalized string: "demandBased" or "outcomeBased"
    """
    if value is None:
        logger.info("rosteringBasis not specified, defaulting to 'demandBased'")
        return "demandBased"
    
    if isinstance(value, str):
        valid_values = ["demandBased", "outcomeBased"]
        if value in valid_values:
            return value
        else:
            logger.warning(f"Invalid rosteringBasis value '{value}', defaulting to 'demandBased'")
            return "demandBased"
    
    # Default fallback
    logger.warning(f"Unexpected rosteringBasis type {type(value)}, defaulting to 'demandBased'")
    return "demandBased"


def normalize_fixed_rotation_offset(value: Union[bool, str]) -> str:
    """
    Normalize fixedRotationOffset value to string format.
    
    Supports backward compatibility:
    - true → "auto"
    - false → "solverOptimized"
    - String values pass through
    
    Args:
        value: Boolean or string value
    
    Returns:
        Normalized string: "auto", "ouOffsets", or "solverOptimized"
    """
    if isinstance(value, bool):
        return "auto" if value else "solverOptimized"
    
    if isinstance(value, str):
        valid_values = ["auto", "ouOffsets", "solverOptimized"]
        if value in valid_values:
            return value
        else:
            logger.warning(f"Invalid fixedRotationOffset value '{value}', defaulting to 'auto'")
            return "auto"
    
    # Default fallback
    logger.warning(f"Unexpected fixedRotationOffset type {type(value)}, defaulting to 'auto'")
    return "auto"


def validate_rostering_basis_combination(rostering_basis: str, offset_mode: str, input_data: Dict[str, Any]) -> None:
    """
    Validate that rosteringBasis and fixedRotationOffset are compatible.
    
    Valid combinations:
    - demandBased + auto
    - demandBased + solverOptimized
    - outcomeBased + ouOffsets
    
    Invalid combinations:
    - demandBased + ouOffsets
    - outcomeBased + auto
    - outcomeBased + solverOptimized
    
    Args:
        rostering_basis: "demandBased" or "outcomeBased"
        offset_mode: "auto", "ouOffsets", or "solverOptimized"
        input_data: Full input JSON data (to check for ouOffsets)
    
    Raises:
        ValueError: If combination is invalid
    """
    # Define valid combinations
    valid_combinations = {
        "demandBased": ["auto", "solverOptimized"],
        "outcomeBased": ["ouOffsets"]
    }
    
    # Check if combination is valid
    allowed_modes = valid_combinations.get(rostering_basis, [])
    if offset_mode not in allowed_modes:
        raise ValueError(
            f"Invalid combination: rosteringBasis='{rostering_basis}' cannot use fixedRotationOffset='{offset_mode}'. "
            f"Valid modes for {rostering_basis}: {allowed_modes}"
        )
    
    # Additional validation for outcomeBased mode
    if rostering_basis == "outcomeBased":
        if offset_mode == "ouOffsets":
            ou_offsets = input_data.get('ouOffsets', [])
            if not ou_offsets:
                raise ValueError(
                    "outcomeBased mode with fixedRotationOffset='ouOffsets' requires 'ouOffsets' array in input"
                )
    
    logger.info(f"✓ Valid combination: rosteringBasis='{rostering_basis}' + fixedRotationOffset='{offset_mode}'")


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


def has_off_days(work_pattern: List[str]) -> bool:
    """
    Check if work pattern contains off days ('O').
    
    Args:
        work_pattern: List like ['D', 'D', 'N', 'N', 'O', 'O']
    
    Returns:
        True if pattern contains 'O' days
    """
    return 'O' in work_pattern


def validate_ou_offsets(input_data: Dict[str, Any], cycle_length: int) -> tuple[bool, List[str]]:
    """
    Validate ouOffsets configuration.
    
    Args:
        input_data: Full input JSON data
        cycle_length: Pattern cycle length
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    ou_offsets_list = input_data.get('ouOffsets', [])
    if not ou_offsets_list:
        errors.append("fixedRotationOffset='ouOffsets' requires 'ouOffsets' array in input")
        return False, errors
    
    # Build OU offset map
    ou_offset_map = {}
    for entry in ou_offsets_list:
        ou_id = entry.get('ouId')
        offset = entry.get('rotationOffset')
        
        if not ou_id:
            errors.append(f"ouOffsets entry missing 'ouId': {entry}")
            continue
        
        if offset is None:
            errors.append(f"ouOffsets entry for OU '{ou_id}' missing 'rotationOffset'")
            continue
        
        # Validate offset within cycle length
        if not isinstance(offset, int):
            errors.append(f"OU '{ou_id}' has non-integer offset: {offset}")
            continue
        
        if offset < 0 or offset >= cycle_length:
            errors.append(f"OU '{ou_id}' offset {offset} out of range [0, {cycle_length-1}] for cycle length {cycle_length}")
            continue
        
        ou_offset_map[ou_id] = offset
    
    # Warn (don't error) if employees have OUs not in the map
    employees = input_data.get('employees', [])
    for emp in employees:
        emp_id = emp.get('employeeId')
        ou_id = emp.get('ouId')
        
        if ou_id and ou_id not in ou_offset_map:
            logger.warning(f"Employee '{emp_id}' has OU '{ou_id}' not found in ouOffsets array - will use rotationOffset=0")
    
    is_valid = len(errors) == 0
    return is_valid, errors


def apply_ou_offsets(input_data: Dict[str, Any]) -> int:
    """
    Apply OU-level offsets to employees.
    
    Each employee inherits the rotationOffset from their OU.
    
    Args:
        input_data: Full input JSON data (modified in place)
    
    Returns:
        Number of employees updated
    """
    ou_offsets_list = input_data.get('ouOffsets', [])
    
    # Build OU offset map
    ou_offset_map = {}
    for entry in ou_offsets_list:
        ou_id = entry.get('ouId')
        offset = entry.get('rotationOffset')
        if ou_id and offset is not None:
            ou_offset_map[ou_id] = offset
    
    # Apply to employees based on their ouId
    updated_count = 0
    employees = input_data.get('employees', [])
    for emp in employees:
        ou_id = emp.get('ouId')
        if ou_id and ou_id in ou_offset_map:
            new_offset = ou_offset_map[ou_id]
            old_offset = emp.get('rotationOffset', 0)
            
            if old_offset != new_offset:
                emp['rotationOffset'] = new_offset
                updated_count += 1
    
    return updated_count


def should_stagger_offsets(mode: str, input_data: Dict[str, Any]) -> bool:
    """
    Determine if offsets should be automatically processed.
    
    Args:
        mode: Normalized mode ("auto", "ouOffsets", "solverOptimized")
        input_data: Full input JSON data
    
    Returns:
        True if offsets need processing
    """
    if mode == "solverOptimized":
        logger.info("Mode 'solverOptimized' - no preprocessing needed (solver will optimize)")
        return False
    
    if mode in ["auto", "ouOffsets"]:
        # Check if there are employees
        employees = input_data.get('employees', [])
        if not employees:
            logger.warning("No employees found in input")
            return False
        
        return True
    
    return False


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


def stagger_offsets(employees: List[Dict[str, Any]], cycle_length: int) -> int:
    """
    Distribute employees evenly across rotation offsets.
    
    Args:
        employees: List of employee objects (modified in place)
        cycle_length: Pattern cycle length (e.g., 6 for DDNNOO)
    
    Returns:
        Number of employees updated
    """
    updated_count = 0
    
    for i, emp in enumerate(employees):
        new_offset = i % cycle_length
        old_offset = emp.get('rotationOffset', 0)
        
        if old_offset != new_offset:
            emp['rotationOffset'] = new_offset
            updated_count += 1
    
    return updated_count


def ensure_staggered_offsets(input_data: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
    """
    Ensure employees have proper rotation offsets based on fixedRotationOffset mode.
    
    Supported modes:
    - "auto": Sequential staggering (0, 1, 2, ...)
    - "ouOffsets": Apply OU-level offsets
    - "solverOptimized": Skip processing (solver decides)
    - true (legacy): Converts to "auto"
    - false (legacy): Converts to "solverOptimized"
    
    Args:
        input_data: Full input JSON data (modified in place)
        force: If True, process even if mode suggests skipping
    
    Returns:
        Modified input_data with offsets applied
    
    Raises:
        ValueError: If validation fails (invalid OU offsets, etc.)
    """
    logger.info("=" * 80)
    logger.info("OFFSET MANAGER: Processing rotation offsets")
    logger.info("=" * 80)
    
    employees = input_data.get('employees', [])
    if not employees:
        logger.warning("No employees to process")
        return input_data
    
    # Normalize rosteringBasis
    rostering_basis_raw = input_data.get('rosteringBasis')
    rostering_basis = normalize_rostering_basis(rostering_basis_raw)
    
    # Update input_data to use normalized value
    if input_data.get('rosteringBasis') != rostering_basis:
        logger.info(f"Setting rosteringBasis: {rostering_basis_raw} → '{rostering_basis}'")
        input_data['rosteringBasis'] = rostering_basis
    
    # Normalize and store the offset mode
    raw_value = input_data.get('fixedRotationOffset', True)
    mode = normalize_fixed_rotation_offset(raw_value)
    
    # Update input_data to use normalized string value
    if input_data['fixedRotationOffset'] != mode:
        logger.info(f"Converting fixedRotationOffset: {raw_value} → '{mode}'")
        input_data['fixedRotationOffset'] = mode
    
    # Validate combination of rosteringBasis and fixedRotationOffset
    try:
        validate_rostering_basis_combination(rostering_basis, mode, input_data)
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise
    
    logger.info(f"Mode: {mode}")
    
    # Check if processing is needed
    if not force and not should_stagger_offsets(mode, input_data):
        logger.info(f"No offset processing needed for mode '{mode}'")
        logger.info("=" * 80)
        return input_data
    
    # Determine cycle length from patterns
    cycle_length = 6  # Default for DDNNOO
    demand_items = input_data.get('demandItems', [])
    if demand_items and demand_items[0].get('requirements'):
        first_pattern = demand_items[0]['requirements'][0].get('workPattern', [])
        if first_pattern:
            cycle_length = get_pattern_cycle_length(first_pattern)
            logger.info(f"Detected pattern cycle length: {cycle_length} from {first_pattern}")
    
    # Get current state
    before_dist = get_current_offset_distribution(employees)
    logger.info(f"Current offset distribution: {dict(sorted(before_dist.items()))}")
    
    # Process based on mode
    if mode == "auto":
        # Check if already properly staggered
        if len(before_dist) > 1 and all(count > 0 for count in before_dist.values()):
            logger.info("✓ Offsets already staggered - no changes needed")
        else:
            # Apply sequential staggering
            logger.info(f"Applying sequential staggered offsets across {cycle_length} values...")
            updated_count = stagger_offsets(employees, cycle_length)
            logger.info(f"✓ Updated {updated_count} employees")
    
    elif mode == "ouOffsets":
        # Validate OU offsets first
        is_valid, errors = validate_ou_offsets(input_data, cycle_length)
        if not is_valid:
            error_msg = "OU offset validation failed:\n  - " + "\n  - ".join(errors)
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Apply OU offsets
        logger.info("Applying OU-level offsets...")
        updated_count = apply_ou_offsets(input_data)
        logger.info(f"✓ Updated {updated_count} employees from OU offsets")
    
    # Report final state
    after_dist = get_current_offset_distribution(employees)
    logger.info(f"Final offset distribution: {dict(sorted(after_dist.items()))}")
    
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
    
    raw_value = input_data.get('fixedRotationOffset', True)
    mode = normalize_fixed_rotation_offset(raw_value)
    
    employees = input_data.get('employees', [])
    
    if not employees:
        return True, []  # No employees, nothing to validate
    
    # Check for O-patterns
    has_o_pattern = False
    demand_items = input_data.get('demandItems', [])
    cycle_length = 6  # default
    
    for demand in demand_items:
        requirements = demand.get('requirements', [])
        for req in requirements:
            work_pattern = req.get('workPattern', [])
            if has_off_days(work_pattern):
                has_o_pattern = True
                cycle_length = len(work_pattern)
                break
    
    if not has_o_pattern and mode != "solverOptimized":
        issues.append(f"No O-patterns found but fixedRotationOffset is '{mode}' - consider 'solverOptimized'")
    
    # Validate based on mode
    if mode == "ouOffsets":
        is_valid, errors = validate_ou_offsets(input_data, cycle_length)
        if not is_valid:
            issues.extend(errors)
    
    elif mode == "auto":
        offset_dist = get_current_offset_distribution(employees)
        
        if len(offset_dist) == 1 and 0 in offset_dist:
            issues.append(f"All {len(employees)} employees have offset 0 - need staggered offsets for O-pattern coverage (will be auto-fixed)")
        elif len(offset_dist) < 3 and has_o_pattern:
            issues.append(f"Only {len(offset_dist)} different offset values - recommend more variety for better coverage (will be auto-fixed)")
    
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
