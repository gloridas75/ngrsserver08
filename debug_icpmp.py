#!/usr/bin/env python3
"""
Debug script to run ICPMP preprocessing and show detailed results.
"""
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.preprocessing.icpmp_integration import ICPMPPreprocessor

def main():
    input_file = Path("input/RST-20251212-39F6E7F5_Solver_Input.json")
    
    print("=" * 80)
    print("ICPMP PREPROCESSING DEBUG")
    print("=" * 80)
    
    # Load input
    with open(input_file) as f:
        input_data = json.load(f)
    
    print(f"\n📥 INPUT:")
    print(f"  Total employees: {len(input_data['employees'])}")
    print(f"  Schema version: {input_data.get('schemaVersion')}")
    
    # Check if employees have patterns
    employees_with_patterns = sum(1 for e in input_data['employees'] if e.get('workPattern'))
    print(f"  Employees with workPattern: {employees_with_patterns}")
    
    # Check rotation offsets
    offsets = [e.get('rotationOffset', 0) for e in input_data['employees']]
    unique_offsets = sorted(set(offsets))
    print(f"  Unique rotation offsets: {unique_offsets}")
    
    # Show requirements
    print(f"\n📋 REQUIREMENTS:")
    for di in input_data['demandItems']:
        for req in di['requirements']:
            req_id = req['requirementId']
            headcount = req['headcount']
            pattern = req.get('workPattern', 'NOT SPECIFIED')
            scheme = req.get('scheme', 'NOT SPECIFIED')
            print(f"  {req_id}: {headcount} employees, Pattern: {pattern}, Scheme: {scheme}")
    
    # Run ICPMP preprocessing
    print(f"\n🔧 RUNNING ICPMP v3.0 PREPROCESSING...")
    preprocessor = ICPMPPreprocessor(input_data)
    result = preprocessor.preprocess_all_requirements()
    
    filtered_employees = result['filtered_employees']
    
    print(f"\n✅ ICPMP RESULTS:")
    print(f"  Filtered employees: {len(filtered_employees)}")
    print(f"  Reduction: {len(input_data['employees'])} → {len(filtered_employees)}")
    
    # Show detailed employee info
    print(f"\n👥 SELECTED EMPLOYEES (with patterns and offsets):")
    print(f"  {'Employee ID':<15} {'Rotation Offset':<17} {'Work Pattern':<30} {'Scheme':<10}")
    print(f"  {'-'*15} {'-'*17} {'-'*30} {'-'*10}")
    
    for emp in filtered_employees:
        emp_id = emp['employeeId']
        offset = emp.get('rotationOffset', 'NONE')
        pattern = emp.get('workPattern', 'NOT ASSIGNED')
        if isinstance(pattern, list):
            pattern = ''.join(pattern)
        scheme = emp.get('scheme', 'N/A')
        print(f"  {emp_id:<15} {str(offset):<17} {pattern:<30} {scheme:<10}")
    
    # Verify pattern distribution
    print(f"\n📊 PATTERN DISTRIBUTION:")
    patterns = {}
    for emp in filtered_employees:
        pattern = emp.get('workPattern', 'NONE')
        if isinstance(pattern, list):
            pattern = ''.join(pattern)
        patterns[pattern] = patterns.get(pattern, 0) + 1
    
    for pattern, count in patterns.items():
        print(f"  {pattern}: {count} employees")
    
    # Verify offset distribution
    print(f"\n📊 OFFSET DISTRIBUTION:")
    offsets_dist = {}
    for emp in filtered_employees:
        offset = emp.get('rotationOffset', 'NONE')
        offsets_dist[offset] = offsets_dist.get(offset, 0) + 1
    
    for offset in sorted(offsets_dist.keys()):
        print(f"  Offset {offset}: {offsets_dist[offset]} employees")
    
    # Calculate expected coverage
    print(f"\n📈 COVERAGE ANALYSIS:")
    days_in_period = 31  # January 2026
    required_headcount = 10  # From requirement
    total_slots = days_in_period * required_headcount
    print(f"  Days in period: {days_in_period}")
    print(f"  Required headcount per day: {required_headcount}")
    print(f"  Total slots to fill: {total_slots}")
    
    # Assuming DDDDDOO pattern (5 work days per 7-day cycle)
    work_days_per_cycle = 5
    cycle_length = 7
    work_ratio = work_days_per_cycle / cycle_length
    
    expected_employee_days = len(filtered_employees) * days_in_period * work_ratio
    print(f"  Expected employee-days: {expected_employee_days:.1f}")
    print(f"  Utilization: {(total_slots / expected_employee_days * 100):.1f}%")
    
    if expected_employee_days < total_slots:
        print(f"  ⚠️  WARNING: Insufficient capacity! Need {(total_slots / work_ratio / days_in_period):.1f} employees")
    else:
        print(f"  ✅ Sufficient capacity")
    
    # Save filtered employees for inspection
    output_file = Path("output/icpmp_filtered_employees.json")
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(filtered_employees, f, indent=2)
    print(f"\n💾 Saved filtered employees to: {output_file}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
