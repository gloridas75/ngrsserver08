"""
Test ICPMP v3.0 Integration with CP-SAT Solver

This script tests the complete integration flow:
1. Load test input JSON (RST-20251210-0870DE6A_Solver_Input.json)
2. Run ICPMP v3.0 preprocessing
3. Validate employee selection and offset assignment
4. Show before/after comparison

Usage:
    python test_icpmp_integration.py
"""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.preprocessing.icpmp_integration import ICPMPPreprocessor


def load_test_input():
    """Load test input JSON file"""
    # Try Downloads folder first (from user's system)
    downloads_path = Path.home() / "Downloads" / "RST-20251210-0870DE6A_Solver_Input.json"
    
    if downloads_path.exists():
        print(f"Loading test input from: {downloads_path}")
        with open(downloads_path, 'r') as f:
            return json.load(f)
    
    # Fallback to input folder
    input_path = Path(__file__).parent / "input" / "RST-20251210-0870DE6A_Solver_Input.json"
    if input_path.exists():
        print(f"Loading test input from: {input_path}")
        with open(input_path, 'r') as f:
            return json.load(f)
    
    raise FileNotFoundError(
        "Could not find RST-20251210-0870DE6A_Solver_Input.json in Downloads or input/ folder"
    )


def print_section(title):
    """Print formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_icpmp_preprocessing():
    """Main test function"""
    
    print_section("ICPMP v3.0 INTEGRATION TEST")
    
    # Load input
    input_json = load_test_input()
    
    print("\n📋 INPUT SUMMARY:")
    print(f"  Planning Reference: {input_json.get('planningReference')}")
    print(f"  Planning Horizon: {input_json['planningHorizon']['startDate']} to {input_json['planningHorizon']['endDate']}")
    print(f"  Total Employees: {len(input_json.get('employees', []))}")
    print(f"  Total Demand Items: {len(input_json.get('demandItems', []))}")
    
    # Count requirements
    total_requirements = sum(
        len(demand.get('requirements', [])) 
        for demand in input_json.get('demandItems', [])
    )
    print(f"  Total Requirements: {total_requirements}")
    
    # Show employee scheme distribution
    from collections import Counter
    schemes = Counter(emp.get('scheme') for emp in input_json.get('employees', []))
    print(f"\n  Employee Scheme Distribution:")
    for scheme, count in schemes.items():
        print(f"    {scheme}: {count}")
    
    # Show first requirement details
    if input_json.get('demandItems'):
        first_demand = input_json['demandItems'][0]
        if first_demand.get('requirements'):
            first_req = first_demand['requirements'][0]
            print(f"\n  First Requirement:")
            print(f"    ID: {first_req.get('requirementId')}")
            print(f"    Work Pattern: {len(first_req.get('workPattern', []))}-day cycle")
            print(f"    Headcount: {first_req.get('headcount')}")
            print(f"    Scheme: {first_req.get('scheme')}")
    
    print_section("RUNNING ICPMP v3.0 PREPROCESSING")
    
    # Run preprocessing
    preprocessor = ICPMPPreprocessor(input_json)
    result = preprocessor.preprocess_all_requirements()
    
    print("\n✅ PREPROCESSING COMPLETED")
    
    print_section("RESULTS")
    
    # Summary
    summary = result['summary']
    print("\n📊 SUMMARY:")
    print(f"  Requirements Processed: {summary['total_requirements_processed']}")
    print(f"  Employees Available: {summary['total_employees_available']}")
    print(f"  Employees Selected: {summary['total_employees_selected']}")
    print(f"  Utilization Rate: {summary['utilization_rate']:.1%}")
    
    # Per-requirement details
    print("\n📋 PER-REQUIREMENT DETAILS:")
    for req_id, metadata in result['icpmp_metadata'].items():
        print(f"\n  Requirement: {req_id}")
        print(f"    Demand ID: {metadata['demandId']}")
        print(f"    Optimal Employees: {metadata['optimal_employees']}")
        print(f"    Selected Count: {metadata['selected_count']}")
        print(f"    U-Slots Total: {metadata['u_slots_total']}")
        print(f"    Is Optimal: {metadata['is_optimal']}")
        
        # Format offset distribution display
        offsets = metadata['offset_distribution']
        if isinstance(offsets, dict):
            offsets_display = str(offsets)
        else:
            offsets_display = str(offsets)
        print(f"    Offset Distribution: {offsets_display}")
    
    # Selected employees
    print("\n👥 SELECTED EMPLOYEES:")
    filtered_employees = result['filtered_employees']
    
    # Group by requirement
    from collections import defaultdict
    by_requirement = defaultdict(list)
    for emp in filtered_employees:
        req_id = emp.get('_icpmp_requirement_id', 'UNKNOWN')
        by_requirement[req_id].append(emp)
    
    for req_id, employees in by_requirement.items():
        print(f"\n  Requirement: {req_id} ({len(employees)} employees)")
        
        # Show scheme distribution
        scheme_dist = Counter(emp.get('scheme') for emp in employees)
        print(f"    Schemes: {dict(scheme_dist)}")
        
        # Show working hours distribution
        working_hours = [emp.get('totalWorkingHours', 0) for emp in employees]
        if any(h > 0 for h in working_hours):
            print(f"    Working Hours: min={min(working_hours):.1f}, max={max(working_hours):.1f}, avg={sum(working_hours)/len(working_hours):.1f}")
        else:
            print(f"    Working Hours: Not specified (all 0)")
        
        # Show rotation offsets
        offsets = [emp.get('rotationOffset', 0) for emp in employees]
        print(f"    Rotation Offsets: {offsets}")
        
        # Show first 3 employees
        print(f"    Sample Employees:")
        for emp in employees[:3]:
            print(f"      - {emp['employeeId']} ({emp.get('scheme')}, offset={emp.get('rotationOffset')}, hours={emp.get('totalWorkingHours', 0)})")
    
    # Warnings
    if result['warnings']:
        print("\n⚠️  WARNINGS:")
        for warning in result['warnings']:
            print(f"  - {warning}")
    else:
        print("\n✅ No warnings")
    
    print_section("VALIDATION")
    
    # Validate results
    validation_passed = True
    
    # Check 1: All employees have rotation offsets
    for emp in filtered_employees:
        if 'rotationOffset' not in emp:
            print(f"❌ FAIL: Employee {emp['employeeId']} missing rotationOffset")
            validation_passed = False
    
    if validation_passed:
        print("✅ All employees have rotation offsets")
    
    # Check 2: All employees assigned to requirements
    for emp in filtered_employees:
        if '_icpmp_requirement_id' not in emp:
            print(f"❌ FAIL: Employee {emp['employeeId']} not assigned to requirement")
            validation_passed = False
    
    if validation_passed:
        print("✅ All employees assigned to requirements")
    
    # Check 3: Employee count matches optimal
    for req_id, metadata in result['icpmp_metadata'].items():
        if metadata['selected_count'] != metadata['optimal_employees']:
            print(f"⚠️  WARNING: Requirement {req_id} selected {metadata['selected_count']} but optimal is {metadata['optimal_employees']}")
        else:
            print(f"✅ Requirement {req_id}: Selected count matches optimal ({metadata['optimal_employees']})")
    
    # Check 4: No duplicate employees across requirements
    all_emp_ids = [emp['employeeId'] for emp in filtered_employees]
    if len(all_emp_ids) != len(set(all_emp_ids)):
        print("❌ FAIL: Duplicate employees found across requirements")
        validation_passed = False
    else:
        print("✅ No duplicate employees across requirements")
    
    print_section("TEST RESULT")
    
    if validation_passed:
        print("\n🎉 ALL VALIDATIONS PASSED!")
        print("\n✅ ICPMP v3.0 integration is working correctly")
        print("✅ Ready to test with actual CP-SAT solver")
    else:
        print("\n❌ SOME VALIDATIONS FAILED")
        print("⚠️  Please review warnings above")
    
    print("\n" + "=" * 80 + "\n")
    
    return result


if __name__ == "__main__":
    try:
        result = test_icpmp_preprocessing()
        
        # Optionally save result to file
        output_path = Path(__file__).parent / "output" / "icpmp_integration_test_result.json"
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, 'w') as f:
            # Remove employee objects (too large), keep metadata
            output_data = {
                'summary': result['summary'],
                'icpmp_metadata': result['icpmp_metadata'],
                'warnings': result['warnings'],
                'selected_employee_ids': [emp['employeeId'] for emp in result['filtered_employees']],
                'selected_employee_count': len(result['filtered_employees'])
            }
            json.dump(output_data, f, indent=2)
        
        print(f"📄 Detailed results saved to: {output_path}")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH ERROR:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
