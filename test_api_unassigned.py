#!/usr/bin/env python3
"""
Test UNASSIGNED slot consistency on production API
"""
import json
import requests
import time
import sys

PRODUCTION_URL = "https://ngrssolver09.comcentricapps.com"

def test_production_unassigned():
    """Test UNASSIGNED consistency on production API"""
    print("="*80)
    print("PRODUCTION API TEST: UNASSIGNED SLOT CONSISTENCY")
    print("="*80)
    print(f"API: {PRODUCTION_URL}")
    print()
    
    # Load test input
    test_file = "RST-20260113-C9FE1E08_Solver_Input.json"
    print(f"Loading test input: {test_file}")
    with open(test_file, 'r') as f:
        input_data = json.load(f)
    
    # Submit async job
    print(f"\n1. Submitting async job...")
    response = requests.post(
        f"{PRODUCTION_URL}/solve/async",
        json=input_data,
        timeout=30
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to submit job: {response.status_code}")
        print(response.text[:500])
        return False
    
    result = response.json()
    job_id = result.get('job_id')
    print(f"✓ Job submitted: {job_id}")
    
    # Poll for completion
    print(f"\n2. Polling for job completion...")
    max_wait = 300  # 5 minutes
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        status_response = requests.get(
            f"{PRODUCTION_URL}/solve/async/{job_id}",
            timeout=10
        )
        
        if status_response.status_code != 200:
            print(f"❌ Failed to get status: {status_response.status_code}")
            return False
        
        status = status_response.json()
        job_status = status.get('status')
        print(f"  Status: {job_status}")
        
        if job_status == 'completed':
            print(f"✓ Job completed in {time.time() - start_time:.1f}s")
            break
        elif job_status == 'failed':
            print(f"❌ Job failed: {status.get('error')}")
            return False
        
        time.sleep(5)
    else:
        print(f"❌ Job timed out after {max_wait}s")
        return False
    
    # Get result
    print(f"\n3. Fetching result...")
    result_response = requests.get(
        f"{PRODUCTION_URL}/solve/async/{job_id}/result",
        timeout=30
    )
    
    if result_response.status_code != 200:
        print(f"❌ Failed to get result: {result_response.status_code}")
        return False
    
    output = result_response.json()
    print(f"✓ Result retrieved")
    
    # Verify UNASSIGNED consistency
    print(f"\n4. Verifying UNASSIGNED consistency...")
    
    # Count UNASSIGNED in assignments (check shiftCode)
    unassigned_in_assignments = sum(
        1 for a in output.get('assignments', [])
        if a.get('shiftCode') == 'UNASSIGNED'
    )
    
    # Count UNASSIGNED in employeeRoster
    unassigned_in_roster = sum(
        1 for emp in output.get('employeeRoster', [])
        for day in emp.get('dailyStatus', [])
        if day.get('status') == 'UNASSIGNED'
    )
    
    # Count in summary
    summary_unassigned = output.get('rosterSummary', {}).get('byStatus', {}).get('UNASSIGNED', 0)
    
    print(f"\nUNASSIGNED COUNTS:")
    print(f"  assignments[] array: {unassigned_in_assignments}")
    print(f"  employeeRoster.dailyStatus[]: {unassigned_in_roster}")
    print(f"  rosterSummary.byStatus.UNASSIGNED: {summary_unassigned}")
    
    # Sample UNASSIGNED assignments
    if unassigned_in_assignments > 0:
        samples = [a for a in output['assignments'] if a.get('shiftCode') == 'UNASSIGNED'][:3]
        print(f"\nSample UNASSIGNED assignments:")
        for s in samples:
            print(f"  - {s.get('employeeId')} on {s.get('date')}")
    
    # Check consistency
    if unassigned_in_assignments == unassigned_in_roster == summary_unassigned:
        print(f"\n{'='*80}")
        print(f"✅ PASS: UNASSIGNED counts are CONSISTENT")
        print(f"{'='*80}")
        return True
    else:
        print(f"\n{'='*80}")
        print(f"❌ FAIL: UNASSIGNED counts are INCONSISTENT")
        print(f"  Expected: {unassigned_in_roster} (from roster)")
        print(f"  Actual: {unassigned_in_assignments} (in assignments)")
        print(f"  Missing: {unassigned_in_roster - unassigned_in_assignments}")
        print(f"{'='*80}")
        return False

def main():
    """Run production test"""
    success = test_production_unassigned()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
