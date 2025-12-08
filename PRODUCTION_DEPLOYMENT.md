# 🚀 Production Deployment Guide - AWS Ubuntu Server

## Quick Deployment Steps

### 1. SSH into Production Server
```bash
ssh ubuntu@your-server-ip
# or
ssh ubuntu@ngrssolver09.comcentricapps.com
```

### 2. Navigate to Project Directory
```bash
cd /path/to/ngrssolver
# Common locations:
# cd ~/ngrssolver
# cd /opt/ngrssolver
# cd /var/www/ngrssolver
```

### 3. Pull Latest Code from GitHub
```bash
# Stash any local changes (if needed)
git stash

# Pull latest changes
git pull origin main

# Verify you got the latest commit
git log -1
# Should show: "feat: Deploy ICPMP v2.0 with 24% efficiency improvement"
# Commit: 18fa663
```

### 4. Check for New Dependencies
```bash
# Activate virtual environment
source venv/bin/activate
# or
source .venv/bin/activate

# Install any new dependencies (if requirements.txt changed)
pip install -r requirements.txt
```

### 5. Restart the Solver Service

**Option A: Using systemd service**
```bash
sudo systemctl restart ngrs-solver
# Check status
sudo systemctl status ngrs-solver
```

**Option B: Using supervisor**
```bash
sudo supervisorctl restart ngrs-solver
# Check status
sudo supervisorctl status ngrs-solver
```

**Option C: Manual restart (if using screen/tmux)**
```bash
# Find and kill existing process
ps aux | grep uvicorn
kill <PID>

# Or use pkill
pkill -f "uvicorn.*api_server"

# Start new instance
nohup uvicorn src.api_server:app --host 0.0.0.0 --port 8080 --workers 2 > /tmp/ngrs_server.log 2>&1 &

# Or with screen
screen -S ngrs-solver
uvicorn src.api_server:app --host 0.0.0.0 --port 8080 --workers 2
# Press Ctrl+A then D to detach
```

### 6. Verify Deployment
```bash
# Check if server is running
curl http://localhost:8080/health | jq

# Check version (should show 0.96.0 with ICPMP v2.0)
curl http://localhost:8080/version | jq

# Expected output:
# {
#   "apiVersion": "0.96.0",
#   "solverVersion": "optSolve-py-0.96.0-icpmp-v2",
#   "schemaVersion": "0.96",
#   "icpmpVersion": "2.0",
#   "timestamp": "2025-12-08T..."
# }

# Test ICPMP endpoint
curl -X POST http://localhost:8080/configure \
  -H "Content-Type: application/json" \
  -d '{
    "planningHorizon": {
      "startDate": "2026-03-01",
      "endDate": "2026-03-31"
    },
    "requirements": [
      {
        "requirementId": "TEST",
        "requirementName": "Test",
        "coverageDays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        "shiftTypes": ["D"],
        "headcountByShift": {"D": 10},
        "strictAdherence": true
      }
    ],
    "constraints": {
      "maxRegularHoursPerWeek": 44,
      "maxOvertimeHoursPerMonth": 72
    }
  }' | jq '.summary'

# Expected: Should show ICPMP v2.0 optimizer version
```

### 7. Check External Access
```bash
# From local machine or another server
curl https://ngrssolver09.comcentricapps.com/health

curl https://ngrssolver09.comcentricapps.com/version
```

---

## 🆕 What's New in v0.96.0

### ICPMP v2.0 Enhancements
- ✅ Coverage-aware pattern generation (5-day for Mon-Fri, 7-day for full week)
- ✅ 24.4% more efficient employee allocation
- ✅ Zero pattern/coverage mismatches
- ✅ Intelligent offset distribution with rotation preprocessor
- ✅ Pattern length validation

### API Updates
- Version bumped to 0.96.0
- `/configure` endpoint now uses ICPMP v2.0
- Enhanced documentation in OpenAPI/Swagger
- New `icpmpVersion` field in `/version` endpoint

### Files Changed
- `context/engine/config_optimizer.py` - Now ICPMP v2.0
- `context/engine/config_optimizer_v1_original.py` - Original backed up
- `context/engine/rotation_preprocessor.py` - New preprocessing module
- `src/api_server.py` - Updated to v0.96.0
- `postman/NGRS_Solver_API.postman_collection.json` - Updated examples

---

## Troubleshooting

### Issue: Port 8080 already in use
```bash
# Find process using port
sudo lsof -i :8080
# or
sudo netstat -tlnp | grep 8080

# Kill the process
sudo kill <PID>
```

### Issue: Permission denied
```bash
# Make sure you have proper permissions
sudo chown -R ubuntu:ubuntu /path/to/ngrssolver

# Or run with sudo (not recommended for production)
sudo systemctl restart ngrs-solver
```

### Issue: Module not found errors
```bash
# Reinstall dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Issue: Server not responding
```bash
# Check logs
tail -f /tmp/ngrs_server.log
# or
journalctl -u ngrs-solver -f
# or
sudo supervisorctl tail -f ngrs-solver

# Check if process is running
ps aux | grep uvicorn

# Check system resources
free -h
df -h
```

### Issue: Git pull conflicts
```bash
# If you have local changes that conflict
git stash
git pull origin main
git stash pop

# Or discard local changes
git reset --hard origin/main
```

---

## Rollback Instructions (if needed)

If you need to rollback to previous version:

```bash
# View recent commits
git log --oneline -5

# Rollback to previous commit (before v0.96.0)
git checkout 77e34d5  # Previous commit

# Restart service
sudo systemctl restart ngrs-solver

# Check version (should be back to 0.95.0)
curl http://localhost:8080/version
```

To return to latest:
```bash
git checkout main
sudo systemctl restart ngrs-solver
```

---

## Production Service Setup (If Not Already Configured)

### Create systemd service file
```bash
sudo nano /etc/systemd/system/ngrs-solver.service
```

```ini
[Unit]
Description=NGRS Solver API Service
After=network.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/path/to/ngrssolver
Environment="PATH=/path/to/ngrssolver/venv/bin"
ExecStart=/path/to/ngrssolver/venv/bin/uvicorn src.api_server:app --host 0.0.0.0 --port 8080 --workers 2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable ngrs-solver
sudo systemctl start ngrs-solver
sudo systemctl status ngrs-solver
```

---

## Environment Variables (if needed)

If your production uses environment variables:

```bash
# Edit .env file
nano .env

# Add/update:
# SOLVER_WORKERS=2
# REDIS_HOST=localhost
# REDIS_PORT=6379
# ADMIN_API_KEY=your-secret-key
```

Or set in systemd service file:
```ini
[Service]
Environment="SOLVER_WORKERS=2"
Environment="REDIS_HOST=localhost"
Environment="ADMIN_API_KEY=your-secret-key"
```

---

## Post-Deployment Checklist

- [ ] Code pulled successfully (commit 18fa663)
- [ ] Dependencies installed
- [ ] Service restarted
- [ ] `/health` endpoint responding
- [ ] `/version` shows 0.96.0 with icpmpVersion: "2.0"
- [ ] `/configure` endpoint working (ICPMP v2.0)
- [ ] External access working (https://ngrssolver09.comcentricapps.com)
- [ ] Logs showing no errors
- [ ] Test solve request completed successfully

---

## Testing ICPMP v2.0

Quick test to verify v2 is working with improved efficiency:

```bash
curl -X POST https://ngrssolver09.comcentricapps.com/configure \
  -H "Content-Type: application/json" \
  -d '{
    "planningHorizon": {"startDate": "2026-03-01", "endDate": "2026-03-31"},
    "requirements": [{
      "requirementId": "REQ_52_1",
      "requirementName": "Weekday Coverage",
      "coverageDays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
      "shiftTypes": ["D"],
      "headcountByShift": {"D": 10},
      "strictAdherence": true
    }],
    "constraints": {
      "maxRegularHoursPerWeek": 44,
      "maxOvertimeHoursPerMonth": 72
    }
  }' | jq '.summary'
```

**Expected Results:**
- Employees needed: ~13 (vs 18 in v1) - **27.8% improvement**
- Pattern length: 5 days (matches Mon-Fri coverage)
- Optimizer version: "ICPMP v2.0 (Enhanced)"

---

## Support & Documentation

- **API Documentation**: https://ngrssolver09.comcentricapps.com/docs
- **GitHub Repository**: https://github.com/gloridas75/ngrsserver08
- **Latest Commit**: 18fa663
- **ICPMP Documentation**: See `ICPMP_STATUS_AND_IMPROVEMENTS.md`
- **Postman Collection**: `postman/NGRS_Solver_API.postman_collection.json`

---

**Deployment completed successfully once all checklist items are verified! 🎉**
