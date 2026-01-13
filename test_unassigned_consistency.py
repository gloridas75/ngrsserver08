#!/usr/bin/env python3
"""
Test UNASSIGNED slot consistency across outputs
"""
import json
import subprocess
import sys
import os

def test_unassigned_consistency(input_file):
    """Run solver and verify UNASSIGNED slots are consistent"""
    print(f"\nTesting: {input_file}")
    
    # Run solver
    output_file = f"output/test_unassigned_{os.path.basename(input_file).replace('_Input', '_Output')}"
    print(f"  Running solver...", end=" ")
    result = subprocess.run(
        ["python", "src/run_solver.py", "--in", input_file, "--out", output_file, "--time", "30"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("❌ FAILED")
        print(result.stderr[-500:])
        return False
    print("✓")
    
    # Check UNASSIGNED consistency
    print(f"  Verifying UNASSIGNED consistency...", end=" ")
    with open(output_file, 'r') as f:
        output = json.load(f)
    
    # Count UNASSIGNED in assignments (check shiftCode)
    unassigned_in_assignments = sum(1 for a in output['assignments'] if a.get('shiftCode') == 'UNASSIGNED')
    
    # Count UNASSIGNED in employeeRoster
    unassigned_in_roster = sum(
        1 for emp in output['employeeRoster']
        for day in emp['dailyStatus']
        if day.get('status') == 'UNASSIGNED'
    )
    
    # Count in summary
    summary_unassigned = output['rosterSummary']['byStatus'].get('UNASSIGNED', 0)
    
    # Check consistency
    if unassigned_in_assignments == unassigned_in_roster == summary_unassigned:
        print(f"✅ PASS")
        print(f"    Assignments UNASSIGNED: {unassigned_in_assignments}")
        print(f"    Roster UNASSIGNED: {unassigned_in_roster}")
        print(f"    Summary UNASSIGNED: {summary_unassigned}")
        
        # If UNASSIGNED > 0, sample some entries
        if unassigned_in_assignments > 0:
            samples = [a for a in output['assignments'] if a.get('shiftCode') == 'UNASSIGNED'][:2]
            print(f"    Sample UNASSIGNED assignments:")
            for s in samples:
                print(f"      - {s.get('employeeId')} on {s.get('date')}")
        return True
    else:
        print(f"❌ FAIL")
        print(f"    Assignments UNASSIGNED: {unassigned_in_assignments}")
        print(f"    Roster UNASSIGNED: {unassigned_in_roster}")
        print(f"    Summary UNASSIGNED: {summary_unassigned}")
        return False

def main():
    """Run UNASSIGNED consistency tests"""
    print("="*80)
    print("REGRESSION TEST: UNASSIGNED SLOT CONSISTENCY CHECK")
    print("="*80)
    
    # Test cases
    test_cases = [
        "RST-20260113-C9FE1E08_Solver_Input.json",  # Has UNASSIGNED slots (employee 00034833)
        "input/RST-20260112-4E8B07EE_Solver_Input.json",  # demandBased roster
        "input/RST-20260113-6C5FEBA6_Solver_Input.json",  # outcomeBased roster
    ]
    
    results = []
    for test_file in test_cases:
        if os.path.exists(test_file):
            results.append(test_unassigned_consistency(test_file))
        else:
            print(f"\n⚠️  Skipping {test_file} (not found)")
    
    # Summary
    print("\n" + "="*80)
    passed = sum(results)
    total = len(results)
    print(f"SUMMARY: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ ALL TESTS PASSED")
        return 0
    else:
        print(f"❌ {total - passed} test(s) FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
