# 🚨 Server Crash Prevention - Quick Reference

## ❓ Is My Server Crashing Due to Large Problems?

### Check Crash Logs (Ubuntu)
```bash
# Check OOM killer logs
sudo dmesg -T | grep -i "killed process" | tail -20

# Check service logs
sudo journalctl -u ngrs-solver -n 100 | grep -i "killed\|memory"

# Or use our script
./scripts/check_crash_logs.sh
```

**Look for:**
- `Out of memory: Killed process ... (python)`
- `oom-killer: gfp_mask=...`
- `Memory cgroup out of memory`

---

## ✅ Solution Deployed (v0.96)

### What's New
1. **Pre-solve validation** - Rejects oversized problems BEFORE solving
2. **Resource monitoring** - Tracks memory/CPU in real-time
3. **Adaptive limits** - Auto-adjusts based on server capacity
4. **New endpoints** - `/metrics` and `/estimate-complexity`

### How It Works
```
User Request → Pre-Solve Check → Reject if too large ✅
                               → Solve if safe ✅
```

---

## 📊 Server Capacity Limits

| Server | RAM | vCPUs | Max Variables | Max Employees | Max Headcount |
|--------|-----|-------|---------------|---------------|---------------|
| Small | 4GB | 2 | 50,000 | ~100 | ~30 |
| Medium | 8GB | 4 | 200,000 | ~400 | ~60 |
| Large | 16GB | 8 | 1,000,000 | ~2000 | ~100 |

**Formula:** `Variables ≈ Employees × Slots × PatternLength / 10`

---

## 🔍 Check Server Capacity

```bash
# Get server metrics
curl http://YOUR_SERVER:8080/metrics | jq '.'

# Output:
{
  "capacity": {
    "tier": "small",           # small/medium/large
    "max_variables": 50000,
    "max_employees_estimate": 100
  },
  "system": {
    "memory_total_gb": 3.84,
    "memory_available_gb": 2.1,
    "cpu_count": 2
  }
}
```

---

## 🧪 Test Problem Size Before Solving

```bash
# Check if problem will crash server
curl -X POST http://YOUR_SERVER:8080/estimate-complexity \
  -H "Content-Type: application/json" \
  -d @input/my_problem.json | jq '.'

# Output:
{
  "complexity": {
    "estimated_variables": 542500,      # 50 headcount × 31 days
    "estimated_memory_mb": 5168,
    "num_employees": 50,
    "num_slots": 10850
  },
  "safety": {
    "can_solve": false,                  # ❌ TOO LARGE
    "error": "Problem too large: 542,500 variables (limit: 50,000)",
    "recommendation": "Problem too large for this server"
  }
}
```

---

## ⚠️ What Happens Now?

### Before (Crash)
```
User: POST /solve with 50 headcount
→ Server starts solving
→ Memory usage: 100% → 200% → OOM Killer
→ Server CRASHES 💥
```

### After (Safe Rejection)
```
User: POST /solve with 50 headcount
→ Pre-solve check runs
→ Estimates: 542K variables, 5GB memory needed
→ Server has: 4GB total, 50K variable limit
→ Returns 400 error with suggestions ✅
→ Server stays healthy 🎉
```

**Error Response:**
```json
{
  "detail": {
    "error": "Problem size exceeds server capacity",
    "message": "Problem too large for this server: 542,500 variables (limit: 50,000). Server capacity: 3.8GB RAM, 2 vCPUs.",
    "suggestions": [
      "Reduce headcount per requirement (e.g., 50 → 30)",
      "Use incremental solver for partial month re-runs",
      "Split large requirements into smaller ones",
      "Upgrade to larger server (8GB+ RAM recommended)"
    ]
  }
}
```

---

## 🛠️ Quick Fixes

### Option 1: Reduce Problem Size (Immediate)
```json
// Before (crashes)
{"requirementId": "REQ001", "headcount": 50}

// After (safe)
{"requirementId": "REQ001", "headcount": 30}
```

### Option 2: Use Incremental Solver
Instead of full month solve, use partial re-runs:
```bash
POST /solve/incremental
# Only solve Dec 16-31, keep Dec 1-15 locked
```

### Option 3: Upgrade Server (Recommended)
```
Current: 2 vCPU, 4GB RAM ($20-40/mo)
Upgrade: 4 vCPU, 8GB RAM ($40-80/mo)
Result: 4x capacity, handles 60+ headcount
```

---

## 🚀 Deploy to Production

### 1. Update Code
```bash
cd /path/to/ngrssolver
git pull origin main  # Get latest with resource monitor
```

### 2. Restart Service
```bash
sudo systemctl restart ngrs-solver
```

### 3. Verify
```bash
# Check health
curl http://localhost:8080/health

# Check metrics
curl http://localhost:8080/metrics | jq '.capacity'

# Test with large problem (should reject)
curl -X POST http://localhost:8080/estimate-complexity \
  -d @input/large_50_headcount.json
```

---

## 📞 Emergency Recovery

If server crashed:
```bash
# 1. Restart service
sudo systemctl restart ngrs-solver

# 2. Check if working
curl http://localhost:8080/health

# 3. Review crash logs
./scripts/check_crash_logs.sh > crash_report.txt

# 4. Check what caused crash
sudo journalctl -u ngrs-solver -n 200 | grep -B5 -A5 "killed"
```

---

## ⚙️ Environment Variables (Optional)

```bash
# /etc/systemd/system/ngrs-solver.service or docker-compose.yml

# Memory limits
MAX_SOLVER_MEMORY_PERCENT=70    # Use max 70% of RAM
MAX_SOLVER_MEMORY_GB=2.5        # Or max 2.5GB absolute

# Time limits
MAX_SOLVER_TIME_LIMIT=120       # Max 2 minutes

# CPU limits
MAX_CPSAT_WORKERS=2             # Max 2 parallel workers
```

Reload after changes:
```bash
sudo systemctl daemon-reload
sudo systemctl restart ngrs-solver
```

---

## ✅ Verification Checklist

- [ ] New code deployed (`src/resource_monitor.py`)
- [ ] Service restarted
- [ ] `/metrics` endpoint returns capacity
- [ ] `/estimate-complexity` endpoint works
- [ ] Small problem (30 headcount) succeeds
- [ ] Large problem (50+ headcount) rejects with clear error
- [ ] No more crashes! 🎉

---

## 📚 Full Documentation

See: `implementation_docs/SERVER_CRASH_PREVENTION.md`

---

## 💡 Tips

1. **Always check complexity first:**
   ```bash
   curl -X POST .../estimate-complexity -d @input.json
   ```

2. **Monitor during solve:**
   ```bash
   watch -n 1 'curl -s localhost:8080/metrics | jq ".system.memory_percent_used"'
   ```

3. **Start small, scale up:**
   - Test with 20 employees first
   - Gradually increase to find limit
   - Upgrade server when needed

---

**Questions?** Check logs with `./scripts/check_crash_logs.sh`
