#!/usr/bin/env python3
"""Verify that unavailability violations are fixed in the output."""

import json
import sys

def verify_output(input_file, output_file):
    """Check output for unavailability violations."""
    
    # Load input to get unavailability data
    with open(input_file, 'r') as f:
        input_data = json.load(f)
    
    # Build unavailability map
    unavail_map = {}
    for emp in input_data['employees']:
        emp_id = emp['employeeId']
        unavail_list = emp.get('unavailability', [])
        unavailable_dates = set(unavail_list)
        if unavailable_dates:
            unavail_map[emp_id] = unavailable_dates
    
    print("Unavailability map: {} employees with unavailable dates".format(len(unavail_map)))
    for emp_id, dates in unavail_map.items():
        print("  {}: {} unavailable dates".format(emp_id, len(dates)))
    
    # Load output
    with open(output_file, 'r') as f:
        output = json.load(f)
    
    assignments = output['assignments']
    print("\nTotal assignments: {}".format(len(assignments)))
    
    # Check for violations (only count ASSIGNED or PUBLIC_HOLIDAY, not UNASSIGNED)
    violations = []
    for asg in assignments:
        emp_id = asg.get('employeeId')
        date = asg.get('date')
        status = asg.get('status')
        
        # Skip UNASSIGNED - those are legitimate gaps
        if status == 'UNASSIGNED' or emp_id is None:
            continue
        
        if emp_id and date and emp_id in unavail_map and date in unavail_map[emp_id]:
            violations.append((emp_id, date, status))
    
    if violations:
        print("\n*** FAILURE! Found {} unavailability violations:".format(len(violations)))
        for emp_id, date, status in violations[:10]:
            print("  Employee {} on {} (status: {})".format(emp_id, date, status))
        if len(violations) > 10:
            print("  ... and {} more".format(len(violations) - 10))
        return False
    else:
        print("\n*** SUCCESS! NO UNAVAILABILITY VIOLATIONS!")
    
    # Check specific employees
    for emp_id in ['30025411', '30025637']:
        emp_assignments = [a for a in assignments if a.get('employeeId') == emp_id]
        print("\nEmployee {}: {} assignments".format(emp_id, len(emp_assignments)))
        if emp_assignments:
            print("  Sample: {}".format(emp_assignments[:2]))
    
    return True

if __name__ == '__main__':
    input_file = 'input/RST-20260228-003BBFE2_Solver_Input.json'
    output_file = '/tmp/test_COMPLETE_FIX.json'
    
    if len(sys.argv) > 2:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
    
    success = verify_output(input_file, output_file)
    sys.exit(0 if success else 1)
