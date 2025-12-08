import json, pathlib
from typing import Union, Dict, Any
from .rotation_preprocessor import preprocess_rotation_offsets

def load_input(path: Union[str, Dict[str, Any]]):
    """
    Load input data from file path or dict.
    
    Args:
        path: File path (str) or dict with input data
        
    Returns:
        dict: Parsed input data with preprocessed rotation offsets
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
    
    return data
