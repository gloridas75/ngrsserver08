#!/usr/bin/env python3
"""
Simple Redis async test (1 worker, no multiprocessing complexity)
"""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.redis_job_manager import RedisJobManager, JobStatus

def test_redis_async():
    """Test Redis job manager"""
    
    print("=" * 60)
    print("REDIS JOB MANAGER TEST")
    print("=" * 60)
    
    # Load small test input
    input_file = Path("input/async_test_small.json")
    with open(input_file) as f:
        test_input = json.load(f)
    
    print(f"\n✓ Loaded test input: {input_file}")
    
    # Create job manager
    jm = RedisJobManager()
    print("\n✓ Created RedisJobManager")
    
    # Check Redis connection
    try:
        jm.redis.ping()
        print("✓ Redis connected")
    except Exception as e:
        print(f"✗ Redis not connected: {e}")
        print("\nStart Redis with: docker run -d -p 6379:6379 --name ngrs-redis redis:7-alpine")
        return
    
    # Submit job
    print("\n✓ Submitting job...")
    job_id = jm.create_job(test_input)
    print(f"  Job ID: {job_id}")
    
    # Check status
    job_info = jm.get_job(job_id)
    print(f"  Status: {job_info.status.value}")
    print(f"  Created: {time.strftime('%H:%M:%S', time.localtime(job_info.created_at))}")
    
    # Get stats
    stats = jm.get_stats()
    print(f"\n✓ Stats:")
    print(f"  Queue length: {stats['queue_length']}")
    print(f"  Total jobs: {stats['total_jobs']}")
    print(f"  Results cached: {stats['results_cached']}")
    
    # Simulate processing (would be done by worker)
    print(f"\n✓ Simulating job processing...")
    jm.update_status(job_id, JobStatus.IN_PROGRESS)
    time.sleep(0.5)
    
    # Simulate completion
    mock_result = {
        "schemaVersion": "0.70",
        "solverRun": {"status": "OPTIMAL"},
        "assignments": [{"employeeId": "EMP_001", "date": "2025-12-01"}],
        "score": {"hard": 0, "soft": 0}
    }
    jm.store_result(job_id, mock_result)
    jm.update_status(job_id, JobStatus.COMPLETED)
    print(f"  Status: {jm.get_job(job_id).status.value}")
    
    # Retrieve result
    result = jm.get_result(job_id)
    print(f"  Result assignments: {len(result['assignments'])}")
    
    # Cleanup
    print(f"\n✓ Cleaning up...")
    jm.delete_job(job_id)
    
    print("\n" + "=" * 60)
    print("✅ TEST COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Start worker: python src/redis_worker.py")
    print("2. Submit jobs via API: POST /solve/async")
    print("3. Monitor: GET /solve/async/stats")

if __name__ == "__main__":
    test_redis_async()
