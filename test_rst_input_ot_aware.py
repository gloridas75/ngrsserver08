"""
Test OT-aware ICPMP with actual RST-20251213 input.

Compares results with/without enableOtAwareIcpmp flag.
"""

import json
import copy
import subprocess
import os

def run_solver_with_input(input_data, output_path):
    """Run solver with given input and return result."""
    
    # Write input to temp file
    temp_input = "temp_solver_input.json"
    with open(temp_input, 'w') as f:
        json.dump(input_data, f, indent=2)
    
    # Run solver
    cmd = f"python src/run_solver.py --in {temp_input} --out {output_path} --time 60"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    # Clean up temp file
    os.remove(temp_input)
    
    # Load result
    if os.path.exists(output_path):
        with open(output_path, 'r') as f:
            return json.load(f)
    else:
        return {'status': 'FAILED', 'error': result.stderr}


def test_rst_input_with_ot_aware():
    """Test RST-20251213 input with and without OT-aware flag."""
    
    # Load original input
    input_path = "/Users/glori/Downloads/RST-20251213-A2B37D35_Solver_Input.json"
    with open(input_path, 'r') as f:
        input_data = json.load(f)
    
    print("=" * 80)
    print("RST-20251213 OT-AWARE ICPMP TEST")
    print("=" * 80)
    print(f"Input: {input_data['planningReference']}")
    print(f"Horizon: {input_data['planningHorizon']['startDate']} to {input_data['planningHorizon']['endDate']}")
    print(f"Employees: {len(input_data['employees'])}")
    
    # Find Scheme P requirement
    requirement = input_data['demandItems'][0]['requirements'][0]
    print(f"Requirement: {requirement['requirementId']}")
    print(f"  Pattern: {requirement['workPattern']}")
    print(f"  Headcount: {requirement['headcount']}")
    print(f"  Scheme: {requirement['scheme']}")
    print()
    
    # Test 1: WITHOUT OT-aware (current behavior)
    print("-" * 80)
    print("TEST 1: OT-Aware DISABLED (current behavior)")
    print("-" * 80)
    
    input_disabled = copy.deepcopy(input_data)
    # Ensure flag is not set (default behavior)
    if 'enableOtAwareIcpmp' in input_disabled['demandItems'][0]['requirements'][0]:
        del input_disabled['demandItems'][0]['requirements'][0]['enableOtAwareIcpmp']
    
    print("Running solver...")
    result_disabled = run_solver_with_input(input_disabled, "output/rst_disabled.json")
    
    if 'error' in result_disabled:
        print(f"✗ Solver failed: {result_disabled.get('error', 'Unknown error')}")
        return None
    
    # Extract status from solverRun
    status_disabled = result_disabled.get('solverRun', {}).get('status', 'UNKNOWN')
    
    # Extract status from solverRun
    status_disabled = result_disabled.get('solverRun', {}).get('status', 'UNKNOWN')
    
    if status_disabled == 'OPTIMAL' or status_disabled == 'FEASIBLE':
        assigned_disabled = len(result_disabled.get('assignments', []))
        unassigned = result_disabled.get('scoreBreakdown', {}).get('unassignedSlots', {})
        total_slots = unassigned.get('total', 0)
        print(f"✓ Status: {status_disabled}")
        print(f"  Assignments: {assigned_disabled}/{total_slots} ({assigned_disabled/total_slots*100:.1f}% if total_slots else 0)")
        print(f"  Solve time: {result_disabled.get('solverRun', {}).get('durationSeconds', 0):.2f}s")
        
        # Count unique employees assigned
        unique_employees_disabled = len(set(a['employeeId'] for a in result_disabled.get('assignments', [])))
        print(f"  Employees used: {unique_employees_disabled}/{len(input_data['employees'])}")
    else:
        print(f"✗ Status: {status_disabled}")
        assigned_disabled = 0
        unique_employees_disabled = 0
        total_slots = 0
    
    print()
    
    # Test 2: WITH OT-aware (new feature)
    print("-" * 80)
    print("TEST 2: OT-Aware ENABLED (new feature)")
    print("-" * 80)
    
    input_enabled = copy.deepcopy(input_data)
    # Add flag to requirement
    input_enabled['demandItems'][0]['requirements'][0]['enableOtAwareIcpmp'] = True
    
    print("Running solver with OT-aware ICPMP...")
    result_enabled = run_solver_with_input(input_enabled, "output/rst_enabled.json")
    
    if 'error' in result_enabled:
        print(f"✗ Solver failed: {result_enabled.get('error', 'Unknown error')}")
        return None
    
    status_enabled = result_enabled.get('solverRun', {}).get('status', 'UNKNOWN')
    
    if status_enabled == 'OPTIMAL' or status_enabled == 'FEASIBLE':
        assigned_enabled = len(result_enabled.get('assignments', []))
        unassigned = result_enabled.get('scoreBreakdown', {}).get('unassignedSlots', {})
        total_slots = unassigned.get('total', 0)
        print(f"✓ Status: {status_enabled}")
        print(f"  Assignments: {assigned_enabled}/{total_slots} ({assigned_enabled/total_slots*100:.1f}% if total_slots else 0)")
        print(f"  Solve time: {result_enabled.get('solverRun', {}).get('durationSeconds', 0):.2f}s")
        
        # Count unique employees assigned
        unique_employees_enabled = len(set(a['employeeId'] for a in result_enabled.get('assignments', [])))
        print(f"  Employees used: {unique_employees_enabled}/{len(input_data['employees'])}")
    else:
        print(f"✗ Status: {status_enabled}")
        assigned_enabled = 0
        unique_employees_enabled = 0
    
    print()
    
    # Compare results
    print("=" * 80)
    print("COMPARISON")
    print("=" * 80)
    
    if unique_employees_disabled > 0 and unique_employees_enabled > 0:
        employee_diff = unique_employees_disabled - unique_employees_enabled
        assignment_diff = assigned_enabled - assigned_disabled
        
        print(f"Employee usage reduction: {employee_diff} employees saved")
        print(f"  Disabled: {unique_employees_disabled} employees")
        print(f"  Enabled:  {unique_employees_enabled} employees")
        print(f"  Savings:  {employee_diff / unique_employees_disabled * 100:.1f}%")
        print()
        
        print(f"Assignment coverage change: {'+' if assignment_diff >= 0 else ''}{assignment_diff} slots")
        print(f"  Disabled: {assigned_disabled} assignments")
        print(f"  Enabled:  {assigned_enabled} assignments")
        print()
        
        if employee_diff > 0:
            print(f"✅ SUCCESS: OT-aware ICPMP reduced employee count by {employee_diff}")
            print(f"   This means fewer employees needed for same coverage!")
        elif employee_diff == 0:
            print(f"➡️  NEUTRAL: Same employee count, but may have better utilization")
        else:
            print(f"⚠️  WARNING: More employees used - investigate why")
    else:
        print("⚠️  Cannot compare - one or both tests failed")
    
    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    
    return {
        'disabled': result_disabled,
        'enabled': result_enabled
    }


if __name__ == "__main__":
    results = test_rst_input_with_ot_aware()
    
    # Save results
    output_path = "output/rst_ot_aware_comparison.json"
    with open(output_path, 'w') as f:
        json.dump({
            'disabled': {
                'status': results['disabled'].get('solverRun', {}).get('status'),
                'assignmentCount': len(results['disabled'].get('assignments', [])),
                'solveTime': results['disabled'].get('solverRun', {}).get('durationSeconds', 0)
            },
            'enabled': {
                'status': results['enabled'].get('solverRun', {}).get('status'),
                'assignmentCount': len(results['enabled'].get('assignments', [])),
                'solveTime': results['enabled'].get('solverRun', {}).get('durationSeconds', 0)
            }
        }, f, indent=2)
    
    print(f"Results saved to: {output_path}")
