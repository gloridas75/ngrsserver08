# NGRS Solver - Production Deployment Guide

## Quick Fix for Current Issue

**Problem:** `NameError: name 'List' is not defined` causing service crash

**Solution:** Pull latest code with the import fix

```bash
cd /opt/ngrs-solver
git pull origin main
./deploy_update.sh
```

---

## Deployment Methods

### Method 1: Full Deployment (Recommended)
Comprehensive script with backup, syntax check, and verification.

```bash
cd /opt/ngrs-solver
git pull origin main
./deploy_update.sh
```

**Features:**
- ✅ Automatic backup before deployment
- ✅ Syntax checking (catches errors before restart)
- ✅ Graceful service shutdown
- ✅ Port cleanup (kills hanging processes)
- ✅ Log archiving
- ✅ Health verification
- ✅ Detailed status reporting

---

### Method 2: Quick Restart
Fast restart for urgent situations (no code pull).

```bash
cd /opt/ngrs-solver
./quick_restart.sh
```

**Use when:**
- Service is hung but code is good
- Need emergency restart
- Port is blocked

---

### Method 3: Manual Steps
For troubleshooting or custom scenarios.

#### Step 1: Stop Service
```bash
sudo systemctl stop ngrs-solver
```

#### Step 2: Kill Hanging Processes
```bash
# Check for processes on port 8080
sudo lsof -i :8080

# Kill them if found
sudo lsof -ti :8080 | xargs -r sudo kill -9
```

#### Step 3: Pull Code
```bash
cd /opt/ngrs-solver
git pull origin main
```

#### Step 4: Check Syntax (Optional but Recommended)
```bash
cd /opt/ngrs-solver
source venv/bin/activate
python3 -m py_compile src/api_server.py
python3 -m py_compile context/engine/solver_engine.py
python3 -m py_compile context/engine/slot_builder.py
```

#### Step 5: Clear Logs
```bash
sudo mv /var/log/ngrs-solver.log /var/log/ngrs-solver.log.$(date +%Y%m%d_%H%M%S)
sudo touch /var/log/ngrs-solver.log
sudo chown ubuntu:ubuntu /var/log/ngrs-solver.log
```

#### Step 6: Start Service
```bash
sudo systemctl start ngrs-solver
```

#### Step 7: Verify
```bash
# Check status
sudo systemctl status ngrs-solver

# Check port
sudo lsof -i :8080

# Test health
curl http://localhost:8080/health

# Test version
curl http://localhost:8080/version
```

---

## Troubleshooting

### Service Won't Start

**Check logs:**
```bash
# Recent logs
tail -50 /var/log/ngrs-solver.log

# Full logs
cat /var/log/ngrs-solver.log

# System logs
sudo journalctl -u ngrs-solver -n 100 --no-pager
```

**Common issues:**

1. **Import Error**
   ```
   NameError: name 'List' is not defined
   ```
   → Pull latest code (fixed in commit 900cb51)

2. **Port Already in Use**
   ```
   ERROR: [Errno 98] Address already in use
   ```
   → Run: `sudo lsof -ti :8080 | xargs -r sudo kill -9`

3. **Syntax Error**
   → Check with: `python3 -m py_compile <file>`

4. **Permission Issues**
   → Check log file ownership: `sudo chown ubuntu:ubuntu /var/log/ngrs-solver.log`

---

### Service Shows "Running" but Not Responding

```bash
# Check if port is actually listening
sudo lsof -i :8080

# If empty, check logs for crash
tail -50 /var/log/ngrs-solver.log

# Look for worker crashes
sudo journalctl -u ngrs-solver -n 50 --no-pager | grep -i error
```

---

### 502 Bad Gateway

**Causes:**
1. Service not running
2. Service crashed on startup
3. Port not listening

**Fix:**
```bash
# Use quick restart script
./quick_restart.sh

# Or full deployment
./deploy_update.sh
```

---

## Rollback Procedure

### Option 1: Using Backup
```bash
# List available backups
ls -lh /opt/ngrs-solver-backups/

# Stop service
sudo systemctl stop ngrs-solver

# Restore from backup
BACKUP_DATE="20251208_120000"  # Use actual backup timestamp
sudo rm -rf /opt/ngrs-solver
sudo cp -r /opt/ngrs-solver-backups/ngrs-solver_$BACKUP_DATE /opt/ngrs-solver

# Start service
sudo systemctl start ngrs-solver
```

### Option 2: Using Git
```bash
cd /opt/ngrs-solver

# Find commit to rollback to
git log --oneline -n 10

# Rollback
git checkout <commit-hash>

# Restart service
./quick_restart.sh
```

---

## Monitoring Commands

```bash
# Real-time logs
tail -f /var/log/ngrs-solver.log

# Service status
watch -n 2 'sudo systemctl status ngrs-solver --no-pager'

# Port status
watch -n 2 'sudo lsof -i :8080'

# Health check
watch -n 5 'curl -s http://localhost:8080/health'
```

---

## Prevention Checklist

Before every deployment:

- [ ] Pull latest code: `git pull origin main`
- [ ] Check syntax locally before pushing
- [ ] Use `deploy_update.sh` for automatic verification
- [ ] Monitor logs for 2-3 minutes after deployment
- [ ] Test health endpoint
- [ ] Test a simple solve request

---

## Emergency Contacts

**Service URL:** https://ngrssolver09.comcentricapps.com

**Server:** AWS Ubuntu (ip-172-31-34-111)

**Key Files:**
- Service: `/etc/systemd/system/ngrs-solver.service`
- Code: `/opt/ngrs-solver`
- Logs: `/var/log/ngrs-solver.log`
- Backups: `/opt/ngrs-solver-backups`

**Quick Commands:**
```bash
# Status
sudo systemctl status ngrs-solver

# Restart
sudo systemctl restart ngrs-solver

# Stop
sudo systemctl stop ngrs-solver

# Logs
tail -50 /var/log/ngrs-solver.log
```
