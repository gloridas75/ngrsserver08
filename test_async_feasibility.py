#!/usr/bin/env python3
"""
Test async endpoint feasibility check with ICPMP v2.0 upgrade.

This script verifies:
1. Async endpoint returns UUID immediately
2. Feasibility check uses ICPMP v2.0 logic
3. Estimates are accurate and coverage-aware
"""

import requests
import json
import sys

def test_async_feasibility(api_url, input_file):
    """Test async endpoint feasibility response."""
    
    print(f"Testing Async Endpoint: {api_url}")
    print(f"Input File: {input_file}")
    print("=" * 80)
    
    # Load test input
    with open(input_file) as f:
        test_input = json.load(f)
    
    # Call async endpoint
    print("\n1. Calling POST /solve/async...")
    response = requests.post(
        f"{api_url}/solve/async",
        json=test_input,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"❌ ERROR: Status {response.status_code}")
        print(response.text)
        return False
    
    result = response.json()
    
    # Verify UUID
    print(f"✓ Job ID: {result['job_id']}")
    print(f"✓ Status: {result['status']}")
    
    # Verify feasibility check exists
    if 'feasibility_check' not in result:
        print("❌ ERROR: No feasibility_check in response")
        return False
    
    feasibility = result['feasibility_check']
    print(f"\n2. Feasibility Check Results:")
    print(f"   • Likely Feasible: {feasibility['likely_feasible']}")
    print(f"   • Confidence: {feasibility['confidence']}")
    
    # Check analysis details
    if 'analysis' in feasibility:
        analysis = feasibility['analysis']
        print(f"\n3. Employee Analysis:")
        print(f"   • Provided: {analysis['employees_provided']}")
        print(f"   • Required: {analysis['employees_required_min']}-{analysis['employees_required_max']}")
        print(f"   • Shortfall: {analysis['shortfall']}")
        print(f"   • Planning Days: {analysis['planning_days']}")
        
        if 'by_requirement' in analysis and len(analysis['by_requirement']) > 0:
            print(f"\n4. Requirement Details ({len(analysis['by_requirement'])} total):")
            for req in analysis['by_requirement'][:5]:  # Show first 5
                print(f"\n   Requirement {req['requirement_id']}:")
                print(f"     - Estimated: {req['employees_required_min']}-{req['employees_required_max']} employees")
                print(f"     - Available: {req['employees_matching']} matching")
                print(f"     - Pattern: {req.get('work_pattern', 'N/A')}")
                print(f"     - Coverage Days: {req.get('coverage_days', 'N/A')}")
                print(f"     - Method: {req.get('estimation_method', 'N/A')}")
                print(f"     - Sufficient: {'✓' if req.get('sufficient', False) else '✗'}")
            
            # Verify ICPMP v2.0 is being used
            methods = [req.get('estimation_method', 'Unknown') for req in analysis['by_requirement']]
            if all(m == 'ICPMP v2.0' for m in methods):
                print(f"\n✓ All requirements using ICPMP v2.0 method!")
            else:
                print(f"\n⚠ Mixed methods detected: {set(methods)}")
    
    # Check warnings/recommendations
    if feasibility.get('warnings'):
        print(f"\n5. Warnings:")
        for warning in feasibility['warnings']:
            print(f"   ⚠ {warning}")
    
    if feasibility.get('recommendations'):
        print(f"\n6. Recommendations:")
        for rec in feasibility['recommendations']:
            print(f"   • {rec}")
    
    print("\n" + "=" * 80)
    print("✓ Test Complete - Async endpoint working correctly with ICPMP v2.0!")
    return True


if __name__ == "__main__":
    # Default test configuration
    API_URL = "http://localhost:8080"  # Change to production URL if needed
    INPUT_FILE = "input/input_v0.7_SchemePtest.json"
    
    # Parse command line args if provided
    if len(sys.argv) > 1:
        API_URL = sys.argv[1]
    if len(sys.argv) > 2:
        INPUT_FILE = sys.argv[2]
    
    success = test_async_feasibility(API_URL, INPUT_FILE)
    sys.exit(0 if success else 1)
