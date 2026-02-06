import json, pathlib
from typing import Union, Dict, Any, List
from .rotation_preprocessor import preprocess_rotation_offsets


def normalize_requirements_rankIds(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize requirements to use rankIds (array) format internally.
    
    Supports backward compatibility:
    - If 'rankId' (singular) exists → convert to 'rankIds': [rankId]
    - If 'rankIds' (plural) exists → use as-is
    - Store original format for output preservation
    
    Args:
        data: Input data dict with demandItems/requirements
        
    Returns:
        Data dict with normalized requirements (all have rankIds array)
    """
    for demand in data.get('demandItems', []):
        for req in demand.get('requirements', []):
            # Check which format is present
            if 'rankIds' in req:
                # Already using plural format - ensure it's a list
                if not isinstance(req['rankIds'], list):
                    req['rankIds'] = [req['rankIds']]
                req['_original_format'] = 'rankIds'
            elif 'rankId' in req:
                # Convert singular to plural for internal use
                req['rankIds'] = [req['rankId']]
                req['_original_format'] = 'rankId'
            else:
                # No rank specified - treat as empty list
                req['rankIds'] = []
                req['_original_format'] = None
    
    return data


def extract_rostering_basis(data: Dict[str, Any]) -> str:
    """
    Extract rosteringBasis from data with backward compatibility.
    
    Priority:
    1. demandItems[0].rosteringBasis (new location)
    2. root.rosteringBasis (old location)
    3. Default: 'demandBased'
    
    Args:
        data: Input data dict
        
    Returns:
        str: 'demandBased' or 'outcomeBased'
    """
    # Try demandItems first (new location)
    demand_items = data.get('demandItems', [])
    if demand_items and len(demand_items) > 0:
        rostering_basis = demand_items[0].get('rosteringBasis')
        if rostering_basis:
            return rostering_basis
    
    # Fall back to root level (old location for backward compatibility)
    rostering_basis = data.get('rosteringBasis')
    if rostering_basis:
        return rostering_basis
    
    # Default
    return 'demandBased'


def build_ou_offset_mapping(data: Dict[str, Any]) -> Dict[str, int]:
    """
    Build mapping from ouId to rotationOffset.
    
    Reads from root-level 'ouOffsets' array:
    [
        {"ouId": "ATSU T1 LSU A1", "rotationOffset": 0},
        {"ouId": "ATSU T2 LSU B1", "rotationOffset": 1}
    ]
    
    Args:
        data: Input data dict
        
    Returns:
        dict: {ouId: rotationOffset} mapping
    """
    ou_offsets = data.get('ouOffsets', [])
    return {ou['ouId']: ou['rotationOffset'] for ou in ou_offsets if 'ouId' in ou}


def copy_work_pattern_to_employees(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    For outcomeBased mode, copy workPattern from requirements to all employees.
    
    Since UI enforces same pattern for all requirements in outcomeBased mode,
    we copy the first requirement's workPattern to all employees.
    
    Args:
        data: Input data dict
        
    Returns:
        dict: Updated data with employees having workPattern
    """
    rostering_basis = extract_rostering_basis(data)
    
    if rostering_basis != 'outcomeBased':
        return data  # Only apply for outcomeBased mode
    
    # Get work pattern from first requirement
    demand_items = data.get('demandItems', [])
    if not demand_items or len(demand_items) == 0:
        return data
    
    requirements = demand_items[0].get('requirements', [])
    if not requirements or len(requirements) == 0:
        return data
    
    work_pattern = requirements[0].get('workPattern', [])
    if not work_pattern:
        return data
    
    # Copy pattern to all employees
    for employee in data.get('employees', []):
        if 'workPattern' not in employee or not employee['workPattern']:
            employee['workPattern'] = work_pattern.copy()
    
    return data


def filter_employees_by_rank(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter employees to keep only those whose rank matches at least one requirement.
    
    For outcomeBased mode, this reduces the employee pool before CP-SAT solving
    to improve performance.
    
    Args:
        data: Input data dict
        
    Returns:
        dict: Updated data with filtered employees
    """
    rostering_basis = extract_rostering_basis(data)
    
    if rostering_basis != 'outcomeBased':
        return data  # Only filter for outcomeBased mode
    
    # Collect all required ranks from all requirements
    required_ranks = set()
    demand_items = data.get('demandItems', [])
    for demand in demand_items:
        for req in demand.get('requirements', []):
            rank_ids = req.get('rankIds', [])
            required_ranks.update(rank_ids)
    
    if not required_ranks:
        return data  # No rank filtering if no ranks specified
    
    # Filter employees
    original_count = len(data.get('employees', []))
    filtered_employees = [
        emp for emp in data.get('employees', [])
        if emp.get('rankId') in required_ranks
    ]
    
    data['employees'] = filtered_employees
    
    print(f"[data_loader] Rank filtering: {original_count} → {len(filtered_employees)} employees")
    
    return data


def load_input(path: Union[str, Dict[str, Any]]):
    """
    Load input data from file path or dict.
    
    Args:
        path: File path (str) or dict with input data
        
    Returns:
        dict: Parsed input data with preprocessed rotation offsets and normalized rankIds
    """
    # If already a dict, return it
    if isinstance(path, dict):
        data = path
    else:
        # Otherwise, load from file path
        p = pathlib.Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
    
    # TODO: validate against schemas/input.schema.json
    
    # Extract rosteringBasis early to determine preprocessing path
    rostering_basis_temp = None
    demand_items_temp = data.get('demandItems', [])
    if demand_items_temp and len(demand_items_temp) > 0:
        rostering_basis_temp = demand_items_temp[0].get('rosteringBasis')
    if not rostering_basis_temp:
        rostering_basis_temp = data.get('rosteringBasis', 'demandBased')
    
    # CRITICAL: Preprocess rotation offsets ONLY for demandBased mode
    # outcomeBased mode uses OU offsets directly, no pattern preprocessing needed
    if rostering_basis_temp == 'demandBased':
        data = preprocess_rotation_offsets(data)
    
    # Normalize requirements to use rankIds (plural) internally
    data = normalize_requirements_rankIds(data)
    
    # Extract and store rosteringBasis in root for easy access
    data['_rosteringBasis'] = extract_rostering_basis(data)
    
    # Build OU offset mapping and store in root
    data['_ouOffsetMap'] = build_ou_offset_mapping(data)
    
    # For outcomeBased mode: copy work pattern to employees
    data = copy_work_pattern_to_employees(data)
    
    # For outcomeBased mode: filter employees by rank
    data = filter_employees_by_rank(data)
    
    # ====== API VERSION FLAGS ======
    # Pass through API version flags from input to context
    # These are set by the API router (or auto-detected)
    if '_apiVersion' in data:
        pass  # Already set by API
    else:
        # Auto-detect if not explicitly set
        has_daily_headcount = False
        for dmd in data.get('demandItems', []):
            for req in dmd.get('requirements', []):
                if req.get('dailyHeadcount'):
                    has_daily_headcount = True
                    break
        
        if has_daily_headcount:
            data['_apiVersion'] = 'v2'
            data['_hasDailyHeadcount'] = True
        else:
            data['_apiVersion'] = 'v1'
            data['_hasDailyHeadcount'] = False
    
    return data
