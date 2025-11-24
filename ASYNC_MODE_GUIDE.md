# Asynchronous Solver Mode - Quick Reference

## Overview

The NGRS Solver now supports asynchronous job processing, allowing you to submit large scheduling problems without blocking and track their progress via UUID.

## Architecture

- **Job Manager**: In-memory queue and result storage
- **Worker Pool**: 2 threads processing jobs concurrently (configurable via env var)
- **Result TTL**: 1 hour by default (configurable)
- **Queue Capacity**: 10 jobs max (configurable)

## API Endpoints

### 1. Submit Job (POST /solve/async)

Submit a solver job for asynchronous processing.

**Request:**
```bash
curl -X POST http://localhost:8080/solve/async \
  -H "Content-Type: application/json" \
  -d '{
    "input_json": {...},
    "priority": 0,
    "ttl_seconds": 3600
  }'
```

**Response:**
```json
{
  "job_id": "fab9b8c7-315e-43dd-ac53-533a58ba2435",
  "status": "queued",
  "created_at": "2025-11-24T12:30:00",
  "message": "Job submitted successfully"
}
```

### 2. Check Status (GET /solve/async/{job_id})

Get current status of a submitted job.

**Request:**
```bash
curl http://localhost:8080/solve/async/fab9b8c7-315e-43dd-ac53-533a58ba2435
```

**Response:**
```json
{
  "job_id": "fab9b8c7-315e-43dd-ac53-533a58ba2435",
  "status": "completed",
  "created_at": "2025-11-24T12:30:00",
  "started_at": "2025-11-24T12:30:05",
  "completed_at": "2025-11-24T12:30:10",
  "result_available": true,
  "result_size_bytes": 125000
}
```

**Job States:**
- `queued`: Waiting in queue
- `in_progress`: Solver running
- `completed`: Solution ready for download
- `failed`: Error occurred (check `error_message`)
- `expired`: Result expired (exceeded TTL)

### 3. Download Result (GET /solve/async/{job_id}/result)

Download the complete solver output JSON.

**Request:**
```bash
curl http://localhost:8080/solve/async/fab9b8c7-315e-43dd-ac53-533a58ba2435/result \
  -o output.json
```

**Response:**
Same format as synchronous `/solve` endpoint - full NGRS output JSON.

### 4. Cancel/Delete Job (DELETE /solve/async/{job_id})

Remove job from queue or delete result.

**Request:**
```bash
curl -X DELETE http://localhost:8080/solve/async/fab9b8c7-315e-43dd-ac53-533a58ba2435
```

**Response:**
```json
{
  "message": "Job fab9b8c7-315e-43dd-ac53-533a58ba2435 cancelled/deleted",
  "job_id": "fab9b8c7-315e-43dd-ac53-533a58ba2435"
}
```

### 5. Get Statistics (GET /solve/async/stats)

Monitor queue and worker status.

**Request:**
```bash
curl http://localhost:8080/solve/async/stats
```

**Response:**
```json
{
  "total_jobs": 15,
  "queue_length": 3,
  "queue_capacity": 10,
  "results_cached": 8,
  "status_breakdown": {
    "queued": 3,
    "in_progress": 2,
    "completed": 8,
    "failed": 2
  },
  "ttl_seconds": 3600,
  "workers": 2
}
```

## Environment Variables

Configure async mode via environment variables:

```bash
# Number of concurrent worker threads (default: 2)
export SOLVER_WORKERS=4

# Maximum jobs in queue (default: 10)
export MAX_QUEUE_SIZE=20

# Result time-to-live in seconds (default: 3600 = 1 hour)
export RESULT_TTL_SECONDS=7200

# Start API server
uvicorn src.api_server:app --host 0.0.0.0 --port 8080
```

## Usage Patterns

### Pattern 1: Submit and Poll

```python
import requests
import time

# Submit job
response = requests.post('http://localhost:8080/solve/async', json={
    'input_json': {...}
})
job_id = response.json()['job_id']

# Poll until complete
while True:
    status = requests.get(f'http://localhost:8080/solve/async/{job_id}').json()
    
    if status['status'] == 'completed':
        # Download result
        result = requests.get(f'http://localhost:8080/solve/async/{job_id}/result').json()
        break
    
    elif status['status'] == 'failed':
        print(f"Error: {status['error_message']}")
        break
    
    time.sleep(2)  # Poll every 2 seconds
```

### Pattern 2: Batch Submission

```python
# Submit multiple jobs
job_ids = []
for input_data in input_files:
    response = requests.post('http://localhost:8080/solve/async', json={
        'input_json': input_data
    })
    job_ids.append(response.json()['job_id'])

# Wait for all to complete
for job_id in job_ids:
    while True:
        status = requests.get(f'http://localhost:8080/solve/async/{job_id}').json()
        if status['status'] in ['completed', 'failed']:
            break
        time.sleep(1)
```

## When to Use Async vs Sync

**Use Synchronous Mode (POST /solve):**
- Small problems (< 50 employees, < 30 days)
- Quick results needed (< 15 seconds)
- Single solve operation
- Immediate feedback required

**Use Asynchronous Mode (POST /solve/async):**
- Large problems (100+ employees, 60+ days)
- Long-running solves (> 30 seconds)
- Batch processing multiple solves
- Background processing needed
- Want to queue multiple jobs

## Testing Locally

Test async mode without API server:

```bash
python test_async_mode.py
```

This will:
1. Start 2 worker threads
2. Submit 3 jobs
3. Monitor progress
4. Display results
5. Clean up workers

## Performance Notes

- **Threading vs Multiprocessing**: Currently uses threading for simplicity. For CPU-intensive large jobs, consider switching to multiprocessing in production.
- **Worker Count**: Start with 2 workers. Increase based on CPU cores available (recommended: 1 worker per 2 cores).
- **Queue Size**: Limits memory usage. Monitor with `/solve/async/stats`.
- **Result TTL**: Balance between availability and memory usage.

## Error Handling

**HTTP Status Codes:**
- `201`: Job created successfully
- `400`: Invalid input
- `404`: Job not found
- `410`: Result expired or job failed
- `425`: Job not completed yet (too early to get result)
- `503`: Queue full

## Migration from Sync to Async

Replace:
```python
# Synchronous (old)
result = requests.post('http://localhost:8080/solve', json=input_data).json()
```

With:
```python
# Asynchronous (new)
response = requests.post('http://localhost:8080/solve/async', json={'input_json': input_data})
job_id = response.json()['job_id']

# Poll for completion
while True:
    status = requests.get(f'http://localhost:8080/solve/async/{job_id}').json()
    if status['status'] == 'completed':
        result = requests.get(f'http://localhost:8080/solve/async/{job_id}/result').json()
        break
    time.sleep(2)
```

## Monitoring & Troubleshooting

**Check queue status:**
```bash
curl http://localhost:8080/solve/async/stats | jq
```

**Check specific job:**
```bash
curl http://localhost:8080/solve/async/{job_id} | jq
```

**View API logs:**
```bash
# Worker activity logged with [WORKER-1], [WORKER-2] prefixes
# Job lifecycle: queued → in_progress → completed/failed
```

## Future Enhancements

Phase 2+ improvements planned:
- Multiprocessing worker pool for better CPU utilization
- Job priority queue
- Persistent storage (Redis/Database)
- Job cancellation mid-execution
- Webhook notifications on completion
- Result pagination for large outputs
- Worker auto-scaling based on queue depth
