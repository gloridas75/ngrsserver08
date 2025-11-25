#!/usr/bin/env python3
"""
Test async mode locally without running full API server
"""
import sys
import json
import time
import threading
from pathlib import Path

# Setup path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.job_manager import JobManager, JobStatus
from src.async_worker import start_worker_pool, cleanup_worker_pool

def test_async_mode():
    """Test async solver mode"""
    
    print("=" * 60)
    print("ASYNC MODE TEST")
    print("=" * 60)
    
    # Load test input
    input_file = Path("input/async_test_small.json")
    with open(input_file) as f:
        test_input = json.load(f)
    
    print(f"\n✓ Loaded test input: {input_file}")
    print(f"  Planning: {test_input['planningHorizon']}")
    print(f"  Employees: {len(test_input['employees'])}")
    
    # Create job manager
    job_manager = JobManager(max_queue_size=5, result_ttl_seconds=300)
    print("\n✓ Created JobManager")
    
    # Start worker pool
    print("\n✓ Starting 2 workers...")
    worker_threads, stop_event = start_worker_pool(job_manager, num_workers=2)
    time.sleep(1)  # Let workers initialize
    
    # Submit jobs
    print("\n✓ Submitting 3 jobs...")
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
        
        # Check if all completed or failed
        all_completed = all(s in ['completed', 'failed'] for s in statuses)
        
        # Print status
        status_summary = ", ".join(statuses)
        print(f"  Status: {status_summary}", end="\r")
    
    print()  # New line after progress
    
    # Check results
    print("\n✓ Checking results...")
    for i, job_id in enumerate(job_ids, 1):
        job_info = job_manager.get_job(job_id)
        
        if not job_info:
            print(f"  Job {i}: NOT FOUND")
            continue
        
        print(f"  Job {i}: {job_info.status.value}")
        
        if job_info.status == JobStatus.COMPLETED:
            result = job_manager.get_result(job_id)
            if result:
                assignments = len(result.get('assignments', []))
                solver_status = result.get('solverRun', {}).get('status', 'UNKNOWN')
                print(f"    → {solver_status}, {assignments} assignments")
        
        elif job_info.status == JobStatus.FAILED:
            print(f"    → Error: {job_info.error_message}")
    
    # Get stats
    stats = job_manager.get_stats()
    print(f"\n✓ Final stats:")
    print(f"  Total jobs: {stats['total_jobs']}")
    print(f"  Queue length: {stats['queue_length']}")
    print(f"  Results cached: {stats['results_cached']}")
    print(f"  Status breakdown: {stats['status_breakdown']}")
    
    # Cleanup
    print("\n✓ Cleaning up workers...")
    cleanup_worker_pool(worker_threads, stop_event)
    time.sleep(1)
    
    print("\n" + "=" * 60)
    print("✅ TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    test_async_mode()
