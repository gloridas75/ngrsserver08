#!/usr/bin/env python3
"""
Test Redis worker standalone (manual mode)
"""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.redis_job_manager import RedisJobManager, JobStatus

def manual_worker_test():
    """Test worker logic manually without multiprocessing"""
    
    print("=" * 60)
    print("REDIS WORKER TEST (Manual)")
    print("=" * 60)
    
    jm = RedisJobManager()
    
    # Load test input
    input_file = Path("input/async_test_small.json")
    with open(input_file) as f:
        test_input = json.load(f)
    
    # Submit job
    job_id = jm.create_job(test_input)
    print(f"\n✓ Job submitted: {job_id}")
    
    # Simulate worker picking up job
    print("\n[WORKER] Looking for jobs...")
    next_job = jm.get_next_job(timeout=0)
    
    if not next_job:
        print("[WORKER] No jobs in queue")
        return
    
    print(f"[WORKER] Processing job {next_job}")
    jm.update_status(next_job, JobStatus.IN_PROGRESS)
    
    # Get job data
    job_info = jm.get_job(next_job)
    input_data = job_info.input_data
    
    print(f"[WORKER] Input: {input_data.get('planningReference', 'ASYNC_TEST')}")
    print(f"[WORKER] Employees: {len(input_data.get('employees', []))}")
    print(f"[WORKER] Planning horizon: {input_data.get('planningHorizon', {})}")
    
    # Run solver
    print("[WORKER] Running solver...")
    start_time = time.time()
    
    try:
        from context.engine.data_loader import load_input
        from context.engine.solver_engine import solve
        from src.output_builder import build_output
        
        ctx = load_input(input_data)
        ctx["timeLimit"] = input_data.get("solverRunTime", {}).get("maxSeconds", 5)
        
        status_code, solver_result, assignments, violations = solve(ctx)
        
        result = build_output(
            input_data, ctx, status_code, solver_result, assignments, violations
        )
        
        elapsed = time.time() - start_time
        print(f"[WORKER] Solved in {elapsed:.2f}s")
        print(f"[WORKER] Status: {result['solverRun']['status']}")
        print(f"[WORKER] Assignments: {len(result['assignments'])}")
        
        # Store result
        jm.store_result(next_job, result)
        jm.update_status(next_job, JobStatus.COMPLETED)
        print(f"[WORKER] Job completed")
        
    except Exception as e:
        print(f"[WORKER] Job failed: {e}")
        jm.update_status(next_job, JobStatus.FAILED, error_message=str(e))
    
    # Verify result
    final_job = jm.get_job(next_job)
    print(f"\n✓ Final status: {final_job.status.value}")
    
    if final_job.status == JobStatus.COMPLETED:
        result = jm.get_result(next_job)
        print(f"✓ Result available: {len(result['assignments'])} assignments")
    
    # Cleanup
    jm.delete_job(next_job)
    print(f"✓ Cleaned up")
    
    print("\n" + "=" * 60)
    print("✅ WORKER TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    manual_worker_test()
