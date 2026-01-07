#!/usr/bin/env python3
"""
Verify output format consistency across all rostering modes.
"""
import json

# Test files representing different modes
test_files = {
    'demandBased': 'output/RST-20260105-8D58C796_Solver_Output.json',  # Old demandBased
    'outcomeBased_cpsat': 'output/test_cpsat_fixed.json',  # New CP-SAT template
}

required_fields = ['assignmentId', 'slotId', 'employeeId', 'demandId', 'requirementId', 
                   'date', 'shiftCode', 'status', 'startDateTime', 'endDateTime', 'hours']

print("=" * 80)
print("OUTPUT FORMAT VERIFICATION")
print("=" * 80)
print()

for mode, filepath in test_files.items():
    try:
        with open(filepath) as f:
            data = json.load(f)
        
        assignments = data.get('assignments', [])
        if not assignments:
            print(f"❌ {mode}: No assignments found")
            continue
        
        first_assignment = assignments[0]
        missing_fields = [f for f in required_fields if f not in first_assignment]
        
        if missing_fields:
            print(f"❌ {mode}: Missing fields: {missing_fields}")
            print(f"   Available fields: {list(first_assignment.keys())}")
        else:
            print(f"✅ {mode}: All required fields present")
            print(f"   Total assignments: {len(assignments)}")
            print(f"   Status values: {set(a.get('status') for a in assignments)}")
        print()
        
    except FileNotFoundError:
        print(f"⚠️  {mode}: Test file not found: {filepath}")
        print()
    except Exception as e:
        print(f"❌ {mode}: Error: {e}")
        print()

print("=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
