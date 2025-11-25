#!/usr/bin/env python3
"""
Test Redis-based async mode
Requires Redis server running on localhost:6379
"""
import sys
import json
import time
from pathlib import Path

# Setup path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.redis_job_manager import RedisJobManager
from src.redis_worker import start_worker_pool, cleanup_worker_pool


def test_redis_async_mode():
    """Test Redis-based async solver mode"""
    
    print("=" * 60)
    print("REDIS ASYNC MODE TEST")
    print("=" * 60)
    
    try:
        # Test Redis connection
        print("\n✓ Testing Redis connection...")
        job_manager = RedisJobManager(result_ttl_seconds=300, key_prefix="ngrs_test")
        
        # Clear test data
        print("✓ Clearing test data...")
        from src.redis_manager import get_redis_client
        redis_client = get_redis_client()
        
        # Delete all test keys
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(cursor, match="ngrs_test:*", count=100)
            if keys:
                redis_client.delete(*keys)
            if cursor == 0:
                break
        
        print(f"✓ Redis connected (TTL: {job_manager.result_ttl_seconds}s)")
        
    except ConnectionError as e:
        print(f"\n❌ Redis connection failed: {e}")
        print("\nTo start Redis:")
        print("  macOS:   brew install redis && brew services start redis")
        print("  Ubuntu:  sudo apt install redis-server && sudo systemctl start redis")
        print("  Docker:  docker run -d -p 6379:6379 redis:7-alpine")
        return False
    
    # Load test input
    input_file = Path("input/async_test_small.json")
    with open(input_file) as f:
        test_input = json.load(f)
    
    print(f"\n✓ Loaded test input: {input_file}")
    print(f"  Planning: {test_input['planningHorizon']}")
    print(f"  Employees: {len(test_input['employees'])}")
    
    # Start worker pool
    print("\n✓ Starting 2 Redis workers (multiprocessing)...")
    worker_processes, stop_event = start_worker_pool(num_workers=2, ttl_seconds=300)
    time.sleep(2)  # Let workers initialize
    
    # Submit jobs
    print("\n✓ Submitting 3 jobs to Redis queue...")
    job_ids = []
    for i in range(3):
        job_id = job_manager.create_job(test_input)
        job_ids.append(job_id)
        print(f"  Job {i+1}: {job_id}")
    
    # Monitor jobs
    print("\n✓ Monitoring jobs...")
    all_completed = False
    max_wait = 30  # seconds
    start_time = time.time()
    
    while not all_completed and (time.time() - start_time) < max_wait:
        time.sleep(1)
        
        statuses = []
        for job_id in job_ids:
            job_info = job_manager.get_job(job_id)
            if job_info:
                statuses.append(job_info.status.value)
            else:
                statuses.append("NOT_FOUND")
        
        # Check if all completed or failed
        all_completed = all(s in ['completed', 'failed'] for s in statuses)
        
        # Print status
        status_summary = ", ".join(statuses)
        print(f"  Status: {status_summary}", end="\r")
    
    print()  # New line after progress
    
    # Check results
    print("\n✓ Checking results...")
    success_count = 0
    for i, job_id in enumerate(job_ids, 1):
        job_info = job_manager.get_job(job_id)
        
        if not job_info:
            print(f"  Job {i}: NOT FOUND")
            continue
        
        print(f"  Job {i}: {job_info.status.value}")
        
        if job_info.status.value == "completed":
            result = job_manager.get_result(job_id)
            if result:
                assignments = len(result.get('assignments', []))
                solver_status = result.get('solverRun', {}).get('status', 'UNKNOWN')
                print(f"    → {solver_status}, {assignments} assignments")
                success_count += 1
        
        elif job_info.status.value == "failed":
            print(f"    → Error: {job_info.error_message}")
    
    # Get stats
    stats = job_manager.get_stats()
    print(f"\n✓ Final stats:")
    print(f"  Total jobs created: {stats['total_jobs']}")
    print(f"  Active jobs: {stats['active_jobs']}")
    print(f"  Queue length: {stats['queue_length']}")
    print(f"  Results cached: {stats['results_cached']}")
    print(f"  Status breakdown: {stats['status_breakdown']}")
    print(f"  Redis connected: {stats['redis_connected']}")
    
    # Test persistence
    print("\n✓ Testing job persistence...")
    job_4_id = job_manager.create_job(test_input)
    print(f"  Created job {job_4_id}")
    
    # Simulate API restart (worker pool stops, job remains in Redis)
    print("  Simulating API restart (workers stop)...")
    cleanup_worker_pool(worker_processes, stop_event, timeout=5)
    time.sleep(1)
    
    # Job should still exist in Redis
    job_4_info = job_manager.get_job(job_4_id)
    if job_4_info:
        print(f"  ✓ Job {job_4_id} persisted in Redis (status: {job_4_info.status.value})")
    else:
        print(f"  ✗ Job {job_4_id} NOT found after restart!")
    
    # Cleanup test data
    print("\n✓ Cleaning up test data...")
    for job_id in job_ids + [job_4_id]:
        job_manager.delete_job(job_id)
    
    print("\n" + "=" * 60)
    if success_count == 3:
        print("✅ ALL TESTS PASSED")
    else:
        print(f"⚠️  PARTIAL SUCCESS: {success_count}/3 jobs completed")
    print("=" * 60)
    
    return success_count == 3


if __name__ == "__main__":
    success = test_redis_async_mode()
    sys.exit(0 if success else 1)
