#!/usr/bin/env python3
"""Roster Configuration Optimizer - Find optimal work patterns and staffing.

This tool analyzes simple requirements and suggests:
1. Optimal work patterns for each requirement
2. Minimum employee count needed
3. Recommended rotation offsets

Usage:
    python src/configure_roster.py --in input/requirements_simple.json --out config/recommended.json
"""

import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import json
import argparse
from datetime import datetime
from context.engine.config_optimizer_v3 import optimize_all_requirements, format_output_config


def load_requirements(filepath: str) -> dict:
    """Load simple requirements file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_config(config: dict, filepath: str):
    """Save optimized configuration to file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def print_summary(config: dict):
    """Print summary of optimized configuration."""
    print(f"\n{'='*80}")
    print("OPTIMIZATION SUMMARY")
    print(f"{'='*80}\n")
    
    summary = config['summary']
    print(f"Total Requirements: {summary['totalRequirements']}")
    print(f"Total Employees Needed: {summary['totalEmployees']}")
    print(f"Planning Horizon: {summary['planningHorizon']['days']} days")
    print()
    
    print("Recommendations by Requirement:")
    print("-" * 80)
    
    for rec in config['recommendations']:
        print(f"\n{rec['requirementId']}: {rec['requirementName']}")
        print(f"  Product: {rec['productType']}, Rank: {rec['rank']}, Scheme: {rec['scheme']}")
        print(f"  Work Pattern: {rec['configuration']['workPattern']}")
        print(f"  Employees Required: {rec['configuration']['employeesRequired']}")
        print(f"  Rotation Offsets: {rec['configuration']['rotationOffsets']}")
        print(f"  Expected Coverage: {rec['coverage']['expectedCoverageRate']}%")
        print(f"  Balance Score: {rec['quality']['balanceScore']:.1f}")
        
        if rec['notes']:
            print("  Notes:")
            for note in rec['notes']:
                print(f"    - {note}")
    
    print(f"\n{'='*80}\n")


def generate_employee_list(config: dict) -> list:
    """Generate employee list from configuration."""
    employees = []
    employee_counter = 1
    
    for rec in config['recommendations']:
        req_id = rec['requirementId']
        product_type = rec['productType']
        rank = rec['rank']
        scheme = rec['scheme']
        employee_count = rec['configuration']['employeesRequired']
        offsets = rec['configuration']['rotationOffsets']
        
        for i in range(employee_count):
            emp_id = f"EMP_{employee_counter:03d}"
            employee = {
                'employeeId': emp_id,
                'name': f"{product_type} {scheme} Employee {i+1}",
                'productTypeId': product_type,
                'rank': rank,
                'scheme': scheme,
                'rotationOffset': offsets[i] if i < len(offsets) else i % 6,
                'assignedRequirement': req_id
            }
            employees.append(employee)
            employee_counter += 1
    
    return employees


def main():
    parser = argparse.ArgumentParser(
        description='Optimize roster configuration from simple requirements'
    )
    parser.add_argument('--in', dest='input_file', required=True,
                       help='Input requirements file (JSON)')
    parser.add_argument('--out', dest='output_file', required=False,
                       help='Output configuration file (JSON)')
    parser.add_argument('--employees', dest='employee_file', required=False,
                       help='Output employee list file (JSON)')
    
    args = parser.parse_args()
    
    print(f"\n{'='*80}")
    print("ROSTER CONFIGURATION OPTIMIZER")
    print(f"{'='*80}\n")
    print(f"Input: {args.input_file}")
    
    # Load requirements
    print("Loading requirements...")
    requirements_data = load_requirements(args.input_file)
    
    # Optimize configuration
    optimized = optimize_all_requirements(
        requirements_data['requirements'],
        requirements_data['constraints'],
        requirements_data['planningHorizon']
    )
    
    # Format output
    output_config = format_output_config(optimized, requirements_data['requirements'])
    
    # Print summary
    print_summary(output_config)
    
    # Save configuration
    if args.output_file:
        save_config(output_config, args.output_file)
        print(f"✓ Saved configuration to: {args.output_file}")
    else:
        # Default output location
        output_path = 'config/recommended_config.json'
        save_config(output_config, output_path)
        print(f"✓ Saved configuration to: {output_path}")
    
    # Generate and save employee list if requested
    if args.employee_file:
        employees = generate_employee_list(output_config)
        employee_data = {
            'generatedAt': datetime.now().isoformat(),
            'totalEmployees': len(employees),
            'employees': employees
        }
        with open(args.employee_file, 'w') as f:
            json.dump(employee_data, f, indent=2)
        print(f"✓ Generated employee list: {args.employee_file}")
        print(f"  Total employees: {len(employees)}")
    
    print(f"\n{'='*80}")
    print("NEXT STEPS:")
    print(f"{'='*80}")
    print("1. Review the recommended configuration")
    print("2. Adjust patterns/offsets if needed")
    print("3. Generate full input file with these recommendations")
    print("4. Run main solver: python src/run_solver.py --in input/input_generated.json")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()
