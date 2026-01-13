#!/usr/bin/env python3
"""
Test the production API endpoint for OFF_DAY consistency
"""
import requests
import json
import time

# Use production endpoint as per guidelines
API_URL = "https://ngrssolver09.comcentricapps.com"

print("="*80)
print("TESTING PRODUCTION API - OFF_DAY CONSISTENCY")
print("="*80)
print(f"Endpoint: {API_URL}")
print()

# Load test input
with open('RST-20260113-C9FE1E08_Solver_Input.json', 'r') as f:
    input_data = json.load(f)

print("Submitting job to async endpoint...")
try:
    response = requests.post(
        f"{API_URL}/solve/async",
        json=input_data,
        timeout=30
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to submit job: {response.status_code}")
        print(response.text[:500])
        exit(1)
    
    result = response.json()
    job_id = result.get('job_id')
    print(f"✓ Job submitted: {job_id}")
    print()
    
    # Poll for completion
    print("Waiting for job to complete...")
    max_attempts = 60
    for attempt in range(max_attempts):
        time.sleep(2)
        
        status_response = requests.get(
            f"{API_URL}/solve/async/{job_id}",
            timeout=10
        )
        
        if status_response.status_code != 200:
            print(f"❌ Failed to get status: {status_response.status_code}")
            continue
        
        status_data = status_response.json()
        job_status = status_data.get('status')
        
        print(f"  Attempt {attempt+1}/{max_attempts}: {job_status}", end='\r')
        
        if job_status == 'completed':
            print()
            print("✓ Job completed!")
            break
        elif job_status == 'failed':
            print()
            print(f"❌ Job failed: {status_data.get('error')}")
            exit(1)
    else:
        print()
        print("❌ Job timed out")
        exit(1)
    
    # Get final results
    print()
    print("Fetching final results...")
    result_response = requests.get(
        f"{API_URL}/solve/async/{job_id}/result",
        timeout=30
    )
    
    if result_response.status_code != 200:
        print(f"❌ Failed to get results: {result_response.status_code}")
        exit(1)
    
    output_data = result_response.json()
    
    # Verify OFF_DAY consistency
    print("─"*80)
    print("VERIFYING OFF_DAY CONSISTENCY:")
    print("─"*80)
    
    assignments_off = len([a for a in output_data['assignments'] if a.get('status') == 'OFF_DAY'])
    roster_off = sum(len([d for d in emp['dailyStatus'] if d.get('status') == 'OFF_DAY']) 
                     for emp in output_data['employeeRoster'])
    summary_off = output_data['rosterSummary']['byStatus']['OFF_DAY']
    
    print(f"  Assignments OFF_DAYs: {assignments_off}")
    print(f"  EmployeeRoster OFF_DAYs: {roster_off}")
    print(f"  RosterSummary OFF_DAYs: {summary_off}")
    print(f"  Total Assignments: {len(output_data['assignments'])}")
    print()
    
    if assignments_off == roster_off == summary_off:
        print("✅ PASS: OFF_DAYs are consistent across all sections!")
        print("="*80)
        exit(0)
    else:
        print("❌ FAIL: OFF_DAYs are inconsistent!")
        print(f"   Missing in assignments: {roster_off - assignments_off}")
        print("="*80)
        exit(1)
        
except requests.exceptions.RequestException as e:
    print(f"❌ Network error: {e}")
    exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)
