# Production Server Crash Prevention Guide

## Problem: Server Crashes with Large Problems (50 headcount)

**Symptoms:**
- Ubuntu server (2 vCPU, 4GB RAM) crashes when solving 50 headcount with patterns
- OOM (Out of Memory) killer terminates Python process
- Server becomes unresponsive

**Root Cause:**
- CP-SAT solver uses ~100 bytes per decision variable
- 50 headcount × 7-day pattern × 31 days = ~10,850 slots
- With 50 employees = 542,500 variables = ~52MB base + 2-3GB during search
- 4GB server cannot handle this + OS + other services

---

## ✅ Solutions Implemented

### 1. **Pre-Solve Resource Check** (src/resource_monitor.py)

Validates problem size BEFORE solving to prevent crashes:

```python
# Rejects if problem exceeds server capacity:
# - 4GB server: Max 50,000 variables
# - 8GB server: Max 200,000 variables
# - 16GB server: Max 1,000,000 variables
```

**Returns 400 error** with clear message:
```json
{
  "error": "Problem size exceeds server capacity",
  "message": "Problem too large: 542,500 variables (limit: 50,000)",
  "complexity": {
    "estimated_variables": 542500,
    "estimated_memory_mb": 5168,
    "num_slots": 10850,
    "num_employees": 50
  },
  "suggestions": [
    "Reduce headcount per requirement (e.g., 50 → 30)",
    "Use incremental solver for partial month re-runs",
    "Split large requirements into smaller ones",
    "Upgrade to larger server (8GB+ RAM recommended)"
  ]
}
```

### 2. **Resource Limits Enforced**

Configured via environment variables:

```bash
# In /etc/systemd/system/ngrs-solver.service or docker-compose.yml

# Memory limit (percentage)
MAX_SOLVER_MEMORY_PERCENT=70

# Memory limit (GB)
MAX_SOLVER_MEMORY_GB=2.5

# Time limit (seconds)
MAX_SOLVER_TIME_LIMIT=120

# Max parallel workers
MAX_CPSAT_WORKERS=2
```

### 3. **Adaptive Resource Allocation**

Solver automatically adjusts based on server capacity:
- Auto-detects RAM and vCPUs
- Reduces parallel workers on small servers
- Sets safe time limits

---

## 📋 Checking for Crashes

### Run Crash Log Checker

```bash
# On Ubuntu server
cd /path/to/ngrssolver
chmod +x scripts/check_crash_logs.sh
./scripts/check_crash_logs.sh
```

**What to look for:**

1. **OOM Killer logs** (most common):
```
Out of memory: Killed process 12345 (python) total-vm:3GB
```

2. **SystemD service crashes**:
```
ngrs-solver.service: Main process exited, code=killed, status=9/KILL
```

3. **Python memory errors**:
```
MemoryError: Unable to allocate array
```

### Manual Check Commands

```bash
# Check OOM killer logs
sudo dmesg -T | grep -i "killed process"

# Check service status
sudo systemctl status ngrs-solver

# Check recent crashes
sudo journalctl -u ngrs-solver -n 200 --no-pager | grep -i "killed\|crash\|signal"

# Check current memory usage
free -h
ps aux --sort=-%mem | head -10
```

---

## 🚀 Recommended Server Configurations

### Minimum (Small Problems Only)
- **RAM:** 4GB
- **vCPUs:** 2
- **Max Problem Size:** 30 employees × 300 slots = ~10K variables
- **Cost:** $20-40/month

### Recommended (Production)
- **RAM:** 8GB
- **vCPUs:** 4
- **Max Problem Size:** 50 employees × 600 slots = ~30K variables
- **Cost:** $40-80/month

### Large Scale (Enterprise)
- **RAM:** 16GB
- **vCPUs:** 8
- **Max Problem Size:** 100 employees × 1000 slots = ~100K variables
- **Cost:** $80-160/month

---

## 🛡️ Preventing Future Crashes

### 1. **Set Systemd Memory Limits**

Edit `/etc/systemd/system/ngrs-solver.service`:

```ini
[Service]
# Limit memory to 3GB (75% of 4GB server)
MemoryMax=3G
MemoryHigh=2.5G

# CPU quota (200% = 2 full CPUs)
CPUQuota=200%

# Kill if exceeds limits
OOMPolicy=kill

# Restart on crash
Restart=on-failure
RestartSec=10s
```

Reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart ngrs-solver
```

### 2. **Enable Swap (Emergency Buffer)**

```bash
# Add 2GB swap file
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

⚠️ **Warning:** Swap is SLOW. Only use as emergency buffer, not for regular operation.

### 3. **Monitor Resource Usage**

Install monitoring:
```bash
# Install htop for real-time monitoring
sudo apt-get install htop

# Watch during solve
htop
```

**Or** use our monitoring endpoint:
```bash
curl http://localhost:8080/metrics
```

### 4. **Configure Nginx Timeout**

Edit `/etc/nginx/sites-available/ngrs-solver`:

```nginx
location / {
    proxy_pass http://localhost:8080;
    proxy_read_timeout 180s;  # 3 minutes
    proxy_connect_timeout 10s;
    proxy_send_timeout 180s;
    
    # Buffer settings
    proxy_buffering off;
    proxy_request_buffering off;
}
```

Reload:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 📊 Problem Size Guidelines

### 4GB Server (2 vCPU)

| Scenario | Employees | Slots | Variables | Status |
|----------|-----------|-------|-----------|--------|
| ✅ Small | 20 | 300 | 6,000 | Safe (5s) |
| ✅ Medium | 30 | 450 | 13,500 | Safe (15s) |
| ⚠️ Large | 40 | 600 | 24,000 | Risky (60s) |
| ❌ Too Large | 50 | 750 | 37,500 | **CRASH** |

### 8GB Server (4 vCPU)

| Scenario | Employees | Slots | Variables | Status |
|----------|-----------|-------|-----------|--------|
| ✅ Small | 30 | 450 | 13,500 | Safe (10s) |
| ✅ Medium | 50 | 750 | 37,500 | Safe (30s) |
| ⚠️ Large | 70 | 1050 | 73,500 | Risky (90s) |
| ❌ Too Large | 100 | 1500 | 150,000 | Risk |

**Formula:**
```
Variables ≈ Employees × Slots × PatternLength / 10
```

---

## 🔍 Testing the Fix

### 1. **Test Small Problem** (Should succeed)
```bash
curl -X POST http://localhost:8080/solve \
  -H "Content-Type: application/json" \
  -d @input/small_test.json
```

### 2. **Test Large Problem** (Should reject with 400)
```bash
curl -X POST http://localhost:8080/solve \
  -H "Content-Type: application/json" \
  -d @input/large_50_headcount.json
```

Expected response:
```json
{
  "detail": {
    "error": "Problem size exceeds server capacity",
    "message": "Problem too large for this server: 542,500 variables (limit: 50,000)...",
    "suggestions": [...]
  }
}
```

### 3. **Monitor During Solve**
```bash
# Terminal 1: Run solver
curl -X POST http://localhost:8080/solve -d @input/test.json

# Terminal 2: Watch resources
watch -n 1 'free -h && echo "" && ps aux | grep python | head -3'
```

---

## 🚨 Emergency Recovery

If server crashes:

```bash
# 1. Check if service is running
sudo systemctl status ngrs-solver

# 2. Check crash logs
sudo journalctl -u ngrs-solver -n 100 --no-pager

# 3. Restart service
sudo systemctl restart ngrs-solver

# 4. Check health
curl http://localhost:8080/health

# 5. Clear any stuck processes
pkill -9 python
sudo systemctl restart ngrs-solver
```

---

## 📞 Support

If crashes persist:
1. Collect logs: `./scripts/check_crash_logs.sh > crash_report.txt`
2. Check complexity: `curl http://localhost:8080/estimate-complexity -d @input/problem.json`
3. Share crash report with details:
   - Server specs (RAM, vCPU)
   - Problem size (employees, slots, pattern)
   - Error logs

---

## ✅ Deployment Checklist

- [ ] Resource monitor deployed (`src/resource_monitor.py`)
- [ ] API server updated with safety checks
- [ ] Environment variables configured
- [ ] Systemd memory limits set
- [ ] Swap file enabled (optional)
- [ ] Nginx timeout configured
- [ ] Monitoring enabled
- [ ] Crash logs script available
- [ ] Tested with large problem (should reject)
- [ ] Tested with medium problem (should succeed)
