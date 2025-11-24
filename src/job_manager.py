"""
Job Manager for Asynchronous Solver
Handles job queue, status tracking, and result storage
"""
import uuid
import time
from typing import Dict, Optional, Any
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import threading


class JobStatus(Enum):
    """Job execution states"""
    QUEUED = "queued"
    VALIDATING = "validating"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class JobInfo:
    """Job metadata and tracking information"""
    job_id: str
    status: JobStatus
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    result_size_bytes: Optional[int] = None


class JobManager:
    """
    Manages asynchronous solver jobs with in-memory storage
    
    Features:
    - Job queue management
    - Status tracking
    - Result caching with TTL
    - Thread-safe operations
    """
    
    def __init__(self, max_queue_size: int = 10, result_ttl_seconds: int = 3600):
        """
        Initialize job manager
        
        Args:
            max_queue_size: Maximum jobs in queue (prevents memory overflow)
            result_ttl_seconds: Time to keep results before expiration (default: 1 hour)
        """
        self.max_queue_size = max_queue_size
        self.result_ttl_seconds = result_ttl_seconds
        
        # Job storage
        self.jobs: Dict[str, JobInfo] = {}
        self.results: Dict[str, Dict[str, Any]] = {}
        
        # Queue for processing
        self.queue: list[str] = []
        
        # Thread safety
        self.lock = threading.Lock()
    
    def create_job(self, input_data: Dict[str, Any]) -> str:
        """
        Create new job and add to queue
        
        Args:
            input_data: Solver input JSON
            
        Returns:
            job_id: UUID for tracking
            
        Raises:
            ValueError: If queue is full
        """
        with self.lock:
            if len(self.queue) >= self.max_queue_size:
                raise ValueError(f"Queue full: {len(self.queue)}/{self.max_queue_size} jobs")
            
            job_id = str(uuid.uuid4())
            job_info = JobInfo(
                job_id=job_id,
                status=JobStatus.QUEUED,
                created_at=time.time(),
                input_data=input_data
            )
            
            self.jobs[job_id] = job_info
            self.queue.append(job_id)
            
            return job_id
    
    def get_job(self, job_id: str) -> Optional[JobInfo]:
        """
        Retrieve job information
        
        Args:
            job_id: Job UUID
            
        Returns:
            JobInfo or None if not found
        """
        with self.lock:
            return self.jobs.get(job_id)
    
    def get_next_job(self) -> Optional[str]:
        """
        Get next job from queue
        
        Returns:
            job_id or None if queue empty
        """
        with self.lock:
            if not self.queue:
                return None
            return self.queue.pop(0)
    
    def update_status(self, job_id: str, status: JobStatus, 
                     error_message: Optional[str] = None) -> bool:
        """
        Update job status
        
        Args:
            job_id: Job UUID
            status: New status
            error_message: Optional error message for FAILED status
            
        Returns:
            True if updated, False if job not found
        """
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return False
            
            job.status = status
            
            if status == JobStatus.IN_PROGRESS and not job.started_at:
                job.started_at = time.time()
            elif status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                job.completed_at = time.time()
            
            if error_message:
                job.error_message = error_message
            
            return True
    
    def store_result(self, job_id: str, result: Dict[str, Any]) -> bool:
        """
        Store job result
        
        Args:
            job_id: Job UUID
            result: Solver output JSON
            
        Returns:
            True if stored, False if job not found
        """
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return False
            
            self.results[job_id] = result
            
            # Calculate result size for monitoring
            import json
            job.result_size_bytes = len(json.dumps(result).encode('utf-8'))
            
            return True
    
    def get_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve job result
        
        Args:
            job_id: Job UUID
            
        Returns:
            Result JSON or None if not found
        """
        with self.lock:
            return self.results.get(job_id)
    
    def cleanup_expired_jobs(self):
        """
        Remove expired job results to free memory
        Should be called periodically (e.g., every 5 minutes)
        """
        current_time = time.time()
        expired_jobs = []
        
        with self.lock:
            for job_id, job in self.jobs.items():
                if job.completed_at and (current_time - job.completed_at) > self.result_ttl_seconds:
                    expired_jobs.append(job_id)
            
            for job_id in expired_jobs:
                # Mark as expired and remove result
                if job_id in self.jobs:
                    self.jobs[job_id].status = JobStatus.EXPIRED
                if job_id in self.results:
                    del self.results[job_id]
        
        return len(expired_jobs)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get current queue and job statistics
        
        Returns:
            Statistics dictionary
        """
        with self.lock:
            status_counts = {}
            for job in self.jobs.values():
                status_name = job.status.value
                status_counts[status_name] = status_counts.get(status_name, 0) + 1
            
            return {
                "total_jobs": len(self.jobs),
                "queue_length": len(self.queue),
                "queue_capacity": self.max_queue_size,
                "results_cached": len(self.results),
                "status_breakdown": status_counts,
                "ttl_seconds": self.result_ttl_seconds
            }
    
    def delete_job(self, job_id: str) -> bool:
        """
        Delete job and its result (for cancellation)
        
        Args:
            job_id: Job UUID
            
        Returns:
            True if deleted, False if not found
        """
        with self.lock:
            deleted = False
            
            # Remove from queue if present
            if job_id in self.queue:
                self.queue.remove(job_id)
                deleted = True
            
            # Remove job info
            if job_id in self.jobs:
                del self.jobs[job_id]
                deleted = True
            
            # Remove result
            if job_id in self.results:
                del self.results[job_id]
                deleted = True
            
            return deleted
