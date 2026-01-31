"""
Input Validator for NGRS Solver
Validates input JSON before submission to solver to catch errors early.
"""

from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
import re


class ValidationError:
    """Represents a validation error or warning"""
    def __init__(self, field: str, code: str, message: str, severity: str = "error"):
        self.field = field
        self.code = code
        self.message = message
        self.severity = severity
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "field": self.field,
            "code": self.code,
            "message": self.message,
            "severity": self.severity
        }


class ValidationResult:
    """Result of input validation"""
    def __init__(self):
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []
    
    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0
    
    def add_error(self, field: str, code: str, message: str):
        self.errors.append(ValidationError(field, code, message, "error"))
    
    def add_warning(self, field: str, code: str, message: str):
        self.warnings.append(ValidationError(field, code, message, "warning"))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings]
        }


def validate_input(data: dict) -> ValidationResult:
    """
    Comprehensive validation of solver input.
    
    Returns ValidationResult with errors and warnings.
    Errors block submission, warnings are informational.
    """
    result = ValidationResult()
    
    # Level 1: Schema Structure
    _validate_schema_structure(data, result)
    
    # If critical structure missing, return early
    if not result.is_valid:
        return result
    
    # Level 2: Business Logic
    _validate_planning_horizon(data, result)
    _validate_rostering_basis(data, result)
    _validate_demand_items(data, result)
    _validate_employees(data, result)
    _validate_scheme_consistency(data, result)
    _validate_constraints(data, result)
    _validate_ou_employee_mapping(data, result)
    
    # Level 3: Feasibility Pre-Checks
    _validate_feasibility(data, result)
    
    return result


def _validate_schema_structure(data: dict, result: ValidationResult):
    """Validate basic schema structure and required fields"""
    
    # Required top-level fields
    required_fields = [
        'schemaVersion',
        'planningReference',
        'planningHorizon',
        'demandItems',
        'employees'
    ]
    
    for field in required_fields:
        if field not in data:
            result.add_error(field, "MISSING_FIELD", f"Required field '{field}' is missing")
    
    # Schema version check
    if 'schemaVersion' in data:
        version = data['schemaVersion']
        if version not in ['0.70', '0.95', '0.98']:
            result.add_warning('schemaVersion', 'UNKNOWN_VERSION', 
                             f"Schema version '{version}' may not be fully supported")
    
    # Check arrays are actually arrays
    if 'demandItems' in data and not isinstance(data['demandItems'], list):
        result.add_error('demandItems', 'INVALID_TYPE', 
                        "demandItems must be an array")
    
    if 'employees' in data and not isinstance(data['employees'], list):
        result.add_error('employees', 'INVALID_TYPE', 
                        "employees must be an array")
    
    # Check non-empty arrays
    if 'demandItems' in data and isinstance(data['demandItems'], list):
        if len(data['demandItems']) == 0:
            result.add_error('demandItems', 'EMPTY_ARRAY', 
                           "demandItems array cannot be empty")
    
    if 'employees' in data and isinstance(data['employees'], list):
        if len(data['employees']) == 0:
            result.add_error('employees', 'EMPTY_ARRAY', 
                           "employees array cannot be empty")


def _validate_planning_horizon(data: dict, result: ValidationResult):
    """Validate planning horizon dates"""
    
    if 'planningHorizon' not in data:
        return
    
    horizon = data['planningHorizon']
    
    # Check required date fields
    if 'startDate' not in horizon:
        result.add_error('planningHorizon.startDate', 'MISSING_FIELD', 
                        "startDate is required")
        return
    
    if 'endDate' not in horizon:
        result.add_error('planningHorizon.endDate', 'MISSING_FIELD', 
                        "endDate is required")
        return
    
    # Validate date formats
    start_date_str = horizon['startDate']
    end_date_str = horizon['endDate']
    
    try:
        start_date = datetime.fromisoformat(start_date_str).date()
    except (ValueError, TypeError):
        result.add_error('planningHorizon.startDate', 'INVALID_DATE', 
                        f"Invalid date format: '{start_date_str}'. Expected YYYY-MM-DD")
        return
    
    try:
        end_date = datetime.fromisoformat(end_date_str).date()
    except (ValueError, TypeError):
        result.add_error('planningHorizon.endDate', 'INVALID_DATE', 
                        f"Invalid date format: '{end_date_str}'. Expected YYYY-MM-DD")
        return
    
    # Check date range validity (allow same-day planning: startDate == endDate)
    if start_date > end_date:
        result.add_error('planningHorizon', 'INVALID_RANGE', 
                        f"startDate ({start_date_str}) must be on or before endDate ({end_date_str})")
    
    # Warning for very long planning periods
    days = (end_date - start_date).days + 1
    if days > 62:
        result.add_warning('planningHorizon', 'LONG_PERIOD', 
                          f"Planning period of {days} days may result in long solver times")


def _validate_demand_items(data: dict, result: ValidationResult):
    """Validate demand items structure and shift definitions"""
    
    if 'demandItems' not in data or not isinstance(data['demandItems'], list):
        return
    
    for di_idx, demand_item in enumerate(data['demandItems']):
        di_path = f"demandItems[{di_idx}]"
        
        # Check required fields
        if 'demandId' not in demand_item:
            result.add_error(f"{di_path}.demandId", "MISSING_FIELD", 
                           "demandId is required")
        
        if 'shifts' not in demand_item or not isinstance(demand_item['shifts'], list):
            result.add_error(f"{di_path}.shifts", "MISSING_FIELD", 
                           "shifts array is required")
            continue
        
        if 'requirements' not in demand_item or not isinstance(demand_item['requirements'], list):
            result.add_error(f"{di_path}.requirements", "MISSING_FIELD", 
                           "requirements array is required")
            continue
        
        if len(demand_item['requirements']) == 0:
            result.add_error(f"{di_path}.requirements", "EMPTY_ARRAY", 
                           "requirements array cannot be empty")
            continue
        
        # Get rosteringBasis for this demand item (used in requirement validation)
        rostering_basis = demand_item.get('rosteringBasis', 'demandBased')
        
        # Collect all shift codes from requirements
        all_shift_codes = set()
        
        for req_idx, requirement in enumerate(demand_item['requirements']):
            req_path = f"{di_path}.requirements[{req_idx}]"
            
            # Validate requirement structure
            _validate_requirement(requirement, req_path, result, all_shift_codes, rostering_basis)
        
        # Validate shift details against required shift codes
        for shift_idx, shift in enumerate(demand_item['shifts']):
            shift_path = f"{di_path}.shifts[{shift_idx}]"
            _validate_shift_details(shift, shift_path, all_shift_codes, result)


def _validate_requirement(req: dict, path: str, result: ValidationResult, 
                         all_shift_codes: set, rostering_basis: str = 'demandBased'):
    """Validate individual requirement"""
    
    # Required fields (headcount removed from here, validated separately)
    required_fields = {
        'requirementId': str,
        'productTypeId': str,
        'workPattern': list
    }
    
    for field, expected_type in required_fields.items():
        if field not in req:
            result.add_error(f"{path}.{field}", "MISSING_FIELD", 
                           f"Required field '{field}' is missing")
        elif not isinstance(req[field], expected_type):
            result.add_error(f"{path}.{field}", "INVALID_TYPE", 
                           f"Field '{field}' must be of type {expected_type.__name__}")
    
    # Validate rank field (support both rankId singular and rankIds plural)
    has_rank_id = 'rankId' in req
    has_rank_ids = 'rankIds' in req
    
    if not has_rank_id and not has_rank_ids:
        result.add_error(f"{path}.rankId", "MISSING_FIELD", 
                       "Required field 'rankId' or 'rankIds' is missing")
    elif has_rank_id and not isinstance(req['rankId'], str):
        result.add_error(f"{path}.rankId", "INVALID_TYPE", 
                       "Field 'rankId' must be a string")
    elif has_rank_ids and not isinstance(req['rankIds'], list):
        result.add_error(f"{path}.rankIds", "INVALID_TYPE", 
                       "Field 'rankIds' must be a list")
    
    # Validate headcount - support both formats: int (legacy) or dict (new)
    # Special case: Allow headcount=0 for outcomeBased mode (template-based rostering)
    if 'headcount' not in req:
        result.add_error(f"{path}.headcount", "MISSING_FIELD", 
                       "Required field 'headcount' is missing")
    elif isinstance(req['headcount'], int):
        # Legacy format: single integer
        # Allow 0 for outcomeBased mode (template-based rostering ignores headcount)
        if req['headcount'] < 0:
            result.add_error(f"{path}.headcount", "INVALID_VALUE", 
                           "headcount cannot be negative")
        elif req['headcount'] == 0 and rostering_basis != 'outcomeBased':
            result.add_error(f"{path}.headcount", "INVALID_VALUE", 
                           "headcount must be greater than 0 (or use rosteringBasis='outcomeBased' for template mode)")
        elif req['headcount'] > 100:
            result.add_warning(f"{path}.headcount", "HIGH_HEADCOUNT", 
                             f"headcount of {req['headcount']} is very high")
    elif isinstance(req['headcount'], dict):
        # New format: per-shift headcount like {"D": 10, "N": 10}
        if not req['headcount']:
            result.add_error(f"{path}.headcount", "EMPTY_DICT", 
                           "headcount dict cannot be empty")
        else:
            for shift_code, count in req['headcount'].items():
                if not isinstance(count, int) or count <= 0:
                    result.add_error(f"{path}.headcount.{shift_code}", "INVALID_VALUE", 
                                   f"headcount for shift '{shift_code}' must be a positive integer")
                elif count > 100:
                    result.add_warning(f"{path}.headcount.{shift_code}", "HIGH_HEADCOUNT", 
                                     f"headcount of {count} for shift '{shift_code}' is very high")
    else:
        result.add_error(f"{path}.headcount", "INVALID_TYPE", 
                       "headcount must be either an integer or a dictionary (e.g., {'D': 10, 'N': 10})")
    
    # Validate work pattern
    if 'workPattern' in req and isinstance(req['workPattern'], list):
        if len(req['workPattern']) == 0:
            result.add_error(f"{path}.workPattern", "EMPTY_ARRAY", 
                           "workPattern cannot be empty")
        else:
            # Collect unique shift codes (excluding 'O' for off days)
            for code in req['workPattern']:
                if code not in ['O', 'o'] and isinstance(code, str):
                    all_shift_codes.add(code)
            
            # Check pattern length
            if len(req['workPattern']) < 3:
                result.add_warning(f"{path}.workPattern", "SHORT_PATTERN", 
                                 "workPattern is very short (< 3 days)")
            elif len(req['workPattern']) > 28:
                result.add_warning(f"{path}.workPattern", "LONG_PATTERN", 
                                 "workPattern is very long (> 28 days)")
    
    # Validate gender
    if 'gender' in req:
        valid_genders = ['Any', 'M', 'F', 'Male', 'Female', 'MALE', 'FEMALE', 'Mix']
        if req['gender'] not in valid_genders:
            result.add_error(f"{path}.gender", "INVALID_VALUE", 
                           f"Invalid gender value: '{req['gender']}'")


def _validate_shift_details(shift: dict, path: str, required_shift_codes: set, 
                           result: ValidationResult):
    """Validate shift details and ensure all required shift codes are defined"""
    
    if 'shiftDetails' not in shift:
        result.add_error(f"{path}.shiftDetails", "MISSING_FIELD", 
                        "shiftDetails array is required")
        return
    
    shift_details = shift['shiftDetails']
    
    if not isinstance(shift_details, list):
        result.add_error(f"{path}.shiftDetails", "INVALID_TYPE", 
                        "shiftDetails must be an array")
        return
    
    # CRITICAL: Check if shift details is empty when shift codes are required
    if len(shift_details) == 0 and len(required_shift_codes) > 0:
        result.add_error(f"{path}.shiftDetails", "EMPTY_SHIFT_DETAILS", 
                        f"Work patterns reference shift codes {sorted(required_shift_codes)} "
                        f"but shiftDetails array is empty. Shifts must be defined with start/end times.")
        return
    
    # Collect defined shift codes
    defined_shift_codes = set()
    
    for sd_idx, shift_detail in enumerate(shift_details):
        sd_path = f"{path}.shiftDetails[{sd_idx}]"
        
        # Validate shift detail structure
        if 'shiftCode' not in shift_detail:
            result.add_error(f"{sd_path}.shiftCode", "MISSING_FIELD", 
                           "shiftCode is required")
            continue
        
        shift_code = shift_detail['shiftCode']
        defined_shift_codes.add(shift_code)
        
        # Validate time fields
        if 'start' not in shift_detail:
            result.add_error(f"{sd_path}.start", "MISSING_FIELD", 
                           "start time is required")
        elif not _is_valid_time_format(shift_detail['start']):
            result.add_error(f"{sd_path}.start", "INVALID_TIME", 
                           f"Invalid time format: '{shift_detail['start']}'. Expected HH:MM:SS")
        
        if 'end' not in shift_detail:
            result.add_error(f"{sd_path}.end", "MISSING_FIELD", 
                           "end time is required")
        elif not _is_valid_time_format(shift_detail['end']):
            result.add_error(f"{sd_path}.end", "INVALID_TIME", 
                           f"Invalid time format: '{shift_detail['end']}'. Expected HH:MM:SS")
        
        if 'nextDay' not in shift_detail:
            result.add_warning(f"{sd_path}.nextDay", "MISSING_FIELD", 
                             "nextDay field is recommended (defaults to false)")
    
    # Check for missing shift definitions
    missing_codes = required_shift_codes - defined_shift_codes
    if missing_codes:
        result.add_error(f"{path}.shiftDetails", "MISSING_SHIFT_DEFINITIONS", 
                        f"Work patterns reference shift codes {sorted(missing_codes)} "
                        f"but they are not defined in shiftDetails array")


def _is_valid_time_format(time_str: str) -> bool:
    """Check if time string is in HH:MM:SS format"""
    if not isinstance(time_str, str):
        return False
    
    pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$'
    return bool(re.match(pattern, time_str))


def _validate_employees(data: dict, result: ValidationResult):
    """Validate employee structure"""
    
    if 'employees' not in data or not isinstance(data['employees'], list):
        return
    
    employees = data['employees']
    
    for emp_idx, employee in enumerate(employees):
        emp_path = f"employees[{emp_idx}]"
        
        # Required fields
        required_fields = ['employeeId', 'productTypeId', 'rankId', 'scheme']
        
        for field in required_fields:
            if field not in employee:
                result.add_error(f"{emp_path}.{field}", "MISSING_FIELD", 
                               f"Required field '{field}' is missing")
        
        # Validate gender if present
        if 'gender' in employee:
            gender = employee['gender']
            valid_genders = ['Male', 'Female', 'MALE', 'FEMALE', 'M', 'F']
            if gender not in valid_genders:
                result.add_warning(f"{emp_path}.gender", "INVALID_VALUE", 
                                 f"Unusual gender value: '{gender}'")
        
        # Validate rotation offset if present
        if 'rotationOffset' in employee:
            offset = employee['rotationOffset']
            if not isinstance(offset, int):
                result.add_error(f"{emp_path}.rotationOffset", "INVALID_TYPE", 
                               "rotationOffset must be an integer")
            elif offset < 0 or offset > 100:
                result.add_warning(f"{emp_path}.rotationOffset", "UNUSUAL_VALUE", 
                                 f"rotationOffset of {offset} seems unusual")


def _validate_scheme_consistency(data: dict, result: ValidationResult):
    """Validate scheme consistency across requirements and employees (v0.96: Support multiple schemes)"""
    
    scheme_map = data.get('schemeMap', {})
    
    if not scheme_map:
        result.add_warning('schemeMap', 'MISSING_FIELD', 
                         "schemeMap is recommended for scheme normalization")
        return
    
    # Collect all employee schemes
    employee_schemes = set()
    if 'employees' in data:
        for emp in data['employees']:
            if 'scheme' in emp:
                scheme = emp['scheme']
                employee_schemes.add(scheme)
                
                # Check if scheme is short code or full name
                if scheme not in scheme_map and scheme not in scheme_map.values():
                    # Not in keys or values
                    if scheme not in ['Global', 'global']:
                        result.add_error(f"employees[].scheme", "INVALID_SCHEME", 
                                       f"Employee scheme '{scheme}' not found in schemeMap")
    
    # Collect all requirement schemes (v0.96: Support both 'scheme' and 'schemes')
    requirement_schemes = set()
    if 'demandItems' in data:
        for di in data['demandItems']:
            if 'requirements' in di:
                for req in di['requirements']:
                    # v0.96: Check plural 'schemes' first (recommended)
                    if 'schemes' in req:
                        schemes = req['schemes']
                        if isinstance(schemes, list):
                            for scheme in schemes:
                                requirement_schemes.add(scheme)
                                # Check scheme validity
                                if scheme not in ['Any', 'Global', 'global']:
                                    if scheme not in scheme_map and scheme not in scheme_map.values():
                                        result.add_error(f"requirements[].schemes", "INVALID_SCHEME", 
                                                       f"Requirement scheme '{scheme}' not found in schemeMap")
                        else:
                            result.add_error(f"requirements[].schemes", "INVALID_TYPE",
                                           "'schemes' must be an array of scheme values")
                    
                    # Backward compatible: Check singular 'Scheme' (deprecated but supported)
                    if 'Scheme' in req:
                        scheme = req['Scheme']
                        requirement_schemes.add(scheme)
                        
                        # Check scheme validity
                        if scheme not in ['Global', 'global']:
                            if scheme not in scheme_map and scheme not in scheme_map.values():
                                result.add_error(f"requirements[].Scheme", "INVALID_SCHEME", 
                                               f"Requirement scheme '{scheme}' not found in schemeMap")
                    
                    # v0.96: Add deprecation warning for enableAPGD-D10 flag
                    if 'enableAPGD-D10' in req:
                        result.add_warning('requirements[].enableAPGD-D10', 'DEPRECATED_FIELD',
                                         "enableAPGD-D10 flag is no longer needed. "
                                         "APGD-D10 is now automatically enabled for all Scheme A + APO employees. "
                                         "This field will be ignored.")


def _validate_constraints(data: dict, result: ValidationResult):
    """Validate constraint definitions"""
    
    if 'constraintList' not in data:
        result.add_warning('constraintList', 'MISSING_FIELD', 
                         "No constraints defined - solution may be unrealistic")
        return
    
    constraint_list = data['constraintList']
    
    if not isinstance(constraint_list, list):
        result.add_error('constraintList', 'INVALID_TYPE', 
                        "constraintList must be an array")
        return
    
    for const_idx, constraint in enumerate(constraint_list):
        const_path = f"constraintList[{const_idx}]"
        
        if 'id' not in constraint:
            result.add_error(f"{const_path}.id", "MISSING_FIELD", 
                           "Constraint id is required")
        
        if 'enforcement' not in constraint:
            result.add_error(f"{const_path}.enforcement", "MISSING_FIELD", 
                           "Constraint enforcement is required")
        elif constraint['enforcement'] not in ['hard', 'medium', 'soft']:
            result.add_error(f"{const_path}.enforcement", "INVALID_VALUE", 
                           f"Invalid enforcement: '{constraint['enforcement']}'")
        
        # Check for unreasonable constraint values
        if 'params' in constraint and isinstance(constraint['params'], dict):
            params = constraint['params']
            
            # Check max days
            if 'maxDays' in params:
                max_days = params['maxDays']
                if max_days <= 0:
                    result.add_error(f"{const_path}.params.maxDays", "INVALID_VALUE", 
                                   "maxDays must be greater than 0")
                elif max_days > 31:
                    result.add_warning(f"{const_path}.params.maxDays", "HIGH_VALUE", 
                                     f"maxDays of {max_days} is very high")
            
            # Check weekly hours cap
            if 'maxWeeklyHours' in params:
                max_hours = params['maxWeeklyHours']
                if max_hours <= 0:
                    result.add_error(f"{const_path}.params.maxWeeklyHours", "INVALID_VALUE", 
                                   "maxWeeklyHours must be greater than 0")


def _validate_feasibility(data: dict, result: ValidationResult):
    """Pre-check feasibility: Are there matching employees for each requirement?"""
    
    if 'demandItems' not in data or 'employees' not in data:
        return
    
    employees = data['employees']
    scheme_map = data.get('schemeMap', {})
    
    # Normalize employee schemes
    normalized_employees = []
    for emp in employees:
        emp_copy = emp.copy()
        emp_scheme = emp.get('scheme', '')
        
        # Normalize scheme
        if emp_scheme in scheme_map:
            # Already short code
            emp_copy['normalized_scheme'] = emp_scheme
        else:
            # Try reverse lookup
            for short_code, full_name in scheme_map.items():
                if full_name == emp_scheme:
                    emp_copy['normalized_scheme'] = short_code
                    break
            else:
                # Use as-is
                emp_copy['normalized_scheme'] = emp_scheme
        
        normalized_employees.append(emp_copy)
    
    # Check each requirement
    for di_idx, demand_item in enumerate(data['demandItems']):
        if 'requirements' not in demand_item:
            continue
        
        for req_idx, requirement in enumerate(demand_item['requirements']):
            req_path = f"demandItems[{di_idx}].requirements[{req_idx}]"
            
            req_product = requirement.get('productTypeId', '')
            
            # Support both rankId (singular) and rankIds (plural)
            req_ranks = requirement.get('rankIds', [])
            if not req_ranks:
                # Fallback to singular rankId
                req_rank = requirement.get('rankId', '')
                req_ranks = [req_rank] if req_rank else []
            
            req_scheme_raw = requirement.get('Scheme', 'Global')
            
            # Normalize headcount to handle both formats
            req_headcount_raw = requirement.get('headcount', 1)
            if isinstance(req_headcount_raw, dict):
                # New format: sum all shift headcounts
                req_headcount = sum(req_headcount_raw.values())
            else:
                # Legacy format: use as-is
                req_headcount = req_headcount_raw
            
            # Normalize requirement scheme
            if req_scheme_raw == 'Global' or req_scheme_raw == 'global':
                req_scheme = 'Global'
            elif req_scheme_raw in scheme_map:
                req_scheme = req_scheme_raw
            else:
                # Try reverse lookup
                for short_code, full_name in scheme_map.items():
                    if full_name == req_scheme_raw:
                        req_scheme = short_code
                        break
                else:
                    req_scheme = req_scheme_raw
            
            # Count matching employees
            matching_count = 0
            for emp in normalized_employees:
                emp_product = emp.get('productTypeId', '')
                emp_rank = emp.get('rankId', '')
                emp_scheme = emp.get('normalized_scheme', '')
                
                # Check match (with OR logic for ranks)
                product_match = (emp_product == req_product)
                rank_match = (emp_rank in req_ranks) if req_ranks else True
                scheme_match = (req_scheme == 'Global' or emp_scheme == req_scheme)
                
                if product_match and rank_match and scheme_match:
                    matching_count += 1
            
            # Check if sufficient employees
            if matching_count == 0:
                # Format ranks for error message
                ranks_str = '/'.join(req_ranks) if req_ranks else ''
                result.add_error(f"{req_path}", "NO_MATCHING_EMPLOYEES", 
                               f"No employees match requirement {requirement.get('requirementId', '?')}: "
                               f"{req_product}/{ranks_str}/{req_scheme_raw}")
            elif matching_count < req_headcount:
                result.add_warning(f"{req_path}", "INSUFFICIENT_EMPLOYEES", 
                                 f"Only {matching_count} employees match requirement "
                                 f"{requirement.get('requirementId', '?')} but headcount is {req_headcount}")


def _validate_rostering_basis(data: dict, result: ValidationResult):
    """
    Validate rosteringBasis field and related outcomeBased-specific fields.
    
    Checks both new location (demandItems[0]) and old location (root) for backward compatibility.
    """
    # Extract rosteringBasis from either location
    rostering_basis = None
    
    # Try new location first (demandItems[0])
    demand_items = data.get('demandItems', [])
    if demand_items and len(demand_items) > 0:
        rostering_basis = demand_items[0].get('rosteringBasis')
    
    # Fall back to old location (root level)
    if not rostering_basis:
        rostering_basis = data.get('rosteringBasis')
    
    # Validate value if present
    if rostering_basis:
        valid_values = ['demandBased', 'outcomeBased']
        if rostering_basis not in valid_values:
            result.add_error('rosteringBasis', 'INVALID_VALUE',
                           f"rosteringBasis must be one of: {', '.join(valid_values)}")
            return
        
        # Validate outcomeBased-specific fields
        if rostering_basis == 'outcomeBased':
            # Check minStaffThresholdPercentage
            if demand_items and len(demand_items) > 0:
                min_threshold = demand_items[0].get('minStaffThresholdPercentage')
                if min_threshold is None:
                    result.add_warning('demandItems[0].minStaffThresholdPercentage', 
                                     'MISSING_FIELD',
                                     'minStaffThresholdPercentage not specified, defaulting to 100%')
                elif not isinstance(min_threshold, (int, float)):
                    result.add_error('demandItems[0].minStaffThresholdPercentage',
                                   'INVALID_TYPE',
                                   'minStaffThresholdPercentage must be a number')
                elif min_threshold < 1 or min_threshold > 100:
                    result.add_error('demandItems[0].minStaffThresholdPercentage',
                                   'OUT_OF_RANGE',
                                   f'minStaffThresholdPercentage must be between 1 and 100 (got {min_threshold})')
            
            # Check ouOffsets array
            ou_offsets = data.get('ouOffsets', [])
            if not ou_offsets:
                result.add_warning('ouOffsets', 'MISSING_FIELD',
                                 'outcomeBased mode requires ouOffsets array at root level')
            elif not isinstance(ou_offsets, list):
                result.add_error('ouOffsets', 'INVALID_TYPE',
                               'ouOffsets must be an array')
            else:
                # Validate each OU offset entry
                for idx, ou in enumerate(ou_offsets):
                    if not isinstance(ou, dict):
                        result.add_error(f'ouOffsets[{idx}]', 'INVALID_TYPE',
                                       'Each OU offset entry must be an object')
                        continue
                    
                    if 'ouId' not in ou:
                        result.add_error(f'ouOffsets[{idx}].ouId', 'MISSING_FIELD',
                                       'ouId is required')
                    
                    if 'rotationOffset' not in ou:
                        result.add_error(f'ouOffsets[{idx}].rotationOffset', 'MISSING_FIELD',
                                       'rotationOffset is required')
                    elif not isinstance(ou['rotationOffset'], int):
                        result.add_error(f'ouOffsets[{idx}].rotationOffset', 'INVALID_TYPE',
                                       'rotationOffset must be an integer')
                    elif ou['rotationOffset'] < 0:
                        result.add_error(f'ouOffsets[{idx}].rotationOffset', 'OUT_OF_RANGE',
                                       f"rotationOffset cannot be negative (got {ou['rotationOffset']})")
            
            # Check fixedRotationOffset mode
            fixed_rotation_mode = data.get('fixedRotationOffset')
            if fixed_rotation_mode and fixed_rotation_mode != 'ouOffsets':
                result.add_warning('fixedRotationOffset', 'INCONSISTENT_CONFIG',
                                 f"outcomeBased mode should use fixedRotationOffset='ouOffsets' (got '{fixed_rotation_mode}')")


def _validate_ou_employee_mapping(data: dict, result: ValidationResult):
    """
    Validate that employees have ouId and that ouIds exist in ouOffsets.
    
    Only applies to outcomeBased mode.
    """
    # Check if outcomeBased mode
    rostering_basis = None
    demand_items = data.get('demandItems', [])
    if demand_items and len(demand_items) > 0:
        rostering_basis = demand_items[0].get('rosteringBasis')
    if not rostering_basis:
        rostering_basis = data.get('rosteringBasis', 'demandBased')
    
    if rostering_basis != 'outcomeBased':
        return  # Only validate for outcomeBased mode
    
    # Build set of valid OU IDs
    ou_offsets = data.get('ouOffsets', [])
    valid_ou_ids = {ou.get('ouId') for ou in ou_offsets if isinstance(ou, dict) and 'ouId' in ou}
    
    # Check each employee
    employees = data.get('employees', [])
    employees_without_ou = 0
    employees_with_invalid_ou = 0
    
    for emp_idx, emp in enumerate(employees):
        ou_id = emp.get('ouId')
        
        if not ou_id:
            employees_without_ou += 1
        elif valid_ou_ids and ou_id not in valid_ou_ids:
            employees_with_invalid_ou += 1
            if employees_with_invalid_ou <= 5:  # Limit error messages
                result.add_error(f'employees[{emp_idx}].ouId', 'INVALID_VALUE',
                               f"Employee {emp.get('employeeId', '?')} has ouId '{ou_id}' which is not defined in ouOffsets")
    
    if employees_without_ou > 0:
        result.add_warning('employees', 'MISSING_OU_ID',
                         f"{employees_without_ou} employees missing ouId field (will default to offset=0)")
    
    if employees_with_invalid_ou > 5:
        result.add_error('employees', 'INVALID_OU_IDS',
                       f"{employees_with_invalid_ou} employees have ouIds not defined in ouOffsets")


def validate_input_quick(data: dict) -> Tuple[bool, str]:
    """
    Quick validation - returns (is_valid, error_message).
    Use for simple pass/fail checks.
    """
    result = validate_input(data)
    
    if result.is_valid:
        return True, ""
    
    # Return first error message
    if result.errors:
        first_error = result.errors[0]
        return False, f"{first_error.field}: {first_error.message}"
    
    return True, ""
