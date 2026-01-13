#!/usr/bin/env python3
"""
Regression test for OFF_DAY consistency across assignments and employeeRoster
"""
import json
import os
import subprocess
import sys
from pathlib import Path

def verify_off_days_consistency(output_file):
    """Verify OFF_DAYs are present in both assignments and employeeRoster"""
    try:
        with open(output_file, 'r') as f:
            output = json.load(f)
        
        # Get all OFF_DAYs from employeeRoster
        roster_off_days = set()
        for emp in output.get('employeeRoster', []):
            for day in emp.get('dailyStatus', []):
                if day.get('status') == 'OFF_DAY':
                    key = f"{emp['employeeId']}_{day['date']}"
                    roster_off_days.add(key)
        
        # Get all OFF_DAYs from assignments
        assignment_off_days = set()
        for a in output.get('assignments', []):
            if a.get('status') == 'OFF_DAY':
                key = f"{a['employeeId']}_{a['date']}"
                assignment_off_days.add(key)
        
        # Check consistency
        missing = roster_off_days - assignment_off_days
        extra = assignment_off_days - roster_off_days
        
        roster_summary_off_days = output.get('rosterSummary', {}).get('byStatus', {}).get('OFF_DAY', 0)
        
        return {
            'status': 'PASS' if len(missing) == 0 and len(extra) == 0 else 'FAIL',
            'assignments_off_days': len(assignment_off_days),
            'roster_off_days': len(roster_off_days),
            'summary_off_days': roster_summary_off_days,
            'missing': len(missing),
            'extra': len(extra),
            'total_assignments': len(output.get('assignments', [])),
            'solver_status': output.get('solverRun', {}).get('status', 'UNKNOWN')
        }
    except Exception as e:
        return {
            'status': 'ERROR',
            'error': str(e)
        }

def run_solver_test(input_file, timeout=30):
    """Run solver on input file and return output path"""
    input_path = Path(input_file)
    output_file = f"output/regression_{input_path.stem}_output.json"
    
    cmd = [
        'python', 'src/run_solver.py',
        '--in', str(input_file),
        '--out', output_file,
        '--time', str(timeout)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 10
        )
        
        if result.returncode == 0 and os.path.exists(output_file):
            return output_file, None
        else:
            return None, f"Solver failed: {result.stderr[:200]}"
    except subprocess.TimeoutExpired:
        return None, "Timeout"
    except Exception as e:
        return None, str(e)

def main():
    print("="*80)
    print("REGRESSION TEST: OFF_DAY CONSISTENCY CHECK")
    print("="*80)
    
    # Test cases
    test_files = [
        # Current test case
        'RST-20260113-C9FE1E08_Solver_Input.json',
        # Input folder test cases
        'input/RST-20260112-4E8B07EE_Solver_Input.json',
        'input/RST-20260112-71DA90DC_Solver_Input.json',
        'input/RST-20260112-D6226DC3_Solver_Input.json',
        'input/RST-20260113-6C5FEBA6_Solver_Input.json',
        # Test baselines
        'test_baselines/RST-20260112-4E8B07EE_Solver_Input.json',
        'test_baselines/AUTO-20251206-233E7006_Solver_Input.json',
    ]
    
    results = []
    
    for test_file in test_files:
        if not os.path.exists(test_file):
            print(f"⚠️  SKIP: {test_file} (not found)")
            continue
        
        print(f"\n{'─'*80}")
        print(f"Testing: {test_file}")
        print(f"{'─'*80}")
        
        # Get rostering basis
        try:
            with open(test_file, 'r') as f:
                input_data = json.load(f)
            rostering_basis = input_data.get('demandItems', [{}])[0].get('rosteringBasis', 'unknown')
            print(f"  Rostering Basis: {rostering_basis}")
        except:
            rostering_basis = 'unknown'
        
        # Run solver
        print(f"  Running solver...", end='', flush=True)
        output_file, error = run_solver_test(test_file, timeout=30)
        
        if error:
            print(f" ❌ FAILED")
            print(f"  Error: {error}")
            results.append({
                'test': test_file,
                'rostering_basis': rostering_basis,
                'status': 'ERROR',
                'error': error
            })
            continue
        
        print(f" ✓")
        
        # Verify OFF_DAY consistency
        print(f"  Verifying OFF_DAY consistency...", end='', flush=True)
        verification = verify_off_days_consistency(output_file)
        
        result = {
            'test': test_file,
            'rostering_basis': rostering_basis,
            'output_file': output_file,
            **verification
        }
        results.append(result)
        
        if verification['status'] == 'PASS':
            print(f" ✅ PASS")
            print(f"    Assignments OFF_DAYs: {verification['assignments_off_days']}")
            print(f"    Roster OFF_DAYs: {verification['roster_off_days']}")
            print(f"    Summary OFF_DAYs: {verification['summary_off_days']}")
            print(f"    Total Assignments: {verification['total_assignments']}")
        else:
            print(f" ❌ FAIL")
            if verification.get('error'):
                print(f"    Error: {verification['error']}")
            else:
                print(f"    Assignments OFF_DAYs: {verification['assignments_off_days']}")
                print(f"    Roster OFF_DAYs: {verification['roster_off_days']}")
                print(f"    Missing: {verification['missing']}")
                print(f"    Extra: {verification['extra']}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    total = len(results)
    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = sum(1 for r in results if r['status'] == 'FAIL')
    errors = sum(1 for r in results if r['status'] == 'ERROR')
    
    print(f"Total Tests: {total}")
    print(f"  ✅ Passed: {passed}")
    print(f"  ❌ Failed: {failed}")
    print(f"  🔥 Errors: {errors}")
    
    if failed > 0:
        print("\nFailed Tests:")
        for r in results:
            if r['status'] == 'FAIL':
                print(f"  - {r['test']}")
                print(f"    Rostering Basis: {r['rostering_basis']}")
                print(f"    Missing: {r['missing']}, Extra: {r['extra']}")
    
    print("="*80)
    
    # Write detailed results
    with open('output/regression_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetailed results written to: output/regression_test_results.json")
    
    # Exit with appropriate code
    sys.exit(0 if failed == 0 and errors == 0 else 1)

if __name__ == '__main__':
    main()
