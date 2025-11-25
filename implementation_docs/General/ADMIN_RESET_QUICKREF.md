# Admin Reset - Quick Reference

## 🔑 Setup API Key (First Time Only)

```bash
# 1. Generate secure key (32+ characters)
openssl rand -base64 32

# 2. Set on server (AWS App Runner)
Configuration → Environment Variables
Add: ADMIN_API_KEY = <your-key>
Deploy

# 3. Set locally
export ADMIN_API_KEY='<your-key>'
echo "export ADMIN_API_KEY='<your-key>'" >> ~/.zshrc
```

## 🚨 Perform Reset

```bash
# Interactive (recommended)
./admin_reset.sh

# Direct API call
curl -X POST https://ngrssolver08.comcentricapps.com/admin/reset \
  -H "x-api-key: $ADMIN_API_KEY"
```

## 📊 Check System Stats

```bash
# Detailed stats with job UUIDs
curl "https://ngrssolver08.comcentricapps.com/solve/async/stats?details=true"

# Or use helper script
./check_async_stats.sh
```

## 🧪 Test Authentication

```bash
./test_admin_reset.sh
```

## ✅ What Reset Does

- Flushes Redis (all jobs/results deleted)
- Restarts worker processes
- Resets counters to zero
- Returns fresh system stats

## ⚠️ When to Use

✅ **Use when:**
- System recovery after errors
- Redis memory issues
- Worker deadlock
- Testing/development

❌ **Don't use when:**
- Jobs actively processing
- During business hours
- As routine operation

## 🔍 Verify Reset

```bash
# Check stats after reset
curl https://ngrssolver08.comcentricapps.com/solve/async/stats

# Should show:
# total_jobs: 0
# active_jobs: 0
# queue_length: 0
```

## 📝 Logs

```bash
# View reset logs
sudo journalctl -u ngrs-solver -f | grep -i reset
```

## 🆘 Troubleshooting

**"Invalid API key"**
```bash
echo $ADMIN_API_KEY  # Should match server
```

**"Connection refused"**
```bash
# Check server is running
curl https://ngrssolver08.comcentricapps.com/health
```

**Reset hangs**
```bash
# Workers stuck - force restart
sudo systemctl restart ngrs-solver
```

---

**Full docs:** `implementation_docs/ADMIN_RESET.md`
