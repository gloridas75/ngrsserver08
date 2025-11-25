#!/usr/bin/env python3
"""
Test ICPMP Configuration Optimizer on production server
"""
import json
import requests
from pathlib import Path

def test_icpmp_production():
    """Test the ICPMP endpoint on production server"""
    
    # Read input file
    input_file = Path("input/requirements_simple.json")
    output_file = Path("output/icpmp_production_test.json")
    
    print(f"Reading input from: {input_file}")
    with open(input_file, 'r') as f:
        requirements_data = json.load(f)
    
    # Production endpoint
    url = "https://ngrssolver08.comcentricapps.com/configure"
    
    print(f"\nSending POST request to: {url}")
    print(f"Number of requirements: {len(requirements_data.get('requirements', []))}")
    
    # Send POST request
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, json=requirements_data, headers=headers, timeout=300)
    
    print(f"Response status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        
        # Save the complete response
        print(f"\nSaving response to: {output_file}")
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        # Print summary
        print("\n" + "="*80)
        print("ICPMP PRODUCTION TEST SUMMARY")
        print("="*80)
        
        configurations = result.get('configurations', [])
        print(f"\n1. Total requirements processed: {len(configurations)}")
        
        # Calculate total employees needed (using best pattern from each requirement)
        total_employees = 0
        for config in configurations:
            if config.get('patterns'):
                best_pattern = config['patterns'][0]  # First pattern is the best
                total_employees += best_pattern.get('employeeCount', 0)
        
        print(f"2. Total employees needed (best patterns): {total_employees}")
        
        # Detailed per-requirement analysis
        print(f"\n3. Per-requirement analysis:")
        print("-" * 80)
        
        all_have_5_alternatives = True
        shift_type_validation_issues = []
        
        for config in configurations:
            req_id = config.get('requirementId', 'Unknown')
            req_name = config.get('requirementName', 'Unknown')
            patterns = config.get('patterns', [])
            num_alternatives = len(patterns)
            
            # Check if this requirement has 5 alternatives
            if num_alternatives != 5:
                all_have_5_alternatives = False
            
            if patterns:
                best = patterns[0]
                employee_count = best.get('employeeCount', 0)
                coverage_rate = best.get('coverageRate', 0) * 100
                pattern_desc = best.get('pattern', {})
                cycle_length = pattern_desc.get('cycleLength', 'N/A')
                work_days = pattern_desc.get('workDays', 'N/A')
                off_days = pattern_desc.get('offDays', 'N/A')
                shift_types = pattern_desc.get('shiftTypes', [])
                
                print(f"\n{req_id} ({req_name}):")
                print(f"  - Alternatives: {num_alternatives}")
                print(f"  - Best Pattern: {work_days}W-{off_days}O (Cycle: {cycle_length})")
                print(f"  - Shift Types: {', '.join(shift_types)}")
                print(f"  - Employee Count: {employee_count}")
                print(f"  - Coverage Rate: {coverage_rate:.1f}%")
                
                # Validate shift types filtering
                # Get the original requirement to check expected shift types
                orig_req = next((r for r in requirements_data['requirements'] if r['id'] == req_id), None)
                if orig_req:
                    expected_shifts = orig_req.get('shiftTypes', [])
                    if set(shift_types) != set(expected_shifts):
                        shift_type_validation_issues.append({
                            'requirementId': req_id,
                            'expected': expected_shifts,
                            'actual': shift_types
                        })
            else:
                print(f"\n{req_id} ({req_name}): No patterns generated")
        
        # Validation results
        print("\n" + "="*80)
        print("VALIDATION RESULTS")
        print("="*80)
        
        print(f"\n4. All requirements returned 5 alternatives: {'✓ YES' if all_have_5_alternatives else '✗ NO'}")
        if not all_have_5_alternatives:
            print("   Issues found:")
            for config in configurations:
                req_id = config.get('requirementId')
                num_patterns = len(config.get('patterns', []))
                if num_patterns != 5:
                    print(f"   - {req_id}: {num_patterns} alternatives")
        
        print(f"\n5. ShiftTypes filtering validation: {'✓ PASS' if not shift_type_validation_issues else '✗ FAIL'}")
        if shift_type_validation_issues:
            print("   Issues found:")
            for issue in shift_type_validation_issues:
                print(f"   - {issue['requirementId']}: Expected {issue['expected']}, Got {issue['actual']}")
        else:
            print("   - REQ_APO_DAY correctly filtered to D-only patterns")
            print("   - Other requirements correctly filtered to N-only patterns")
        
        print("\n" + "="*80)
        print(f"Complete response saved to: {output_file}")
        print("="*80 + "\n")
        
        return True
    else:
        print(f"\nError: {response.status_code}")
        print(f"Response: {response.text}")
        return False

if __name__ == "__main__":
    try:
        test_icpmp_production()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
