# Admin Reset Endpoint

## Overview

The `/admin/reset` endpoint provides a secure way to completely reset the NGRS Solver system, including:
- Flushing all Redis data (jobs, results, queue)
- Restarting worker processes
- Resetting all counters and stats

## Security

### API Key Authentication

The endpoint requires an API key passed via the `x-api-key` header. 

**Set the API key via environment variable:**
```bash
export ADMIN_API_KEY="your-super-secret-key-here"
```

**⚠️ Security Best Practices:**
- Generate a strong, random API key (32+ characters)
- Never commit the key to version control
- Rotate the key regularly
- Use different keys for staging/production
- Keep the key secret - only share with authorized administrators

## Usage

### Using the Helper Script (Recommended)

```bash
# Set API key
export ADMIN_API_KEY="your-secret-key"

# Run reset
./admin_reset.sh
```

The script will:
1. Prompt for confirmation (type "yes")
2. Send the reset request
3. Display detailed results

### Using cURL Directly

```bash
curl -X POST https://ngrssolver08.comcentricapps.com/admin/reset \
  -H "x-api-key: your-secret-key" \
  -H "Content-Type: application/json"
```

### Using Python

```python
import requests

response = requests.post(
    "https://ngrssolver08.comcentricapps.com/admin/reset",
    headers={"x-api-key": "your-secret-key"}
)

print(response.json())
```

## Response Format

### Success (200)

```json
{
  "status": "success",
  "message": "System reset completed",
  "timestamp": "2025-11-24T10:30:00Z",
  "actions": [
    "Redis database flushed (all jobs and results deleted)",
    "Worker pool restarted (6 workers)",
    "System ready for new jobs"
  ],
  "workers_restarted": true,
  "current_stats": {
    "total_jobs": 0,
    "active_jobs": 0,
    "queue_length": 0,
    "results_cached": 0,
    "workers": 6,
    "redis_connected": true,
    "status_breakdown": {}
  }
}
```

### Unauthorized (401)

```json
{
  "detail": "Invalid API key"
}
```

### Error (500)

```json
{
  "detail": "Reset failed: <error message>"
}
```

## When to Use

### ✅ Appropriate Use Cases

- **System Recovery**: After critical errors or Redis corruption
- **Testing**: Clean slate before running test suites
- **Maintenance**: During scheduled maintenance windows
- **Memory Issues**: When Redis memory usage is too high
- **Stuck Workers**: When workers are deadlocked or unresponsive

### ❌ Do NOT Use When

- Jobs are actively processing important work
- During business hours (unless emergency)
- As routine operation (use TTL cleanup instead)
- When unsure about system state

## Impact

### What Gets Deleted

- ✅ All job metadata (queued, in_progress, completed, failed)
- ✅ All cached results
- ✅ Queue entries
- ✅ All Redis keys under `ngrs:*` namespace

### What Gets Restarted

- ✅ Worker processes (if managed by API server)
- ✅ Worker connections to Redis
- ✅ Job processing queue

### What Is NOT Affected

- ❌ Redis configuration
- ❌ Server configuration
- ❌ File system (input/output files remain)
- ❌ Logs
- ❌ Deployment settings

## Deployment Configuration

### Environment Variables

Add to your deployment configuration (systemd, AWS App Runner, etc.):

```bash
# Production
ADMIN_API_KEY="prod-secret-key-xyz123abc456"

# Staging
ADMIN_API_KEY="staging-secret-key-def789ghi012"
```

### Systemd Example

```bash
# Edit service file
sudo nano /etc/systemd/system/ngrs-solver.service

# Add to [Service] section
Environment="ADMIN_API_KEY=your-secret-key"

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart ngrs-solver
```

### AWS App Runner

1. Go to App Runner console
2. Select your service
3. Configuration → Environment variables
4. Add: `ADMIN_API_KEY` = `your-secret-key`
5. Deploy new configuration

## Monitoring

All admin reset operations are logged with **WARNING** level:

```
2025-11-24 10:30:00 - ngrs.api - WARNING - Admin reset initiated - flushing Redis and restarting workers
2025-11-24 10:30:01 - ngrs.api - INFO - Flushing Redis database...
2025-11-24 10:30:01 - ngrs.api - INFO - Redis flushed
2025-11-24 10:30:01 - ngrs.api - INFO - Restarting worker pool...
2025-11-24 10:30:02 - ngrs.api - INFO - Workers restarted
2025-11-24 10:30:02 - ngrs.api - WARNING - Admin reset completed successfully
```

Check logs after reset:
```bash
# Local
tail -f logs/api.log

# Production (systemd)
sudo journalctl -u ngrs-solver -f

# Production (docker)
docker logs -f ngrs-solver
```

## Troubleshooting

### "Invalid API key" Error

- Check environment variable: `echo $ADMIN_API_KEY`
- Verify key matches server configuration
- Ensure no extra spaces or quotes

### Reset Hangs or Times Out

- Workers may be stuck on long-running jobs
- Check worker logs for errors
- Consider force-restart via systemd/docker

### Redis Connection Errors After Reset

- Verify Redis is running: `redis-cli ping`
- Check Redis connection settings
- Review Redis logs for errors

### Workers Not Restarting

If workers run separately from API server:
1. Reset will flush Redis but not restart workers
2. Manually restart worker processes
3. Or redeploy the application

## Alternative: Partial Cleanup

If you don't want a full reset, use these alternatives:

### Delete Specific Job
```bash
curl -X DELETE https://ngrssolver08.comcentricapps.com/solve/async/{job_id}
```

### Clean Old Jobs (Script)
```bash
./bulk_cleanup.sh
```

### Rely on TTL
Wait for automatic cleanup (default: 1 hour)

## Security Audit Log

**Track who performs resets:**

```bash
# Add to admin_reset.sh
echo "$(date) - Reset by $USER from $(hostname)" >> /var/log/admin_resets.log
```

**Monitor failed attempts:**

```bash
# Filter logs for unauthorized attempts
grep "Admin reset attempted with invalid API key" /var/log/ngrs-solver.log
```

## FAQ

**Q: How long does a reset take?**  
A: Typically 1-3 seconds (flush + worker restart)

**Q: Can I reset without restarting workers?**  
A: Yes, if workers run separately. The endpoint will flush Redis only.

**Q: Will active jobs be saved?**  
A: No. All job data is deleted immediately. Complete active jobs before reset.

**Q: Can I undo a reset?**  
A: No. Reset is permanent. Jobs and results cannot be recovered.

**Q: How often should I reset?**  
A: Rarely. Only when necessary for recovery or testing. Rely on TTL for routine cleanup.

---

**Related Documentation:**
- [Memory Cleanup Guide](./MEMORY_CLEANUP.md)
- [Job Management](./JOB_MANAGEMENT.md)
- [Deployment Guide](./DEPLOYMENT.md)
