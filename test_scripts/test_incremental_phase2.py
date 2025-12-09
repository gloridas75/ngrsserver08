#!/usr/bin/env python3
"""
Test Incremental Solver - Phase 2 Validation
Tests new joiner, departure, and long leave scenarios
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.incremental_solver import solve_incremental, IncrementalSolverError
from src.models import IncrementalSolveRequest
from context.engine.solver_engine import solve as solver_engine

def test_scenario(test_file: str, scenario_name: str):
    """Test a single incremental solve scenario"""
    print(f"\n{'='*80}")
    print(f"Testing: {scenario_name}")
    print(f"{'='*80}")
    
    test_path = Path(test_file)
    if not test_path.exists():
        print(f"❌ Test file not found: {test_file}")
        return False
    
    # Load test input
    with open(test_path) as f:
        input_data = json.load(f)
    
    # Load previousOutput if path is provided
    if "previousOutputPath" in input_data:
        prev_path = Path(input_data["previousOutputPath"])
        if prev_path.exists():
            with open(prev_path) as f:
                input_data["previousOutput"] = json.load(f)
            del input_data["previousOutputPath"]
            print(f"✓ Loaded previousOutput from: {prev_path.name}")
        else:
            print(f"❌ previousOutput file not found: {prev_path}")
            return False
    
    print(f"✓ Loaded test file: {test_path.name}")
    print(f"  Temporal Window: {input_data['temporalWindow']['cutoffDate']} → "
          f"{input_data['temporalWindow']['solveFromDate']} to {input_data['temporalWindow']['solveToDate']}")
    
    # Validate with Pydantic
    try:
        request = IncrementalSolveRequest(**input_data)
        print(f"✓ Schema validation passed (v{input_data['schemaVersion']})")
    except Exception as e:
        print(f"❌ Schema validation failed: {e}")
        return False
    
    # Check employee changes
    changes = input_data['employeeChanges']
    print(f"  Employee Changes:")
    print(f"    - New Joiners: {len(changes.get('newJoiners', []))}")
    print(f"    - Not Available: {len(changes.get('notAvailableFrom', []))}")
    print(f"    - Long Leave: {len(changes.get('longLeave', []))}")
    
    # Run incremental solve
    try:
        print(f"\n🔄 Running incremental solver...")
        
        # Generate unique run ID
        run_id = f"SRN-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Convert request to dict (Pydantic v1)
        request_dict = request.dict()
        
        result = solve_incremental(
            request_data=request_dict,
            solver_engine=solver_engine,
            run_id=run_id
        )
        
        # Debug: Check what was returned
        print(f"\n[DEBUG] Result keys: {list(result.keys())}")
        print(f"[DEBUG] Schema version in result: {result.get('schemaVersion')}")
        print(f"[DEBUG] Has incrementalSolve? {'incrementalSolve' in result}")
        
        print(f"\n✅ Solve completed successfully!")
        print(f"  Schema Version: {result.get('schemaVersion')}")
        print(f"  Total Assignments: {len(result.get('assignments', []))}")
        
        # Analyze assignments by source
        assignments = result.get('assignments', [])
        locked_count = sum(1 for a in assignments if a.get('auditInfo', {}).get('source') == 'locked')
        incremental_count = sum(1 for a in assignments if a.get('auditInfo', {}).get('source') == 'incremental')
        
        print(f"\n  Assignment Breakdown:")
        print(f"    - Locked (from previous): {locked_count}")
        print(f"    - Incremental (new): {incremental_count}")
        
        # Check incremental metadata
        incr_meta = result.get('incrementalSolve', {})
        print(f"\n  Incremental Metadata:")
        print(f"    - Cutoff Date: {incr_meta.get('cutoffDate')}")
        print(f"    - Locked Count: {incr_meta.get('lockedCount')}")
        print(f"    - Freed Departed: {incr_meta.get('freedDepartedCount')}")
        print(f"    - Freed Leave: {incr_meta.get('freedLeaveCount')}")
        print(f"    - Total Solvable: {incr_meta.get('solvableCount')}")
        
        # Check solver status
        solver_run = result.get('solverRun', {})
        print(f"\n  Solver Run:")
        print(f"    - Status: {solver_run.get('status')}")
        print(f"    - Duration: {solver_run.get('durationSeconds', 0):.2f}s")
        print(f"    - Run ID: {solver_run.get('runId')}")
        
        # Save output
        output_file = f"output/incremental_{scenario_name}.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n💾 Output saved: {output_file}")
        
        return True
        
    except IncrementalSolverError as e:
        print(f"\n❌ Incremental Solver Error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all test scenarios"""
    print("\n" + "="*80)
    print("INCREMENTAL SOLVER - PHASE 2 VALIDATION TEST SUITE")
    print("="*80)
    
    test_scenarios = [
        ("input/incremental/test_new_joiner.json", "new_joiner"),
        ("input/incremental/test_departure.json", "departure"),
        ("input/incremental/test_long_leave.json", "long_leave")
    ]
    
    results = {}
    
    for test_file, scenario_name in test_scenarios:
        results[scenario_name] = test_scenario(test_file, scenario_name)
    
    # Summary
    print(f"\n\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    
    for scenario_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {scenario_name:20} {status}")
    
    all_passed = all(results.values())
    print(f"\n{'='*80}")
    if all_passed:
        print("🎉 ALL TESTS PASSED - PHASE 2 VALIDATION COMPLETE")
    else:
        print("⚠️  SOME TESTS FAILED - REVIEW ERRORS ABOVE")
    print(f"{'='*80}\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
