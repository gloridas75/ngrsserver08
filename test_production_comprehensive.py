#!/usr/bin/env python3
"""
Comprehensive production API test for OFF_DAY consistency
"""
import requests
import json
import time

API_URL = "https://ngrssolver09.comcentricapps.com"

def test_input_file(input_file, test_name):
    """Test a single input file"""
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"{'='*80}")
    
    # Load input
    with open(input_file, 'r') as f:
        input_data = json.load(f)
    
    rostering_basis = input_data.get('demandItems', [{}])[0].get('rosteringBasis', 'unknown')
    print(f"Rostering Basis: {rostering_basis}")
    print(f"Submitting to: {API_URL}/solve/async")
    
    # Submit job
    try:
        response = requests.post(
            f"{API_URL}/solve/async",
            json=input_data,
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ FAIL: {response.status_code}")
            return False
        
        job_id = response.json().get('job_id')
        print(f"Job ID: {job_id}")
        
        # Poll for completion
        for attempt in range(60):
            time.sleep(2)
            status_response = requests.get(f"{API_URL}/solve/async/{job_id}", timeout=10)
            
            if status_response.status_code != 200:
                continue
            
            status = status_response.json().get('status')
            
            if status == 'completed':
                break
            elif status == 'failed':
                print(f"❌ FAIL: Job failed")
                return False
        
        # Get results
        result_response = requests.get(f"{API_URL}/solve/async/{job_id}/result", timeout=30)
        
        if result_response.status_code != 200:
            print(f"❌ FAIL: Could not get results")
            return False
        
        output = result_response.json()
        
        # Verify consistency
        assignments_off = len([a for a in output['assignments'] if a.get('status') == 'OFF_DAY'])
        roster_off = sum(len([d for d in emp['dailyStatus'] if d.get('status') == 'OFF_DAY']) 
                         for emp in output['employeeRoster'])
        summary_off = output['rosterSummary']['byStatus']['OFF_DAY']
        
        print(f"\nRESULTS:")
        print(f"  Assignments OFF_DAYs: {assignments_off}")
        print(f"  EmployeeRoster OFF_DAYs: {roster_off}")
        print(f"  RosterSummary OFF_DAYs: {summary_off}")
        print(f"  Solver Status: {output['solverRun']['status']}")
        
        if assignments_off == roster_off == summary_off:
            print(f"✅ PASS")
            return True
        else:
            print(f"❌ FAIL: Inconsistent ({assignments_off}/{roster_off}/{summary_off})")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

# Test cases
print("="*80)
print("COMPREHENSIVE PRODUCTION API TEST - OFF_DAY CONSISTENCY")
print("="*80)

tests = [
    ("RST-20260113-C9FE1E08_Solver_Input.json", "outcomeBased - Small Roster"),
    ("input/RST-20260113-6C5FEBA6_Solver_Input.json", "demandBased - Template"),
]

results = []
for input_file, test_name in tests:
    try:
        result = test_input_file(input_file, test_name)
        results.append((test_name, result))
    except Exception as e:
        print(f"❌ Test failed: {e}")
        results.append((test_name, False))

# Summary
print(f"\n{'='*80}")
print("FINAL SUMMARY")
print(f"{'='*80}")

passed = sum(1 for _, r in results if r)
total = len(results)

print(f"Tests: {passed}/{total} passed")
for test_name, result in results:
    status = "✅ PASS" if result else "❌ FAIL"
    print(f"  {status} - {test_name}")

print(f"{'='*80}")

if passed == total:
    print("✅ ALL PRODUCTION TESTS PASSED!")
    print("   OFF_DAY fix successfully deployed and verified on production.")
else:
    print("⚠️  Some tests failed. Review above for details.")

print(f"{'='*80}")
