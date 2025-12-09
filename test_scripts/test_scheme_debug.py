#!/usr/bin/env python3
"""Debug script to trace scheme normalization in slot building."""

import json
import sys
from typing import Dict, Optional

def normalize_scheme(scheme_value: str, scheme_map: Optional[Dict[str, str]] = None) -> str:
    """Normalize scheme value to short code format (A, B, P, or Global)."""
    print(f"  [normalize_scheme] Input: '{scheme_value}', scheme_map: {scheme_map}")
    
    if not scheme_value or scheme_value == "Global":
        print(f"  [normalize_scheme] Returning 'Global'")
        return "Global"
    
    # If scheme_map is provided, try reverse lookup
    if scheme_map:
        # Check if value is already a short code (key in scheme_map)
        if scheme_value in scheme_map:
            print(f"  [normalize_scheme] Found '{scheme_value}' in keys, returning as-is")
            return scheme_value
        
        # Try to find matching short code by value ("Scheme P" → "P")
        for short_code, full_name in scheme_map.items():
            if full_name == scheme_value:
                print(f"  [normalize_scheme] Found match: '{full_name}' == '{scheme_value}' → '{short_code}'")
                return short_code
    
    # Fallback: If it starts with "Scheme ", extract the letter
    if scheme_value.startswith("Scheme "):
        result = scheme_value.replace("Scheme ", "").strip()
        print(f"  [normalize_scheme] Fallback: stripped 'Scheme ' → '{result}'")
        return result
    
    # Already in short format
    print(f"  [normalize_scheme] Already short format: '{scheme_value}'")
    return scheme_value


def main():
    # Load input
    input_file = '/Users/glori/Downloads/RST-20251208-3B20055D_Solver_Input.json'
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    scheme_map = data.get('schemeMap', {})
    print(f"schemeMap: {scheme_map}\n")
    
    # Get employees with Scheme P
    employees = data.get('employees', [])
    scheme_p_employees = [e for e in employees if e.get('scheme') == 'P']
    print(f"Found {len(scheme_p_employees)} Scheme P employees:")
    for emp in scheme_p_employees:
        emp_id = emp.get('id') or emp.get('employeeId')
        print(f"  - {emp_id}: {emp.get('productTypeId')}/{emp.get('rankId')}, scheme={emp.get('scheme')}")
    
    print("\n" + "="*60)
    print("Processing requirements:")
    print("="*60)
    
    # Process requirements
    for demand in data.get('demandItems', []):
        demand_id = demand.get('demandId')
        for req in demand.get('requirements', []):
            req_id = req.get('requirementId')
            scheme_req_raw = req.get('Scheme', 'Global')
            
            print(f"\nRequirement {req_id}:")
            print(f"  Raw Scheme: '{scheme_req_raw}'")
            scheme_req = normalize_scheme(scheme_req_raw, scheme_map)
            print(f"  Normalized Scheme: '{scheme_req}'")
            
            # Check employee matching
            product_type = req.get('productTypeId')
            rank_id = req.get('rankId')
            matching = [e for e in employees 
                       if e.get('productTypeId') == product_type 
                       and e.get('rankId') == rank_id
                       and (scheme_req == 'Global' or e.get('scheme') == scheme_req)]
            
            print(f"  Product: {product_type}, Rank: {rank_id}")
            print(f"  Matching employees: {len(matching)}")
            if matching:
                for emp in matching[:5]:  # Show first 5
                    emp_id = emp.get('id') or emp.get('employeeId')
                    print(f"    - {emp_id}: scheme={emp.get('scheme')}")

if __name__ == '__main__':
    main()
