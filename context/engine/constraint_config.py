"""Constraint Configuration Helper - v0.98

This module provides helper functions to read constraint parameters from input JSON
with support for scheme-specific, product-type-specific, and rank-specific overrides.

New JSON Format (v0.98):
    {
      "id": "momDailyHoursCap",
      "defaultValue": 9,
      "schemeOverrides": {
        "A": 14,
        "B": 13,
        "P": 9
      }
    }

Old JSON Format (v0.7) - Still supported:
    {
      "id": "momDailyHoursCap",
      "params": {
        "maxDailyHoursA": 14,
        "maxDailyHoursB": 13,
        "maxDailyHoursP": 9
      }
    }
"""

from typing import Any, Dict, List, Optional
from calendar import monthrange


def get_constraint_param(
    ctx: dict,
    constraint_id: str,
    employee: Optional[dict] = None,
    param_name: Optional[str] = None,
    default: Any = None
) -> Any:
    """
    Get constraint parameter value with scheme/product/rank-specific support.
    
    Supports both NEW format (v0.98) and OLD format (v0.7) for backward compatibility.
    
    NEW format lookup priority:
    1. Scheme-specific override with productTypes/ranks filter match
    2. Scheme-specific override (simple value)
    3. defaultValue
    4. Fallback to default parameter
    
    OLD format lookup priority:
    1. Scheme-specific parameter (e.g., 'maxDailyHoursA')
    2. General parameter (e.g., 'maxDailyHoursGeneral')
    3. Base parameter (e.g., 'maxDailyHours')
    4. Fallback to default parameter
    
    Args:
        ctx: Context dict with 'constraintList'
        constraint_id: Constraint identifier (e.g., 'momDailyHoursCap')
        employee: Employee dict with 'scheme', 'productTypes', 'rank' (optional)
        param_name: Parameter name for OLD format lookup (e.g., 'maxDailyHours')
        default: Default value if not found
    
    Returns:
        Parameter value for this employee/constraint
    
    Examples:
        # NEW format (v0.98) - with employee
        max_hours = get_constraint_param(ctx, 'momDailyHoursCap', employee=emp, default=9)
        
        # NEW format - without employee (returns defaultValue)
        max_weekly = get_constraint_param(ctx, 'momWeeklyHoursCap44h', default=44)
        
        # OLD format (v0.7) - backward compatible
        max_hours = get_constraint_param(ctx, 'momDailyHoursCap', employee=emp, 
                                        param_name='maxDailyHours', default=9)
    """
    from context.engine.time_utils import normalize_scheme
    
    constraint_list = ctx.get('constraintList', [])
    
    # Find constraint by ID
    constraint = None
    for c in constraint_list:
        if c.get('id') == constraint_id:
            constraint = c
            break
    
    if not constraint:
        return default
    
    # NEW format (v0.98): has 'defaultValue' or 'schemeOverrides'
    if 'defaultValue' in constraint or 'schemeOverrides' in constraint:
        return _get_param_new_format(constraint, employee, default)
    
    # OLD format (v0.7): has 'params' dict
    if 'params' in constraint:
        return _get_param_old_format(constraint, employee, param_name, default)
    
    # No recognized format, return default
    return default


def _get_param_new_format(constraint: dict, employee: Optional[dict], default: Any) -> Any:
    """
    Extract parameter from NEW format (v0.98).
    
    NEW format:
        {
          "id": "maxConsecutiveWorkingDays",
          "defaultValue": 12,
          "schemeOverrides": {
            "A": {
              "productTypes": ["APO"],
              "value": 8
            },
            "B": 12,
            "P": 12
          }
        }
    """
    from context.engine.time_utils import normalize_scheme
    
    # If no employee, return defaultValue
    if employee is None:
        return constraint.get('defaultValue', default)
    
    # Extract employee attributes
    scheme_raw = employee.get('scheme', 'A')
    scheme = normalize_scheme(scheme_raw)
    product_types = employee.get('productTypes', [])
    rank = employee.get('rank', '')
    
    # Check for scheme overrides
    scheme_overrides = constraint.get('schemeOverrides', {})
    
    if scheme in scheme_overrides:
        override = scheme_overrides[scheme]
        
        # Simple override: just a value (int, float, str)
        if isinstance(override, (int, float, str)):
            return override
        
        # Complex override: single dict with filters
        if isinstance(override, dict):
            # Check if this is a value dict (has 'value' key)
            if 'value' in override:
                # Check filters
                if _matches_filters(override, product_types, rank):
                    return override['value']
            else:
                # No 'value' key, treat entire dict as override
                return override
        
        # Array of rules: check each rule's filters
        if isinstance(override, list):
            for rule in override:
                if isinstance(rule, dict):
                    if _matches_filters(rule, product_types, rank):
                        return rule.get('value')
                else:
                    # Simple value in array
                    return rule
    
    # No scheme override matched, return defaultValue
    return constraint.get('defaultValue', default)


def _get_param_old_format(
    constraint: dict,
    employee: Optional[dict],
    param_name: Optional[str],
    default: Any
) -> Any:
    """
    Extract parameter from OLD format (v0.7).
    
    OLD format:
        {
          "id": "momDailyHoursCap",
          "params": {
            "maxDailyHoursGeneral": 9,
            "maxDailyHoursA": 14,
            "maxDailyHoursB": 13,
            "maxDailyHoursP": 9
          }
        }
    """
    from context.engine.time_utils import normalize_scheme
    
    params = constraint.get('params', {})
    
    if not param_name:
        # No param_name specified, return first param value or default
        if params:
            return list(params.values())[0]
        return default
    
    # If no employee, try to find general or base parameter
    if employee is None:
        # Try: paramNameGeneral, paramName, or first value
        general_param = f"{param_name}General"
        if general_param in params:
            return params[general_param]
        if param_name in params:
            return params[param_name]
        if params:
            return list(params.values())[0]
        return default
    
    # Extract employee scheme
    scheme_raw = employee.get('scheme', 'A')
    scheme = normalize_scheme(scheme_raw)
    
    # Priority 1: Scheme-specific parameter (e.g., 'maxDailyHoursA')
    scheme_param = f"{param_name}{scheme}"
    if scheme_param in params:
        return params[scheme_param]
    
    # Priority 2: General parameter (e.g., 'maxDailyHoursGeneral')
    general_param = f"{param_name}General"
    if general_param in params:
        return params[general_param]
    
    # Priority 3: Base parameter (e.g., 'maxDailyHours')
    if param_name in params:
        return params[param_name]
    
    # Priority 4: Default
    return default


def _matches_filters(rule: dict, product_types: List[str], rank: str) -> bool:
    """
    Check if employee matches rule's productTypes and ranks filters.
    
    Args:
        rule: Rule dict with optional 'productTypes' and 'ranks' filters
        product_types: Employee's product types
        rank: Employee's rank
    
    Returns:
        True if employee matches all specified filters
    """
    # Check productTypes filter
    required_products = rule.get('productTypes', [])
    if required_products:
        # Employee must have ALL required product types
        if not all(pt in product_types for pt in required_products):
            return False
    
    # Check ranks filter
    required_ranks = rule.get('ranks', [])
    if required_ranks:
        # Employee rank must be in the list
        if rank not in required_ranks:
            return False
    
    # Check employeeType filter (for future use)
    required_emp_types = rule.get('employeeTypes', [])
    if required_emp_types:
        # For now, we don't have employeeType in employee dict
        # This is a placeholder for future functionality
        pass
    
    # All filters passed
    return True


def get_constraint_by_id(ctx: dict, constraint_id: str) -> Optional[dict]:
    """
    Find constraint by ID in constraintList.
    
    Args:
        ctx: Context dict with 'constraintList'
        constraint_id: Constraint identifier
    
    Returns:
        Constraint dict or None if not found
    """
    constraint_list = ctx.get('constraintList', [])
    for c in constraint_list:
        if c.get('id') == constraint_id:
            return c
    return None


def is_constraint_enabled(ctx: dict, constraint_id: str) -> bool:
    """
    Check if a constraint is enabled in the input.
    
    Args:
        ctx: Context dict with 'constraintList'
        constraint_id: Constraint identifier
    
    Returns:
        True if constraint exists and is not explicitly disabled
    """
    constraint = get_constraint_by_id(ctx, constraint_id)
    if not constraint:
        return False
    
    # Check if explicitly disabled
    enabled = constraint.get('enabled', True)
    return enabled


def get_all_constraint_ids(ctx: dict) -> List[str]:
    """
    Get list of all constraint IDs in the input.
    
    Args:
        ctx: Context dict with 'constraintList'
    
    Returns:
        List of constraint IDs
    """
    constraint_list = ctx.get('constraintList', [])
    return [c.get('id') for c in constraint_list if c.get('id')]


def get_constraint_frequency(ctx: dict, constraint_id: str) -> Optional[str]:
    """
    Get frequency metadata for a constraint.
    
    Frequency indicates how often the constraint is checked/applied:
    - "Daily" - Once per day
    - "Weekly" - Once per week
    - "Monthly" - Once per month
    - "Per Shift" - Applied to each shift
    - "Per Day" - Checked per calendar day
    - "Between Shifts" - Checked between consecutive shifts
    - "Continuous" - Checked across rolling window
    
    Args:
        ctx: Context dict with 'constraintList'
        constraint_id: Constraint identifier
    
    Returns:
        Frequency string or None if not specified
    
    Example:
        freq = get_constraint_frequency(ctx, 'momDailyHoursCap')
        # Returns: "Daily"
    """
    constraint = get_constraint_by_id(ctx, constraint_id)
    return constraint.get('frequency') if constraint else None


def get_constraint_uom(ctx: dict, constraint_id: str) -> Optional[str]:
    """
    Get unit of measurement (UOM) for a constraint.
    
    UOM indicates the unit for constraint values:
    - "Days"
    - "Hours"
    - "Minutes"
    - "Number"
    
    Args:
        ctx: Context dict with 'constraintList'
        constraint_id: Constraint identifier
    
    Returns:
        UOM string or None if not specified
    
    Example:
        uom = get_constraint_uom(ctx, 'momWeeklyHoursCap44h')
        # Returns: "Hours"
    """
    constraint = get_constraint_by_id(ctx, constraint_id)
    return constraint.get('uom') if constraint else None


def get_constraint_metadata(ctx: dict, constraint_id: str) -> dict:
    """
    Get all metadata for a constraint (frequency, uom, description, etc.).
    
    Args:
        ctx: Context dict with 'constraintList'
        constraint_id: Constraint identifier
    
    Returns:
        Dict with constraint metadata or empty dict if not found
    
    Example:
        metadata = get_constraint_metadata(ctx, 'momDailyHoursCap')
        # Returns: {
        #   'id': 'momDailyHoursCap',
        #   'enforcement': 'hard',
        #   'description': 'Maximum daily working hours',
        #   'frequency': 'Daily',
        #   'uom': 'Hours',
        #   'defaultValue': 9,
        #   ...
        # }
    """
    constraint = get_constraint_by_id(ctx, constraint_id)
    return constraint if constraint else {}


def format_constraint_value(value: Any, uom: Optional[str] = None, 
                           frequency: Optional[str] = None) -> str:
    """
    Format constraint value with UOM and frequency for display.
    
    Args:
        value: Constraint value
        uom: Unit of measurement
        frequency: Frequency of application
    
    Returns:
        Formatted string
    
    Examples:
        format_constraint_value(44, "Hours", "Weekly")  # "44 Hours/Weekly"
        format_constraint_value(8, "Days")  # "8 Days"
        format_constraint_value(1, "Number", "Per Day")  # "1/Per Day"
    """
    parts = [str(value)]
    
    if uom:
        parts.append(uom)
    
    if frequency:
        if uom:
            parts.append(f"/{frequency}")
        else:
            parts.append(frequency)
    
    return " ".join(parts)


def get_employee_type(employee: dict) -> str:
    """
    Get employee type from employee dict.
    
    Employee dict has 'local' field: 1 = Local, 0 = Foreigner
    
    Args:
        employee: Employee dict with 'local' field
    
    Returns:
        'Local' or 'Foreigner'
    """
    local_flag = employee.get('local', 1)
    return 'Local' if local_flag == 1 else 'Foreigner'


def matches_monthly_limit_filters(limit_config: dict, employee: dict) -> bool:
    """
    Check if employee matches monthly limit filters.
    
    Handles complex filtering including:
    - employeeType (Local/Foreigner)
    - schemes
    - productTypes
    - ranks (with exclusion support)
    
    Args:
        limit_config: Monthly limit configuration with applicableTo filters
        employee: Employee dict
    
    Returns:
        True if employee matches all filters
    """
    from context.engine.time_utils import normalize_scheme
    
    applicable_to = limit_config.get('applicableTo', {})
    
    # Get employee attributes
    emp_type = get_employee_type(employee)
    emp_scheme = normalize_scheme(employee.get('scheme', 'A'))
    emp_products = employee.get('productTypes', [])
    emp_rank = employee.get('rank', '')
    
    # Check employeeType filter
    allowed_emp_types = applicable_to.get('employeeType', 'All')
    if allowed_emp_types != 'All':
        if isinstance(allowed_emp_types, str):
            allowed_emp_types = [allowed_emp_types]
        if emp_type not in allowed_emp_types:
            return False
    
    # Check schemes filter
    allowed_schemes = applicable_to.get('schemes', 'All')
    if allowed_schemes != 'All':
        if isinstance(allowed_schemes, str):
            allowed_schemes = [allowed_schemes]
        if emp_scheme not in allowed_schemes:
            return False
    
    # Check productTypes filter
    allowed_products = applicable_to.get('productTypes', 'All')
    if allowed_products != 'All':
        if isinstance(allowed_products, str):
            allowed_products = [allowed_products]
        # Employee must have at least one of the required product types
        if not any(pt in emp_products for pt in allowed_products):
            return False
    
    # Check ranks filter (with exclusion support)
    allowed_ranks = applicable_to.get('ranks', 'All')
    if allowed_ranks != 'All':
        if isinstance(allowed_ranks, str):
            allowed_ranks = [allowed_ranks]
        if emp_rank not in allowed_ranks:
            return False
    
    # Check ranksExcluded filter (complex: per employee type)
    ranks_excluded = applicable_to.get('ranksExcluded', {})
    if ranks_excluded:
        excluded_for_type = ranks_excluded.get(emp_type, [])
        if emp_rank in excluded_for_type:
            return False
    
    return True


def get_monthly_hour_limits(ctx: dict, employee: dict, year: int, month: int) -> dict:
    """
    Get monthly hour limits for an employee based on month length.
    
    Returns limits including:
    - normalHours or minimumContractualHours (for APGD-D10)
    - maxOvertimeHours
    - totalMaxHours
    
    Args:
        ctx: Context dict with 'monthlyHourLimits'
        employee: Employee dict
        year: Year (for calculating month length)
        month: Month (1-12)
    
    Returns:
        Dict with hour limits:
        {
            'normalHours': 176,              # Standard monthly hours
            'minimumContractualHours': None, # APGD-D10 minimum (if applicable)
            'maxOvertimeHours': 112,
            'totalMaxHours': 288,
            'enforcement': 'hard',           # 'hard' or 'soft'
            'ruleId': 'standardMonthlyHours' # Which rule was matched
        }
    
    Example:
        limits = get_monthly_hour_limits(ctx, employee, 2025, 2)
        # For standard employee in Feb: normalHours=176, maxOvertimeHours=112
        # For APGD-D10 in Feb: minimumContractualHours=224, maxOvertimeHours=112
    """
    # Calculate month length
    _, month_days = monthrange(year, month)
    month_key = str(month_days)
    
    monthly_limits = ctx.get('monthlyHourLimits', [])
    
    # Sort rules by specificity (most specific first)
    # Rules with more filters (ranksExcluded, specific ranks, specific productTypes) come first
    def rule_specificity(limit_config):
        applicable = limit_config.get('applicableTo', {})
        score = 0
        
        # Rank exclusions make a rule very specific
        if 'ranksExcluded' in applicable:
            score += 100
        
        # Specific ranks make a rule specific
        ranks = applicable.get('ranks', 'All')
        if ranks != 'All' and isinstance(ranks, list):
            score += 50
        
        # Specific productTypes make a rule specific
        product_types = applicable.get('productTypes', 'All')
        if product_types != 'All' and isinstance(product_types, list):
            score += 30
        
        # Specific schemes make a rule specific
        schemes = applicable.get('schemes', 'All')
        if schemes != 'All' and isinstance(schemes, list):
            score += 20
        
        # Specific employeeType makes a rule specific
        emp_type = applicable.get('employeeType', 'All')
        if emp_type != 'All' and isinstance(emp_type, list):
            score += 10
        
        return -score  # Negative for descending sort (most specific first)
    
    sorted_limits = sorted(monthly_limits, key=rule_specificity)
    
    # Check rules in order of specificity (most specific to least specific)
    for limit_config in sorted_limits:
        if not matches_monthly_limit_filters(limit_config, employee):
            continue
        
        values = limit_config.get('valuesByMonthLength', {}).get(month_key, {})
        if not values:
            continue
        
        # Found a matching rule
        return {
            'normalHours': values.get('normalHours'),
            'minimumContractualHours': values.get('minimumContractualHours'),
            'maxOvertimeHours': values.get('maxOvertimeHours'),
            'totalMaxHours': values.get('totalMaxHours'),
            'enforcement': limit_config.get('enforcement', 'hard'),
            'ruleId': limit_config.get('id'),
            'monthDays': month_days
        }
    
    # No matching rule found, return defaults based on month length
    month_defaults = {
        28: {'normalHours': 176, 'maxOvertimeHours': 112, 'totalMaxHours': 288},
        29: {'normalHours': 182, 'maxOvertimeHours': 116, 'totalMaxHours': 298},
        30: {'normalHours': 189, 'maxOvertimeHours': 120, 'totalMaxHours': 309},
        31: {'normalHours': 195, 'maxOvertimeHours': 124, 'totalMaxHours': 319}
    }
    
    defaults = month_defaults.get(month_days, month_defaults[30])
    return {
        'normalHours': defaults['normalHours'],
        'minimumContractualHours': None,
        'maxOvertimeHours': defaults['maxOvertimeHours'],
        'totalMaxHours': defaults['totalMaxHours'],
        'enforcement': 'hard',
        'ruleId': 'default',
        'monthDays': month_days
    }


def get_all_monthly_limit_rules(ctx: dict) -> List[dict]:
    """
    Get all monthly hour limit rules.
    
    Args:
        ctx: Context dict with 'monthlyHourLimits'
    
    Returns:
        List of monthly limit rule configurations
    """
    return ctx.get('monthlyHourLimits', [])


# Convenience function for common pattern
def get_scheme_specific_value(
    ctx: dict,
    constraint_id: str,
    employee: dict,
    default: Any = None
) -> Any:
    """
    Convenience wrapper for getting scheme-specific constraint values.
    
    This is the most common usage pattern - just pass employee and get the value.
    
    Args:
        ctx: Context dict
        constraint_id: Constraint ID
        employee: Employee dict
        default: Default value
    
    Returns:
        Constraint value for this employee's scheme
    """
    return get_constraint_param(ctx, constraint_id, employee=employee, default=default)
