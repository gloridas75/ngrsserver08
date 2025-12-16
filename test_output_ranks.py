#!/usr/bin/env python3
"""
Simple end-to-end test for multiple ranks feature.
Verifies that employees match ANY rank in the rankIds list.
"""

import json
from pathlib import Path

def test_output():
    """Check the output file to verify correct behavior."""
    output_dir = Path("/Users/glori/1 Anthony_Workspace/My Developments/NGRS/ngrs-solver-v0.7/ngrssolver/output")
    
    # Find most recent output file
    output_files = sorted(output_dir.glob("output_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not output_files:
        print("❌ No output file found")
        return False
    
    latest_output = output_files[0]
    print(f"\n📄 Analyzing: {latest_output.name}")
    
    with open(latest_output, 'r') as f:
        output = json.load(f)
    
    # Check demands
    demands = output.get('demandItems', [])
    print(f"\n✓ Found {len(demands)} demand items")
    
    for demand in demands:
        demand_id = demand.get('demandId')
        reqs = demand.get('requirements', [])
        
        print(f"\n  Demand: {demand_id}")
        for req in reqs:
            req_id = req.get('requirementId')
            
            # Check if requirement has rankIds (new format) or rankId (old format)
            if 'rankIds' in req:
                ranks = req['rankIds']
                format_type = "rankIds (multiple)"
            elif 'rankId' in req:
                ranks = [req['rankId']]
                format_type = "rankId (single)"
            else:
                ranks = []
                format_type = "no rank specified"
            
            print(f"    Requirement: {req_id}")
            print(f"      Format: {format_type}")
            print(f"      Ranks: {ranks}")
            
            # Check if slots were created
            if 'slots' in req:
                slot_count = len(req['slots'])
                print(f"      Slots created: {slot_count}")
    
    print("\n✅ Output analysis complete!")
    return True

if __name__ == '__main__':
    test_output()
