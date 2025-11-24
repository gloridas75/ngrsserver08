#!/usr/bin/env python3
"""
Complete Redis API Integration Test

Tests the full async job lifecycle:
1. Submit job via POST /solve/async
2. Check status via GET /solve/async/{job_id}
3. Retrieve result via GET /solve/async/{job_id}/result
4. Verify stats via GET /solve/async/stats
5. Delete job via DELETE /solve/async/{job_id}

Prerequisites:
- Redis running (docker)
- API server running: python -m uvicorn src.api_server:app --host 127.0.0.1 --port 8080
- Workers running (started by API server or manually)
"""

import json
import time
import requests
from pathlib import Path

API_BASE = "http://127.0.0.1:8080"

def load_test_input():
    """Load test input JSON"""
    input_file = Path("input/async_test_small.json")
    with open(input_file) as f:
        return json.load(f)

def test_complete_lifecycle():
    """Test complete async job lifecycle"""
    print("=" * 70)
    print("REDIS API INTEGRATION TEST")
    print("=" * 70)
    
    # Step 1: Submit job
    print("\n[1] Submitting async job...")
    input_data = load_test_input()
    response = requests.post(
        f"{API_BASE}/solve/async",
        json={"input_json": input_data}
    )
    
    if response.status_code != 200:
        print(f"✗ Job submission failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return False
    
    result = response.json()
    job_id = result["job_id"]
    print(f"✓ Job submitted: {job_id}")
    print(f"  Status: {result['status']}")
    print(f"  Created: {result['created_at']}")
    
    # Step 2: Poll for completion
    print(f"\n[2] Polling job status...")
    max_polls = 10
    poll_interval = 0.5
    
    for i in range(max_polls):
        time.sleep(poll_interval)
        response = requests.get(f"{API_BASE}/solve/async/{job_id}")
        
        if response.status_code != 200:
            print(f"✗ Status check failed: {response.status_code}")
            return False
        
        status_data = response.json()
        status = status_data["status"]
        print(f"  Poll {i+1}/{max_polls}: {status}")
        
        if status == "completed":
            print(f"✓ Job completed")
            print(f"  Started: {status_data['started_at']}")
            print(f"  Completed: {status_data['completed_at']}")
            print(f"  Result size: {status_data['result_size_bytes']} bytes")
            break
        elif status == "failed":
            print(f"✗ Job failed: {status_data.get('error_message')}")
            return False
    else:
        print(f"✗ Job did not complete within {max_polls * poll_interval}s")
        return False
    
    # Step 3: Retrieve result
    print(f"\n[3] Retrieving result...")
    response = requests.get(f"{API_BASE}/solve/async/{job_id}/result")
    
    if response.status_code != 200:
        print(f"✗ Result retrieval failed: {response.status_code}")
        return False
    
    result_data = response.json()
    print(f"✓ Result retrieved")
    print(f"  Solver status: {result_data['solverRun']['status']}")
    print(f"  Overall score: {result_data['score']['overall']}")
    print(f"  Hard violations: {result_data['score']['hard']}")
    print(f"  Duration: {result_data['solverRun']['durationSeconds']}s")
    
    if result_data['solverRun']['status'] != 'OPTIMAL':
        print(f"✗ Expected OPTIMAL status, got {result_data['solverRun']['status']}")
        return False
    
    # Step 4: Check stats
    print(f"\n[4] Checking stats...")
    response = requests.get(f"{API_BASE}/solve/async/stats")
    
    if response.status_code != 200:
        print(f"✗ Stats retrieval failed: {response.status_code}")
        return False
    
    stats = response.json()
    print(f"✓ Stats retrieved")
    print(f"  Total jobs: {stats['total_jobs']}")
    print(f"  Active jobs: {stats['active_jobs']}")
    print(f"  Queue length: {stats['queue_length']}")
    print(f"  Results cached: {stats['results_cached']}")
    print(f"  Workers: {stats['workers']}")
    print(f"  Redis connected: {stats['redis_connected']}")
    
    if not stats['redis_connected']:
        print(f"✗ Redis not connected")
        return False
    
    # Step 5: Delete job
    print(f"\n[5] Deleting job...")
    response = requests.delete(f"{API_BASE}/solve/async/{job_id}")
    
    if response.status_code != 200:
        print(f"✗ Job deletion failed: {response.status_code}")
        return False
    
    delete_result = response.json()
    print(f"✓ Job deleted: {delete_result.get('message', 'OK')}")
    
    # Verify deletion
    response = requests.get(f"{API_BASE}/solve/async/{job_id}")
    if response.status_code == 404:
        print(f"✓ Verified job no longer exists")
    else:
        print(f"⚠ Job still exists after deletion (status: {response.status_code})")
    
    print("\n" + "=" * 70)
    print("✓ ALL TESTS PASSED")
    print("=" * 70)
    return True

if __name__ == "__main__":
    try:
        success = test_complete_lifecycle()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
