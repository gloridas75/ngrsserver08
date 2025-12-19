"""
Redis-based Async Worker for Background Solver Processing
Uses multiprocessing for true parallel execution with Redis queue
"""
import time
import traceback
import sys
import pathlib
from typing import List
from multiprocessing import Process, Event
import signal
from functools import wraps
import errno
import os

# Setup path for imports
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.redis_job_manager import RedisJobManager, JobStatus
from src.solver import solve_problem


class TimeoutError(Exception):
    """Raised when a function call exceeds its timeout"""
    pass


def timeout_handler(signum, frame):
    """Signal handler for timeout"""
    raise TimeoutError("Function call timed out")


def with_timeout(timeout_seconds):
    """
    Decorator to add timeout to a function using SIGALRM
    
    Args:
        timeout_seconds: Maximum seconds to allow function to run
        
    Raises:
        TimeoutError: If function exceeds timeout
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Set the timeout alarm
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                # Cancel the alarm
                signal.alarm(0)
            return result
        return wrapper
    return decorator


def solver_worker(worker_id: int, stop_event: Event, ttl_seconds: int = 3600):
    """
    Background worker that processes jobs from Redis queue
    
    Runs in separate process and continuously polls Redis queue.
    Each worker is independent and can run on different machines.
    
    Args:
        worker_id: Worker identifier (1, 2, ...)
        stop_event: Multiprocessing event to signal shutdown
        ttl_seconds: Result TTL for job manager
    """
    # Each process needs its own job manager instance
    job_manager = RedisJobManager(result_ttl_seconds=ttl_seconds)
    
    print(f"[WORKER-{worker_id}] Solver worker started (PID: {__import__('os').getpid()})")
    
    # Handle graceful shutdown
    def signal_handler(signum, frame):
        print(f"[WORKER-{worker_id}] Received shutdown signal")
        stop_event.set()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    while not stop_event.is_set():
        try:
            # Get next job from Redis queue (blocking with 1 second timeout)
            job_id = job_manager.get_next_job(timeout=1)
            
            if not job_id:
                # No jobs available, loop will retry
                continue
            
            print(f"[WORKER-{worker_id}] Processing job {job_id}")
            
            # Check if job was cancelled before we started
            if job_manager.check_cancellation_flag(job_id):
                print(f"[WORKER-{worker_id}] Job {job_id} was cancelled before processing")
                job_manager.update_status(job_id, JobStatus.CANCELLED)
                job_manager.clear_cancellation_flag(job_id)
                continue
            
            # Update status to IN_PROGRESS
            job_manager.update_status(job_id, JobStatus.IN_PROGRESS)
            
            # Get job details
            job_info = job_manager.get_job(job_id)
            if not job_info:
                print(f"[WORKER-{worker_id}] Job {job_id} not found, skipping")
                continue
            
            input_data = job_info.input_data
            
            # Extract timeout from input (with safety buffer)
            solver_timeout = 300  # Default 5 minutes
            try:
                if 'solverRunTime' in input_data and 'maxSeconds' in input_data['solverRunTime']:
                    solver_timeout = int(input_data['solverRunTime']['maxSeconds'])
                    # Add 60 second buffer for processing overhead
                    worker_timeout = solver_timeout + 60
                else:
                    worker_timeout = solver_timeout + 60
            except Exception as e:
                print(f"[WORKER-{worker_id}] Could not extract timeout from input, using default: {e}")
                worker_timeout = solver_timeout + 60
            
            print(f"[WORKER-{worker_id}] Job {job_id} timeout: {solver_timeout}s (worker timeout: {worker_timeout}s)")
            
            # Run solver (unified solver handles everything)
            start_time = time.time()
            
            try:
                # ============================================================
                # UNIFIED SOLVER - ALL LOGIC IN src/solver.py
                # ============================================================
                # solve_problem() handles:
                # - Rotation offset staggering
                # - ICPMP v3.0 preprocessing
                # - Input loading
                # - CP-SAT solving
                # - Output building
                #
                # TIMEOUT PROTECTION: Wrap with external timeout
                # ============================================================
                @with_timeout(worker_timeout)
                def solve_with_timeout():
                    return solve_problem(input_data, log_prefix=f"[WORKER-{worker_id}]")
                
                result = solve_with_timeout()
                
                elapsed_time = time.time() - start_time
                
                print(f"[WORKER-{worker_id}] Job {job_id} completed in {elapsed_time:.2f}s")
                
                # Check if job was cancelled during solving
                if job_manager.check_cancellation_flag(job_id):
                    print(f"[WORKER-{worker_id}] Job {job_id} was cancelled during solving - discarding result")
                    job_manager.update_status(job_id, JobStatus.CANCELLED)
                    job_manager.clear_cancellation_flag(job_id)
                    
                    # Send webhook notification for cancelled job
                    try:
                        base_url = __import__('os').getenv('API_BASE_URL')
                        webhook_sent = job_manager.send_webhook_notification(job_id, base_url)
                        if webhook_sent:
                            print(f"[WORKER-{worker_id}] Webhook notification sent for cancelled job {job_id}")
                    except Exception as webhook_error:
                        print(f"[WORKER-{worker_id}] Webhook notification failed for job {job_id}: {webhook_error}")
                    
                    continue
                
                # Store result in Redis
                job_manager.store_result(job_id, result)
                job_manager.update_status(job_id, JobStatus.COMPLETED)
                
                # Send webhook notification if webhook_url provided
                try:
                    # Get base URL from environment or use default
                    base_url = __import__('os').getenv('API_BASE_URL')
                    webhook_sent = job_manager.send_webhook_notification(job_id, base_url)
                    if webhook_sent:
                        print(f"[WORKER-{worker_id}] Webhook notification sent for job {job_id}")
                except Exception as webhook_error:
                    # Don't fail the job if webhook fails
                    print(f"[WORKER-{worker_id}] Webhook notification failed for job {job_id}: {webhook_error}")
                
            except TimeoutError as timeout_error:
                # Handle job timeout - separate from other solver errors
                elapsed_time = time.time() - start_time
                error_msg = f"Job exceeded timeout limit of {worker_timeout}s (elapsed: {elapsed_time:.1f}s). Solver may have hung or problem is too complex."
                
                print(f"[WORKER-{worker_id}] Job {job_id} TIMEOUT: {error_msg}")
                
                job_manager.update_status(
                    job_id,
                    JobStatus.FAILED,
                    error_message=error_msg
                )
                
                # Send webhook notification for timeout
                try:
                    base_url = __import__('os').getenv('API_BASE_URL')
                    webhook_sent = job_manager.send_webhook_notification(job_id, base_url)
                    if webhook_sent:
                        print(f"[WORKER-{worker_id}] Webhook notification sent for timed-out job {job_id}")
                except Exception as webhook_error:
                    print(f"[WORKER-{worker_id}] Webhook notification failed for job {job_id}: {webhook_error}")
                
            except Exception as solve_error:
                # Handle solver-specific errors
                error_msg = f"{type(solve_error).__name__}: {str(solve_error)}"
                error_trace = traceback.format_exc()
                
                print(f"[WORKER-{worker_id}] Job {job_id} solve failed: {error_msg}")
                print(f"[WORKER-{worker_id}] Traceback:\n{error_trace}")
                
                job_manager.update_status(
                    job_id, 
                    JobStatus.FAILED, 
                    error_message=error_msg
                )
                
                # Send webhook notification for failed job
                try:
                    base_url = __import__('os').getenv('API_BASE_URL')
                    webhook_sent = job_manager.send_webhook_notification(job_id, base_url)
                    if webhook_sent:
                        print(f"[WORKER-{worker_id}] Webhook notification sent for failed job {job_id}")
                except Exception as webhook_error:
                    print(f"[WORKER-{worker_id}] Webhook notification failed for job {job_id}: {webhook_error}")
        
        except Exception as e:
            # Handle worker-level errors (e.g., Redis connection issues)
            error_msg = f"{type(e).__name__}: {str(e)}"
            print(f"[WORKER-{worker_id}] Worker error: {error_msg}")
            print(f"[WORKER-{worker_id}] Traceback:\n{traceback.format_exc()}")
            
            # Brief pause before retrying
            time.sleep(2)
    
    print(f"[WORKER-{worker_id}] Worker stopped")


def start_worker_pool(num_workers: int = 2, ttl_seconds: int = 3600) -> tuple[List[Process], Event]:
    """
    Start pool of worker processes
    
    Args:
        num_workers: Number of concurrent worker processes
        ttl_seconds: Result TTL for job managers
        
    Returns:
        Tuple of (process list, stop_event)
    """
    processes = []
    stop_event = Event()
    
    for i in range(num_workers):
        process = Process(
            target=solver_worker,
            args=(i+1, stop_event, ttl_seconds),
            name=f"SolverWorker-{i+1}",
            daemon=False  # Allow graceful shutdown
        )
        process.start()
        processes.append(process)
        print(f"[MANAGER] Started worker {i+1}/{num_workers} (PID: {process.pid})")
    
    return processes, stop_event


def cleanup_worker_pool(processes: List[Process], stop_event: Event, timeout: int = 10):
    """
    Gracefully terminate worker processes
    
    Args:
        processes: List of Process objects from start_worker_pool
        stop_event: Event to signal shutdown
        timeout: Seconds to wait for graceful shutdown
    """
    print(f"[MANAGER] Terminating {len(processes)} workers...")
    
    # Signal all workers to stop
    stop_event.set()
    
    # Wait for processes to finish current jobs
    start_time = time.time()
    for process in processes:
        remaining_time = max(0, timeout - (time.time() - start_time))
        process.join(timeout=remaining_time)
        
        if process.is_alive():
            print(f"[MANAGER] Force terminating worker {process.name}")
            process.terminate()
            process.join(timeout=2)
            
            if process.is_alive():
                print(f"[MANAGER] Force killing worker {process.name}")
                process.kill()
                process.join()
    
    print("[MANAGER] All workers terminated")
