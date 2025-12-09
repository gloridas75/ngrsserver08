"""
Test ICPMP v2 with icpmp_v2_test2.json input file
Tests the 7-day APO coverage scenario with 30 headcount
"""
import json
from datetime import datetime
import sys
import os

# Add context path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'context'))

from context.engine.config_optimizer import (
    optimize_all_requirements,
    format_output_config
)

def load_test_input(filepath: str):
    """Load test input from JSON file"""
    with open(filepath, 'r') as f:
        return json.load(f)

def run_icpmp_test():
    """Run ICPMP v2 on test2 input file"""
    
    print("="*80)
    print("ICPMP v2 Test - Full Week Coverage (30 headcount)")
    print("="*80)
    print()
    
    # Load input file
    input_file = "output/icpmp_v2_test2.json"
    print(f"Loading input: {input_file}")
    
    try:
        input_config = load_test_input(input_file)
    except FileNotFoundError:
        print(f"ERROR: File not found: {input_file}")
        return
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}")
        return
    
    print(f"✓ Loaded successfully")
    print()
    
    # Display input summary
    print("INPUT SUMMARY:")
    print(f"  Organization: {input_config.get('organizationId')}")
    print(f"  Planning Horizon: {input_config['planningHorizon']['startDate']} to {input_config['planningHorizon']['endDate']}")
    print(f"  Total Days: {input_config['planningHorizon']['totalDays']}")
    print()
    
    for req in input_config['requirements']:
        print(f"  Requirement: {req['requirementId']}")
        print(f"    Name: {req['requirementName']}")
        print(f"    Coverage Days: {', '.join(req['coverageDays'])} ({len(req['coverageDays'])} days)")
        print(f"    Shift Types: {', '.join(req['shiftTypes'])}")
        print(f"    Headcount: {req.get('headcountByShift', req.get('headcountPerShift'))}")
        print()
    
    # Run ICPMP v2 optimizer
    print("RUNNING ICPMP v2 OPTIMIZER...")
    print()
    
    try:
        optimized_result = optimize_all_requirements(
            requirements=input_config['requirements'],
            constraints=input_config['constraints'],
            planning_horizon=input_config['planningHorizon'],
            top_n=5  # Get top 5 alternatives
        )
        
        # Format output
        output_config = format_output_config(optimized_result, input_config)
        
        # Save output
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"output/icpmp_v2_test2_result_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(output_config, f, indent=2)
        
        print()
        print("="*80)
        print("RESULTS SUMMARY")
        print("="*80)
        print()
        print(f"Total Requirements: {output_config['summary']['totalRequirements']}")
        print(f"Total Employees Needed: {output_config['summary']['totalEmployees']}")
        print(f"Optimizer Version: {output_config['summary']['optimizerVersion']}")
        print()
        
        # Display top recommendations
        print("TOP RECOMMENDATIONS:")
        print()
        
        for rec in output_config['recommendations']:
            if rec['alternativeRank'] == 1:  # Show only best for each requirement
                print(f"  {rec['requirementId']}: {rec['requirementName']}")
                print(f"    Pattern: {' '.join(rec['configuration']['workPattern'])}")
                print(f"    Employees: {rec['configuration']['employeesRequired']}")
                print(f"      - Strict: {rec['configuration']['strictEmployees']}")
                print(f"      - Flexible: {rec['configuration']['flexibleEmployees']}")
                print(f"    Quality Score: {rec['quality']['score']}")
                print(f"    Coverage: {rec['coverage']['coverageType']}")
                print()
        
        print("="*80)
        print(f"✓ Output saved to: {output_file}")
        print("="*80)
        print()
        
        return output_config
        
    except Exception as e:
        print(f"ERROR during optimization: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = run_icpmp_test()
    
    if result:
        print("\n✅ Test completed successfully!")
    else:
        print("\n❌ Test failed!")
        sys.exit(1)
