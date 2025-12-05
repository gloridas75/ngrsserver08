# NGRS Solver - Ubuntu EC2 Deployment Guide

**Production Server**: https://ngrssolver08.comcentricapps.com  
**Version**: v0.95  
**Platform**: Ubuntu 22.04 LTS on AWS EC2  
**Last Updated**: December 5, 2025

---

## 🎯 Overview

Complete guide for deploying and managing NGRS Solver on Ubuntu EC2 instances in production.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│            Ubuntu EC2 Instance                          │
│         (t3.medium: 2 vCPU, 4 GB RAM)                  │
│                                                         │
│  ┌──────────────┐      ┌──────────────────────────┐   │
│  │   Redis      │◄─────┤  FastAPI Server          │   │
│  │  (Docker)    │      │  + Background Workers    │   │
│  │  port 6379   │      │  port 8080               │   │
│  └──────────────┘      └──────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐  │
│  │         systemd services (auto-restart)         │  │
│  │  • ngrs-redis.service                          │  │
│  │  • ngrs-api.service                            │  │
│  └─────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
                           │ HTTPS (443)
                           ▼
                    Load Balancer / CDN
                           │
                           ▼
              https://ngrssolver08.comcentricapps.com
```

---

## 📋 Prerequisites

### AWS Requirements
- **EC2 Instance**: t3.medium or larger
- **OS**: Ubuntu 22.04 LTS
- **Storage**: 20 GB GP3 SSD
- **Security Group**: Port 8080 open (API), Port 22 (SSH)
- **Elastic IP**: Recommended for consistent DNS
- **IAM Role**: Optional (for CloudWatch logs, S3 access)

### Local Requirements
- SSH access to EC2 instance
- Git repository access
- AWS CLI configured (optional)

---

## 🚀 Initial Setup (First Time Only)

### Step 1: Launch EC2 Instance

**Via AWS Console:**
1. Go to EC2 → Launch Instance
2. Select **Ubuntu Server 22.04 LTS**
3. Choose **t3.medium** instance type
4. Configure:
   - Storage: 20 GB GP3
   - Security Group: Allow port 8080, 22
5. Create or select key pair
6. Launch instance

**Security Group Rules:**
```
Type        Protocol  Port Range  Source
SSH         TCP       22          Your IP
Custom TCP  TCP       8080        0.0.0.0/0  (or specific IPs)
```

### Step 2: Connect to EC2

```bash
# Get EC2 public IP from AWS console
export EC2_IP="<your-ec2-public-ip>"

# SSH to instance
ssh -i ~/.ssh/your-key.pem ubuntu@$EC2_IP
```

### Step 3: Run Initial Setup Script

On EC2 instance:

```bash
# Clone the repository
git clone https://github.com/gloridas75/ngrsserver08.git
cd ngrsserver08

# Make scripts executable
chmod +x deploy/*.sh

# Run initial setup (installs Docker, Redis, dependencies)
cd deploy
./ec2-setup.sh
```

**What `ec2-setup.sh` does:**
- ✅ Updates system packages
- ✅ Installs Docker and Docker Compose
- ✅ Starts Redis container (port 6379)
- ✅ Installs Python 3.11+ and pip
- ✅ Creates `~/.ngrs-env` configuration file
- ✅ Sets up directories and permissions

### Step 4: Install Python Dependencies

```bash
cd ~/ngrsserver08
pip3 install -r requirements.txt
```

### Step 5: Configure Environment

Edit `~/.ngrs-env`:

```bash
nano ~/.ngrs-env
```

**Production configuration:**
```bash
# Server settings
PORT=8080
HOST=0.0.0.0
START_WORKERS=true
SOLVER_WORKERS=6

# Redis settings
REDIS_URL=localhost:6379

# Solver settings
DEFAULT_TIME_LIMIT=300
MAX_TIME_LIMIT=1800

# Security (optional)
ADMIN_API_KEY=your-secure-random-key-here

# Logging
LOG_LEVEL=INFO
```

### Step 6: Install as systemd Service

```bash
cd ~/ngrsserver08/deploy
sudo ./install-service.sh
```

This creates and enables:
- `ngrs-redis.service` - Redis container
- `ngrs-api.service` - API server + workers

### Step 7: Start Services

```bash
sudo systemctl start ngrs-redis
sudo systemctl start ngrs-api

# Check status
sudo systemctl status ngrs-api
```

### Step 8: Verify Deployment

```bash
# Run health check
cd ~/ngrsserver08/deploy
./health-check.sh

# Should output:
# ✅ Redis container running
# ✅ Redis connectivity OK
# ✅ API server responding
# ✅ Async workers: 6 active
```

**Test from local machine:**
```bash
curl http://$EC2_IP:8080/health
curl http://$EC2_IP:8080/version
```

---

## 🔄 Deploying Updates (v0.95 or newer)

### Method 1: Git Pull (Recommended)

**On EC2:**
```bash
# Stop services
sudo systemctl stop ngrs-api

# Pull latest changes
cd ~/ngrsserver08
git pull origin main

# Install any new dependencies
pip3 install -r requirements.txt --upgrade

# Restart services
sudo systemctl start ngrs-api

# Verify
curl http://localhost:8080/version
```

### Method 2: Manual File Transfer

**From local machine:**
```bash
# Stop services first
ssh ubuntu@$EC2_IP "sudo systemctl stop ngrs-api"

# Transfer updated files
scp -r src/ ubuntu@$EC2_IP:~/ngrsserver08/
scp requirements.txt ubuntu@$EC2_IP:~/ngrsserver08/

# Restart services
ssh ubuntu@$EC2_IP "sudo systemctl start ngrs-api"
```

### Method 3: Automated Deployment Script

Create `deploy_to_ec2.sh` locally:

```bash
#!/bin/bash
set -e

EC2_IP="your-ec2-ip"
EC2_USER="ubuntu"
KEY_FILE="~/.ssh/your-key.pem"

echo "🚀 Deploying to EC2: $EC2_IP"

# Stop services
echo "⏸️  Stopping services..."
ssh -i $KEY_FILE $EC2_USER@$EC2_IP "sudo systemctl stop ngrs-api"

# Pull latest code
echo "📥 Pulling latest code..."
ssh -i $KEY_FILE $EC2_USER@$EC2_IP "cd ~/ngrsserver08 && git pull origin main"

# Update dependencies
echo "📦 Updating dependencies..."
ssh -i $KEY_FILE $EC2_USER@$EC2_IP "cd ~/ngrsserver08 && pip3 install -r requirements.txt --upgrade"

# Restart services
echo "▶️  Starting services..."
ssh -i $KEY_FILE $EC2_USER@$EC2_IP "sudo systemctl start ngrs-api"

# Wait for startup
sleep 5

# Health check
echo "🏥 Running health check..."
ssh -i $KEY_FILE $EC2_USER@$EC2_IP "cd ~/ngrsserver08/deploy && ./health-check.sh"

echo "✅ Deployment complete!"
echo "🌐 Check: http://$EC2_IP:8080/version"
```

**Usage:**
```bash
chmod +x deploy_to_ec2.sh
./deploy_to_ec2.sh
```

---

## 📊 Service Management

### systemd Commands

```bash
# Start services
sudo systemctl start ngrs-redis
sudo systemctl start ngrs-api

# Stop services
sudo systemctl stop ngrs-api
sudo systemctl stop ngrs-redis

# Restart (after config changes)
sudo systemctl restart ngrs-api

# Status check
sudo systemctl status ngrs-api

# Enable auto-start on boot
sudo systemctl enable ngrs-api

# Disable auto-start
sudo systemctl disable ngrs-api

# View logs (live)
sudo journalctl -u ngrs-api -f

# View last 100 lines
sudo journalctl -u ngrs-api -n 100

# View logs from today
sudo journalctl -u ngrs-api --since today
```

### Manual Service Control (Development)

```bash
# Stop systemd service first
sudo systemctl stop ngrs-api

# Run manually
cd ~/ngrsserver08/deploy
./start-solver.sh

# Stop manual run
./stop-solver.sh

# Restart systemd service
sudo systemctl start ngrs-api
```

---

## 🔍 Monitoring & Troubleshooting

### Health Checks

**Quick health check:**
```bash
curl http://localhost:8080/health
```

**Full diagnostics:**
```bash
cd ~/ngrsserver08/deploy
./health-check.sh
```

**Check async worker stats:**
```bash
curl http://localhost:8080/solve/async/stats?details=true
```

### View Logs

**API Server logs:**
```bash
# Live logs
sudo journalctl -u ngrs-api -f

# Last 200 lines
sudo journalctl -u ngrs-api -n 200

# Search for errors
sudo journalctl -u ngrs-api | grep ERROR

# Logs from specific time
sudo journalctl -u ngrs-api --since "2025-12-05 10:00:00"
```

**Redis logs:**
```bash
docker logs ngrs-redis
docker logs ngrs-redis --follow
```

### Check System Resources

```bash
# CPU and memory usage
htop

# Disk space
df -h

# Check Python processes
ps aux | grep python

# Check Redis
docker ps | grep redis
redis-cli ping
```

### Common Issues

**Issue 1: API not responding**
```bash
# Check if service is running
sudo systemctl status ngrs-api

# Check if port is in use
sudo netstat -tlnp | grep 8080

# Check logs for errors
sudo journalctl -u ngrs-api -n 50
```

**Issue 2: Redis connection failed**
```bash
# Check Redis container
docker ps | grep redis

# Start Redis if stopped
docker start ngrs-redis

# Test connectivity
redis-cli ping
```

**Issue 3: Workers not processing jobs**
```bash
# Check worker count
curl http://localhost:8080/solve/async/stats

# Check environment
cat ~/.ngrs-env | grep WORKERS

# Restart service
sudo systemctl restart ngrs-api
```

**Issue 4: High memory usage**
```bash
# Check memory
free -h

# Check Python processes
ps aux --sort=-%mem | grep python | head -5

# Reduce worker count in ~/.ngrs-env
nano ~/.ngrs-env
# Set SOLVER_WORKERS=3

# Restart
sudo systemctl restart ngrs-api
```

---

## 🧪 Testing Production Deployment

### Verify Version

```bash
curl http://$EC2_IP:8080/version

# Expected output:
{
  "apiVersion": "0.95.0",
  "solverVersion": "optSolve-py-0.95.0",
  "schemaVersion": "0.95"
}
```

### Test Basic Solve

```bash
# Sync solve (quick test)
curl -X POST http://$EC2_IP:8080/solve \
  -H "Content-Type: application/json" \
  -d @input/test_input.json

# Async solve
curl -X POST http://$EC2_IP:8080/solve/async \
  -H "Content-Type: application/json" \
  -d @input/test_input.json

# Check result
curl http://$EC2_IP:8080/solve/async/<job-id>
```

### Test Auto-Optimization (v0.95)

```bash
# Submit job with auto-optimization
curl -X POST http://$EC2_IP:8080/solve/async \
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

### Test Caching (v0.95)

**On EC2:**
```bash
cd ~/ngrsserver08

# Check cache stats
python3 src/manage_ratio_cache.py stats

# List cached patterns
python3 src/manage_ratio_cache.py list

# Clear cache (if needed)
python3 src/manage_ratio_cache.py clear
```

### Load Testing

```bash
# Install hey (HTTP load generator)
sudo apt install hey

# Test with 10 concurrent requests
hey -n 100 -c 10 http://$EC2_IP:8080/health

# Test async endpoint
hey -n 50 -c 5 -m POST \
  -H "Content-Type: application/json" \
  -D input/test_input.json \
  http://$EC2_IP:8080/solve/async
```

---

## 🔐 Security Best Practices

### 1. Restrict Security Group

Update security group to allow only:
- Port 22 (SSH) from your IP only
- Port 8080 from load balancer IP or specific IPs

### 2. Enable Admin API Key

In `~/.ngrs-env`:
```bash
ADMIN_API_KEY=$(openssl rand -hex 32)
```

Restart service:
```bash
sudo systemctl restart ngrs-api
```

### 3. Set Up HTTPS

**Option A: Use AWS Application Load Balancer**
- ALB handles HTTPS termination
- EC2 stays on HTTP (internal)

**Option B: Use nginx reverse proxy**
```bash
sudo apt install nginx certbot python3-certbot-nginx

# Configure nginx
sudo nano /etc/nginx/sites-available/ngrs

# Get SSL certificate
sudo certbot --nginx -d ngrssolver08.comcentricapps.com
```

### 4. Regular Updates

```bash
# System updates
sudo apt update && sudo apt upgrade -y

# Python packages
cd ~/ngrsserver08
pip3 install -r requirements.txt --upgrade

# Docker images
docker pull redis:7-alpine
docker restart ngrs-redis
```

### 5. Backup Configuration

```bash
# Backup environment
cp ~/.ngrs-env ~/.ngrs-env.backup

# Backup cache (v0.95)
cp ~/ngrsserver08/config/ratio_cache.json ~/backups/

# Create regular backups
crontab -e
# Add: 0 2 * * * cp ~/ngrsserver08/config/ratio_cache.json ~/backups/cache_$(date +\%Y\%m\%d).json
```

---

## 📈 Performance Optimization

### Recommended Instance Sizes

| Employees | Concurrent Jobs | Instance Type | Workers | RAM |
|-----------|----------------|---------------|---------|-----|
| < 50      | 1-2            | t3.small      | 2       | 2 GB |
| 50-100    | 2-5            | t3.medium     | 4       | 4 GB |
| 100-500   | 5-10           | t3.large      | 6       | 8 GB |
| 500+      | 10+            | t3.xlarge     | 8       | 16 GB |

### Worker Configuration

Edit `~/.ngrs-env`:
```bash
# Formula: WORKERS = vCPU * 2
# t3.medium (2 vCPU) → 4 workers
# t3.large (2 vCPU) → 4-6 workers
SOLVER_WORKERS=6
```

Restart:
```bash
sudo systemctl restart ngrs-api
```

### Redis Optimization

For high volume (1000+ jobs/day):
```bash
# Edit Redis config
docker exec -it ngrs-redis redis-cli CONFIG SET maxmemory 512mb
docker exec -it ngrs-redis redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

### Auto-Optimization Settings (v0.95)

For faster optimization:
```json
{
  "requirements": [{
    "autoOptimizeStrictRatio": true,
    "minStrictRatio": 0.65,
    "maxStrictRatio": 0.75,
    "strictRatioStep": 0.05
  }]
}
```

This tests only 3 ratios (65%, 70%, 75%) instead of default range.

---

## 🔄 Rollback Procedure

If issues occur after deployment:

### Quick Rollback

```bash
# Stop services
sudo systemctl stop ngrs-api

# Revert code
cd ~/ngrsserver08
git log --oneline -5  # Find previous commit
git checkout <previous-commit-hash>

# Reinstall dependencies (if needed)
pip3 install -r requirements.txt

# Restart
sudo systemctl start ngrs-api
```

### Rollback to Specific Version

```bash
sudo systemctl stop ngrs-api
cd ~/ngrsserver08

# Rollback to v0.94 (example)
git checkout v0.94

pip3 install -r requirements.txt
sudo systemctl start ngrs-api
```

### Emergency Recovery

```bash
# Stop everything
sudo systemctl stop ngrs-api
sudo systemctl stop ngrs-redis

# Clear cache if corrupted
rm -f ~/ngrsserver08/config/ratio_cache.json

# Reset Redis
docker rm -f ngrs-redis
docker run -d --name ngrs-redis --restart unless-stopped \
  -p 6379:6379 redis:7-alpine

# Start with fresh state
sudo systemctl start ngrs-api
```

---

## 📊 Monitoring & Alerts

### CloudWatch Integration (Optional)

Install CloudWatch agent:
```bash
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb

# Configure
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-config-wizard
```

### Custom Health Check Script

Create `/usr/local/bin/ngrs-health-monitor.sh`:
```bash
#!/bin/bash

ENDPOINT="http://localhost:8080/health"
WEBHOOK_URL="your-slack-or-sns-webhook"

if ! curl -sf $ENDPOINT > /dev/null; then
    echo "⚠️ NGRS API is DOWN!"
    curl -X POST $WEBHOOK_URL \
      -H "Content-Type: application/json" \
      -d '{"text":"ALERT: NGRS API is DOWN on EC2"}'
    
    # Auto-restart
    sudo systemctl restart ngrs-api
fi
```

Add to crontab:
```bash
# Check every 5 minutes
*/5 * * * * /usr/local/bin/ngrs-health-monitor.sh
```

---

## 📚 Additional Resources

### Documentation
- **Main README**: `/README.md`
- **API Reference**: `/implementation_docs/API_QUICK_REFERENCE.md`
- **Caching Guide**: `/docs/RATIO_CACHING_GUIDE.md`
- **Auto-Optimization**: `/docs/AUTO_OPTIMIZATION_GUIDE.md`
- **Release Notes**: `/RELEASE_NOTES_v0.95.md`

### Deployment Scripts
- **EC2 Setup**: `/deploy/ec2-setup.sh`
- **Start Solver**: `/deploy/start-solver.sh`
- **Install Service**: `/deploy/install-service.sh`
- **Health Check**: `/deploy/health-check.sh`

### Support
- **GitHub**: https://github.com/gloridas75/ngrsserver08
- **Issues**: https://github.com/gloridas75/ngrsserver08/issues

---

## ✅ Deployment Checklist

### Pre-Deployment
- [ ] EC2 instance launched and accessible
- [ ] Security group configured (ports 22, 8080)
- [ ] Elastic IP assigned (optional)
- [ ] SSH key pair available

### Initial Setup
- [ ] `ec2-setup.sh` executed successfully
- [ ] Dependencies installed (`requirements.txt`)
- [ ] `~/.ngrs-env` configured
- [ ] systemd services installed
- [ ] Services started and enabled

### Verification
- [ ] Health check passes (`./health-check.sh`)
- [ ] Version endpoint returns v0.95
- [ ] Test solve completes successfully
- [ ] Workers processing jobs
- [ ] Redis container running

### Post-Deployment
- [ ] DNS configured (ngrssolver08.comcentricapps.com)
- [ ] HTTPS/SSL enabled
- [ ] Monitoring configured
- [ ] Backups automated
- [ ] Documentation updated

### v0.95 Features
- [ ] Auto-optimization tested
- [ ] Caching verified (`manage_ratio_cache.py stats`)
- [ ] Per-requirement configuration tested
- [ ] Schema v0.95 validated

---

**🎉 You're ready for production with NGRS Solver v0.95 on Ubuntu EC2!**
