# EC2 Deployment - Quick Reference

**Production Server**: https://ngrssolver08.comcentricapps.com  
**Version**: v0.95

---

## 🚀 Deploy Updates to EC2

### Method 1: Automated Script (Recommended)

```bash
# Configure (first time only)
export EC2_IP="your-ec2-ip"
export EC2_USER="ubuntu"
export SSH_KEY="~/.ssh/your-key.pem"

# Deploy
./deploy_to_ec2.sh
```

### Method 2: Manual Deployment

```bash
# SSH to EC2
ssh ubuntu@your-ec2-ip

# Stop services
sudo systemctl stop ngrs-api

# Pull updates
cd ~/ngrsserver08
git pull origin main

# Update dependencies
pip3 install -r requirements.txt --upgrade

# Start services
sudo systemctl start ngrs-api

# Verify
./deploy/health-check.sh
```

---

## 📊 Service Management

```bash
# Start
sudo systemctl start ngrs-api

# Stop
sudo systemctl stop ngrs-api

# Restart
sudo systemctl restart ngrs-api

# Status
sudo systemctl status ngrs-api

# Logs (live)
sudo journalctl -u ngrs-api -f

# Last 50 lines
sudo journalctl -u ngrs-api -n 50
```

---

## 🔍 Health Checks

```bash
# Quick check
curl http://localhost:8080/health

# Full diagnostics
cd ~/ngrsserver08/deploy
./health-check.sh

# Check version
curl http://localhost:8080/version

# Worker stats
curl http://localhost:8080/solve/async/stats?details=true
```

---

## 🧪 Test v0.95 Features

### Test Version

```bash
curl http://localhost:8080/version
# Expected: {"apiVersion":"0.95.0","solverVersion":"optSolve-py-0.95.0",...}
```

### Test Auto-Optimization

```bash
curl -X POST http://localhost:8080/solve/async \
  -H "Content-Type: application/json" \
  -d '{
    "schemaVersion": "0.95",
    "requirements": [{
      "autoOptimizeStrictRatio": true,
      "minStrictRatio": 0.6,
      "maxStrictRatio": 0.8,
      "strictRatioStep": 0.1
    }],
    ...
  }'
```

### Check Cache

```bash
cd ~/ngrsserver08
python src/manage_ratio_cache.py stats
python src/manage_ratio_cache.py list
```

---

## 🔄 Rollback

```bash
# Stop service
sudo systemctl stop ngrs-api

# Revert to previous commit
cd ~/ngrsserver08
git log --oneline -5  # Find commit hash
git checkout <previous-commit>

# Reinstall deps
pip3 install -r requirements.txt

# Start service
sudo systemctl start ngrs-api
```

---

## ⚠️ Troubleshooting

### API not responding

```bash
# Check status
sudo systemctl status ngrs-api

# Check logs
sudo journalctl -u ngrs-api -n 100

# Restart
sudo systemctl restart ngrs-api
```

### Redis connection failed

```bash
# Check Redis
docker ps | grep redis

# Start Redis
docker start ngrs-redis

# Test
redis-cli ping
```

### High memory usage

```bash
# Check memory
free -h

# Reduce workers
nano ~/.ngrs-env
# Set SOLVER_WORKERS=3

# Restart
sudo systemctl restart ngrs-api
```

---

## 📦 Backup & Restore

### Backup Cache

```bash
cd ~/ngrsserver08
cp config/ratio_cache.json ~/backups/cache_$(date +%Y%m%d).json
```

### Restore Cache

```bash
cd ~/ngrsserver08
cp ~/backups/cache_20251205.json config/ratio_cache.json
sudo systemctl restart ngrs-api
```

---

## 📚 Documentation

- **Full Guide**: `implementation_docs/EC2_DEPLOYMENT_GUIDE.md`
- **Deploy Scripts**: `deploy/README.md`
- **API Reference**: `implementation_docs/API_QUICK_REFERENCE.md`
- **Caching Guide**: `docs/RATIO_CACHING_GUIDE.md`
- **Release Notes**: `RELEASE_NOTES_v0.95.md`

---

## 🎯 Post-Deployment Checklist

- [ ] Health check passes
- [ ] Version shows v0.95
- [ ] Workers processing jobs
- [ ] Redis connected
- [ ] Test solve completes
- [ ] Cache working (check stats)
- [ ] Logs look clean
- [ ] External URL accessible

---

**Need Help?**
- Check logs: `sudo journalctl -u ngrs-api -f`
- Full diagnostics: `cd deploy && ./health-check.sh`
- Rollback: See rollback section above
