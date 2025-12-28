#!/usr/bin/env python3
"""
Test incremental solving on production server.
Server: https://ngrssolver09.comcentricapps.com

Tests:
1. demandBased incremental solve (traditional pattern-based)
2. outcomeBased incremental solve (template-based with headcount=0)
"""

import json
import requests
import time
from datetime import datetime

# Production server URL
BASE_URL = "https://ngrssolver09.comcentricapps.com"

def print_section(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def test_incremental_demand_based():
    """Test demandBased incremental solving."""
    print_section("TEST 1: demandBased Incremental Solve")
    
    # Load test input
    with open('input/test_incremental_demand_based.json', 'r') as f:
        request_data = json.load(f)
    
    print(f"✓ Loaded test input from: input/test_incremental_demand_based.json")
    print(f"  - Planning: {request_data['planningReference']}")
    print(f"  - Temporal Window: {request_data['temporalWindow']['cutoffDate']} → {request_data['temporalWindow']['solveToDate']}")
    print(f"  - Rostering Basis: {request_data['demandItems'][0].get('rosteringBasis', 'demandBased')}")
    print(f"  - Previous Assignments: {len(request_data['previousOutput']['assignments'])}")
    
    # Test sync endpoint
    print("\n⏳ Sending request to /solve/incremental...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/solve/incremental",
            json=request_data,
            headers={'Content-Type': 'application/json'},
            timeout=180
        )
        
        print(f"✓ Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            # Save response
            output_file = f"output/incremental_demand_based_prod_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            print(f"✓ Response saved to: {output_file}")
            
            # Analyze result
            if 'assignments' in result:
                locked_count = sum(1 for a in result['assignments'] if a.get('status') == 'LOCKED')
                new_count = sum(1 for a in result['assignments'] if a.get('status') == 'ASSIGNED')
                print(f"\n📊 Result Summary:")
                print(f"  - Total Assignments: {len(result['assignments'])}")
                print(f"  - Locked (from previous): {locked_count}")
                print(f"  - New Assignments: {new_count}")
                print(f"  - Solver Status: {result.get('solverRun', {}).get('status', 'Unknown')}")
            
            return True
        else:
            print(f"✗ Request failed: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_incremental_outcome_based():
    """Test outcomeBased incremental solving (with headcount=0 support)."""
    print_section("TEST 2: outcomeBased Incremental Solve (headcount=0)")
    
    # Load test input
    with open('input/test_incremental_outcome_based.json', 'r') as f:
        request_data = json.load(f)
    
    print(f"✓ Loaded test input from: input/test_incremental_outcome_based.json")
    print(f"  - Planning: {request_data['planningReference']}")
    print(f"  - Temporal Window: {request_data['temporalWindow']['cutoffDate']} → {request_data['temporalWindow']['solveToDate']}")
    print(f"  - Rostering Basis: {request_data['demandItems'][0].get('rosteringBasis', 'outcomeBased')}")
    print(f"  - Headcount: {request_data['demandItems'][0]['requirements'][0]['headcount']}")
    print(f"  - Previous Assignments: {len(request_data['previousOutput']['assignments'])}")
    
    # Test sync endpoint
    print("\n⏳ Sending request to /solve/incremental...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/solve/incremental",
            json=request_data,
            headers={'Content-Type': 'application/json'},
            timeout=180
        )
        
        print(f"✓ Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            # Save response
            output_file = f"output/incremental_outcome_based_prod_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            print(f"✓ Response saved to: {output_file}")
            
            # Analyze result
            if 'assignments' in result:
                locked_count = sum(1 for a in result['assignments'] if a.get('status') == 'LOCKED')
                new_count = sum(1 for a in result['assignments'] if a.get('status') == 'ASSIGNED')
                print(f"\n📊 Result Summary:")
                print(f"  - Total Assignments: {len(result['assignments'])}")
                print(f"  - Locked (from previous): {locked_count}")
                print(f"  - New Assignments: {new_count}")
                print(f"  - Solver Status: {result.get('solverRun', {}).get('status', 'Unknown')}")
            
            return True
        else:
            print(f"✗ Request failed: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_server_health():
    """Test if server is responding."""
    print_section("Server Health Check")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            print(f"✓ Server is healthy: {response.json()}")
            return True
        else:
            print(f"✗ Server returned status: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Server unreachable: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "="*80)
    print("  INCREMENTAL SOLVER - PRODUCTION TEST")
    print(f"  Server: {BASE_URL}")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Check server health first
    if not test_server_health():
        print("\n✗ Server health check failed. Aborting tests.")
        exit(1)
    
    # Run tests
    results = []
    
    # Test 1: demandBased incremental
    try:
        results.append(("demandBased Incremental", test_incremental_demand_based()))
    except Exception as e:
        print(f"\n✗ Test 1 crashed: {e}")
        results.append(("demandBased Incremental", False))
    
    time.sleep(2)  # Brief pause between tests
    
    # Test 2: outcomeBased incremental
    try:
        results.append(("outcomeBased Incremental", test_incremental_outcome_based()))
    except Exception as e:
        print(f"\n✗ Test 2 crashed: {e}")
        results.append(("outcomeBased Incremental", False))
    
    # Summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\n{'='*80}")
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ ALL TESTS PASSED")
        print("\nTest files used:")
        print("  - input/test_incremental_demand_based.json")
        print("  - input/test_incremental_outcome_based.json")
        print("\nOutput files saved in: output/incremental_*_prod_*.json")
        exit(0)
    else:
        print("\n✗ SOME TESTS FAILED")
        exit(1)
