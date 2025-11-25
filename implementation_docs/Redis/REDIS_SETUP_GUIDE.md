# Redis Async Mode - Setup & Testing Guide

## Overview

The NGRS Solver now uses **Redis** for distributed async job processing, providing:
- ✅ **True parallelism** with multiprocessing workers
- ✅ **Job persistence** across API restarts
- ✅ **Distributed workers** can run on different machines
- ✅ **Production-grade** queue management
- ✅ **No queue size limits** (bounded only by Redis memory)

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Client    │────▶│  API Server  │────▶│    Redis    │
│             │◀────│  (FastAPI)   │◀────│   (Queue)   │
└─────────────┘     └──────────────┘     └─────────────┘
                           │                      ▲
                           │                      │
                           ▼                      │
                    ┌──────────────┐              │
                    │   Worker 1   │──────────────┘
                    │  (Process)   │
                    └──────────────┘
                    ┌──────────────┐
                    │   Worker 2   │──────────────┘
                    │  (Process)   │
                    └──────────────┘
```

**Data Flow:**
1. Client → POST `/solve/async` → API stores job in Redis
2. Worker pulls job from Redis queue
3. Worker runs solver, stores result in Redis
4. Client → GET `/solve/async/{uuid}/result` → API returns from Redis

## Prerequisites

### Option 1: Install Redis Locally (Recommended for Development)

**macOS:**
```bash
# Install Redis via Homebrew
brew install redis

# Start Redis server
brew services start redis

# Verify Redis is running
redis-cli ping
# Should return: PONG
```

**Ubuntu/Debian:**
```bash
# Install Redis
sudo apt update
sudo apt install redis-server

# Start Redis
sudo systemctl start redis

# Enable auto-start on boot
sudo systemctl enable redis

# Verify
redis-cli ping
```

**Windows:**
```powershell
# Install via Chocolatey
choco install redis-64

# Or use WSL2 and follow Ubuntu instructions
```

### Option 2: Run Redis via Docker (Quick Start)

```bash
# Start Redis container
docker run -d \
  --name ngrs-redis \
  -p 6379:6379 \
  redis:7-alpine

# Verify
docker exec ngrs-redis redis-cli ping

# View logs
docker logs ngrs-redis

# Stop Redis
docker stop ngrs-redis

# Start existing container
docker start ngrs-redis
```

### Option 3: Redis Cloud (Production)

For production deployments, consider:
- **Redis Cloud**: https://redis.com/redis-enterprise-cloud/
- **AWS ElastiCache**: Managed Redis on AWS
- **Azure Cache for Redis**: Managed Redis on Azure

## Configuration

Set environment variables to configure Redis connection:

```bash
# Redis connection
export REDIS_HOST=localhost          # Redis server host
export REDIS_PORT=6379               # Redis server port
export REDIS_DB=0                    # Redis database number (0-15)
export REDIS_PASSWORD=               # Redis password (if auth enabled)

# Connection pool
export REDIS_MAX_CONNECTIONS=10      # Max connections in pool
export REDIS_SOCKET_TIMEOUT=5.0      # Socket timeout (seconds)
export REDIS_CONNECT_TIMEOUT=5.0     # Connection timeout (seconds)

# Worker configuration
export SOLVER_WORKERS=2              # Number of worker processes
export RESULT_TTL_SECONDS=3600       # Result retention time (1 hour)
export REDIS_KEY_PREFIX=ngrs         # Redis key namespace
```

## Testing

### Step 1: Start Redis

```bash
# If using brew
brew services start redis

# If using Docker
docker run -d -p 6379:6379 --name ngrs-redis redis:7-alpine

# Verify
redis-cli ping
```

### Step 2: Run Test Script

```bash
cd /path/to/ngrssolver
python test_scripts/Redis/test_redis_async.py
```

**Expected Output:**
```
============================================================
REDIS ASYNC MODE TEST
============================================================

✓ Testing Redis connection...
✓ Clearing test data...
✓ Redis connected (TTL: 300s)

✓ Loaded test input: input/async_test_small.json
  Planning: {'startDate': '2025-12-01', 'endDate': '2025-12-05'}
  Employees: 2

✓ Starting 2 Redis workers (multiprocessing)...
[MANAGER] Started worker 1/2 (PID: 12345)
[MANAGER] Started worker 2/2 (PID: 12346)

✓ Submitting 3 jobs to Redis queue...
  Job 1: abc123...
  Job 2: def456...
  Job 3: ghi789...

✓ Monitoring jobs...
  Status: completed, completed, completed

✓ Checking results...
  Job 1: completed → OPTIMAL, 5 assignments
  Job 2: completed → OPTIMAL, 5 assignments
  Job 3: completed → OPTIMAL, 5 assignments

✓ Final stats:
  Total jobs created: 3
  Active jobs: 3
  Queue length: 0
  Results cached: 3
  Redis connected: True

✓ Testing job persistence...
  Created job xyz789...
  Simulating API restart (workers stop)...
  ✓ Job xyz789... persisted in Redis (status: queued)

============================================================
✅ ALL TESTS PASSED
============================================================
```

### Step 3: Start API Server

```bash
# Set environment variables (optional)
export SOLVER_WORKERS=4
export RESULT_TTL_SECONDS=7200

# Start server
python -m uvicorn src.api_server:app --host 0.0.0.0 --port 8080

# Or with auto-reload for development
uvicorn src.api_server:app --reload --port 8080
```

**Server Logs:**
```
INFO:     Started worker 1/4 (PID: 12345)
INFO:     Started worker 2/4 (PID: 12346)
INFO:     Started worker 3/4 (PID: 12347)
INFO:     Started worker 4/4 (PID: 12348)
INFO:     Async mode enabled with 4 workers (Redis-backed)
```

### Step 4: Submit Test Job

```bash
# Submit job
curl -X POST http://localhost:8080/solve/async \
  -H "Content-Type: application/json" \
  -d @input/input_v0.7.json | jq

# Response:
{
  "job_id": "fab9b8c7-315e-43dd-ac53-533a58ba2435",
  "status": "queued",
  "created_at": "2025-11-24T12:30:00",
  "message": "Job submitted successfully"
}

# Check status
curl http://localhost:8080/solve/async/fab9b8c7-315e-43dd-ac53-533a58ba2435 | jq

# Get result
curl http://localhost:8080/solve/async/fab9b8c7-315e-43dd-ac53-533a58ba2435/result \
  -o output.json
```

## Redis Key Structure

```
ngrs:job:queue                    # LIST: Job queue (FIFO)
ngrs:job:{uuid}                   # HASH: Job metadata
  - job_id
  - status
  - created_at
  - started_at
  - completed_at
  - input_data (JSON)
  - error_message
  - result_size_bytes

ngrs:result:{uuid}                # STRING: Job result (JSON, with TTL)
ngrs:stats:total_jobs             # STRING: Lifetime job counter
```

## Monitoring Redis

### CLI Tools

```bash
# Monitor real-time commands
redis-cli monitor

# Check queue length
redis-cli LLEN ngrs:job:queue

# List all job keys
redis-cli KEYS "ngrs:job:*"

# Get job info
redis-cli HGETALL ngrs:job:{uuid}

# Check result TTL
redis-cli TTL ngrs:result:{uuid}

# Get stats
redis-cli GET ngrs:stats:total_jobs

# Memory usage
redis-cli INFO memory
```

### Redis Insight (GUI)

Download: https://redis.com/redis-enterprise/redis-insight/

## Performance Tuning

### Worker Count

```bash
# Rule of thumb: 1 worker per 2 CPU cores
export SOLVER_WORKERS=$(python -c "import os; print(os.cpu_count() // 2)")

# For CPU-intensive solves on 8-core machine:
export SOLVER_WORKERS=4
```

### Result TTL

```bash
# Short-lived results (5 minutes)
export RESULT_TTL_SECONDS=300

# Standard (1 hour)
export RESULT_TTL_SECONDS=3600

# Long-lived (24 hours)
export RESULT_TTL_SECONDS=86400
```

### Redis Memory Limits

```bash
# Edit redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru  # Evict least recently used keys
```

## Troubleshooting

### Issue: "Redis connection failed"

**Solution:**
```bash
# Check if Redis is running
redis-cli ping

# Start Redis
brew services start redis  # macOS
sudo systemctl start redis  # Linux

# Check Redis logs
tail -f /usr/local/var/log/redis.log  # macOS
journalctl -u redis -f  # Linux
```

### Issue: "Connection refused"

**Solution:**
```bash
# Check Redis is listening on correct port
redis-cli -p 6379 ping

# Check firewall rules
sudo ufw allow 6379  # Linux

# For remote Redis, set REDIS_HOST
export REDIS_HOST=redis.example.com
```

### Issue: "Workers not processing jobs"

**Solution:**
```bash
# Check worker processes are running
ps aux | grep solver_worker

# Check Redis queue
redis-cli LLEN ngrs:job:queue

# View API logs for worker output
# Workers log with [WORKER-1], [WORKER-2] prefixes

# Restart API server to restart workers
```

### Issue: "Out of memory"

**Solution:**
```bash
# Check Redis memory usage
redis-cli INFO memory

# Clean up expired jobs manually
redis-cli KEYS "ngrs:job:*" | xargs redis-cli DEL

# Reduce result TTL
export RESULT_TTL_SECONDS=300

# Increase Redis maxmemory limit
```

## Production Deployment

### Docker Compose

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes
    
  solver-api:
    build: .
    ports:
      - "8080:8080"
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - SOLVER_WORKERS=4
      - RESULT_TTL_SECONDS=3600
    depends_on:
      - redis
    command: uvicorn src.api_server:app --host 0.0.0.0 --port 8080

volumes:
  redis-data:
```

### Multiple Workers on Different Machines

```bash
# Machine 1: API Server + 2 workers
export REDIS_HOST=redis.example.com
export SOLVER_WORKERS=2
uvicorn src.api_server:app --host 0.0.0.0 --port 8080

# Machine 2: 4 standalone workers (no API)
export REDIS_HOST=redis.example.com
python -c "
from src.redis_worker import start_worker_pool
import time
import signal

workers, stop = start_worker_pool(num_workers=4)
signal.pause()  # Run forever
"
```

## Advantages Over In-Memory Queue

| Feature | In-Memory (Phase 1) | Redis (Phase 2) |
|---------|-------------------|-----------------|
| **Persistence** | ❌ Lost on restart | ✅ Survives restarts |
| **Distributed** | ❌ Single machine | ✅ Multi-machine |
| **Parallelism** | ⚠️ Threading (GIL) | ✅ Multiprocessing |
| **Queue Size** | ⚠️ Limited (10 jobs) | ✅ Unbounded |
| **Production Ready** | ⚠️ Development only | ✅ Production-grade |
| **Monitoring** | ⚠️ Limited stats | ✅ Redis CLI/Insight |
| **Scalability** | ⚠️ Vertical only | ✅ Horizontal |

## Migration from Phase 1

1. Install Redis (see Prerequisites)
2. Start Redis server
3. Update `requirements.txt` (already done)
4. Code changes already implemented:
   - `src/redis_manager.py` - Redis connection
   - `src/redis_job_manager.py` - Redis-based queue
   - `src/redis_worker.py` - Multiprocessing workers
   - `src/api_server.py` - Updated imports
5. Test with `test_scripts/Redis/test_redis_async.py`
6. Deploy!

No changes needed to API endpoints - same REST API interface.
