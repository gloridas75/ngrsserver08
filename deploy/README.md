# EC2 Deployment Scripts

Simple deployment scripts for running NGRS Solver on AWS EC2 (or any Linux server).

## 🌐 Production Environment

**Current Production**: [https://ngrssolver09.comcentricapps.com](https://ngrssolver09.comcentricapps.com)  
**Infrastructure**: Ubuntu 22.04 EC2 instance (NOT AWS App Runner)  
**Server**: `ec2-47-130-131-6.ap-southeast-1.compute.amazonaws.com`  
**Deployment Method**: systemd service with Docker Redis

## Quick Start

### 1. Launch EC2 Instance

**Recommended**:
- **Instance Type**: t3.medium (2 vCPU, 4 GB RAM)
- **OS**: Ubuntu 22.04 LTS or Amazon Linux 2023
- **Storage**: 20 GB GP3
- **Security Group**: Allow inbound TCP port 8080 (API)

### 2. Initial Setup

SSH into your instance and run:

```bash
# Copy deployment scripts to EC2
scp -r deploy/ ubuntu@<ec2-ip>:~/

# SSH to instance
ssh ubuntu@<ec2-ip>

# Run setup script
cd ~/deploy
chmod +x *.sh
./ec2-setup.sh
```

**What it does**:
- ✓ Installs Docker
- ✓ Starts Redis container
- ✓ Creates environment configuration
- ✓ Prepares application directory

### 3. Deploy Application Code

From your local machine:

```bash
# Copy entire project to EC2
scp -r ngrssolver/ ubuntu@<ec2-ip>:~/

# Or use git
ssh ubuntu@<ec2-ip>
cd ~
git clone https://github.com/your-repo/ngrssolver.git
```

### 4. Install Dependencies

On EC2:

```bash
cd ~/ngrssolver
pip3 install -r requirements.txt
```

### 5. Start the Solver

**Option A: Development mode** (manual start)

```bash
cd ~/ngrssolver/deploy
./start-solver.sh
```

**Option B: Production mode** (systemd service)

```bash
cd ~/ngrssolver/deploy
sudo ./install-service.sh
```

The service will auto-start on boot and restart on failure.

---

## Scripts Reference

### `ec2-setup.sh`

Initial setup script for a fresh EC2 instance.

**Run once** when first setting up the instance.

```bash
./ec2-setup.sh
```

**Actions**:
- Installs Docker
- Starts Redis container (port 6379)
- Creates `~/.ngrs-env` configuration file
- Sets up Docker permissions

---

### `start-solver.sh`

Start API server + workers in development mode.

```bash
./start-solver.sh
```

**Features**:
- Loads environment from `~/.ngrs-env`
- Starts Redis if not running
- Runs API + workers in foreground
- Press Ctrl+C to stop

**Environment variables** (in `~/.ngrs-env`):
```bash
START_WORKERS=true       # Start workers with API
SOLVER_WORKERS=4         # Number of worker processes
REDIS_URL=localhost:6379 # Redis connection
PORT=8080               # API port
```

---

### `stop-solver.sh`

Stop the running solver.

```bash
./stop-solver.sh
```

Kills uvicorn processes. Does **not** stop Redis.

---

### `install-service.sh`

Install as systemd service for production (auto-start, auto-restart).

```bash
sudo ./install-service.sh
```

**Creates services**:
- `ngrs-redis.service` - Redis container
- `ngrs-api.service` - API + workers

**After installation**:
```bash
# Start
sudo systemctl start ngrs-api

# Stop
sudo systemctl stop ngrs-api

# Restart
sudo systemctl restart ngrs-api

# Status
sudo systemctl status ngrs-api

# Logs
sudo journalctl -u ngrs-api -f
```

---

### `health-check.sh`

Check if everything is working.

```bash
./health-check.sh
```

**Checks**:
- ✓ Redis container running
- ✓ Redis connectivity
- ✓ API server responding
- ✓ Async mode stats

**Exit codes**:
- `0` - Healthy
- `1` - Unhealthy

Use in monitoring/alerting systems.

---

## Architecture on EC2

```
┌─────────────────────────────────────────────┐
│            EC2 Instance                     │
│                                             │
│  ┌──────────────┐      ┌─────────────────┐ │
│  │   Redis      │◄─────┤  API Server     │ │
│  │  (Docker)    │      │  (uvicorn)      │ │
│  │  port 6379   │      │  port 8080      │ │
│  └──────────────┘      └────────┬────────┘ │
│                                 │          │
│                        ┌────────┴────────┐ │
│                        │  Worker Pool    │ │
│                        │  (4 processes)  │ │
│                        └─────────────────┘ │
│                                             │
└─────────────────────────────────────────────┘
                    ▲
                    │
                Internet (port 8080)
```

**Everything runs on one machine**:
- Redis in Docker container
- API server + workers in same Python process
- Communication via localhost

---

## Configuration

### Environment Variables

Edit `~/.ngrs-env`:

```bash
# Worker configuration
export START_WORKERS=true     # Enable workers
export SOLVER_WORKERS=4       # Number of workers (match CPU count)

# Redis configuration  
export REDIS_URL=localhost:6379
export REDIS_DB=0
export REDIS_PASSWORD=         # Optional

# Result caching
export RESULT_TTL_SECONDS=3600  # 1 hour

# API server
export PORT=8080
```

**Worker count recommendations**:
- **t3.small** (2 vCPU): `SOLVER_WORKERS=2`
- **t3.medium** (2 vCPU): `SOLVER_WORKERS=2-4`
- **t3.large** (2 vCPU): `SOLVER_WORKERS=4`
- **t3.xlarge** (4 vCPU): `SOLVER_WORKERS=6-8`

---

## Testing

After deployment, test the API:

```bash
# From EC2 instance
./health-check.sh

# From your computer
curl http://<ec2-public-ip>:8080/health
curl http://<ec2-public-ip>:8080/solve/async/stats

# Submit a test job
curl -X POST http://<ec2-public-ip>:8080/solve/async \
  -H "Content-Type: application/json" \
  -d @input/async_test_small.json
```

---

## Monitoring

### Check logs

**Development mode**:
```bash
# API server output in terminal
```

**Production mode (systemd)**:
```bash
# API logs
sudo journalctl -u ngrs-api -f

# Redis logs
docker logs ngrs-redis -f

# Last 100 lines
sudo journalctl -u ngrs-api -n 100
```

### Check queue stats

```bash
# Via API
curl http://localhost:8080/solve/async/stats | python3 -m json.tool

# Via Redis directly
docker exec ngrs-redis redis-cli LLEN ngrs:job:queue
docker exec ngrs-redis redis-cli KEYS "ngrs:*"
```

### Check processes

```bash
# API server
ps aux | grep uvicorn

# Workers (part of API process)
ps aux | grep python | grep redis_worker
```

---

## Troubleshooting

### Redis not starting

```bash
# Check Docker
sudo systemctl status docker

# Check if port 6379 is in use
sudo netstat -tlnp | grep 6379

# Restart Redis
docker restart ngrs-redis
```

### API not responding

```bash
# Check if running
ps aux | grep uvicorn

# Check logs (systemd)
sudo journalctl -u ngrs-api -n 50

# Check port
sudo netstat -tlnp | grep 8080

# Restart
sudo systemctl restart ngrs-api
```

### Workers not processing jobs

```bash
# Check environment
echo $START_WORKERS    # Should be "true"
echo $SOLVER_WORKERS   # Should be > 0

# Check logs for worker startup
sudo journalctl -u ngrs-api | grep "Starting.*workers"

# Expected output:
# "Starting 4 solver workers with Redis..."
# "Async mode enabled with 4 workers"
```

### Redis connection failed

```bash
# Test Redis
docker exec ngrs-redis redis-cli ping
# Should return: PONG

# Check if Redis is accessible
redis-cli -h localhost ping

# Check API can reach Redis
curl http://localhost:8080/solve/async/stats | grep redis_connected
# Should show: "redis_connected": true
```

---

## Upgrading

### Update application code

```bash
# SSH to EC2
cd ~/ngrssolver

# Pull latest changes
git pull

# Or upload new files
# scp -r src/ ubuntu@<ec2-ip>:~/ngrssolver/

# Restart service
sudo systemctl restart ngrs-api
```

### Update dependencies

```bash
cd ~/ngrssolver
pip3 install --upgrade -r requirements.txt
sudo systemctl restart ngrs-api
```

### Update Redis

```bash
# Stop old container
docker stop ngrs-redis
docker rm ngrs-redis

# Start new version
docker run -d --name ngrs-redis --restart unless-stopped -p 6379:6379 redis:7-alpine

# Or restart service
sudo systemctl restart ngrs-redis
```

---

## Scaling

### Vertical Scaling (Recommended)

Upgrade to a larger instance:

1. Stop service: `sudo systemctl stop ngrs-api`
2. Create AMI of current instance
3. Launch new larger instance from AMI
4. Update worker count in `~/.ngrs-env`
5. Restart service: `sudo systemctl start ngrs-api`

**Instance recommendations**:
- **Low traffic**: t3.small (2 workers)
- **Medium traffic**: t3.medium (4 workers)
- **High traffic**: t3.large or t3.xlarge (6-8 workers)

### Horizontal Scaling

If you outgrow a single instance, consider:

1. **Add Load Balancer** (ALB)
2. **Use ElastiCache Redis** (shared Redis)
3. **Launch multiple EC2 instances**
4. **Each instance connects to shared Redis**

At that point, consider the App Runner architecture (see `AWS_REDIS_DEPLOYMENT.md`).

---

## Backup & Recovery

### Backup Redis data

```bash
# Create Redis snapshot
docker exec ngrs-redis redis-cli BGSAVE

# Copy RDB file
docker cp ngrs-redis:/data/dump.rdb ~/redis-backup-$(date +%Y%m%d).rdb
```

### Restore Redis data

```bash
# Stop Redis
docker stop ngrs-redis

# Copy backup to container
docker cp ~/redis-backup.rdb ngrs-redis:/data/dump.rdb

# Start Redis
docker start ngrs-redis
```

### Create AMI

Regularly create AMI snapshots in AWS Console for full system backup.

---

## Security

### Firewall (Security Group)

**Inbound rules**:
- Port 22 (SSH) - Your IP only
- Port 8080 (API) - Your application/users

**Outbound rules**:
- Allow all (default)

### Redis Security

Redis runs on localhost only (not exposed to internet).

**Optional**: Add password:

```bash
docker run -d --name ngrs-redis \
  --restart unless-stopped \
  -p 6379:6379 \
  redis:7-alpine \
  redis-server --requirepass YOUR_PASSWORD

# Update ~/.ngrs-env
export REDIS_PASSWORD=YOUR_PASSWORD
```

### HTTPS (Optional)

Use NGINX or ALB for SSL termination:

```bash
sudo apt install nginx certbot python3-certbot-nginx

# Configure NGINX as reverse proxy
sudo nano /etc/nginx/sites-available/ngrs

# Get SSL certificate
sudo certbot --nginx -d solver.yourdomain.com
```

---

## Cost Estimate

| Component | Configuration | Monthly Cost |
|-----------|--------------|--------------|
| EC2 t3.small | 2 vCPU, 2GB RAM | ~$15 |
| EC2 t3.medium | 2 vCPU, 4GB RAM | ~$30 |
| EC2 t3.large | 2 vCPU, 8GB RAM | ~$60 |
| EBS Storage | 20 GB | ~$2 |
| Data Transfer | 1 GB out | Free tier |

**Total**: $17-62/month depending on instance size

**Compared to App Runner + ElastiCache**: Save $50-80/month! 💰

---

## Support

For issues or questions, check:
1. Health check: `./health-check.sh`
2. Logs: `sudo journalctl -u ngrs-api -f`
3. Redis: `docker logs ngrs-redis`
4. Main documentation: `REDIS_API_COMPLETE.md`
