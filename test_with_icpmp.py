#!/usr/bin/env python3
"""
Test solver WITH ICPMP preprocessing (like production redis_worker)
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.preprocessing.icpmp_integration import ICPMPPreprocessor
from context.engine.data_loader import load_input
from context.engine.solver_engine import solve

def main():
    input_file = Path("input/RST-20251212-39F6E7F5_Solver_Input.json")
    
    # Load input
    with open(input_file) as f:
        input_data = json.load(f)
    
    print(f"📥 ORIGINAL INPUT: {len(input_data['employees'])} employees")
    
    # Run ICPMP preprocessing (like redis_worker does)
    print(f"🔧 Running ICPMP preprocessing...")
    preprocessor = ICPMPPreprocessor(input_data)
    preprocessing_result = preprocessor.preprocess_all_requirements()
    
    # Replace employee list (like redis_worker does at line 125)
    input_data['employees'] = preprocessing_result['filtered_employees']
    
    print(f"✅ AFTER ICPMP: {len(input_data['employees'])} employees")
    print(f"   Filtered: {len(input_data['employees'])} employees with rotated patterns")
    
    # Now pass to CP-SAT solver
    print(f"\n🚀 Starting CP-SAT solver...")
    ctx = load_input(input_data)
    ctx["timeLimit"] = 120  # 2 minutes
    
    status_code, solver_result, assignments, violations = solve(ctx)
    
    print(f"\n✅ SOLVE COMPLETE:")
    print(f"   Status: {solver_result.get('status')}")
    print(f"   Assignments: {len(assignments)}")
    print(f"   Hard violations: {solver_result.get('hard_violations', 0)}")
    print(f"   Employees used: {len(set(a['employeeId'] for a in assignments))}")

if __name__ == "__main__":
    main()
