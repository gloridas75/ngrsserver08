"""
Redis-based Job Manager for Asynchronous Solver
Replaces in-memory JobManager with persistent Redis storage
"""
import uuid
import time
import json
from typing import Dict, Optional, Any
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime
import logging

from src.redis_manager import get_redis_client

logger = logging.getLogger(__name__)


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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict, filtering None values for Redis"""
        data = asdict(self)
        data['status'] = self.status.value
        # Serialize input_data as JSON string for Redis HASH
        if 'input_data' in data and isinstance(data['input_data'], dict):
            data['input_data'] = json.dumps(data['input_data'])
        # Redis doesn't accept None values - convert to empty string
        return {k: (v if v is not None else '') for k, v in data.items()}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobInfo':
        """Create JobInfo from dict, handling empty strings as None"""
        data = data.copy()
        data['status'] = JobStatus(data['status'])
        # Convert empty strings back to None
        for key in ['started_at', 'completed_at', 'error_message', 'result_size_bytes']:
            if key in data and data[key] == '':
                data[key] = None
            elif key in data and key in ['started_at', 'completed_at', 'result_size_bytes']:
                # Convert string numbers back to float/int
                if data[key] and data[key] != '':
                    if key == 'result_size_bytes':
                        data[key] = int(float(data[key]))
                    else:
                        data[key] = float(data[key])
        # Handle input_data which might be stored as JSON string
        if 'input_data' in data and isinstance(data['input_data'], str):
            data['input_data'] = json.loads(data['input_data']) if data['input_data'] else {}
        return cls(**data)


class RedisJobManager:
    """
    Redis-based job manager for distributed async processing
    
    Features:
    - Persistent job queue using Redis LIST
    - Job metadata storage using Redis HASH
    - Result caching with TTL using Redis STRING
    - Distributed: Multiple workers can share same Redis
    - Survives restarts: Jobs persist in Redis
    
    Redis Keys:
    - ngrs:job:queue          : LIST - Job queue (LPUSH/BRPOP)
    - ngrs:job:{uuid}         : HASH - Job metadata
    - ngrs:result:{uuid}      : STRING - Job result (JSON)
    - ngrs:stats:total_jobs   : STRING - Counter
    """
    
    def __init__(self, result_ttl_seconds: int = 3600, key_prefix: str = "ngrs"):
        """
        Initialize Redis job manager
        
        Args:
            result_ttl_seconds: Time to keep results before expiration (default: 1 hour)
            key_prefix: Redis key prefix (default: "ngrs")
        """
        self.redis = get_redis_client()
        self.result_ttl_seconds = result_ttl_seconds
        self.key_prefix = key_prefix
        
        # Redis keys
        self.queue_key = f"{key_prefix}:job:queue"
        
        logger.info(f"RedisJobManager initialized (TTL: {result_ttl_seconds}s)")
    
    def _job_key(self, job_id: str) -> str:
        """Generate Redis key for job metadata"""
        return f"{self.key_prefix}:job:{job_id}"
    
    def _result_key(self, job_id: str) -> str:
        """Generate Redis key for job result"""
        return f"{self.key_prefix}:result:{job_id}"
    
    def create_job(self, input_data: Dict[str, Any]) -> str:
        """
        Create new job and add to queue
        
        Args:
            input_data: Solver input JSON
            
        Returns:
            job_id: UUID for tracking
        """
        job_id = str(uuid.uuid4())
        job_info = JobInfo(
            job_id=job_id,
            status=JobStatus.QUEUED,
            created_at=time.time(),
            input_data=input_data
        )
        
        # Store job metadata
        job_key = self._job_key(job_id)
        self.redis.hset(job_key, mapping=job_info.to_dict())
        
        # Add to queue (LPUSH for FIFO with BRPOP)
        self.redis.lpush(self.queue_key, job_id)
        
        # Increment total jobs counter
        self.redis.incr(f"{self.key_prefix}:stats:total_jobs")
        
        logger.info(f"Job created: {job_id}")
        return job_id
    
    def get_job(self, job_id: str) -> Optional[JobInfo]:
        """
        Retrieve job information
        
        Args:
            job_id: Job UUID
            
        Returns:
            JobInfo or None if not found
        """
        job_key = self._job_key(job_id)
        job_data = self.redis.hgetall(job_key)
        
        if not job_data:
            return None
        
        # Convert Redis hash to JobInfo
        # Handle nested input_data JSON
        if 'input_data' in job_data and isinstance(job_data['input_data'], str):
            job_data['input_data'] = json.loads(job_data['input_data'])
        
        # Convert numeric strings back to numbers
        for field in ['created_at', 'started_at', 'completed_at', 'result_size_bytes']:
            if field in job_data and job_data[field]:
                if field == 'result_size_bytes':
                    job_data[field] = int(job_data[field]) if job_data[field] != 'None' else None
                else:
                    job_data[field] = float(job_data[field]) if job_data[field] != 'None' else None
        
        return JobInfo.from_dict(job_data)
    
    def get_next_job(self, timeout: int = 0) -> Optional[str]:
        """
        Get next job from queue (blocking or non-blocking)
        
        Args:
            timeout: Seconds to wait for job (0 = non-blocking, None = block forever)
            
        Returns:
            job_id or None if queue empty
        """
        if timeout == 0:
            # Non-blocking pop
            job_id = self.redis.rpop(self.queue_key)
        else:
            # Blocking pop with timeout
            result = self.redis.brpop(self.queue_key, timeout=timeout)
            job_id = result[1] if result else None
        
        return job_id
    
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
        job_key = self._job_key(job_id)
        
        if not self.redis.exists(job_key):
            return False
        
        # Update status
        self.redis.hset(job_key, 'status', status.value)
        
        # Update timestamps
        current_time = time.time()
        if status == JobStatus.IN_PROGRESS:
            self.redis.hset(job_key, 'started_at', current_time)
        elif status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            self.redis.hset(job_key, 'completed_at', current_time)
        
        # Update error message
        if error_message:
            self.redis.hset(job_key, 'error_message', error_message)
        
        logger.info(f"Job {job_id}: {status.value}")
        return True
    
    def store_result(self, job_id: str, result: Dict[str, Any]) -> bool:
        """
        Store job result with TTL
        
        Args:
            job_id: Job UUID
            result: Solver output JSON
            
        Returns:
            True if stored, False if job not found
        """
        job_key = self._job_key(job_id)
        
        if not self.redis.exists(job_key):
            return False
        
        # Store result as JSON with TTL
        result_key = self._result_key(job_id)
        result_json = json.dumps(result)
        self.redis.setex(result_key, self.result_ttl_seconds, result_json)
        
        # Update result size in job metadata
        result_size = len(result_json.encode('utf-8'))
        self.redis.hset(job_key, 'result_size_bytes', result_size)
        
        logger.info(f"Result stored for {job_id}: {result_size} bytes")
        return True
    
    def get_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve job result
        
        Args:
            job_id: Job UUID
            
        Returns:
            Result JSON or None if not found/expired
        """
        result_key = self._result_key(job_id)
        result_json = self.redis.get(result_key)
        
        if not result_json:
            return None
        
        return json.loads(result_json)
    
    def delete_job(self, job_id: str) -> bool:
        """
        Delete job and its result
        
        Args:
            job_id: Job UUID
            
        Returns:
            True if deleted, False if not found
        """
        job_key = self._job_key(job_id)
        result_key = self._result_key(job_id)
        
        # Delete from Redis
        deleted_count = 0
        deleted_count += self.redis.delete(job_key)
        deleted_count += self.redis.delete(result_key)
        
        # Try to remove from queue (if still queued)
        self.redis.lrem(self.queue_key, 0, job_id)
        
        logger.info(f"Job {job_id} deleted ({deleted_count} keys)")
        return deleted_count > 0
    
    def cleanup_expired_jobs(self) -> int:
        """
        Remove expired job metadata
        Results auto-expire via Redis TTL
        
        Returns:
            Number of jobs cleaned up
        """
        current_time = time.time()
        expired_count = 0
        
        # Scan for all job keys
        cursor = 0
        pattern = f"{self.key_prefix}:job:*"
        
        while True:
            cursor, keys = self.redis.scan(cursor, match=pattern, count=100)
            
            for key in keys:
                if key == self.queue_key:  # Skip queue key
                    continue
                
                job_data = self.redis.hgetall(key)
                
                # Check if completed and past TTL
                if job_data.get('status') in ['completed', 'failed']:
                    completed_at = float(job_data.get('completed_at', 0))
                    if completed_at and (current_time - completed_at) > self.result_ttl_seconds:
                        # Mark as expired
                        self.redis.hset(key, 'status', JobStatus.EXPIRED.value)
                        expired_count += 1
            
            if cursor == 0:
                break
        
        if expired_count > 0:
            logger.info(f"Marked {expired_count} jobs as expired")
        
        return expired_count
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get current queue and job statistics
        
        Returns:
            Statistics dictionary
        """
        # Queue length
        queue_length = self.redis.llen(self.queue_key)
        
        # Total jobs created
        total_jobs = int(self.redis.get(f"{self.key_prefix}:stats:total_jobs") or 0)
        
        # Count jobs by status (scan all job keys)
        status_counts = {}
        results_cached = 0
        
        cursor = 0
        pattern = f"{self.key_prefix}:job:*"
        job_count = 0
        
        while True:
            cursor, keys = self.redis.scan(cursor, match=pattern, count=100)
            
            for key in keys:
                if key == self.queue_key:
                    continue
                
                job_count += 1
                status = self.redis.hget(key, 'status')
                if status:
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                # Check if result exists
                job_id = key.split(':')[-1]
                if self.redis.exists(self._result_key(job_id)):
                    results_cached += 1
            
            if cursor == 0:
                break
        
        return {
            "total_jobs": total_jobs,
            "active_jobs": job_count,
            "queue_length": queue_length,
            "results_cached": results_cached,
            "status_breakdown": status_counts,
            "ttl_seconds": self.result_ttl_seconds,
            "redis_connected": self.redis.ping()
        }
    
    def get_queue_length(self) -> int:
        """Get current queue length"""
        return self.redis.llen(self.queue_key)
