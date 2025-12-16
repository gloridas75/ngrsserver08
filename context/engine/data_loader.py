import json, pathlib
from typing import Union, Dict, Any
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
    
    # CRITICAL: Preprocess rotation offsets before solving
    # Handles synchronized rest days (all offset=0) scenario
    data = preprocess_rotation_offsets(data)
    
    # Normalize requirements to use rankIds (plural) internally
    data = normalize_requirements_rankIds(data)
    
    return data
