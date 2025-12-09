#!/usr/bin/env python3
"""Test solver locally with the product/rank filtering fix."""

import sys
import json
from pathlib import Path

# Add context to path
sys.path.insert(0, str(Path(__file__).parent))

from context.engine.solver_engine import solve

def main():
    # Load input
    input_file = '/Users/glori/Downloads/RST-20251208-3B20055D_Solver_Input.json'
    print(f"Loading input from: {input_file}")
    
    with open(input_file, 'r') as f:
        inputs = json.load(f)
    
    print(f"\n{'='*70}")
    print("RUNNING SOLVER WITH PRODUCT/RANK FILTERING FIX")
    print('='*70)
    
    # Run solver
    result = solve(inputs)
    
    print(f"\n{'='*70}")
    print("SOLUTION SUMMARY")
    print('='*70)
    
    solver_run = result.get('solverRun', {})
    print(f"Status: {solver_run.get('status')}")
    print(f"Duration: {solver_run.get('durationSeconds')} seconds")
    
    score = result.get('score', {})
    print(f"\nScore:")
    print(f"  Overall: {score.get('overall')}")
    print(f"  Hard violations: {score.get('hard')}")
    print(f"  Soft violations: {score.get('soft')}")
    
    # Check requirements
    print(f"\n{'='*70}")
    print("REQUIREMENT ANALYSIS")
    print('='*70)
    
    assignments = result.get('assignments', [])
    req_55_1 = [a for a in assignments if a['requirementId'] == '55_1' and a.get('employeeId')]
    req_57_1 = [a for a in assignments if a['requirementId'] == '57_1' and a.get('employeeId')]
    
    print(f"\nRequirement 55_1 (APO/CON, Global):")
    print(f"  Assigned slots: {len(req_55_1)}/62")
    if req_55_1:
        emp_ids = set(a['employeeId'] for a in req_55_1)
        print(f"  Employees used: {len(emp_ids)}")
        for emp_id in sorted(emp_ids)[:5]:
            count = sum(1 for a in req_55_1 if a['employeeId'] == emp_id)
            print(f"    - {emp_id}: {count} shifts")
    
    print(f"\nRequirement 57_1 (APO/COR, Scheme P):")
    print(f"  Assigned slots: {len(req_57_1)}/62")
    if req_57_1:
        emp_ids = set(a['employeeId'] for a in req_57_1)
        print(f"  Employees used: {len(emp_ids)}")
        for emp_id in sorted(emp_ids):
            count = sum(1 for a in req_57_1 if a['employeeId'] == emp_id)
            print(f"    - {emp_id}: {count} shifts")
    else:
        print(f"  ⚠️  NO ASSIGNMENTS! (This should be fixed now)")
    
    # Check Scheme P employee usage
    print(f"\n{'='*70}")
    print("SCHEME P EMPLOYEE USAGE")
    print('='*70)
    
    scheme_p_ids = ['00083949', '00087101', '00090682', '00126186']
    all_assignments = [a for a in assignments if a.get('employeeId')]
    
    for emp_id in scheme_p_ids:
        emp_assignments = [a for a in all_assignments if a['employeeId'] == emp_id]
        if emp_assignments:
            print(f"  ✓ {emp_id}: {len(emp_assignments)} shifts assigned")
        else:
            print(f"  ✗ {emp_id}: NOT USED")
    
    # Save result
    output_file = '/Users/glori/1 Anthony_Workspace/My Developments/NGRS/ngrs-solver-v0.7/ngrssolver/output/local_test_with_fix.json'
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\n✓ Result saved to: {output_file}")
    
    # Return exit code based on success
    if solver_run.get('status') == 'OPTIMAL' and len(req_57_1) > 0:
        print(f"\n{'='*70}")
        print("✓ SUCCESS! Fix is working correctly!")
        print('='*70)
        return 0
    else:
        print(f"\n{'='*70}")
        print("✗ FAILED! Issue still present")
        print('='*70)
        return 1

if __name__ == '__main__':
    sys.exit(main())
