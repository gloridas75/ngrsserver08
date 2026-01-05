"""
Work Pattern Validator - Relaxed Version

RELAXED VALIDATION: Only checks for patterns that are fundamentally impossible:
- Empty patterns
- Excessive consecutive work days (>12 without any 'O')

ALLOWS flexible patterns like:
- ['D','D','D','D','D','D','D'] - CP-SAT solver will add off-days as needed
- ['D','D','D','O'] - Short patterns are valid

The CP-SAT solver (in both demandBased and outcomeBased modes) will optimize
work/off-day distribution to satisfy all constraints (C1-C17).
"""

import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


def validate_work_pattern(pattern: List[str], shift_details: dict, scheme: str) -> Tuple[bool, List[str]]:
    """
    Validate work pattern for critical structural issues only.
    
    Args:
        pattern: List of shift codes (e.g., ['D','D','D','O'])
        shift_details: Shift timing information (not used in relaxed validation)
        scheme: Employment scheme (SchemeA, SchemeB, SchemeP)
    
    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []
    
    # Check 1: Empty pattern
    if not pattern or len(pattern) == 0:
        violations.append("❌ Pattern is empty - must contain at least one shift code")
        return False, violations
    
    # Check 2: Excessive consecutive work days (>12 without 'O')
    # Count consecutive work days without any 'O' in pattern
    consecutive_work_days = 0
    max_consecutive = 0
    
    for code in pattern:
        if code != 'O':
            consecutive_work_days += 1
            max_consecutive = max(max_consecutive, consecutive_work_days)
        else:
            consecutive_work_days = 0
    
    if max_consecutive > 12:
        violations.append(
            f"❌ Pattern has {max_consecutive} consecutive work days without any 'O' (off-day). "
            f"Maximum allowed: 12. Add 'O' to break the sequence."
        )
        return False, violations
    
    # Pattern passed critical checks
    return True, []


def validate_pattern_for_requirement(
    requirement: dict,
    demand: dict,
    employees: List[dict],
    ctx: dict
) -> Tuple[bool, Dict[str, List[str]]]:
    """
    Validate work pattern for a requirement across all applicable schemes.
    
    Args:
        requirement: Work requirement with workPattern
        demand: Demand item configuration  
        employees: List of employees for this requirement
        ctx: Context dictionary
    
    Returns:
        Tuple of (is_valid, violations_by_scheme)
    """
    pattern = requirement.get('workPattern', [])
    
    # Get shift details
    shifts = demand.get('shifts', [])
    if not shifts:
        return False, {'ALL': ['No shift configuration found']}
    
    shift_details_list = shifts[0].get('shiftDetails', [])
    if not shift_details_list:
        return False, {'ALL': ['No shift details found']}
    
    shift_details = shift_details_list[0]  # Use first shift for timing
    
    # Determine applicable schemes
    applicable_schemes = _get_applicable_schemes(employees, ctx)
    
    violations_by_scheme = {}
    all_valid = True
    
    # Validate against each scheme
    for scheme in applicable_schemes:
        is_valid, violations = validate_work_pattern(pattern, shift_details, scheme)
        
        if not is_valid:
            violations_by_scheme[scheme] = violations
            all_valid = False
    
    return all_valid, violations_by_scheme


def _get_applicable_schemes(employees: List[dict], ctx: dict) -> List[str]:
    """Determine which employment schemes apply to this group of employees."""
    schemes_in_use = set()
    
    for emp in employees:
        scheme = emp.get('scheme', emp.get('employmentScheme', 'SchemeB'))
        # Normalize scheme name
        if scheme == 'A' or 'Scheme A' in scheme:
            schemes_in_use.add('SchemeA')
        elif scheme == 'P' or 'Scheme P' in scheme:
            schemes_in_use.add('SchemeP')
        else:
            schemes_in_use.add('SchemeB')
    
    # If no employees, use context scheme
    if not schemes_in_use:
        context_scheme = ctx.get('planningReference', {}).get('scheme', 'SchemeB')
        schemes_in_use.add(context_scheme.replace(' ', ''))
    
    return sorted(schemes_in_use)


def log_pattern_validation_results(
    is_valid: bool,
    violations_by_scheme: Dict[str, List[str]],
    requirement_id: str = None
):
    """Log pattern validation results with formatted output."""
    if is_valid:
        logger.info("=" * 80)
        logger.info("✅ WORK PATTERN VALIDATION: PASSED")
        if requirement_id:
            logger.info(f"   Requirement: {requirement_id}")
        logger.info("   Pattern passes critical checks (empty pattern, excessive consecutive days)")
        logger.info("   Note: CP-SAT solver will optimize work/off-day distribution to satisfy all constraints")
        logger.info("=" * 80)
    else:
        logger.error("=" * 80)
        logger.error("❌ WORK PATTERN VALIDATION: FAILED")
        if requirement_id:
            logger.error(f"   Requirement: {requirement_id}")
        logger.error("")
        logger.error("The work pattern has CRITICAL issues:")
        logger.error("")
        
        for scheme, violations in violations_by_scheme.items():
            logger.error(f"  {scheme}:")
            for violation in violations:
                logger.error(f"    {violation}")
            logger.error("")
        
        logger.error("=" * 80)
        logger.error("RECOMMENDED ACTIONS:")
        logger.error("")
        logger.error("  1. For empty patterns: Specify at least one shift code (e.g., ['D'])")
        logger.error("")
        logger.error("  2. For excessive consecutive work days (>12):")
        logger.error("     Add 'O' (off-day) to break the sequence")
        logger.error("     Example: ['D','D','D','D','D','D','D','O','D','D','D','D','D','D']")
        logger.error("            → ['D','D','D','D','D','D','O','D','D','D','D','D','D','O']")
        logger.error("")
        logger.error("  3. Flexible patterns like ['D','D','D','D','D','D','D'] are valid")
        logger.error("     The solver will automatically add off-days to satisfy constraints")
        logger.error("")
        logger.error("=" * 80)
