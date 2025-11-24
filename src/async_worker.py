"""
Async Worker for Background Solver Processing
Uses threading for job processing
"""
import time
import traceback
import threading
import sys
import pathlib
from typing import Dict, Any, List

# Setup path for imports
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.job_manager import JobManager, JobStatus
from context.engine.data_loader import load_input
from context.engine.solver_engine import solve
from src.output_builder import build_output


def solver_worker(job_manager: JobManager, worker_id: int, stop_event: threading.Event):
    """
    Background worker that processes jobs from queue
    
    Runs in separate thread and continuously polls queue.
    
    Args:
        job_manager: Shared JobManager instance
        worker_id: Worker identifier (1, 2, ...)
        stop_event: Threading event to signal shutdown
    """
    print(f"[WORKER-{worker_id}] Solver worker started")
    
    while not stop_event.is_set():
        # Get next job from queue
        job_id = job_manager.get_next_job()
        
        if not job_id:
            # No jobs available, sleep and retry
            time.sleep(0.5)
            continue
        
        print(f"[WORKER-{worker_id}] Processing job {job_id}")
        
        # Update status to IN_PROGRESS
        job_manager.update_status(job_id, JobStatus.IN_PROGRESS)
        
        try:
            # Get job details
            job_info = job_manager.get_job(job_id)
            if not job_info:
                print(f"[WORKER-{worker_id}] Job {job_id} not found, skipping")
                continue
            
            input_data = job_info.input_data
            
            # Run solver
            start_time = time.time()
            
            # Load and solve
            ctx = load_input(input_data)
            ctx["timeLimit"] = input_data.get("solverRunTime", {}).get("maxSeconds", 15)
            
            status_code, solver_result, assignments, violations = solve(ctx)
            
            # Build output
            result = build_output(
                input_data, ctx, status_code, solver_result, assignments, violations
            )
            
            elapsed_time = time.time() - start_time
            
            print(f"[WORKER-{worker_id}] Job {job_id} completed in {elapsed_time:.2f}s")
            
            # Store result
            job_manager.store_result(job_id, result)
            job_manager.update_status(job_id, JobStatus.COMPLETED)
            
        except Exception as e:
            # Handle solver errors
            error_msg = f"{type(e).__name__}: {str(e)}"
            error_trace = traceback.format_exc()
            
            print(f"[WORKER-{worker_id}] Job {job_id} failed: {error_msg}")
            print(f"[WORKER-{worker_id}] Traceback:\n{error_trace}")
            
            # Update job with error
            job_manager.update_status(
                job_id, 
                JobStatus.FAILED, 
                error_message=error_msg
            )
    
    print(f"[WORKER-{worker_id}] Worker stopped")


def start_worker_pool(job_manager: JobManager, num_workers: int = 2) -> tuple[List[threading.Thread], threading.Event]:
    """
    Start pool of worker threads
    
    Args:
        job_manager: JobManager instance to share across workers
        num_workers: Number of concurrent worker threads
        
    Returns:
        Tuple of (thread list, stop_event)
    """
    threads = []
    stop_event = threading.Event()
    
    for i in range(num_workers):
        thread = threading.Thread(
            target=solver_worker,
            args=(job_manager, i+1, stop_event),
            name=f"SolverWorker-{i+1}",
            daemon=True
        )
        thread.start()
        threads.append(thread)
        print(f"[MANAGER] Started worker {i+1}/{num_workers}")
    
    return threads, stop_event


def cleanup_worker_pool(threads: List[threading.Thread], stop_event: threading.Event):
    """
    Gracefully terminate worker threads
    
    Args:
        threads: List of Thread objects from start_worker_pool
        stop_event: Event to signal shutdown
    """
    print(f"[MANAGER] Terminating {len(threads)} workers...")
    
    # Signal all workers to stop
    stop_event.set()
    
    # Wait for threads to finish
    for thread in threads:
        thread.join(timeout=5)
        if thread.is_alive():
            print(f"[MANAGER] Worker {thread.name} did not terminate cleanly")
    
    print("[MANAGER] All workers terminated")
